#!/usr/bin/env python3
"""Run generated-loader perf_event lifecycle checks with a C/libbpf baseline."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("KERNELSCRIPT_REPO", ROOT / "kernelscript")).resolve()
RESULTS = ROOT / "results"
BUILD = RESULTS / "build" / "perf_event_loader"
LOGS = RESULTS / "logs" / "perf_event_loader"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"
TRIALS = int(os.environ.get("KERNELSCRIPT_PERF_LOADER_TRIALS", "5"))


def run(
    argv: list[str],
    cwd: Path = ROOT,
    timeout: int = 120,
    sudo: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PWD"] = str(cwd)
    full = ["sudo", "-n"] + argv if sudo else argv
    return subprocess.run(
        full,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def check(cmd: subprocess.CompletedProcess[str], label: str) -> None:
    if cmd.returncode != 0:
        raise RuntimeError(f"{label} failed\nstdout:\n{cmd.stdout}\nstderr:\n{cmd.stderr}")


def check_prerequisites() -> str | None:
    if run(["true"], sudo=True).returncode != 0:
        return "sudo -n unavailable"
    for cmd in ["bpftool", "clang", "gcc", "make", "pkg-config"]:
        if not shutil.which(cmd):
            return f"{cmd} unavailable"
    if not Path("/sys/kernel/btf/vmlinux").exists():
        return "missing /sys/kernel/btf/vmlinux"
    if not COMPILER.exists():
        return f"missing KernelScript compiler at {COMPILER}"
    return None


def compile_kernelscript_loader() -> Path:
    out = BUILD / "kernelscript"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    source = REPO / "examples" / "perf_page_fault.ks"
    res = run([str(COMPILER), "compile", str(source), "-o", str(out)])
    write(LOGS / "kernelscript.compile.stdout", res.stdout)
    write(LOGS / "kernelscript.compile.stderr", res.stderr)
    check(res, "KernelScript perf_page_fault compile")
    make = run(["make"], out)
    write(LOGS / "kernelscript.make.stdout", make.stdout)
    write(LOGS / "kernelscript.make.stderr", make.stderr)
    check(make, "KernelScript generated loader make")
    binary = out / "perf_page_fault"
    if not binary.exists():
        raise RuntimeError(f"missing generated loader binary: {binary}")
    return binary


def compile_c_loader() -> Path:
    out = BUILD / "handwritten"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    btf = run(["bpftool", "btf", "dump", "file", "/sys/kernel/btf/vmlinux", "format", "c"])
    write(LOGS / "handwritten.btf.stdout", btf.stdout)
    write(LOGS / "handwritten.btf.stderr", btf.stderr)
    check(btf, "bpftool btf dump")
    write(out / "vmlinux.h", btf.stdout)

    ebpf_obj = out / "perf_event_loader.ebpf.o"
    clang = run(
        [
            "clang",
            "-target",
            "bpf",
            "-O2",
            "-g",
            "-Wall",
            "-Wextra",
            "-fno-builtin",
            "-I",
            str(out),
            "-c",
            str(ROOT / "experiments" / "baselines" / "perf_event_loader.ebpf.c"),
            "-o",
            str(ebpf_obj),
        ]
    )
    write(LOGS / "handwritten.clang.stdout", clang.stdout)
    write(LOGS / "handwritten.clang.stderr", clang.stderr)
    check(clang, "handwritten perf_event eBPF clang")

    skel = out / "perf_event_loader.skel.h"
    skeleton = run(["bpftool", "gen", "skeleton", str(ebpf_obj)])
    write(LOGS / "handwritten.skeleton.stdout", skeleton.stdout)
    write(LOGS / "handwritten.skeleton.stderr", skeleton.stderr)
    check(skeleton, "handwritten skeleton generation")
    write(skel, skeleton.stdout)

    pkg = run(["pkg-config", "--libs", "libbpf"])
    write(LOGS / "handwritten.pkgconfig.stdout", pkg.stdout)
    write(LOGS / "handwritten.pkgconfig.stderr", pkg.stderr)
    check(pkg, "pkg-config libbpf")
    libs = pkg.stdout.strip().split() or ["-lbpf", "-lelf", "-lz"]

    binary = out / "perf_event_loader_baseline"
    gcc = run(
        [
            "gcc",
            "-O2",
            "-Wall",
            "-Wextra",
            "-I",
            str(out),
            "-o",
            str(binary),
            str(ROOT / "experiments" / "baselines" / "perf_event_loader_user.c"),
            *libs,
            "-lelf",
            "-lz",
        ]
    )
    write(LOGS / "handwritten.gcc.stdout", gcc.stdout)
    write(LOGS / "handwritten.gcc.stderr", gcc.stderr)
    check(gcc, "handwritten perf_event loader gcc")
    return binary


def parse_run_output(output: str, implementation: str) -> dict[str, object]:
    page_match = re.search(r"Page-fault count:\s*([0-9]+)", output)
    branch_match = re.search(r"Branch-miss count:\s*([0-9]+)", output)
    attach_text = "perf_event demo attached" if implementation == "kernelscript" else "perf_event baseline attached"
    detach_text = "perf_event demo detached" if implementation == "kernelscript" else "perf_event baseline detached"
    attached = attach_text in output
    detached = detach_text in output
    page_count = int(page_match.group(1)) if page_match else -1
    branch_count = int(branch_match.group(1)) if branch_match else -1
    return {
        "attached": attached,
        "detached": detached,
        "page_fault_count": page_count,
        "branch_miss_count": branch_count,
        "oracle_passed": attached and detached and page_count > 0 and branch_count >= 0,
    }


def run_trial(name: str, implementation: str, binary: Path, idx: int) -> dict[str, object]:
    start = time.perf_counter()
    proc = run([str(binary)], cwd=binary.parent, timeout=30, sudo=True)
    elapsed = time.perf_counter() - start
    write(LOGS / f"{name}.trial{idx}.stdout", proc.stdout)
    write(LOGS / f"{name}.trial{idx}.stderr", proc.stderr)
    parsed = parse_run_output(proc.stdout + proc.stderr, implementation)
    parsed.update(
        {
            "name": name,
            "implementation": implementation,
            "trial": idx,
            "returncode": proc.returncode,
            "elapsed_sec": elapsed,
        }
    )
    parsed["oracle_passed"] = bool(parsed["oracle_passed"]) and proc.returncode == 0
    return parsed


def summarize(name: str, implementation: str, binary: Path) -> dict[str, object]:
    samples = [run_trial(name, implementation, binary, i) for i in range(TRIALS)]
    page_counts = [int(row["page_fault_count"]) for row in samples]
    branch_counts = [int(row["branch_miss_count"]) for row in samples]
    elapsed = [float(row["elapsed_sec"]) for row in samples]
    return {
        "name": name,
        "implementation": implementation,
        "binary": str(binary.relative_to(ROOT)),
        "trials": TRIALS,
        "returncodes": [int(row["returncode"]) for row in samples],
        "attached_samples": [bool(row["attached"]) for row in samples],
        "detached_samples": [bool(row["detached"]) for row in samples],
        "page_fault_count_samples": page_counts,
        "branch_miss_count_samples": branch_counts,
        "elapsed_sec_samples": elapsed,
        "median_page_fault_count": statistics.median(page_counts),
        "median_branch_miss_count": statistics.median(branch_counts),
        "median_elapsed_sec": statistics.median(elapsed),
        "oracle_passed": all(bool(row["oracle_passed"]) for row in samples),
    }


def main() -> int:
    reason = check_prerequisites()
    if reason:
        summary = {"status": "skipped", "reason": reason}
        write(RESULTS / "perf_event_loader_summary.json", json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0

    if BUILD.exists():
        shutil.rmtree(BUILD)
    if LOGS.exists():
        shutil.rmtree(LOGS)
    BUILD.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    ks_binary = compile_kernelscript_loader()
    c_binary = compile_c_loader()
    rows = [
        summarize("ks_generated", "kernelscript", ks_binary),
        summarize("c_libbpf", "handwritten_c", c_binary),
    ]
    status = "ok" if all(bool(row["oracle_passed"]) for row in rows) else "failed"
    summary = {
        "status": status,
        "description": "privileged perf_event generated-loader lifecycle check with a hand-written C/libbpf loader baseline",
        "trials": TRIALS,
        "rows": rows,
    }

    fields = [
        "name",
        "implementation",
        "binary",
        "trials",
        "median_page_fault_count",
        "median_branch_miss_count",
        "median_elapsed_sec",
        "oracle_passed",
        "returncodes",
        "attached_samples",
        "detached_samples",
        "page_fault_count_samples",
        "branch_miss_count_samples",
        "elapsed_sec_samples",
    ]
    with (RESULTS / "perf_event_loader_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            for key in [
                "returncodes",
                "attached_samples",
                "detached_samples",
                "page_fault_count_samples",
                "branch_miss_count_samples",
                "elapsed_sec_samples",
            ]:
                out[key] = " ".join(str(value) for value in row[key])
            writer.writerow({key: out[key] for key in fields})

    write(RESULTS / "perf_event_loader_summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: summary[key] for key in summary if key != "rows"}, indent=2, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
