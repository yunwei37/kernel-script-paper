#!/usr/bin/env python3
"""Run the KernelScript paper evaluation.

The harness is intentionally conservative: it measures what the current
KernelScript repository can reproduce locally without requiring privileged
attachment to live network interfaces or custom traffic generation.
"""

from __future__ import annotations

import csv
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("KERNELSCRIPT_REPO", ROOT / "kernelscript")).resolve()
RESULTS = Path(os.environ.get("KERNELSCRIPT_RESULTS", ROOT / "results")).resolve()
BUILD_ROOT = RESULTS / "build"
LOG_ROOT = RESULTS / "logs"
EXAMPLES_BUILD = BUILD_ROOT / "examples"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"


@dataclass
class CommandResult:
    argv: list[str]
    cwd: str
    returncode: int
    elapsed_sec: float
    stdout: str
    stderr: str


@dataclass
class ExampleResult:
    name: str
    source: str
    ks_status: str
    make_status: str
    classification: str
    ks_time_sec: float
    make_time_sec: float
    ks_sloc: int
    generated_sloc: int
    userspace_c_sloc: int
    ebpf_c_sloc: int
    module_c_sloc: int
    makefile_sloc: int
    ebpf_object_bytes: int
    ebpf_instruction_count: int
    generated_to_ks_ratio: float
    feature_xdp: bool
    feature_tc: bool
    feature_probe: bool
    feature_tracepoint: bool
    feature_perf_event: bool
    feature_kfunc: bool
    feature_struct_ops: bool
    feature_ringbuf: bool
    feature_tail_call: bool
    feature_dynptr: bool
    feature_maps: bool
    feature_userspace: bool
    failure_excerpt: str


