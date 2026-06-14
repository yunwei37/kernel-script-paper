#!/usr/bin/env python3
"""Opt-in sched_ext attach and bounded-workload experiment.

This script is intentionally not part of the default evaluation pipeline.  It
registers a scheduler extension on the host kernel, so callers must pass
``--allow-host-scheduler`` or set ``KERNELSCRIPT_ALLOW_SCHED_EXT_ATTACH=1``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from run_sched_ext_verifier import (
    COMPILER,
    REPO,
    RESULTS,
    ROOT,
    check,
    check_prerequisites,
    first_error_excerpt,
    program_sections,
    run,
    sysfs_value,
    write,
)

BUILD = RESULTS / "build" / "sched_ext_attach"
LOGS = RESULTS / "logs" / "sched_ext_attach"
SUMMARY_JSON = RESULTS / "sched_ext_attach_summary.json"
SUMMARY_CSV = RESULTS / "sched_ext_attach_summary.csv"
ALLOW_ENV = "KERNELSCRIPT_ALLOW_SCHED_EXT_ATTACH"
PIN_ROOT = Path("/sys/fs/bpf/kernelscript-paper/sched-ext-attach")
BPFTOOL = "bpftool"
CLANG = "clang"
SCHED_EXT_SYSFS = Path("/sys/kernel/sched_ext")
WORKLOAD_SECONDS = 0.75
WORKLOAD_MAX_WORKERS = 4


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def mkdirs() -> None:
    for path in [BUILD, LOGS]:
        path.mkdir(parents=True, exist_ok=True)


def compile_c_attach() -> Path:
    out = BUILD / "handwritten"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    obj = out / "sched_ext_simple.o"

    btf = run([BPFTOOL, "btf", "dump", "file", "/sys/kernel/btf/vmlinux", "format", "c"])
    write(LOGS / "handwritten.btf.stdout", btf.stdout)
    write(LOGS / "handwritten.btf.stderr", btf.stderr)
    check(btf, "bpftool btf dump")
    write(out / "vmlinux.h", btf.stdout)

    res = run(
        [
            CLANG,
            "-target",
            "bpf",
            "-O2",
            "-g",
            "-Wall",
            "-Wextra",
            "-fno-builtin",
            "-D__TARGET_ARCH_x86",
            "-I",
            str(out),
            "-c",
            str(ROOT / "experiments" / "baselines" / "sched_ext_simple.c"),
            "-o",
            str(obj),
        ]
    )
    write(LOGS / "handwritten.clang.stdout", res.stdout)
    write(LOGS / "handwritten.clang.stderr", res.stderr)
    check(res, "compile C sched_ext baseline")
    return obj


def compile_ks_attach() -> Path:
    out = BUILD / "kernelscript"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    source = REPO / "examples" / "sched_ext_simple.ks"
    staged = out / "sched_ext_attach_safe.ks"
    text = source.read_text()
    text = text.replace('name: "simple_fifo"', 'name: "ks_attach_fifo"')
    text = re.sub(r"timeout_ms:\s*0", "timeout_ms: 1000", text, count=1)
    staged.write_text(text)
    shutil.copy2(REPO / "examples" / "sched_ext_ops.kh", out / "sched_ext_ops.kh")

    res = run([str(COMPILER), "compile", str(staged), "-o", str(out)])
    write(LOGS / "kernelscript.compile.stdout", res.stdout)
    write(LOGS / "kernelscript.compile.stderr", res.stderr)
    check(res, "compile KernelScript sched_ext attach variant")

    res = run(["make", "-C", str(out), "ebpf-only"])
    write(LOGS / "kernelscript.make.stdout", res.stdout)
    write(LOGS / "kernelscript.make.stderr", res.stderr)
    check(res, "build KernelScript sched_ext attach eBPF object")
    return out / "sched_ext_attach_safe.ebpf.o"


def sched_ext_value(name: str) -> str:
    return sysfs_value(str(SCHED_EXT_SYSFS / name))


def list_struct_ops() -> list[dict[str, Any]]:
    res = run([BPFTOOL, "-j", "struct_ops", "show"], sudo=True)
    if res.returncode != 0:
        return []
    try:
        data = json.loads(res.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def struct_ops_id(entry: dict[str, Any]) -> str | None:
    for key in ("id", "map_id"):
        value = entry.get(key)
        if value is not None:
            return str(value)
    return None


def struct_ops_name(entry: dict[str, Any]) -> str | None:
    for key in ("name", "map_name"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def wait_for_state_change(before: str, timeout_s: float = 2.0) -> str:
    deadline = time.time() + timeout_s
    last = sched_ext_value("state")
    while time.time() < deadline:
        last = sched_ext_value("state")
        if last != before:
            return last
        time.sleep(0.05)
    return last


def wait_for_enabled(timeout_s: float = 2.0) -> str:
    deadline = time.time() + timeout_s
    last = sched_ext_value("state")
    while time.time() < deadline:
        last = sched_ext_value("state")
        if last == "enabled":
            return last
        time.sleep(0.05)
    return last


def run_workload() -> subprocess.CompletedProcess[str]:
    code = f"""
