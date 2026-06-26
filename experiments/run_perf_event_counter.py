#!/usr/bin/env python3
"""Run sustained perf_event map-counter checks against a C/eBPF baseline."""

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
BUILD = RESULTS / "build" / "perf_event_counter"
LOGS = RESULTS / "logs" / "perf_event_counter"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"
TRIALS = int(os.environ.get("KERNELSCRIPT_PERF_COUNTER_TRIALS", "10"))
PAGES = int(os.environ.get("KERNELSCRIPT_PERF_COUNTER_PAGES", "65536"))
ROUNDS = int(os.environ.get("KERNELSCRIPT_PERF_COUNTER_ROUNDS", "4"))


def run(
    argv: list[str],
    cwd: Path = ROOT,
    timeout: int = 180,
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


def compile_ks() -> Path:
    out = BUILD / "kernelscript"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT / "experiments" / "programs" / "perf_event_count.ks"
    res = run([str(COMPILER), "compile", str(source), "-o", str(out)])
    write(LOGS / "kernelscript.compile.stdout", res.stdout)
    write(LOGS / "kernelscript.compile.stderr", res.stderr)
    check(res, "KernelScript perf_event counter compile")
    make = run(["make", "ebpf-only"], out)
    write(LOGS / "kernelscript.make.stdout", make.stdout)
    write(LOGS / "kernelscript.make.stderr", make.stderr)
    check(make, "KernelScript perf_event counter eBPF build")
    obj = out / "perf_event_count.ebpf.o"
    if not obj.exists():
        raise RuntimeError(f"missing generated object: {obj}")
    return obj


def compile_c() -> Path:
    out = BUILD / "handwritten"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    btf = run(["bpftool", "btf", "dump", "file", "/sys/kernel/btf/vmlinux", "format", "c"])
    write(LOGS / "handwritten.btf.stdout", btf.stdout)
    write(LOGS / "handwritten.btf.stderr", btf.stderr)
    check(btf, "bpftool btf dump")
    write(out / "vmlinux.h", btf.stdout)

    obj = out / "perf_event_count.o"
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
            str(ROOT / "experiments" / "baselines" / "perf_event_count.c"),
            "-o",
            str(obj),
        ]
    )
    write(LOGS / "handwritten.clang.stdout", clang.stdout)
    write(LOGS / "handwritten.clang.stderr", clang.stderr)
    check(clang, "handwritten perf_event counter clang")
    return obj


def compile_runner() -> Path:
    runner = BUILD / "perf_event_counter_user"
    pkg = run(["pkg-config", "--libs", "libbpf"])
    write(LOGS / "runner.pkgconfig.stdout", pkg.stdout)
    write(LOGS / "runner.pkgconfig.stderr", pkg.stderr)
    check(pkg, "pkg-config libbpf")
    libs = pkg.stdout.strip().split() or ["-lbpf", "-lelf", "-lz"]
    gcc = run(
        [
            "gcc",
            "-O2",
            "-Wall",
            "-Wextra",
            "-o",
            str(runner),
            str(ROOT / "experiments" / "baselines" / "perf_event_counter_user.c"),
            *libs,
            "-lelf",
            "-lz",
        ]
    )
    write(LOGS / "runner.gcc.stdout", gcc.stdout)
    write(LOGS / "runner.gcc.stderr", gcc.stderr)
    check(gcc, "perf_event counter runner gcc")
    return runner


def parse_runner_output(text: str) -> dict[str, object]:
    values: dict[str, object] = {}
    for key in ["bpf_count", "perf_count", "elapsed_sec", "pages", "rounds"]:
        match = re.search(rf"^{key}=([0-9.]+)$", text, re.MULTILINE)
        if not match:
            raise RuntimeError(f"missing {key} in runner output:\n{text}")
        raw = match.group(1)
        values[key] = float(raw) if "." in raw else int(raw)
    bpf_count = int(values["bpf_count"])
    perf_count = int(values["perf_count"])
    elapsed = float(values["elapsed_sec"])
    values["event_rate_mps"] = bpf_count / elapsed / 1_000_000.0 if elapsed else 0.0
    values["oracle_passed"] = bpf_count > 0 and bpf_count == perf_count
    return values


