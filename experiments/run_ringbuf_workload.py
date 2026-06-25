#!/usr/bin/env python3
"""Run a matched XDP ring-buffer workload against a C/eBPF baseline."""

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
BUILD = RESULTS / "build" / "ringbuf_workload"
LOGS = RESULTS / "logs" / "ringbuf_workload"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"
TRIALS = int(os.environ.get("KERNELSCRIPT_RINGBUF_TRIALS", "10"))
EVENTS = int(os.environ.get("KERNELSCRIPT_RINGBUF_EVENTS", "50000"))
POLL_EVERY = int(os.environ.get("KERNELSCRIPT_RINGBUF_POLL_EVERY", "128"))


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
    source = ROOT / "experiments" / "programs" / "ringbuf_emit.ks"
    res = run([str(COMPILER), "compile", str(source), "-o", str(out)])
    write(LOGS / "kernelscript.compile.stdout", res.stdout)
    write(LOGS / "kernelscript.compile.stderr", res.stderr)
    check(res, "KernelScript ringbuf compile")
    make = run(["make", "ebpf-only"], out)
    write(LOGS / "kernelscript.make.stdout", make.stdout)
    write(LOGS / "kernelscript.make.stderr", make.stderr)
    check(make, "KernelScript ringbuf eBPF build")
    obj = out / "ringbuf_emit.ebpf.o"
    if not obj.exists():
        raise RuntimeError(f"missing generated object: {obj}")
    return obj


def inspect_generated_dynptr_lowering() -> dict[str, object]:
    generated = BUILD / "kernelscript" / "ringbuf_emit.ebpf.c"
    text = generated.read_text(encoding="utf-8")
    required = {
        "reserve_dynptr": "bpf_ringbuf_reserve_dynptr",
        "reserve_data": "bpf_dynptr_data",
        "write_field": "bpf_dynptr_write",
        "submit_dynptr": "bpf_ringbuf_submit_dynptr",
    }
    present = {name: (needle in text) for name, needle in required.items()}
    return {
        "generated_file": str(generated.relative_to(ROOT)),
        "required_helpers": required,
        "present": present,
        "oracle_passed": all(present.values()),
    }


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

    obj = out / "ringbuf_emit.o"
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
            str(ROOT / "experiments" / "baselines" / "ringbuf_emit.c"),
            "-o",
            str(obj),
        ]
    )
    write(LOGS / "handwritten.clang.stdout", clang.stdout)
    write(LOGS / "handwritten.clang.stderr", clang.stderr)
    check(clang, "handwritten ringbuf clang")
    return obj


def compile_runner() -> Path:
    runner = BUILD / "ringbuf_counter_user"
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
            str(ROOT / "experiments" / "baselines" / "ringbuf_counter_user.c"),
            *libs,
            "-lelf",
            "-lz",
        ]
    )
    write(LOGS / "runner.gcc.stdout", gcc.stdout)
    write(LOGS / "runner.gcc.stderr", gcc.stderr)
    check(gcc, "ringbuf runner gcc")
    return runner


def parse_runner_output(text: str) -> dict[str, object]:
    values: dict[str, object] = {}
    for key in [
        "target_events",
        "submitted",
        "dropped",
        "received",
        "bad_size",
        "bad_marker",
        "bad_retval",
        "run_errors",
        "elapsed_sec",
        "event_rate_mps",
    ]:
        match = re.search(rf"^{key}=([0-9.]+)$", text, re.MULTILINE)
        if not match:
            raise RuntimeError(f"missing {key} in runner output:\n{text}")
        raw = match.group(1)
        values[key] = float(raw) if "." in raw else int(raw)
    values["oracle_passed"] = (
        int(values["submitted"]) == int(values["target_events"])
        and int(values["received"]) == int(values["target_events"])
        and int(values["dropped"]) == 0
        and int(values["bad_size"]) == 0
        and int(values["bad_marker"]) == 0
        and int(values["bad_retval"]) == 0
        and int(values["run_errors"]) == 0
    )
    return values


