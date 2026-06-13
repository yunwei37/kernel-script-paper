#!/usr/bin/env python3
"""Load generated eBPF objects with bpftool to exercise the kernel verifier."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
BUILD = RESULTS / "build" / "examples"
LOGS = RESULTS / "logs" / "verifier_matrix"
SUMMARY_CSV = RESULTS / "examples_summary.csv"
PIN_ROOT = "/sys/fs/bpf/kernelscript-paper/verifier-matrix"


def run(argv: list[str], cwd: Path, timeout: int = 60, sudo: bool = False) -> subprocess.CompletedProcess[str]:
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


def check_prerequisites() -> str | None:
    if run(["true"], ROOT, sudo=True).returncode != 0:
        return "sudo -n unavailable"
    if not SUMMARY_CSV.exists():
        return f"missing {SUMMARY_CSV.relative_to(ROOT)}; run experiments/run_evaluation.py first"
    if not BUILD.exists():
        return f"missing {BUILD.relative_to(ROOT)}; run experiments/run_evaluation.py first"
    if not shutil.which("bpftool"):
        return "bpftool unavailable"
    return None


def load_example_rows() -> list[dict[str, str]]:
    with SUMMARY_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


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


def section_kinds(sections: list[str]) -> list[str]:
    kinds = set()
    for sec in sections:
        if sec == "xdp":
            kinds.add("xdp")
        elif sec.startswith("tc/"):
            kinds.add("tc")
        elif sec.startswith("tracepoint/"):
            kinds.add("tracepoint")
        elif sec.startswith("fentry/"):
            kinds.add("fentry")
        elif sec == "perf_event":
            kinds.add("perf_event")
        elif sec.startswith("struct_ops/"):
            kinds.add("struct_ops")
        else:
            kinds.add(sec.split("/", 1)[0])
    return sorted(kinds)


def first_error_excerpt(text: str, max_lines: int = 12) -> str:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        low = line.lower()
        if "error:" in low or "failed" in low or "unreleased reference" in low or "not found" in low:
            return "\n".join(lines[max(0, idx - 3) : idx + max_lines])
    return "\n".join(lines[:max_lines])


def classify_failure(text: str) -> str:
    low = text.lower()
    if "failed to create" in low and "map" in low:
        return "map_create_failed"
    if "unreleased reference" in low or "reference leak" in low:
        return "verifier_reference_leak"
    if "not found in kernel or module btfs" in low:
        return "missing_kernel_btf_symbol"
    if "arg#0 pointer type struct task_struct" in low:
        return "struct_ops_argument_type"
    if "permission denied" in low:
        return "permission_denied"
    if "failed to load object file" in low or "bpf program load failed" in low:
        return "verifier_rejected"
    return "load_failed"


def load_object(row: dict[str, str], obj: Path, sections: list[str]) -> dict[str, object]:
    name = row["name"]
    pin_base = f"{PIN_ROOT}/{os.getpid()}_{name}"
    prog_pin = f"{pin_base}/progs"
    map_pin = f"{pin_base}/maps"
    run(["rm", "-rf", pin_base], ROOT, sudo=True)
    run(["mkdir", "-p", prog_pin, map_pin], ROOT, sudo=True)
    res = run(["bpftool", "prog", "loadall", str(obj), prog_pin, "pinmaps", map_pin], ROOT, timeout=60, sudo=True)
    write(LOGS / f"{name}.load.stdout", res.stdout)
    write(LOGS / f"{name}.load.stderr", res.stderr)
    run(["rm", "-rf", pin_base], ROOT, sudo=True)
    text = res.stdout + res.stderr
    ok = res.returncode == 0
    return {
        "name": name,
        "source": row["source"],
        "make_status": row["make_status"],
        "classification": row["classification"],
        "object": str(obj.relative_to(ROOT)),
        "program_sections": " ".join(sections),
        "section_kinds": " ".join(section_kinds(sections)),
        "program_count": len(sections),
        "load_status": "ok" if ok else "failed",
        "failure_class": "" if ok else classify_failure(text),
        "failure_excerpt": "" if ok else first_error_excerpt(text),
    }


def main() -> int:
    reason = check_prerequisites()
    if reason:
        summary = {"status": "skipped", "reason": reason}
        write(RESULTS / "verifier_matrix_summary.json", json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0

    if LOGS.exists():
        shutil.rmtree(LOGS)
    LOGS.mkdir(parents=True, exist_ok=True)
    rows = load_example_rows()
    object_rows: list[dict[str, object]] = []
    for row in rows:
        obj = BUILD / row["name"] / f"{row['name']}.ebpf.o"
        if not obj.exists():
            continue
        sections = program_sections(obj)
        if not sections:
            continue
        object_rows.append(load_object(row, obj, sections))

    fields = [
        "name",
        "source",
        "make_status",
        "classification",
        "object",
        "program_sections",
        "section_kinds",
        "program_count",
        "load_status",
        "failure_class",
        "failure_excerpt",
    ]
    with (RESULTS / "verifier_matrix_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in object_rows:
            writer.writerow({k: row[k] for k in fields})

    all_counter = Counter(str(row["load_status"]) for row in object_rows)
    build_rows = [row for row in object_rows if row["make_status"] == "ok"]
    build_counter = Counter(str(row["load_status"]) for row in build_rows)
    failure_counter = Counter(str(row["failure_class"]) for row in object_rows if row["load_status"] != "ok")
    summary = {
        "status": "ok",
        "description": "bpftool prog loadall verifier matrix for generated eBPF objects.",
        "total_objects": len(object_rows),
        "load_ok": all_counter["ok"],
        "load_failed": all_counter["failed"],
        "build_success_objects": len(build_rows),
        "build_success_load_ok": build_counter["ok"],
        "build_success_load_failed": build_counter["failed"],
        "failure_classes": dict(sorted(failure_counter.items())),
        "rows": object_rows,
    }
    write(RESULTS / "verifier_matrix_summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: summary[k] for k in summary if k != "rows"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
