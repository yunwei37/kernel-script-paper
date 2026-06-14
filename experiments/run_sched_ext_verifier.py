#!/usr/bin/env python3
"""Diagnose sched_ext struct_ops verifier behavior without attaching a scheduler."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("KERNELSCRIPT_REPO", ROOT / "kernelscript")).resolve()
RESULTS = ROOT / "results"
BUILD = RESULTS / "build" / "sched_ext_verifier"
LOGS = RESULTS / "logs" / "sched_ext_verifier"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"
PIN_ROOT = "/sys/fs/bpf/kernelscript-paper/sched-ext-verifier"


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
    for cmd in ["bpftool", "clang", "make"]:
        if not shutil.which(cmd):
            return f"{cmd} unavailable"
    if not Path("/sys/kernel/btf/vmlinux").exists():
        return "missing /sys/kernel/btf/vmlinux"
    if not Path("/sys/kernel/sched_ext/state").exists():
        return "missing /sys/kernel/sched_ext/state"
    if not COMPILER.exists():
        return f"missing KernelScript compiler at {COMPILER}"
    return None


def sysfs_value(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return "unavailable"


def compile_ks() -> Path:
    out = BUILD / "kernelscript"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    source = REPO / "examples" / "sched_ext_simple.ks"
    res = run([str(COMPILER), "compile", str(source), "-o", str(out)])
    write(LOGS / "kernelscript.compile.stdout", res.stdout)
    write(LOGS / "kernelscript.compile.stderr", res.stderr)
    check(res, "KernelScript sched_ext compile")
    make = run(["make", "ebpf-only"], out)
    write(LOGS / "kernelscript.make.stdout", make.stdout)
    write(LOGS / "kernelscript.make.stderr", make.stderr)
    check(make, "KernelScript sched_ext eBPF build")
    obj = out / "sched_ext_simple.ebpf.o"
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

    obj = out / "sched_ext_simple.o"
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
            str(ROOT / "experiments" / "baselines" / "sched_ext_simple.c"),
            "-o",
            str(obj),
        ]
    )
    write(LOGS / "handwritten.clang.stdout", clang.stdout)
    write(LOGS / "handwritten.clang.stderr", clang.stderr)
    check(clang, "handwritten sched_ext clang")
    return obj


def program_sections(obj: Path) -> list[str]:
    objdump = shutil.which("llvm-objdump") or shutil.which("llvm-objdump-18") or shutil.which("llvm-objdump-19")
    if not objdump:
        return []
    res = run([objdump, "-h", str(obj)], obj.parent)
    if res.returncode != 0:
        return []
    sections: list[str] = []
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].isdigit() and "TEXT" in parts[4:]:
            name = parts[1]
            if name != ".text":
                sections.append(name)
    return sections


def first_error_excerpt(text: str, max_lines: int = 16) -> str:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        low = line.lower()
        if "error:" in low or "failed" in low or "invalid" in low or "arg#" in low:
            return "\n".join(lines[max(0, idx - 4) : idx + max_lines])
    return "\n".join(lines[:max_lines])


def classify_failure(text: str) -> str:
    low = text.lower()
    if "arg#0 pointer type struct task_struct" in low:
        return "struct_ops_task_arg_type"
    if "arg#3" in low and "bool" in low:
        return "sched_ext_bool_arg_type"
    if "not found in kernel or module btfs" in low:
        return "missing_kernel_btf_symbol"
    if "failed to create" in low and "map" in low:
        return "map_create_failed"
    if "permission denied" in low:
        return "permission_denied"
    if "bpf program load failed" in low or "failed to load object file" in low:
        return "verifier_rejected"
    return "load_failed"


def pinned_program_names(prog_pin: str) -> list[str]:
    res = run(["find", prog_pin, "-maxdepth", "1", "-type", "f", "-printf", "%f\n"], sudo=True)
    if res.returncode != 0:
        return []
    return sorted(name for name in res.stdout.splitlines() if name.strip())


def load_object(name: str, implementation: str, obj: Path) -> dict[str, object]:
    pin_base = f"{PIN_ROOT}/{os.getpid()}_{name}"
    prog_pin = f"{pin_base}/progs"
    map_pin = f"{pin_base}/maps"
    sections = program_sections(obj)
    run(["rm", "-rf", pin_base], sudo=True)
    run(["mkdir", "-p", prog_pin, map_pin], sudo=True)
    res = run(
        ["bpftool", "prog", "loadall", str(obj), prog_pin, "pinmaps", map_pin],
        timeout=120,
        sudo=True,
    )
    write(LOGS / f"{name}.load.stdout", res.stdout)
    write(LOGS / f"{name}.load.stderr", res.stderr)
    pinned = pinned_program_names(prog_pin)
    run(["rm", "-rf", pin_base], sudo=True)
    text = res.stdout + res.stderr
    ok = res.returncode == 0 and bool(pinned)
    if res.returncode == 0 and not pinned:
        text += "\nNo BPF programs were pinned under the program pin directory."
    return {
        "name": name,
        "implementation": implementation,
        "object": str(obj.relative_to(ROOT)),
        "program_sections": " ".join(sections),
        "program_count": len(sections),
        "returncode": res.returncode,
        "pinned_program_count": len(pinned),
        "load_status": "ok" if ok else "failed",
        "failure_class": "" if ok else classify_failure(text),
        "failure_excerpt": "" if ok else first_error_excerpt(text),
    }


def main() -> int:
    reason = check_prerequisites()
    if reason:
        summary = {"status": "skipped", "reason": reason}
        write(RESULTS / "sched_ext_verifier_summary.json", json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0

    if BUILD.exists():
        shutil.rmtree(BUILD)
    if LOGS.exists():
        shutil.rmtree(LOGS)
    BUILD.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    sched_ext_state_before = sysfs_value("/sys/kernel/sched_ext/state")
    sched_ext_enable_seq_before = sysfs_value("/sys/kernel/sched_ext/enable_seq")
    sched_ext_rejected_before = sysfs_value("/sys/kernel/sched_ext/nr_rejected")

    ks_obj = compile_ks()
    c_obj = compile_c()
    rows = [
        load_object("ks_generated", "kernelscript", ks_obj),
        load_object("c_libbpf", "handwritten_c", c_obj),
    ]

    by_name = {row["name"]: row for row in rows}
    c_ok = by_name["c_libbpf"]["load_status"] == "ok"
    ks_ok = by_name["ks_generated"]["load_status"] == "ok"
    if c_ok and ks_ok:
        diagnosis = "both_load"
    elif c_ok and not ks_ok:
        diagnosis = "generated_sched_ext_verifier_gap"
    elif not c_ok and not ks_ok:
        diagnosis = "environment_or_shared_baseline_failure"
    else:
        diagnosis = "unexpected_generated_only_success"

    summary = {
        "status": "ok" if c_ok else "failed",
        "description": "sched_ext struct_ops verifier diagnostic without scheduler attachment",
        "diagnosis": diagnosis,
        "sched_ext_state_before": sched_ext_state_before,
        "sched_ext_state_after": sysfs_value("/sys/kernel/sched_ext/state"),
        "sched_ext_enable_seq_before": sched_ext_enable_seq_before,
        "sched_ext_enable_seq_after": sysfs_value("/sys/kernel/sched_ext/enable_seq"),
        "sched_ext_nr_rejected_before": sched_ext_rejected_before,
        "sched_ext_nr_rejected_after": sysfs_value("/sys/kernel/sched_ext/nr_rejected"),
        "attach_attempted": False,
        "rows": rows,
    }

    fields = [
        "name",
        "implementation",
        "object",
        "program_sections",
        "program_count",
        "returncode",
        "pinned_program_count",
        "load_status",
        "failure_class",
        "failure_excerpt",
    ]
    with (RESULTS / "sched_ext_verifier_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fields})

    write(RESULTS / "sched_ext_verifier_summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: summary[key] for key in summary if key != "rows"}, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
