#!/usr/bin/env python3
"""Run a TCP workload and verify struct_ops callbacks are reached."""

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
BUILD = RESULTS / "build" / "struct_ops_callback_workload"
LOGS = RESULTS / "logs" / "struct_ops_callback_workload"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"
TRIALS = int(os.environ.get("KERNELSCRIPT_STRUCT_OPS_CALLBACK_TRIALS", "10"))
BYTES = int(os.environ.get("KERNELSCRIPT_STRUCT_OPS_CALLBACK_BYTES", str(4 * 1024 * 1024)))
FLAG_NAMES = ["ssthresh", "undo_cwnd", "cong_avoid", "set_state", "cwnd_event"]
REQUIRED_FLAGS = [2, 4]


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
    source = ROOT / "experiments" / "programs" / "struct_ops_callback_count.ks"
    res = run([str(COMPILER), "compile", str(source), "-o", str(out)])
    write(LOGS / "kernelscript.compile.stdout", res.stdout)
    write(LOGS / "kernelscript.compile.stderr", res.stderr)
    check(res, "KernelScript struct_ops callback compile")
    make = run(["make", "ebpf-only"], out)
    write(LOGS / "kernelscript.make.stdout", make.stdout)
    write(LOGS / "kernelscript.make.stderr", make.stderr)
    check(make, "KernelScript struct_ops callback eBPF build")
    obj = out / "struct_ops_callback_count.ebpf.o"
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

    obj = out / "struct_ops_tcp_callback_flags.o"
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
            str(ROOT / "experiments" / "baselines" / "struct_ops_tcp_callback_flags.c"),
            "-o",
            str(obj),
        ]
    )
    write(LOGS / "handwritten.clang.stdout", clang.stdout)
    write(LOGS / "handwritten.clang.stderr", clang.stderr)
    check(clang, "handwritten struct_ops callback clang")
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
    check(gcc, "struct_ops callback workload runner gcc")
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


def callback_flags(values: dict[str, str]) -> list[int]:
    return [int_value(values, f"callback_flag_{idx}") for idx in range(len(FLAG_NAMES))]


def callback_passed(flags: list[int]) -> bool:
    return all(flags[idx] > 0 for idx in REQUIRED_FLAGS)