import multiprocessing as mp
import os
import time

def spin(idx):
    end = time.monotonic() + {WORKLOAD_SECONDS}
    value = idx + 1
    while time.monotonic() < end:
        value = ((value * 1103515245) + 12345 + idx) & 0xffffffff
    return value

workers = min({WORKLOAD_MAX_WORKERS}, os.cpu_count() or 1)
with mp.Pool(workers) as pool:
    values = pool.map(spin, range(workers))
print(sum(values))
"""
    return subprocess.run(
        ["python3", "-c", code],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
        check=False,
    )


def ensure_no_active_scheduler() -> tuple[bool, str]:
    state = sched_ext_value("state")
    if state != "disabled":
        return False, f"sched_ext state is {state!r}, expected 'disabled'"
    return True, ""


def cleanup_pin_dir(path: Path) -> None:
    run(["rm", "-rf", str(path)], sudo=True)


def unregister_new_maps(
    new_entries: list[dict[str, Any]], fallback_names: list[str]
) -> list[dict[str, str]]:
    attempts: list[dict[str, str]] = []
    for entry in new_entries:
        entry_id = struct_ops_id(entry)
        if entry_id is None:
            continue
        res = run([BPFTOOL, "struct_ops", "unregister", "id", entry_id], sudo=True)
        attempts.append(
            {
                "target": f"id {entry_id}",
                "returncode": str(res.returncode),
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip(),
            }
        )
        if res.returncode == 0:
            continue
    if any(attempt["returncode"] == "0" for attempt in attempts):
        return attempts
    for name in fallback_names:
        res = run([BPFTOOL, "struct_ops", "unregister", "name", name], sudo=True)
        attempts.append(
            {
                "target": f"name {name}",
                "returncode": str(res.returncode),
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip(),
            }
        )
    return attempts


def run_variant(
    name: str,
    implementation: str,
    obj: Path,
    expected_map_names: list[str],
) -> dict[str, Any]:
    link_dir = PIN_ROOT / f"{os.getpid()}-{name}"
    row: dict[str, Any] = {
        "name": name,
        "implementation": implementation,
        "object": display_path(obj),
        "link_dir": str(link_dir),
        "attach_attempted": True,
        "status": "failed",
        "register_returncode": "",
        "unregister_returncode": "",
        "workload_returncode": "",
        "state_before": sched_ext_value("state"),
        "state_after_register": "",
        "state_after_workload": "",
        "state_after_unregister": "",
        "enable_seq_before": sched_ext_value("enable_seq"),
        "enable_seq_after_register": "",
        "enable_seq_after_unregister": "",
        "nr_rejected_before": sched_ext_value("nr_rejected"),
        "nr_rejected_after": "",
        "failure_excerpt": "",
        "program_sections": program_sections(obj),
        "new_struct_ops_maps": [],
        "unregister_attempts": [],
    }

    ready, reason = ensure_no_active_scheduler()
    if not ready:
        row["status"] = "skipped"
        row["failure_excerpt"] = reason
        return row

    before = list_struct_ops()
    before_ids = {struct_ops_id(entry) for entry in before if struct_ops_id(entry)}
    run(["mkdir", "-p", str(link_dir)], sudo=True)

    new_entries: list[dict[str, Any]] = []
    try:
        res = run([BPFTOOL, "struct_ops", "register", str(obj), str(link_dir)], sudo=True)
        write(LOGS / f"{name}.register.stdout", res.stdout)
        write(LOGS / f"{name}.register.stderr", res.stderr)
        row["register_returncode"] = res.returncode
        if res.returncode != 0:
            row["failure_excerpt"] = first_error_excerpt(res.stdout + res.stderr)
            return row

        row["state_after_register"] = wait_for_enabled()
        row["enable_seq_after_register"] = sched_ext_value("enable_seq")
        if row["state_after_register"] != "enabled":
            row["failure_excerpt"] = (
                "scheduler did not reach enabled state after registration"
            )
            return row

        after = list_struct_ops()
        new_entries = [
            entry
            for entry in after
            if struct_ops_id(entry) is not None and struct_ops_id(entry) not in before_ids
        ]
        row["new_struct_ops_maps"] = new_entries

        workload = run_workload()
        row["workload_returncode"] = workload.returncode
        write(LOGS / f"{name}.workload.stdout", workload.stdout)
        write(LOGS / f"{name}.workload.stderr", workload.stderr)
        if workload.returncode != 0:
            row["failure_excerpt"] = (workload.stderr or workload.stdout).strip()[:500]
            return row

        row["state_after_workload"] = sched_ext_value("state")
        if row["state_after_workload"] != "enabled":
            row["failure_excerpt"] = "scheduler left enabled state during workload"
            return row

        row["nr_rejected_after"] = sched_ext_value("nr_rejected")
        row["status"] = "ok"
        return row
    except subprocess.TimeoutExpired as exc:
        row["failure_excerpt"] = f"workload timed out after {exc.timeout}s"
        return row
    finally:
        attempts = unregister_new_maps(new_entries, expected_map_names)
        row["unregister_attempts"] = attempts
        row["unregister_returncode"] = (
            ",".join(attempt["returncode"] for attempt in attempts) if attempts else ""
        )
        cleanup_pin_dir(link_dir)
        if sched_ext_value("state") != "disabled":
            retry_attempts = unregister_new_maps(new_entries, expected_map_names)
            row["unregister_attempts"].extend(retry_attempts)
            row["unregister_returncode"] = (
                ",".join(
                    attempt["returncode"] for attempt in row["unregister_attempts"]
                )
                if row["unregister_attempts"]
                else ""
            )
        row["state_after_unregister"] = wait_for_state_change(row["state_after_register"] or row["state_before"])
        row["enable_seq_after_unregister"] = sched_ext_value("enable_seq")
        if not row["nr_rejected_after"]:
            row["nr_rejected_after"] = sched_ext_value("nr_rejected")
        if row["status"] == "ok" and row["state_after_unregister"] != "disabled":
            row["status"] = "failed"
            row["failure_excerpt"] = (
                "scheduler did not return to disabled state after cleanup"
            )


def write_summary(rows: list[dict[str, Any]], overall_status: str) -> None:
    summary = {
        "experiment": "sched_ext_attach",
        "status": overall_status,
        "overall_status": overall_status,
        "host_kernel": os.uname().release,
        "allow_env": ALLOW_ENV,
        "workload_seconds": WORKLOAD_SECONDS,
        "workload_max_workers": WORKLOAD_MAX_WORKERS,
        "rows": rows,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n")

    fieldnames = [
        "name",
        "implementation",
        "status",
        "attach_attempted",
        "register_returncode",
        "unregister_returncode",
        "workload_returncode",
        "state_before",
        "state_after_register",
        "state_after_workload",
        "state_after_unregister",
        "enable_seq_before",
        "enable_seq_after_register",
        "enable_seq_after_unregister",
        "nr_rejected_before",
        "nr_rejected_after",
        "failure_excerpt",
        "object",
        "link_dir",
    ]
    with SUMMARY_CSV.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-host-scheduler",
        action="store_true",
        help="permit temporary sched_ext registration on this host",
    )
    parser.add_argument(
        "--variant",
        action="append",
        choices=["c_libbpf", "ks_generated"],
        help="variant to run; may be supplied more than once",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mkdirs()
    allowed = args.allow_host_scheduler or os.environ.get(ALLOW_ENV) == "1"
    variants = args.variant or ["c_libbpf", "ks_generated"]
    if not allowed:
        rows = [
            {
                "name": variant,
                "implementation": "C/libbpf" if variant == "c_libbpf" else "KernelScript",
                "status": "skipped",
                "attach_attempted": False,
                "failure_excerpt": (
                    f"set {ALLOW_ENV}=1 or pass --allow-host-scheduler to run"
                ),
            }
            for variant in variants
        ]
        write_summary(rows, "skipped")
        return 0

    reason = check_prerequisites()
    if reason:
        rows = [
            {
                "name": variant,
                "implementation": "C/libbpf" if variant == "c_libbpf" else "KernelScript",
                "status": "skipped",
                "attach_attempted": False,
                "failure_excerpt": reason,
            }
            for variant in variants
        ]
        write_summary(rows, "skipped")
        return 0

    ready, reason = ensure_no_active_scheduler()
    if not ready:
        rows = [
            {
                "name": variant,
                "implementation": "C/libbpf" if variant == "c_libbpf" else "KernelScript",
                "status": "skipped",
                "attach_attempted": False,
                "failure_excerpt": reason,
            }
            for variant in variants
        ]
        write_summary(rows, "skipped")
        return 0

    objects: dict[str, tuple[str, Path, list[str]]] = {}
    if "c_libbpf" in variants:
        objects["c_libbpf"] = ("C/libbpf", compile_c_attach(), ["ks_paper_scx"])
    if "ks_generated" in variants:
        objects["ks_generated"] = (
            "KernelScript",
            compile_ks_attach(),
            ["simple_fifo_scheduler", "simple_fifo_sch", "ks_attach_fifo"],
        )

    rows: list[dict[str, Any]] = []
    for variant in variants:
        implementation, obj, expected_map_names = objects[variant]
        rows.append(run_variant(variant, implementation, obj, expected_map_names))

    overall = "ok" if rows and all(row.get("status") == "ok" for row in rows) else "failed"
    write_summary(rows, overall)
    return 0 if overall == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
