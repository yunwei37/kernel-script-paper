#!/usr/bin/env python3
"""Run XDP microbenchmarks for tail-call dispatch workloads.

This benchmark measures two aspects:
1. KernelScript-generated tail-call objects versus equivalent hand-written
   C/eBPF tail-call objects.
2. Tail-call dispatch versus flattened direct dispatch for the same logic.

The harness uses `bpftool prog loadall` so that multi-program objects can
populate their prog-array maps before `bpftool prog run`.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("KERNELSCRIPT_REPO", ROOT / "kernelscript")).resolve()
RESULTS = ROOT / "results"
ARTIFACT_ROOT = Path(
    os.environ.get("KERNELSCRIPT_TAIL_CALL_MICRO_ROOT", str(ROOT / ".tail_call_microbench"))
).resolve()
BUILD = ARTIFACT_ROOT / "build"
LOGS = ARTIFACT_ROOT / "logs"
SUMMARY_JSON = RESULTS / "tail_call_microbench_summary.json"
SUMMARY_CSV = RESULTS / "tail_call_microbench_summary.csv"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"
PIN_ROOT = "/sys/fs/bpf/kernelscript-paper/tail-call-microbench"
REPEAT = int(os.environ.get("KERNELSCRIPT_TAILCALL_REPEAT", "100000"))
TRIALS = int(os.environ.get("KERNELSCRIPT_TAILCALL_TRIALS", "7"))
SUDO_PASSWORD = os.environ.get("KERNELSCRIPT_SUDO_PASSWORD")


@dataclass(frozen=True)
class Variant:
    workload: str
    name: str
    implementation: str
    source: Path
    entry_program: str
    tail_targets: tuple[tuple[str, int], ...] = ()
    is_kernelscript: bool = False


VARIANTS = [
    Variant(
        workload="dispatch",
        name="ks_dispatch_tail",
        implementation="kernelscript_tail",
        source=ROOT / "experiments" / "programs" / "tail_call_dispatch_tail.ks",
        entry_program="packet_filter",
        tail_targets=(("drop_handler", 0),),
        is_kernelscript=True,
    ),
    Variant(
        workload="dispatch",
        name="ks_dispatch_flat",
        implementation="kernelscript_flat",
        source=ROOT / "experiments" / "programs" / "tail_call_dispatch_flat.ks",
        entry_program="packet_filter",
        is_kernelscript=True,
    ),
    Variant(
        workload="dispatch",
        name="c_dispatch_tail",
        implementation="c_tail",
        source=ROOT / "experiments" / "baselines" / "tail_call_dispatch_tail.bpf.c",
        entry_program="packet_filter",
        tail_targets=(("drop_handler", 0),),
    ),
    Variant(
        workload="dispatch",
        name="c_dispatch_flat",
        implementation="c_flat",
        source=ROOT / "experiments" / "baselines" / "tail_call_dispatch_flat.bpf.c",
        entry_program="packet_filter",
    ),
    Variant(
        workload="basic_match",
        name="ks_basic_match_tail",
        implementation="kernelscript_tail",
        source=ROOT / "experiments" / "programs" / "basic_match_tail.ks",
        entry_program="packet_classifier",
        tail_targets=(("udp_port_classifier", 0), ("tcp_port_classifier", 1)),
        is_kernelscript=True,
    ),
    Variant(
        workload="basic_match",
        name="ks_basic_match_flat",
        implementation="kernelscript_flat",
        source=ROOT / "experiments" / "programs" / "basic_match_flat.ks",
        entry_program="packet_classifier",
        is_kernelscript=True,
    ),
    Variant(
        workload="basic_match",
        name="c_basic_match_tail",
        implementation="c_tail",
        source=ROOT / "experiments" / "baselines" / "basic_match_tailcall.bpf.c",
        entry_program="packet_classifier",
        tail_targets=(("udp_port_classifier", 0), ("tcp_port_classifier", 1)),
    ),
    Variant(
        workload="basic_match",
        name="c_basic_match_flat",
        implementation="c_flat",
        source=ROOT / "experiments" / "baselines" / "basic_match_flat.bpf.c",
        entry_program="packet_classifier",
    ),
]


def run(argv: list[str], cwd: Path = ROOT, timeout: int = 120, sudo: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PWD"] = str(cwd)
    input_text: str | None = None
    if sudo:
        if SUDO_PASSWORD is None:
            full = ["sudo", "-n"] + argv
        else:
            full = ["sudo", "-S", "-p", ""] + argv
            input_text = SUDO_PASSWORD + "\n"
    else:
        full = argv
    return subprocess.run(
        full,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        input=input_text,
        timeout=timeout,
        check=False,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def check(cmd: subprocess.CompletedProcess[str], label: str) -> None:
    if cmd.returncode != 0:
        raise RuntimeError(f"{label} failed\nstdout:\n{cmd.stdout}\nstderr:\n{cmd.stderr}")


def check_prerequisites() -> str | None:
    if run(["true"], ROOT, sudo=True).returncode != 0:
        return "sudo -n unavailable"
    for cmd in ("bpftool", "clang", "make"):
        if not shutil.which(cmd):
            return f"{cmd} unavailable"
    if not COMPILER.exists():
        return f"missing KernelScript compiler at {COMPILER}"
    if not Path("/sys/kernel/btf/vmlinux").exists():
        return "missing /sys/kernel/btf/vmlinux"
    for variant in VARIANTS:
        if not variant.source.exists():
            return f"missing source file: {variant.source}"
    return None


def instruction_count(obj: Path) -> int:
    objdump = shutil.which("llvm-objdump") or shutil.which("llvm-objdump-18") or shutil.which("llvm-objdump-19")
    if not objdump:
        return 0
    res = run([objdump, "-d", str(obj)], obj.parent)
    if res.returncode != 0:
        return 0
    return sum(1 for line in res.stdout.splitlines() if re.match(r"\s*[0-9a-f]+:\s", line))


def packet_file() -> Path:
    pkt = BUILD / "packet64.bin"
    pkt.parent.mkdir(parents=True, exist_ok=True)
    pkt.write_bytes(bytes.fromhex("ffffffffffff0000000000010800") + bytes(50))
    return pkt


def hex_bytes(value: int, width: int) -> list[str]:
    return [f"{byte:02x}" for byte in value.to_bytes(width, byteorder="little", signed=False)]


def parse_avg_ns(output: str) -> float:
    match = re.search(r"duration \(average\):\s*([0-9.]+)ns", output)
    if not match:
        raise RuntimeError(f"Could not parse bpftool duration from: {output!r}")
    return float(match.group(1))


def compile_kernelscript(variant: Variant) -> Path:
    out = BUILD / variant.name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    res = run([str(COMPILER), "compile", str(variant.source), "-o", str(out)], ROOT, timeout=240)
    write(LOGS / f"{variant.name}.ks.stdout", res.stdout)
    write(LOGS / f"{variant.name}.ks.stderr", res.stderr)
    check(res, f"{variant.name} KernelScript compile")
    make = run(["make", "ebpf-only"], out, timeout=240)
    write(LOGS / f"{variant.name}.make.stdout", make.stdout)
    write(LOGS / f"{variant.name}.make.stderr", make.stderr)
    check(make, f"{variant.name} make ebpf-only")
    objects = sorted(out.glob("*.ebpf.o"))
    if len(objects) != 1:
        raise RuntimeError(f"Expected one eBPF object in {out}, found {objects}")
    return objects[0]


def prepare_handwritten_dir() -> Path:
    hand_dir = BUILD / "handwritten"
    if hand_dir.exists():
        shutil.rmtree(hand_dir)
    hand_dir.mkdir(parents=True, exist_ok=True)
    btf = run(["bpftool", "btf", "dump", "file", "/sys/kernel/btf/vmlinux", "format", "c"], ROOT, timeout=240)
    write(LOGS / "handwritten.btf.stdout", btf.stdout)
    write(LOGS / "handwritten.btf.stderr", btf.stderr)
    check(btf, "bpftool btf dump")
    write(hand_dir / "vmlinux.h", btf.stdout)
    return hand_dir


def compile_c(variant: Variant, hand_dir: Path) -> Path:
    obj = hand_dir / f"{variant.name}.o"
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
        str(variant.source),
        "-o",
        str(obj),
    ]
    res = run(cmd, ROOT, timeout=240)
    write(LOGS / f"{variant.name}.clang.stdout", res.stdout)
    write(LOGS / f"{variant.name}.clang.stderr", res.stderr)
    check(res, f"{variant.name} clang")
    return obj


def populate_tail_call_map(map_pin: str, prog_pin_dir: str, targets: tuple[tuple[str, int], ...]) -> None:
    for target_name, index in targets:
        target_pin = f"{prog_pin_dir}/{target_name}"
        res = run(
            [
                "bpftool",
                "map",
                "update",
                "pinned",
                map_pin,
                "key",
                *hex_bytes(index, 4),
                "value",
                "pinned",
                target_pin,
                "any",
            ],
            ROOT,
            timeout=60,
            sudo=True,
        )
        check(res, f"prog_array update for {target_name}@{index}")


def benchmark_variant(variant: Variant, obj: Path, pkt: Path) -> dict[str, object]:
    pin_base = f"{PIN_ROOT}/{variant.name}_{os.getpid()}"
    prog_pin_dir = f"{pin_base}/progs"
    map_pin_dir = f"{pin_base}/maps"
    entry_pin = f"{prog_pin_dir}/{variant.entry_program}"
    run(["mkdir", "-p", PIN_ROOT], ROOT, sudo=True)
    run(["rm", "-rf", pin_base], ROOT, sudo=True)
    run(["mkdir", "-p", prog_pin_dir, map_pin_dir], ROOT, sudo=True)
    load = run(
        ["bpftool", "prog", "loadall", str(obj), prog_pin_dir, "pinmaps", map_pin_dir, "type", "xdp"],
        ROOT,
        timeout=240,
        sudo=True,
    )
    write(LOGS / f"{variant.name}.load.stdout", load.stdout)
    write(LOGS / f"{variant.name}.load.stderr", load.stderr)
    check(load, f"{variant.name} bpftool loadall")
    if variant.tail_targets:
        populate_tail_call_map(f"{map_pin_dir}/prog_array", prog_pin_dir, variant.tail_targets)
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
                    entry_pin,
                    "data_in",
                    str(pkt),
                    "repeat",
                    str(REPEAT),
                ],
                ROOT,
                timeout=240,
                sudo=True,
            )
            elapsed = time.perf_counter() - start
            write(LOGS / f"{variant.name}.run{i}.stdout", res.stdout)
            write(LOGS / f"{variant.name}.run{i}.stderr", res.stderr)
            check(res, f"{variant.name} bpftool run trial {i}")
            avg_ns = parse_avg_ns(res.stdout + res.stderr)
            samples.append(avg_ns)
            write(LOGS / f"{variant.name}.run{i}.elapsed", f"{elapsed:.9f}\n")
    finally:
        run(["rm", "-rf", pin_base], ROOT, sudo=True)
    return {
        "name": variant.name,
        "workload": variant.workload,
        "implementation": variant.implementation,
        "source": str(variant.source.relative_to(ROOT)),
        "object": str(obj.relative_to(ROOT)),
        "entry_program": variant.entry_program,
        "tail_target_count": len(variant.tail_targets),
        "repeat": REPEAT,
        "trials": TRIALS,
        "instructions": instruction_count(obj),
        "object_bytes": obj.stat().st_size,
        "samples_avg_ns": samples,
        "median_avg_ns": statistics.median(samples),
        "min_avg_ns": min(samples),
        "max_avg_ns": max(samples),
    }


def comparison(row_by_name: dict[str, dict[str, object]], left: str, right: str) -> dict[str, float | str]:
    left_row = row_by_name[left]
    right_row = row_by_name[right]
    left_ns = float(left_row["median_avg_ns"])
    right_ns = float(right_row["median_avg_ns"])
    left_instr = int(left_row["instructions"])
    right_instr = int(right_row["instructions"])
    return {
        "left": left,
        "right": right,
        "left_median_avg_ns": left_ns,
        "right_median_avg_ns": right_ns,
        "delta_ns": left_ns - right_ns,
        "overhead_pct": ((left_ns - right_ns) / right_ns * 100.0) if right_ns else 0.0,
        "left_instructions": left_instr,
        "right_instructions": right_instr,
        "delta_instructions": left_instr - right_instr,
        "instruction_overhead_pct": ((left_instr - right_instr) / right_instr * 100.0) if right_instr else 0.0,
    }


def main() -> int:
    reason = check_prerequisites()
    if reason:
        summary = {"status": "skipped", "reason": reason}
        write(SUMMARY_JSON, json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0

    if LOGS.exists():
        shutil.rmtree(LOGS)
    if BUILD.exists():
        shutil.rmtree(BUILD)
    LOGS.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    pkt = packet_file()

    hand_dir = prepare_handwritten_dir()
    objects: dict[str, Path] = {}
    for variant in VARIANTS:
        if variant.is_kernelscript:
            objects[variant.name] = compile_kernelscript(variant)
        else:
            objects[variant.name] = compile_c(variant, hand_dir)

    rows = [benchmark_variant(variant, objects[variant.name], pkt) for variant in VARIANTS]
    row_by_name = {str(row["name"]): row for row in rows}
    comparisons = {
        "dispatch_generated_vs_hand_tail": comparison(row_by_name, "ks_dispatch_tail", "c_dispatch_tail"),
        "dispatch_ks_tail_vs_flat": comparison(row_by_name, "ks_dispatch_tail", "ks_dispatch_flat"),
        "dispatch_c_tail_vs_flat": comparison(row_by_name, "c_dispatch_tail", "c_dispatch_flat"),
        "basic_match_generated_vs_hand_tail": comparison(row_by_name, "ks_basic_match_tail", "c_basic_match_tail"),
        "basic_match_ks_tail_vs_flat": comparison(row_by_name, "ks_basic_match_tail", "ks_basic_match_flat"),
        "basic_match_c_tail_vs_flat": comparison(row_by_name, "c_basic_match_tail", "c_basic_match_flat"),
    }

    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        fields = [
            "name",
            "workload",
            "implementation",
            "source",
            "object",
            "entry_program",
            "tail_target_count",
            "repeat",
            "trials",
            "instructions",
            "object_bytes",
            "median_avg_ns",
            "min_avg_ns",
            "max_avg_ns",
            "samples_avg_ns",
        ]
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["samples_avg_ns"] = " ".join(str(x) for x in row["samples_avg_ns"])
            writer.writerow({k: out[k] for k in fields})

    summary = {
        "status": "ok",
        "description": "bpftool prog run microbenchmarks for tail-call dispatch workloads.",
        "repeat": REPEAT,
        "trials": TRIALS,
        "rows": rows,
        "comparisons": comparisons,
    }
    write(SUMMARY_JSON, json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(comparisons, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
