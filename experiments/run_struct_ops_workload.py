#!/usr/bin/env python3
"""Run a TCP workload through generated and hand-written struct_ops objects."""

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
BUILD = RESULTS / "build" / "struct_ops_workload"
LOGS = RESULTS / "logs" / "struct_ops_workload"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"
TRIALS = int(os.environ.get("KERNELSCRIPT_STRUCT_OPS_WORKLOAD_TRIALS", "10"))
BYTES = int(os.environ.get("KERNELSCRIPT_STRUCT_OPS_WORKLOAD_BYTES", str(1024 * 1024)))


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
    source = REPO / "examples" / "struct_ops_simple.ks"
    res = run([str(COMPILER), "compile", str(source), "-o", str(out)])
    write(LOGS / "kernelscript.compile.stdout", res.stdout)
    write(LOGS / "kernelscript.compile.stderr", res.stderr)
    check(res, "KernelScript struct_ops compile")
    make = run(["make", "ebpf-only"], out)
    write(LOGS / "kernelscript.make.stdout", make.stdout)
    write(LOGS / "kernelscript.make.stderr", make.stderr)
    check(make, "KernelScript struct_ops eBPF build")
    obj = out / "struct_ops_simple.ebpf.o"
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

    obj = out / "struct_ops_tcp_cc.o"
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
            str(ROOT / "experiments" / "baselines" / "struct_ops_tcp_cc.c"),
            "-o",
            str(obj),
        ]
    )
    write(LOGS / "handwritten.clang.stdout", clang.stdout)
    write(LOGS / "handwritten.clang.stderr", clang.stderr)
    check(clang, "handwritten struct_ops clang")
    return obj


def compile_runner() -> Path:
    runner = BUILD / "struct_ops_tcp_workload_user"
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
            str(ROOT / "experiments" / "baselines" / "struct_ops_tcp_workload_user.c"),
            *libs,
            "-lelf",
            "-lz",
        ]
    )
    write(LOGS / "runner.gcc.stdout", gcc.stdout)
    write(LOGS / "runner.gcc.stderr", gcc.stderr)
    check(gcc, "struct_ops workload runner gcc")
    return runner


def parse_key_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^([A-Za-z0-9_]+)=(.*)$", line.strip())
        if match:
            values[match.group(1)] = match.group(2)
    return values


def int_value(values: dict[str, str], key: str) -> int:
    try:
        return int(values.get(key, "0"))
    except ValueError:
        return 0


def trial(
    name: str,
    obj: Path,
    map_name: str,
    cc_name: str,
    runner: Path,
    idx: int,
) -> dict[str, object]:
    start = time.perf_counter()
    proc = run([str(runner), str(obj), map_name, cc_name, str(BYTES)], sudo=True, timeout=120)
    elapsed = time.perf_counter() - start
    write(LOGS / f"{name}.trial{idx}.stdout", proc.stdout)
    write(LOGS / f"{name}.trial{idx}.stderr", proc.stderr)
    parsed = parse_key_values(proc.stdout + proc.stderr)
    bytes_received = int_value(parsed, "bytes_received")
    workload_ok = int_value(parsed, "workload_ok")
    cc_selected = int_value(parsed, "cc_selected")
    return {
        "trial": idx,
        "returncode": proc.returncode,
        "elapsed_sec": round(elapsed, 6),
        "load_ok": int_value(parsed, "load_ok"),
        "attach_ok": int_value(parsed, "attach_ok"),
        "client_ok": int_value(parsed, "client_ok"),
        "cc_selected": cc_selected,
        "bytes_received": bytes_received,
        "workload_ok": workload_ok,
        "detach_ok": int_value(parsed, "detach_ok"),
        "oracle_passed": (
            proc.returncode == 0
            and int_value(parsed, "load_ok") == 1
            and int_value(parsed, "attach_ok") == 1
            and int_value(parsed, "client_ok") == 1
            and cc_selected == 1
            and bytes_received == BYTES
            and workload_ok == 1
            and int_value(parsed, "detach_ok") == 1
        ),
    }


def median(values: list[float]) -> float:
    return round(float(statistics.median(values)), 6) if values else 0.0


def summarize(
    name: str,
    implementation: str,
    obj: Path,
    map_name: str,
    cc_name: str,
    runner: Path,
) -> dict[str, object]:
    samples = [trial(name, obj, map_name, cc_name, runner, i) for i in range(TRIALS)]
    elapsed = [float(row["elapsed_sec"]) for row in samples]
    rates = [
        (float(row["bytes_received"]) / (1024 * 1024)) / float(row["elapsed_sec"])
        for row in samples
        if float(row["elapsed_sec"]) > 0 and int(row["bytes_received"]) == BYTES
    ]
    return {
        "name": name,
        "implementation": implementation,
        "object": str(obj.relative_to(ROOT)),
        "map_name": map_name,
        "cc_name": cc_name,
        "trials": TRIALS,
        "bytes_per_trial": BYTES,
        "returncodes": [int(row["returncode"]) for row in samples],
        "load_ok_samples": [int(row["load_ok"]) for row in samples],
        "attach_ok_samples": [int(row["attach_ok"]) for row in samples],
        "client_ok_samples": [int(row["client_ok"]) for row in samples],
        "cc_selected_samples": [int(row["cc_selected"]) for row in samples],
        "bytes_received_samples": [int(row["bytes_received"]) for row in samples],
        "workload_ok_samples": [int(row["workload_ok"]) for row in samples],
        "detach_ok_samples": [int(row["detach_ok"]) for row in samples],
        "elapsed_sec_samples": elapsed,
        "median_elapsed_sec": median(elapsed),
        "median_mib_per_sec": median(rates),
        "oracle_passed": all(bool(row["oracle_passed"]) for row in samples),
    }


def main() -> int:
    reason = check_prerequisites()
    if reason:
        summary = {"status": "skipped", "reason": reason}
        write(RESULTS / "struct_ops_workload_summary.json", json.dumps(summary, indent=2) + "\n")
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

    rows = [
        summarize("ks_generated", "kernelscript", ks_obj, "minimal_congestion_control", "minimal_cc", runner),
        summarize("c_libbpf", "handwritten_c", c_obj, "ks_paper_cc", "ks_paper_cc", runner),
    ]
    status = "ok" if all(row["oracle_passed"] for row in rows) else "failed"
    summary = {
        "status": status,
        "description": "loopback TCP workload using selected BPF tcp_congestion_ops",
        "trials": TRIALS,
        "bytes_per_trial": BYTES,
        "rows": rows,
    }

    fields = [
        "name",
        "implementation",
        "object",
        "map_name",
        "cc_name",
        "trials",
        "bytes_per_trial",
        "oracle_passed",
        "returncodes",
        "load_ok_samples",
        "attach_ok_samples",
        "client_ok_samples",
        "cc_selected_samples",
        "bytes_received_samples",
        "workload_ok_samples",
        "detach_ok_samples",
        "elapsed_sec_samples",
        "median_elapsed_sec",
        "median_mib_per_sec",
    ]
    with (RESULTS / "struct_ops_workload_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            for key in [
                "returncodes",
                "load_ok_samples",
                "attach_ok_samples",
                "client_ok_samples",
                "cc_selected_samples",
                "bytes_received_samples",
                "workload_ok_samples",
                "detach_ok_samples",
                "elapsed_sec_samples",
            ]:
                out[key] = " ".join(str(value) for value in row[key])
            writer.writerow({key: out[key] for key in fields})

    write(RESULTS / "struct_ops_workload_summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: summary[key] for key in summary if key != "rows"}, indent=2, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