def trial(
    name: str,
    obj: Path,
    map_name: str,
    cc_name: str,
    flags_map: str,
    runner: Path,
    idx: int,
) -> dict[str, object]:
    start = time.perf_counter()
    proc = run(
        [str(runner), str(obj), map_name, cc_name, str(BYTES), flags_map],
        sudo=True,
        timeout=120,
    )
    elapsed = time.perf_counter() - start
    write(LOGS / f"{name}.trial{idx}.stdout", proc.stdout)
    write(LOGS / f"{name}.trial{idx}.stderr", proc.stderr)
    parsed = parse_key_values(proc.stdout + proc.stderr)
    bytes_received = int_value(parsed, "bytes_received")
    flags = callback_flags(parsed)
    callback_ok = callback_passed(flags)
    return {
        "trial": idx,
        "returncode": proc.returncode,
        "elapsed_sec": round(elapsed, 6),
        "load_ok": int_value(parsed, "load_ok"),
        "attach_ok": int_value(parsed, "attach_ok"),
        "client_ok": int_value(parsed, "client_ok"),
        "cc_selected": int_value(parsed, "cc_selected"),
        "bytes_received": bytes_received,
        "workload_ok": int_value(parsed, "workload_ok"),
        "callback_map_found": int_value(parsed, "callback_map_found"),
        "callback_flags": flags,
        "callback_any": int_value(parsed, "callback_any"),
        "callback_positive_slots": int_value(parsed, "callback_positive_slots"),
        "callback_required": int_value(parsed, "callback_required"),
        "callback_oracle_passed": callback_ok,
        "detach_ok": int_value(parsed, "detach_ok"),
        "oracle_passed": (
            proc.returncode == 0
            and int_value(parsed, "load_ok") == 1
            and int_value(parsed, "attach_ok") == 1
            and int_value(parsed, "client_ok") == 1
            and int_value(parsed, "cc_selected") == 1
            and bytes_received == BYTES
            and int_value(parsed, "workload_ok") == 1
            and int_value(parsed, "callback_map_found") == 1
            and int_value(parsed, "callback_required") == 1
            and callback_ok
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
    flags_map: str,
    runner: Path,
) -> dict[str, object]:
    samples = [trial(name, obj, map_name, cc_name, flags_map, runner, i) for i in range(TRIALS)]
    elapsed = [float(row["elapsed_sec"]) for row in samples]
    rates = [
        (float(row["bytes_received"]) / (1024 * 1024)) / float(row["elapsed_sec"])
        for row in samples
        if float(row["elapsed_sec"]) > 0 and int(row["bytes_received"]) == BYTES
    ]
    flags_by_slot = [
        [int(row["callback_flags"][idx]) for row in samples]
        for idx in range(len(FLAG_NAMES))
    ]
    required_ok = [
        sum(1 for row in samples if int(row["callback_flags"][idx]) > 0)
        for idx in REQUIRED_FLAGS
    ]
    return {
        "name": name,
        "implementation": implementation,
        "object": str(obj.relative_to(ROOT)),
        "map_name": map_name,
        "cc_name": cc_name,
        "flags_map": flags_map,
        "trials": TRIALS,
        "bytes_per_trial": BYTES,
        "returncodes": [int(row["returncode"]) for row in samples],
        "load_ok_samples": [int(row["load_ok"]) for row in samples],
        "attach_ok_samples": [int(row["attach_ok"]) for row in samples],
        "client_ok_samples": [int(row["client_ok"]) for row in samples],
        "cc_selected_samples": [int(row["cc_selected"]) for row in samples],
        "bytes_received_samples": [int(row["bytes_received"]) for row in samples],
        "workload_ok_samples": [int(row["workload_ok"]) for row in samples],
        "callback_map_found_samples": [int(row["callback_map_found"]) for row in samples],
        "callback_flags_by_slot": flags_by_slot,
        "required_callback_ok_counts": required_ok,
        "callback_any_samples": [int(row["callback_any"]) for row in samples],
        "callback_positive_slots_samples": [int(row["callback_positive_slots"]) for row in samples],
        "callback_required_samples": [int(row["callback_required"]) for row in samples],
        "callback_oracle_samples": [int(row["callback_oracle_passed"]) for row in samples],
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
        write(RESULTS / "struct_ops_callback_workload_summary.json", json.dumps(summary, indent=2) + "\n")
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
        summarize(
            "ks_generated",
            "kernelscript",
            ks_obj,
            "minimal_congestion_control",
            "minimal_cc",
            "callback_flags",
            runner,
        ),
        summarize(
            "c_libbpf",
            "handwritten_c",
            c_obj,
            "ks_paper_cb_cc",
            "ks_cb_cc",
            "callback_flags",
            runner,
        ),
    ]
    status = "ok" if all(row["oracle_passed"] for row in rows) else "failed"
    summary = {
        "status": status,
        "description": "loopback TCP workload with struct_ops callback flags",
        "trials": TRIALS,
        "bytes_per_trial": BYTES,
        "flag_names": FLAG_NAMES,
        "required_callback_flags": [FLAG_NAMES[idx] for idx in REQUIRED_FLAGS],
        "rows": rows,
    }

    fields = [
        "name",
        "implementation",
        "object",
        "map_name",
        "cc_name",
        "flags_map",
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
        "callback_map_found_samples",
        "callback_flags_by_slot",
        "required_callback_ok_counts",
        "callback_any_samples",
        "callback_positive_slots_samples",
        "callback_required_samples",
        "callback_oracle_samples",
        "detach_ok_samples",
        "elapsed_sec_samples",
        "median_elapsed_sec",
        "median_mib_per_sec",
    ]
    list_fields = {
        "returncodes",
        "load_ok_samples",
        "attach_ok_samples",
        "client_ok_samples",
        "cc_selected_samples",
        "bytes_received_samples",
        "workload_ok_samples",
        "callback_map_found_samples",
        "required_callback_ok_counts",
        "callback_any_samples",
        "callback_positive_slots_samples",
        "callback_required_samples",
        "callback_oracle_samples",
        "detach_ok_samples",
        "elapsed_sec_samples",
    }
    with (RESULTS / "struct_ops_callback_workload_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            for key in list_fields:
                out[key] = " ".join(str(value) for value in row[key])
            out["callback_flags_by_slot"] = ";".join(
                f"{FLAG_NAMES[idx]}:{' '.join(str(value) for value in values)}"
                for idx, values in enumerate(row["callback_flags_by_slot"])
            )
            writer.writerow({key: out[key] for key in fields})

    write(RESULTS / "struct_ops_callback_workload_summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: summary[key] for key in summary if key != "rows"}, indent=2, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
