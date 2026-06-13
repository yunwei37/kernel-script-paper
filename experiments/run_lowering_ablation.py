#!/usr/bin/env python3
"""Run a map-update lowering ablation for the XDP count benchmark."""

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
BUILD = RESULTS / "build" / "lowering_ablation"
LOGS = RESULTS / "logs" / "lowering_ablation"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"
PIN_ROOT = "/sys/fs/bpf/kernelscript-paper"
REPEAT = int(os.environ.get("KERNELSCRIPT_ABLATION_REPEAT", "100000"))
TRIALS = int(os.environ.get("KERNELSCRIPT_ABLATION_TRIALS", "7"))


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


def compile_ks_project() -> Path:
    out = BUILD / "ks_count_current"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT / "experiments" / "programs" / "perf_count.ks"
    res = run([str(COMPILER), "compile", str(source), "-o", str(out)], ROOT)
    write(LOGS / "ks_count_current.ks.stdout", res.stdout)
    write(LOGS / "ks_count_current.ks.stderr", res.stderr)
    check(res, "KernelScript count compile")
    make = run(["make", "ebpf-only"], out)
    write(LOGS / "ks_count_current.make.stdout", make.stdout)
    write(LOGS / "ks_count_current.make.stderr", make.stderr)
    check(make, "KernelScript count eBPF build")
    return out


def compile_handwritten() -> Path:
    hand_dir = BUILD / "handwritten"
    if hand_dir.exists():
        shutil.rmtree(hand_dir)
    hand_dir.mkdir(parents=True, exist_ok=True)
    btf = run(["bpftool", "btf", "dump", "file", "/sys/kernel/btf/vmlinux", "format", "c"], ROOT)
    write(LOGS / "handwritten.btf.stdout", btf.stdout)
    write(LOGS / "handwritten.btf.stderr", btf.stderr)
    check(btf, "bpftool btf dump")
    write(hand_dir / "vmlinux.h", btf.stdout)
    obj = hand_dir / "c_count.o"
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
        str(ROOT / "experiments" / "baselines" / "xdp_count.c"),
        "-o",
        str(obj),
    ]
    res = run(cmd, ROOT)
    write(LOGS / "c_count.clang.stdout", res.stdout)
    write(LOGS / "c_count.clang.stderr", res.stderr)
    check(res, "hand-written count clang")
    return obj


def patch_atomic_lowering(current: Path) -> Path:
    patched = BUILD / "ks_count_atomic"
    if patched.exists():
        shutil.rmtree(patched)
    shutil.copytree(current, patched)
    for generated in [patched / "perf_count.ebpf.o", patched / "perf_count.skel.h", patched / "perf_count"]:
        if generated.exists():
            generated.unlink()

    source = patched / "perf_count.ebpf.c"
    text = source.read_text(encoding="utf-8")
    old = """    __u64 __binop_1;
    __u64* __map_lookup_0;
    __u32 key_1 = 0;
    __map_lookup_0 = bpf_map_lookup_elem(&counts, &key_1);
    __binop_1 = (({ __u64 __val = {0}; if (__map_lookup_0) { __val = *(__map_lookup_0); } __val; }) + 1);
    __u32 key_2 = 0;
    bpf_map_update_elem(&counts, &key_2, &__binop_1, BPF_ANY);
"""
    new = """    __u32 key_1 = 0;
    __u64* value = bpf_map_lookup_elem(&counts, &key_1);
    if (value) {
        __sync_fetch_and_add(value, 1);
    }
"""
    if old not in text:
        raise RuntimeError("expected KernelScript map-update lowering pattern was not found")
    source.write_text(text.replace(old, new), encoding="utf-8")

    make = run(["make", "ebpf-only"], patched)
    write(LOGS / "ks_count_atomic.make.stdout", make.stdout)
    write(LOGS / "ks_count_atomic.make.stderr", make.stderr)
    check(make, "patched atomic lowering eBPF build")
    return patched


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


def hex_bytes(value: int, width: int) -> list[str]:
    return [f"{byte:02x}" for byte in value.to_bytes(width, byteorder="little", signed=False)]


def reset_count_map(map_pin: str) -> None:
    res = run(
        [
            "bpftool",
            "map",
            "update",
            "pinned",
            map_pin,
            "key",
            *hex_bytes(0, 4),
            "value",
            *hex_bytes(0, 8),
            "any",
        ],
        ROOT,
        sudo=True,
    )
    check(res, f"reset map {map_pin}")


