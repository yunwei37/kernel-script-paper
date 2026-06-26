#!/usr/bin/env python3
"""Run a small static-check corpus against the KernelScript compiler."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("KERNELSCRIPT_REPO", ROOT / "kernelscript")).resolve()
RESULTS = ROOT / "results"
BUILD = RESULTS / "build" / "static_checks"
LOGS = RESULTS / "logs" / "static_checks"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"
CASES_DIR = ROOT / "experiments" / "static_checks"


@dataclass(frozen=True)
class Case:
    name: str
    category: str
    expect_success: bool
    expected_substrings: tuple[str, ...] = ()
    env: tuple[tuple[str, str], ...] = ()


CASES = [
    Case("valid_pass", "positive_control", True),
    Case(
        "arith_bool",
        "type_system",
        False,
        ("Cannot unify types for arithmetic operation",),
    ),
    Case(
        "attach_without_load",
        "lifecycle_api",
        False,
        ("attach() requires (handle, target, flags)",),
    ),
    Case(
        "attach_integer_handle",
        "lifecycle_api",
        False,
        ("attach() requires (handle, target, flags)",),
    ),
    Case(
        "config_write_ebpf",
        "config_boundary",
        False,
        ("Config field assignments are not allowed in eBPF programs",),
    ),
    Case(
        "detach_string",
        "lifecycle_api",
        False,
        ("detach() requires a ProgramHandle or PerfAttachment",),
    ),
    Case(
        "detach_integer",
        "lifecycle_api",
        False,
        ("detach() requires a ProgramHandle or PerfAttachment",),
    ),
    Case(
        "duplicate_main",
        "symbol_validation",
        False,
        ("Duplicate main function",),
    ),
    Case(
        "fn_wrong_arg_type",
        "type_system",
        False,
        ("Type mismatch in function call: add_one",),
    ),
    Case(
        "gfp_from_userspace",
        "kernel_context",
        False,
        ("GFP allocation flags can only be used in @kfunc functions (kernel context), not in userspace",),
    ),
    Case(
        "gfp_from_xdp",
        "kernel_context",
        False,
        (
            "GFP allocation flags can only be used in @kfunc functions (kernel context), not in eBPF programs",
        ),
    ),
    Case(
        "helper_from_userspace",
        "helper_scope",
        False,
        (
            "Helper function 'kernel_helper' can only be called from eBPF programs or other helper functions",
        ),
    ),
    Case(
        "load_string",
        "lifecycle_api",
        False,
        ("Type mismatch in function call: load",),
    ),
    Case(
        "map_string_key",
        "map_type",
        False,
        ("Map key type mismatch",),
    ),
    Case(
        "map_string_value",
        "map_type",
        False,
        ("Map value type mismatch",),
    ),
    Case(
        "map_undefined",
        "map_type",
        False,
        ("Undefined symbol: missing_map",),
    ),
    Case(
        "perf_wrong_context",
        "program_signature",
        False,
        ("@perf_event attributed function parameter must be ctx: *bpf_perf_event_data",),
    ),
    Case(
        "perf_group_too_large",
        "perf_event_group",
        False,
        (
            "perf event group rooted at 'cache' needs 5 PMU counter slot(s), but target PMU group limit is 4",
        ),
        (("KERNELSCRIPT_PERF_GROUP_MAX_EVENTS", "4"),),
    ),
    Case(
        "perf_group_too_many_members",
        "perf_event_group",
        False,
        (
            "perf event group rooted at 'leader' has 17 member(s), but target perf group limit is 16",
        ),
        (("KERNELSCRIPT_PERF_GROUP_MAX_EVENTS", "16"),),
    ),
    Case(
        "probe_wrong_return",
        "program_signature",
        False,
        ("@fprobe attributed function must return i32",),
    ),
    Case(
        "ringbuf_submit_integer",
        "ringbuf_api",
        False,
        ("Type mismatch: expected pointer to Event",),
    ),
    Case(
        "stack_overflow",
        "safety_analysis",
        False,
        ("Stack overflow detected", "exceeds eBPF limit of 512 bytes"),
    ),
    Case(
        "struct_bad_field",
        "type_system",
        False,
        ("Field not found: missing_field in struct Config",),
    ),
    Case(
        "tc_wrong_context",
        "program_signature",
        False,
        ("@tc attributed function must have signature",),
    ),
    Case(
        "undefined_struct",
        "type_system",
        False,
        ("Undefined struct: MissingStruct",),
    ),
    Case(
        "xdp_main",
        "symbol_validation",
        False,
        ("main function cannot have attributes",),
    ),
    Case(
        "xdp_wrong_context",
        "program_signature",
        False,
        ("@xdp attributed function must have signature",),
    ),
    Case(
        "xdp_wrong_return",
        "program_signature",
        False,
        ("@xdp attributed function must have signature",),
    ),
]


def run(
    argv: list[str],
    cwd: Path,
    timeout: int = 120,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PWD"] = str(cwd)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        argv,
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


def ensure_compiler() -> None:
    if COMPILER.exists():
        return
    build = run(["dune", "build"], REPO, timeout=180)
    write(LOGS / "dune_build.stdout", build.stdout)
    write(LOGS / "dune_build.stderr", build.stderr)
    if build.returncode != 0:
        raise RuntimeError("dune build failed; see results/logs/static_checks/")


def ascii_text(text: str) -> str:
    return text.replace("\u2014", "-").encode("ascii", "ignore").decode("ascii")


def excerpt(text: str, max_lines: int = 8) -> str:
    lines = [line.rstrip() for line in ascii_text(text).splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        low = line.lower()
        if "error:" in low or "type error" in low or "stack overflow" in low:
            return "\n".join(lines[max(0, idx - 2) : idx + max_lines])
    return "\n".join(lines[:max_lines])


def run_case(case: Case) -> dict[str, object]:
    source = CASES_DIR / f"{case.name}.ks"
    out = BUILD / case.name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    res = run(
        [str(COMPILER), "compile", str(source), "-o", str(out)],
        ROOT,
        extra_env=dict(case.env),
    )
    elapsed = time.perf_counter() - start

    text = res.stdout + res.stderr
    write(LOGS / f"{case.name}.stdout", res.stdout)
    write(LOGS / f"{case.name}.stderr", res.stderr)

    observed_success = res.returncode == 0
    substrings_match = all(s in text for s in case.expected_substrings)
    matched = observed_success if case.expect_success else (not observed_success and substrings_match)
    expected = "success" if case.expect_success else "failure"
    observed = "success" if observed_success else "failure"

    return {
        "name": case.name,
        "source": str(source.relative_to(ROOT)),
        "category": case.category,
        "expected": expected,
        "observed": observed,
        "matched": matched,
        "returncode": res.returncode,
        "elapsed_sec": round(elapsed, 4),
        "expected_substrings": " | ".join(case.expected_substrings),
        "diagnostic_excerpt": "" if matched and case.expect_success else excerpt(text),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ensure_compiler()
    LOGS.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)

    rows = [run_case(case) for case in CASES]
    matched = sum(1 for row in rows if row["matched"])
    expected_failures = sum(1 for case in CASES if not case.expect_success)
    expected_successes = sum(1 for case in CASES if case.expect_success)
    category_counts: dict[str, int] = {}
    for row in rows:
        if row["matched"]:
            category = str(row["category"])
            category_counts[category] = category_counts.get(category, 0) + 1

    summary = {
        "status": "ok" if matched == len(rows) else "failed",
        "total_cases": len(rows),
        "matched_cases": matched,
        "expected_failures": expected_failures,
        "expected_successes": expected_successes,
        "matched_by_category": category_counts,
        "rows": rows,
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    write_csv(RESULTS / "static_checks_summary.csv", rows)
    write(RESULTS / "static_checks_summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: summary[k] for k in ["status", "total_cases", "matched_cases"]}, indent=2))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
