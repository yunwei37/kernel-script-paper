#!/usr/bin/env python3
"""Run small XDP runtime microbenchmarks.

This benchmark compares KernelScript-generated eBPF objects with equivalent
hand-written C/eBPF objects using bpftool's BPF_PROG_TEST_RUN path.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("KERNELSCRIPT_REPO", ROOT / "kernelscript")).resolve()
RESULTS = ROOT / "results"
BUILD = RESULTS / "build" / "microbench"
LOGS = RESULTS / "logs" / "microbench"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"
PIN_ROOT = "/sys/fs/bpf/kernelscript-paper"
REPEAT = int(os.environ.get("KERNELSCRIPT_MICRO_REPEAT", "100000"))
TRIALS = int(os.environ.get("KERNELSCRIPT_MICRO_TRIALS", "7"))


def run(argv: list[str], cwd: Path, timeout: int = 120, sudo: bool = False) -> subprocess.CompletedProcess[str]:
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


def instruction_count(obj: Path) -> int:
    objdump = shutil.which("llvm-objdump") or shutil.which("llvm-objdump-18") or shutil.which("llvm-objdump-19")
    if not objdump:
        return 0
    res = run([objdump, "-d", str(obj)], obj.parent)
    if res.returncode != 0:
        return 0
    return sum(1 for line in res.stdout.splitlines() if re.match(r"\s*[0-9a-f]+:\s", line))


def compile_ks(name: str, source: Path) -> Path:
    out = BUILD / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    res = run([str(COMPILER), "compile", str(source), "-o", str(out)], ROOT)
    write(LOGS / f"{name}.ks.stdout", res.stdout)
    write(LOGS / f"{name}.ks.stderr", res.stderr)
    check(res, f"{name} KernelScript compile")
    make = run(["make"], out)
    write(LOGS / f"{name}.make.stdout", make.stdout)
    write(LOGS / f"{name}.make.stderr", make.stderr)
    check(make, f"{name} make")
    objects = sorted(out.glob("*.ebpf.o"))
    if len(objects) != 1:
        raise RuntimeError(f"Expected one eBPF object in {out}, found {objects}")
    return objects[0]


def compile_c(name: str, source: Path, hand_dir: Path) -> Path:
    obj = hand_dir / f"{name}.o"
    cmd = [
        "clang",
        "-target",
        "bpf",
        "-O2",
        "-g",
        "-Wall",
        "-Wextra",
        "-fno-builtin",
        "-I",
        str(hand_dir),
        "-c",
        str(source),
        "-o",
        str(obj),
    ]
    res = run(cmd, ROOT)
    write(LOGS / f"{name}.clang.stdout", res.stdout)
    write(LOGS / f"{name}.clang.stderr", res.stderr)
    check(res, f"{name} clang")
    return obj


def prepare_handwritten() -> dict[str, Path]:
    hand_dir = BUILD / "handwritten"
    if hand_dir.exists():
        shutil.rmtree(hand_dir)
    hand_dir.mkdir(parents=True)
    btf = run(["bpftool", "btf", "dump", "file", "/sys/kernel/btf/vmlinux", "format", "c"], ROOT)
    check(btf, "bpftool btf dump")
    write(hand_dir / "vmlinux.h", btf.stdout)
    return {
        "c_pass": compile_c("c_pass", ROOT / "experiments" / "baselines" / "xdp_pass.c", hand_dir),
        "c_count": compile_c("c_count", ROOT / "experiments" / "baselines" / "xdp_count.c", hand_dir),
    }


def packet_file() -> Path:
    pkt = BUILD / "packet64.bin"
    pkt.parent.mkdir(parents=True, exist_ok=True)
    pkt.write_bytes(bytes.fromhex("ffffffffffff0000000000010800") + bytes(50))
    return pkt


def parse_avg_ns(output: str) -> float:
    match = re.search(r"duration \(average\):\s*([0-9.]+)ns", output)
    if not match:
        raise RuntimeError(f"Could not parse bpftool duration from: {output!r}")
    return float(match.group(1))


def benchmark_object(name: str, obj: Path, pkt: Path) -> dict[str, object]:
    pin = f"{PIN_ROOT}/{name}_{os.getpid()}"
    run(["mkdir", "-p", PIN_ROOT], ROOT, sudo=True)
    run(["rm", "-f", pin], ROOT, sudo=True)
    load = run(["bpftool", "prog", "load", str(obj), pin, "type", "xdp"], ROOT, sudo=True)
    write(LOGS / f"{name}.load.stdout", load.stdout)
    write(LOGS / f"{name}.load.stderr", load.stderr)
    check(load, f"{name} bpftool load")
    samples: list[float] = []
    try:
        for i in range(TRIALS):
            start = time.perf_counter()
            res = run(
                [
                    "bpftool",
                    "prog",
                    "run",
                    "pinned",
                    pin,
                    "data_in",
                    str(pkt),
                    "repeat",
                    str(REPEAT),
                ],
                ROOT,
                sudo=True,
            )
            elapsed = time.perf_counter() - start
            write(LOGS / f"{name}.run{i}.stdout", res.stdout)
            write(LOGS / f"{name}.run{i}.stderr", res.stderr)
            check(res, f"{name} bpftool run trial {i}")
            samples.append(parse_avg_ns(res.stdout + res.stderr))
    finally:
        run(["rm", "-f", pin], ROOT, sudo=True)
    return {
        "name": name,
        "object": str(obj.relative_to(ROOT)),
        "object_bytes": obj.stat().st_size,
        "instructions": instruction_count(obj),
        "repeat": REPEAT,
        "trials": TRIALS,
        "samples_avg_ns": samples,
        "median_avg_ns": statistics.median(samples),
        "min_avg_ns": min(samples),
        "max_avg_ns": max(samples),
    }


def main() -> int:
    if run(["true"], ROOT, sudo=True).returncode != 0:
        summary = {"status": "skipped", "reason": "sudo -n unavailable"}
        write(RESULTS / "microbench_summary.json", json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0

    LOGS.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    pkt = packet_file()

    objects = {
        "ks_pass": compile_ks("ks_pass", ROOT / "experiments" / "programs" / "perf_pass.ks"),
        "ks_count": compile_ks("ks_count", ROOT / "experiments" / "programs" / "perf_count.ks"),
    }
    objects.update(prepare_handwritten())

    rows = [benchmark_object(name, obj, pkt) for name, obj in objects.items()]
    by_bench = {
        "pass": ("ks_pass", "c_pass"),
        "count": ("ks_count", "c_count"),
    }
    row_by_name = {row["name"]: row for row in rows}
    comparisons = {}
    for bench, (ks_name, c_name) in by_bench.items():
        ks = float(row_by_name[ks_name]["median_avg_ns"])
        c = float(row_by_name[c_name]["median_avg_ns"])
        comparisons[bench] = {
            "ks_median_avg_ns": ks,
            "c_median_avg_ns": c,
            "delta_ns": ks - c,
            "overhead_pct": ((ks - c) / c * 100.0) if c else 0.0,
        }

    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / "microbench_summary.csv").open("w", newline="", encoding="utf-8") as f:
        fields = [
            "name",
            "object",
            "object_bytes",
            "instructions",
            "repeat",
            "trials",
            "median_avg_ns",
            "min_avg_ns",
            "max_avg_ns",
            "samples_avg_ns",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["samples_avg_ns"] = " ".join(str(x) for x in row["samples_avg_ns"])
            writer.writerow({k: out[k] for k in fields})

    summary = {"status": "ok", "rows": rows, "comparisons": comparisons}
    write(RESULTS / "microbench_summary.json", json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary["comparisons"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