def read_count_map(map_pin: str) -> int:
    res = run(
        ["bpftool", "-j", "map", "lookup", "pinned", map_pin, "key", *hex_bytes(0, 4)],
        ROOT,
        sudo=True,
    )
    check(res, f"lookup map {map_pin}")
    decoded = json.loads(res.stdout)
    formatted = decoded.get("formatted", {})
    if "value" in formatted:
        return int(formatted["value"])
    value = decoded["value"]
    if isinstance(value, list):
        raw = bytes(int(part, 16) for part in value)
        return int.from_bytes(raw, byteorder="little", signed=False)
    return int(value)


def benchmark_object(name: str, obj: Path, pkt: Path) -> dict[str, object]:
    pin = f"{PIN_ROOT}/{name}_{os.getpid()}"
    map_dir = f"{PIN_ROOT}/{name}_{os.getpid()}_maps"
    map_pin = f"{map_dir}/counts"
    run(["mkdir", "-p", PIN_ROOT], ROOT, sudo=True)
    run(["rm", "-rf", pin, map_dir], ROOT, sudo=True)
    run(["mkdir", "-p", map_dir], ROOT, sudo=True)
    load = run(["bpftool", "prog", "load", str(obj), pin, "type", "xdp", "pinmaps", map_dir], ROOT, sudo=True)
    write(LOGS / f"{name}.load.stdout", load.stdout)
    write(LOGS / f"{name}.load.stderr", load.stderr)
    check(load, f"{name} bpftool load")
    samples: list[float] = []
    observed_counts: list[int] = []
    try:
        for i in range(TRIALS):
            reset_count_map(map_pin)
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
            observed = read_count_map(map_pin)
            if observed != REPEAT:
                raise RuntimeError(f"{name} trial {i} count oracle failed: expected {REPEAT}, got {observed}")
            observed_counts.append(observed)
    finally:
        run(["rm", "-rf", pin, map_dir], ROOT, sudo=True)
    return {
        "name": name,
        "object": str(obj.relative_to(ROOT)),
        "object_bytes": obj.stat().st_size,
        "instructions": instruction_count(obj),
        "repeat": REPEAT,
        "trials": TRIALS,
        "expected_count": REPEAT,
        "observed_counts": observed_counts,
        "samples_avg_ns": samples,
        "median_avg_ns": statistics.median(samples),
        "min_avg_ns": min(samples),
        "max_avg_ns": max(samples),
    }


def pct_delta(before: float, after: float) -> float:
    return ((before - after) / before * 100.0) if before else 0.0


def main() -> int:
    if run(["true"], ROOT, sudo=True).returncode != 0:
        summary = {"status": "skipped", "reason": "sudo -n unavailable"}
        write(RESULTS / "lowering_ablation_summary.json", json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0

    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    pkt = packet_file()

    current = compile_ks_project()
    atomic = patch_atomic_lowering(current)
    c_count = compile_handwritten()

    objects = {
        "ks_count_current": current / "perf_count.ebpf.o",
        "ks_count_atomic": atomic / "perf_count.ebpf.o",
        "c_count": c_count,
    }
    rows = [benchmark_object(name, obj, pkt) for name, obj in objects.items()]
    by_name = {row["name"]: row for row in rows}
    current_row = by_name["ks_count_current"]
    atomic_row = by_name["ks_count_atomic"]
    c_row = by_name["c_count"]
    comparisons = {
        "current_vs_atomic": {
            "instruction_reduction": int(current_row["instructions"]) - int(atomic_row["instructions"]),
            "instruction_reduction_pct": pct_delta(float(current_row["instructions"]), float(atomic_row["instructions"])),
            "median_ns_reduction": float(current_row["median_avg_ns"]) - float(atomic_row["median_avg_ns"]),
            "median_ns_reduction_pct": pct_delta(float(current_row["median_avg_ns"]), float(atomic_row["median_avg_ns"])),
        },
        "atomic_vs_c": {
            "instruction_delta": int(atomic_row["instructions"]) - int(c_row["instructions"]),
            "median_ns_delta": float(atomic_row["median_avg_ns"]) - float(c_row["median_avg_ns"]),
        },
        "current_vs_c": {
            "instruction_delta": int(current_row["instructions"]) - int(c_row["instructions"]),
            "median_ns_delta": float(current_row["median_avg_ns"]) - float(c_row["median_avg_ns"]),
        },
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / "lowering_ablation_summary.csv").open("w", newline="", encoding="utf-8") as f:
        fields = [
            "name",
            "object",
            "object_bytes",
            "instructions",
            "repeat",
            "trials",
            "expected_count",
            "observed_counts",
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
            out["observed_counts"] = " ".join(str(x) for x in row["observed_counts"])
            writer.writerow({k: out[k] for k in fields})

    summary = {
        "status": "ok",
        "description": "Ablation patches generated map update lowering from lookup+update to in-place atomic add.",
        "rows": rows,
        "comparisons": comparisons,
    }
    write(RESULTS / "lowering_ablation_summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(comparisons, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