def run(argv: list[str], cwd: Path, timeout: int | None = None) -> CommandResult:
    start = time.perf_counter()
    env = os.environ.copy()
    env["PWD"] = str(cwd)
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    elapsed = time.perf_counter() - start
    return CommandResult(argv, str(cwd), proc.returncode, elapsed, proc.stdout, proc.stderr)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def nonblank_noncomment_sloc(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    in_block = False
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        if in_block:
            if "*/" in line:
                in_block = False
                line = line.split("*/", 1)[1].strip()
            else:
                continue
        while "/*" in line:
            before, after = line.split("/*", 1)
            if "*/" in after:
                after = after.split("*/", 1)[1]
                line = (before + " " + after).strip()
            else:
                in_block = True
                line = before.strip()
                break
        if not line or line.startswith("//") or line.startswith("# "):
            continue
        count += 1
    return count


def command_version(argv: list[str]) -> str:
    exe = shutil.which(argv[0])
    if not exe:
        return "not-found"
    try:
        res = run(argv, ROOT, timeout=10)
        text = (res.stdout + res.stderr).strip().splitlines()
        return text[0] if text else f"exit={res.returncode}"
    except Exception as exc:  # pragma: no cover - diagnostic path
        return f"error: {exc}"


def optional_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return "unavailable"


def lscpu_field(name: str) -> str:
    if not shutil.which("lscpu"):
        return "unavailable"
    try:
        res = run(["lscpu"], ROOT, timeout=10)
        for line in res.stdout.splitlines():
            if line.startswith(name + ":"):
                return line.split(":", 1)[1].strip()
    except Exception as exc:  # pragma: no cover - diagnostic path
        return f"error: {exc}"
    return "unavailable"


def collect_environment() -> dict[str, object]:
    git_head = run(["git", "rev-parse", "HEAD"], REPO)
    git_date = run(["git", "log", "-1", "--date=iso-strict", "--pretty=%ad"], REPO)
    git_subject = run(["git", "log", "-1", "--pretty=%s"], REPO)
    virt = command_version(["systemd-detect-virt"])
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "platform": platform.platform(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "cpu_model": lscpu_field("Model name"),
        "cpu_count": lscpu_field("CPU(s)"),
        "cpu_threads_per_core": lscpu_field("Thread(s) per core"),
        "cpu_governor_cpu0": optional_file("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"),
        "cpu_intel_pstate_no_turbo": optional_file("/sys/devices/system/cpu/intel_pstate/no_turbo"),
        "virtualization": virt,
        "python": sys.version.split()[0],
        "kernelscript_repo": str(REPO),
        "kernelscript_git_head": git_head.stdout.strip(),
        "kernelscript_git_date": git_date.stdout.strip(),
        "kernelscript_git_subject": git_subject.stdout.strip(),
        "clang": command_version(["clang", "--version"]),
        "gcc": command_version(["gcc", "--version"]),
        "bpftool": command_version(["bpftool", "version"]),
        "dune": command_version(["dune", "--version"]),
        "ocamlc": command_version(["ocamlc", "-version"]),
        "libbpf_pkg_config": command_version(["pkg-config", "--modversion", "libbpf"]),
        "btf_vmlinux_exists": Path("/sys/kernel/btf/vmlinux").exists(),
    }


def parse_unit_summary(output: str) -> dict[str, int]:
    tests = [int(x) for x in re.findall(r"Test Successful in [^\n]*?(\d+) tests run", output)]
    return {
        "suites_successful": len(tests),
        "tests_successful": sum(tests),
        "reported_failures": len(re.findall(r"\[(?:FAIL|ERROR)\]", output)),
    }


def objdump_instruction_count(obj: Path) -> int:
    if not obj.exists():
        return 0
    objdump = shutil.which("llvm-objdump") or shutil.which("llvm-objdump-18") or shutil.which("llvm-objdump-19")
    if not objdump:
        return 0
    res = run([objdump, "-d", str(obj)], obj.parent, timeout=20)
    if res.returncode != 0:
        return 0
    count = 0
    for line in res.stdout.splitlines():
        if re.match(r"\s*[0-9a-f]+:\s", line):
            count += 1
    return count


def classify_failure(ks_status: str, make_status: str, log_text: str) -> str:
    if ks_status != "ok":
        if "Stack overflow detected" in log_text:
            return "safety_rejected_stack_limit"
        if "Type checking" in log_text:
            return "ks_compile_rejected"
        return "ks_compile_failed"
    if make_status == "ok":
        return "success"
    if "struct bpf_map_skeleton" in log_text and "no member named" in log_text and "link" in log_text:
        return "libbpf_struct_ops_skeleton_api_mismatch"
    if "No rule to make target" in log_text:
        return "kernel_module_make_path_error"
    return "generated_c_build_failed"


def first_error_excerpt(text: str, max_lines: int = 8) -> str:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        low = line.lower()
        if "error:" in low or "compilation halted" in low or "stack overflow" in low:
            return "\n".join(lines[max(0, idx - 2) : idx + max_lines])
    return "\n".join(lines[:max_lines])


def detect_features(name: str, source: str) -> dict[str, bool]:
    return {
        "feature_xdp": "@xdp" in source,
        "feature_tc": "@tc" in source,
        "feature_probe": "@probe" in source,
        "feature_tracepoint": "@tracepoint" in source,
        "feature_perf_event": "@perf_event" in source,
        "feature_kfunc": "@kfunc" in source or "extern " in source,
        "feature_struct_ops": "@struct_ops" in source or "register(" in source,
        "feature_ringbuf": "ringbuf" in source or "ring_buffer" in source,
        "feature_tail_call": "tail_call" in name or "tail-call" in source or "TAIL CALL" in source,
        "feature_dynptr": "dynptr" in source,
        "feature_maps": re.search(r"\b(hash|array|percpu_array|lru_hash|ringbuf)\s*<", source) is not None,
        "feature_userspace": re.search(r"\bfn\s+main\s*\(", source) is not None,
    }


def evaluate_examples() -> list[ExampleResult]:
    if EXAMPLES_BUILD.exists():
        shutil.rmtree(EXAMPLES_BUILD)
    EXAMPLES_BUILD.mkdir(parents=True, exist_ok=True)
    results: list[ExampleResult] = []

    for source_path in sorted((REPO / "examples").glob("*.ks")):
        name = source_path.stem
        out_dir = EXAMPLES_BUILD / name
        out_dir.mkdir(parents=True, exist_ok=True)

        compile_res = run([str(COMPILER), "compile", str(source_path), "-o", str(out_dir)], REPO, timeout=60)
        write_text(LOG_ROOT / "examples" / f"{name}.ks.stdout", compile_res.stdout)
        write_text(LOG_ROOT / "examples" / f"{name}.ks.stderr", compile_res.stderr)
        ks_status = "ok" if compile_res.returncode == 0 else "failed"

        make_status = "not_run"
        make_time = 0.0
        make_stdout = ""
        make_stderr = ""
        if ks_status == "ok":
            make_res = run(["make"], out_dir, timeout=120)
            make_status = "ok" if make_res.returncode == 0 else "failed"
            make_time = make_res.elapsed_sec
            make_stdout = make_res.stdout
            make_stderr = make_res.stderr
            write_text(LOG_ROOT / "examples" / f"{name}.make.stdout", make_stdout)
            write_text(LOG_ROOT / "examples" / f"{name}.make.stderr", make_stderr)

        source = source_path.read_text(encoding="utf-8", errors="ignore")
        features = detect_features(name, source)
        userspace_c = out_dir / f"{name}.c"
        ebpf_c = out_dir / f"{name}.ebpf.c"
        module_c = out_dir / f"{name}.mod.c"
        makefile = out_dir / "Makefile"
        userspace_sloc = nonblank_noncomment_sloc(userspace_c)
        ebpf_sloc = nonblank_noncomment_sloc(ebpf_c)
        module_sloc = nonblank_noncomment_sloc(module_c)
        makefile_sloc = nonblank_noncomment_sloc(makefile)
        generated_sloc = userspace_sloc + ebpf_sloc + module_sloc + makefile_sloc
        ks_sloc = nonblank_noncomment_sloc(source_path)
        log_text = compile_res.stdout + compile_res.stderr + make_stdout + make_stderr
        classification = classify_failure(ks_status, make_status, log_text)
        ebpf_object = out_dir / f"{name}.ebpf.o"
        result = ExampleResult(
            name=name,
            source=str(source_path.relative_to(REPO)),
            ks_status=ks_status,
            make_status=make_status,
            classification=classification,
            ks_time_sec=round(compile_res.elapsed_sec, 4),
            make_time_sec=round(make_time, 4),
            ks_sloc=ks_sloc,
            generated_sloc=generated_sloc,
            userspace_c_sloc=userspace_sloc,
            ebpf_c_sloc=ebpf_sloc,
            module_c_sloc=module_sloc,
            makefile_sloc=makefile_sloc,
            ebpf_object_bytes=ebpf_object.stat().st_size if ebpf_object.exists() else 0,
            ebpf_instruction_count=objdump_instruction_count(ebpf_object),
            generated_to_ks_ratio=round(generated_sloc / ks_sloc, 2) if ks_sloc else 0.0,
            failure_excerpt=first_error_excerpt(log_text) if classification != "success" else "",
            **features,
        )
        results.append(result)
    return results


def write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def summarize_examples(results: list[ExampleResult]) -> dict[str, object]:
    total = len(results)
    ks_ok = sum(1 for r in results if r.ks_status == "ok")
    make_ok = sum(1 for r in results if r.make_status == "ok")
    successes = [r for r in results if r.classification == "success"]
    generated_ratios = [r.generated_to_ks_ratio for r in successes if r.generated_to_ks_ratio > 0]
    ks_sloc = [r.ks_sloc for r in successes if r.ks_sloc > 0]
    generated_sloc = [r.generated_sloc for r in successes if r.generated_sloc > 0]
    instructions = [r.ebpf_instruction_count for r in successes if r.ebpf_instruction_count > 0]
    features = [
        "feature_xdp",
        "feature_tc",
        "feature_probe",
        "feature_tracepoint",
        "feature_perf_event",
        "feature_kfunc",
        "feature_struct_ops",
        "feature_ringbuf",
        "feature_tail_call",
        "feature_dynptr",
        "feature_maps",
        "feature_userspace",
    ]
    by_class: dict[str, int] = {}
    for r in results:
        by_class[r.classification] = by_class.get(r.classification, 0) + 1
    return {
        "total_examples": total,
        "ks_compile_ok": ks_ok,
        "ks_compile_failed": total - ks_ok,
        "make_ok": make_ok,
        "make_failed_after_ks": sum(1 for r in results if r.ks_status == "ok" and r.make_status != "ok"),
        "median_ks_sloc_success": median(ks_sloc),
        "median_generated_sloc_success": median(generated_sloc),
        "median_generated_to_ks_ratio_success": median(generated_ratios),
        "max_generated_to_ks_ratio_success": max(generated_ratios) if generated_ratios else 0,
        "median_ebpf_instructions_success": median(instructions),
        "feature_counts": {f: sum(1 for r in results if getattr(r, f)) for f in features},
        "classifications": by_class,
    }


def median(values: list[int | float]) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    n = len(values)
    mid = n // 2
    if n % 2:
        return float(values[mid])
    return (float(values[mid - 1]) + float(values[mid])) / 2.0


def main() -> int:
    if not REPO.exists():
        print(f"KernelScript repo not found: {REPO}", file=sys.stderr)
        return 2
    RESULTS.mkdir(parents=True, exist_ok=True)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)

    env = collect_environment()
    write_json(RESULTS / "environment.json", env)

    build = run(["dune", "build"], REPO, timeout=120)
    write_text(LOG_ROOT / "dune_build.stdout", build.stdout)
    write_text(LOG_ROOT / "dune_build.stderr", build.stderr)
    write_json(RESULTS / "dune_build.json", asdict(build))
    if build.returncode != 0:
        print("dune build failed; see results/logs/dune_build.stderr", file=sys.stderr)
        return build.returncode

    tests = run(["dune", "runtest", "--force"], REPO, timeout=120)
    write_text(LOG_ROOT / "dune_runtest.stdout", tests.stdout)
    write_text(LOG_ROOT / "dune_runtest.stderr", tests.stderr)
    write_json(RESULTS / "dune_runtest.json", asdict(tests))
    unit = parse_unit_summary(tests.stdout + tests.stderr)
    unit["returncode"] = tests.returncode
    write_json(RESULTS / "unit_tests_summary.json", unit)
    if tests.returncode != 0:
        print("dune runtest failed; continuing to examples for diagnostic data", file=sys.stderr)

    examples = evaluate_examples()
    rows = [asdict(r) for r in examples]
    write_csv(RESULTS / "examples_summary.csv", rows)
    write_json(RESULTS / "examples_summary.json", rows)
    summary = summarize_examples(examples)
    write_json(RESULTS / "evaluation_summary.json", summary)

    print(json.dumps({"unit_tests": unit, "examples": summary}, indent=2, sort_keys=True))
    return 0 if tests.returncode == 0 else tests.returncode


if __name__ == "__main__":
    raise SystemExit(main())