def trial(name: str, obj: Path, runner: Path, idx: int) -> dict[str, object]:
    start = time.perf_counter()
    proc = run(
        [
            str(runner),
            str(obj),
            "count_page_fault",
            "counts",
            str(PAGES),
            str(ROUNDS),
        ],
        sudo=True,
        timeout=240,
    )
    elapsed_wall = time.perf_counter() - start
    write(LOGS / f"{name}.trial{idx}.stdout", proc.stdout)
    write(LOGS / f"{name}.trial{idx}.stderr", proc.stderr)
    parsed = parse_runner_output(proc.stdout + proc.stderr) if proc.returncode == 0 else {
        "bpf_count": 0,
        "perf_count": 0,
        "elapsed_sec": 0.0,
        "pages": PAGES,
        "rounds": ROUNDS,
        "event_rate_mps": 0.0,
        "oracle_passed": False,
    }
    parsed.update({"trial": idx, "returncode": proc.returncode, "wall_sec": elapsed_wall})
    parsed["oracle_passed"] = bool(parsed["oracle_passed"]) and proc.returncode == 0
    return parsed


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def summarize(name: str, implementation: str, obj: Path, runner: Path) -> dict[str, object]:
    samples = [trial(name, obj, runner, i) for i in range(TRIALS)]
    bpf_counts = [int(row["bpf_count"]) for row in samples]
    perf_counts = [int(row["perf_count"]) for row in samples]
    elapsed = [float(row["elapsed_sec"]) for row in samples]
    rates = [float(row["event_rate_mps"]) for row in samples]
    return {
        "name": name,
        "implementation": implementation,
        "object": str(obj.relative_to(ROOT)),
        "trials": TRIALS,
        "pages": PAGES,
        "rounds": ROUNDS,
        "returncodes": [int(row["returncode"]) for row in samples],
        "bpf_count_samples": bpf_counts,
        "perf_count_samples": perf_counts,
        "elapsed_sec_samples": elapsed,
        "event_rate_mps_samples": rates,
        "median_bpf_count": median(bpf_counts),
        "median_perf_count": median(perf_counts),
        "median_elapsed_sec": median(elapsed),
        "median_event_rate_mps": median(rates),
        "min_event_rate_mps": min(rates),
        "max_event_rate_mps": max(rates),
        "oracle_passed": all(bool(row["oracle_passed"]) for row in samples),
    }


def comparison(rows: dict[str, dict[str, object]]) -> dict[str, float]:
    ks = float(rows["ks_generated"]["median_event_rate_mps"])
    c = float(rows["c_libbpf"]["median_event_rate_mps"])
    return {
        "ks_median_event_rate_mps": ks,
        "c_median_event_rate_mps": c,
        "delta_mps": ks - c,
        "ks_over_c_ratio": (ks / c) if c else 0.0,
        "overhead_pct": ((c - ks) / c * 100.0) if c else 0.0,
    }


def main() -> int:
    reason = check_prerequisites()
    if reason:
        summary = {"status": "skipped", "reason": reason}
        write(RESULTS / "perf_event_counter_summary.json", json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0

    if BUILD.exists():
        shutil.rmtree(BUILD)
    if LOGS.exists():
        shutil.rmtree(LOGS)
    BUILD.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    ks_obj = compile_ks()
    c_obj = compile_c()
    runner = compile_runner()

    row_list = [
        summarize("ks_generated", "kernelscript", ks_obj, runner),
        summarize("c_libbpf", "handwritten_c", c_obj, runner),
    ]
    rows = {row["name"]: row for row in row_list}
    status = "ok" if all(row["oracle_passed"] for row in row_list) else "failed"
    summary = {
        "status": status,
        "description": "perf_event page-fault map-counter workload using one libbpf runner for KernelScript-generated and hand-written C/eBPF objects",
        "trials": TRIALS,
        "pages": PAGES,
        "rounds": ROUNDS,
        "rows": row_list,
        "comparison": comparison(rows),
    }

    fields = [
        "name",
        "implementation",
        "object",
        "trials",
        "pages",
        "rounds",
        "median_bpf_count",
        "median_perf_count",
        "median_elapsed_sec",
        "median_event_rate_mps",
        "min_event_rate_mps",
        "max_event_rate_mps",
        "oracle_passed",
        "returncodes",
        "bpf_count_samples",
        "perf_count_samples",
        "elapsed_sec_samples",
        "event_rate_mps_samples",
    ]
    with (RESULTS / "perf_event_counter_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in row_list:
            out = dict(row)
            for key in [
                "returncodes",
                "bpf_count_samples",
                "perf_count_samples",
                "elapsed_sec_samples",
                "event_rate_mps_samples",
            ]:
                out[key] = " ".join(str(value) for value in row[key])
            writer.writerow({key: out[key] for key in fields})

    write(RESULTS / "perf_event_counter_summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: summary[key] for key in summary if key != "rows"}, indent=2, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