def trial(name: str, obj: Path, runner: Path, idx: int) -> dict[str, object]:
    start = time.perf_counter()
    proc = run(
        [
            str(runner),
            str(obj),
            "emit_event",
            "events",
            "counts",
            str(EVENTS),
            str(POLL_EVERY),
        ],
        sudo=True,
        timeout=240,
    )
    elapsed_wall = time.perf_counter() - start
    write(LOGS / f"{name}.trial{idx}.stdout", proc.stdout)
    write(LOGS / f"{name}.trial{idx}.stderr", proc.stderr)
    parsed = parse_runner_output(proc.stdout + proc.stderr) if proc.returncode == 0 else {
        "target_events": EVENTS,
        "submitted": 0,
        "dropped": 0,
        "received": 0,
        "bad_size": 0,
        "bad_marker": 0,
        "bad_retval": 0,
        "run_errors": 1,
        "elapsed_sec": 0.0,
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
    rates = [float(row["event_rate_mps"]) for row in samples]
    elapsed = [float(row["elapsed_sec"]) for row in samples]
    return {
        "name": name,
        "implementation": implementation,
        "object": str(obj.relative_to(ROOT)),
        "trials": TRIALS,
        "target_events": EVENTS,
        "poll_every": POLL_EVERY,
        "returncodes": [int(row["returncode"]) for row in samples],
        "submitted_samples": [int(row["submitted"]) for row in samples],
        "received_samples": [int(row["received"]) for row in samples],
        "dropped_samples": [int(row["dropped"]) for row in samples],
        "bad_size_samples": [int(row["bad_size"]) for row in samples],
        "bad_marker_samples": [int(row["bad_marker"]) for row in samples],
        "bad_retval_samples": [int(row["bad_retval"]) for row in samples],
        "run_error_samples": [int(row["run_errors"]) for row in samples],
        "elapsed_sec_samples": elapsed,
        "event_rate_mps_samples": rates,
        "median_submitted": median([int(row["submitted"]) for row in samples]),
        "median_received": median([int(row["received"]) for row in samples]),
        "median_dropped": median([int(row["dropped"]) for row in samples]),
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
        write(RESULTS / "ringbuf_workload_summary.json", json.dumps(summary, indent=2) + "\n")
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
    lowering = inspect_generated_dynptr_lowering()

    row_list = [
        summarize("ks_generated", "kernelscript", ks_obj, runner),
        summarize("c_libbpf", "handwritten_c", c_obj, runner),
    ]
    rows = {row["name"]: row for row in row_list}
    status = "ok" if all(row["oracle_passed"] for row in row_list) and bool(lowering["oracle_passed"]) else "failed"
    summary = {
        "status": status,
        "description": "XDP ring-buffer event emission workload using one libbpf runner for KernelScript-generated and hand-written C/eBPF objects, plus a generated-code check that high-level reserve/write/submit source operations lower to dynptr helpers",
        "trials": TRIALS,
        "target_events": EVENTS,
        "poll_every": POLL_EVERY,
        "dynptr_lowering": lowering,
        "rows": row_list,
        "comparison": comparison(rows),
    }

    fields = [
        "name",
        "implementation",
        "object",
        "trials",
        "target_events",
        "poll_every",
        "median_submitted",
        "median_received",
        "median_dropped",
        "median_elapsed_sec",
        "median_event_rate_mps",
        "min_event_rate_mps",
        "max_event_rate_mps",
        "oracle_passed",
        "returncodes",
        "submitted_samples",
        "received_samples",
        "dropped_samples",
        "bad_size_samples",
        "bad_marker_samples",
        "bad_retval_samples",
        "run_error_samples",
        "elapsed_sec_samples",
        "event_rate_mps_samples",
    ]
    with (RESULTS / "ringbuf_workload_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in row_list:
            out = dict(row)
            for key in [
                "returncodes",
                "submitted_samples",
                "received_samples",
                "dropped_samples",
                "bad_size_samples",
                "bad_marker_samples",
                "bad_retval_samples",
                "run_error_samples",
                "elapsed_sec_samples",
                "event_rate_mps_samples",
            ]:
                out[key] = " ".join(str(value) for value in row[key])
            writer.writerow({key: out[key] for key in fields})

    write(RESULTS / "ringbuf_workload_summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: summary[key] for key in summary if key != "rows"}, indent=2, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
