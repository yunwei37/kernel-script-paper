#!/usr/bin/env python3
"""Check a version-aware struct_ops skeleton repair for local libbpf headers."""

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
BUILD = RESULTS / "build" / "struct_ops_skeleton_repair"
LOGS = RESULTS / "logs" / "struct_ops_skeleton_repair"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"

EXAMPLES = [
    ("struct_ops_simple", REPO / "examples" / "struct_ops_simple.ks"),
    ("sched_ext_simple", REPO / "examples" / "sched_ext_simple.ks"),
]


def run(argv: list[str], cwd: Path = ROOT, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PWD"] = str(cwd)
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


def check_prerequisites() -> str | None:
    for cmd in ["bpftool", "clang", "gcc", "make"]:
        if not shutil.which(cmd):
            return f"{cmd} unavailable"
    if not Path("/sys/kernel/btf/vmlinux").exists():
        return "missing /sys/kernel/btf/vmlinux"
    if not COMPILER.exists():
        return f"missing KernelScript compiler at {COMPILER}"
    for _, source in EXAMPLES:
        if not source.exists():
            return f"missing example source: {source}"
    return None


def skeleton_link_field_supported() -> bool:
    header = Path("/usr/include/bpf/libbpf.h")
    text = header.read_text(encoding="utf-8", errors="ignore") if header.exists() else ""
    match = re.search(r"struct bpf_map_skeleton\s*\{(?P<body>.*?)\};", text, re.DOTALL)
    return bool(match and re.search(r"\blink\s*;", match.group("body")))


def libbpf_version() -> str:
    res = run(["pkg-config", "--modversion", "libbpf"]) if shutil.which("pkg-config") else None
    return res.stdout.strip() if res and res.returncode == 0 else "unavailable"


def classify_build(stderr: str) -> str:
    if (
        "struct bpf_map_skeleton" in stderr
        and "no member named" in stderr
        and "link" in stderr
    ):
        return "map_link_field_missing"
    if "error:" in stderr.lower():
        return "other_compile_error"
    return "success"


def repair_skeleton(path: Path, apply_repair: bool) -> tuple[int, str]:
    if not path.exists():
        return 0, "missing_skeleton"
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"^\s*map->link\s*=\s*&obj->links\.[A-Za-z0-9_]+;\n", re.MULTILINE)
    matches = pattern.findall(text)
    if not apply_repair:
        return len(matches), "not_needed"
    repaired = pattern.sub("", text)
    path.write_text(repaired, encoding="utf-8")
    return len(matches), "removed_map_link_assignments"


def compile_and_repair(name: str, source: Path, link_field_supported: bool) -> dict[str, object]:
    out = BUILD / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    compile_res = run([str(COMPILER), "compile", str(source), "-o", str(out)])
    write(LOGS / f"{name}.compile.stdout", compile_res.stdout)
    write(LOGS / f"{name}.compile.stderr", compile_res.stderr)
    compile_ok = compile_res.returncode == 0

    baseline_make = run(["make"], out) if compile_ok else subprocess.CompletedProcess(["make"], 1, "", "")
    write(LOGS / f"{name}.baseline_make.stdout", baseline_make.stdout)
    write(LOGS / f"{name}.baseline_make.stderr", baseline_make.stderr)
    baseline_ok = baseline_make.returncode == 0
    failure_class = classify_build(baseline_make.stderr)

    skeleton = out / f"{name}.skel.h"
    repair_needed = (not baseline_ok) and (not link_field_supported) and failure_class == "map_link_field_missing"
    removed, repair_action = repair_skeleton(skeleton, repair_needed)

    repaired_make = run(["make"], out) if compile_ok else subprocess.CompletedProcess(["make"], 1, "", "")
    write(LOGS / f"{name}.repaired_make.stdout", repaired_make.stdout)
    write(LOGS / f"{name}.repaired_make.stderr", repaired_make.stderr)
    repaired_ok = repaired_make.returncode == 0

    binary = out / name
    repair_or_baseline_ok = baseline_ok or (repair_needed and removed > 0)
    return {
        "name": name,
        "source": str(source.relative_to(REPO)),
        "compile_ok": compile_ok,
        "baseline_build_ok": baseline_ok,
        "baseline_failure_class": failure_class,
        "skeleton": str(skeleton.relative_to(ROOT)) if skeleton.exists() else "",
        "repair_needed": repair_needed,
        "repair_action": repair_action,
        "removed_map_link_assignments": removed,
        "repaired_build_ok": repaired_ok,
        "binary": str(binary.relative_to(ROOT)) if binary.exists() else "",
        "oracle_passed": compile_ok and repaired_ok and repair_or_baseline_ok,
    }


def main() -> int:
    reason = check_prerequisites()
    if reason:
        summary = {"status": "skipped", "reason": reason}
        write(RESULTS / "struct_ops_skeleton_repair_summary.json", json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0

    if BUILD.exists():
        shutil.rmtree(BUILD)
    if LOGS.exists():
        shutil.rmtree(LOGS)
    BUILD.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    link_field_supported = skeleton_link_field_supported()
    rows = [compile_and_repair(name, source, link_field_supported) for name, source in EXAMPLES]
    status = "ok" if all(bool(row["oracle_passed"]) for row in rows) else "failed"
    summary = {
        "status": status,
        "description": "version-aware struct_ops skeleton map-link repair for generated userspace builds",
        "libbpf_version": libbpf_version(),
        "skeleton_map_link_field_supported": link_field_supported,
        "examples": len(rows),
        "baseline_build_ok": sum(1 for row in rows if bool(row["baseline_build_ok"])),
        "baseline_map_link_failures": sum(
            1 for row in rows if row["baseline_failure_class"] == "map_link_field_missing"
        ),
        "repair_needed": sum(1 for row in rows if bool(row["repair_needed"])),
        "repaired_build_ok": sum(1 for row in rows if bool(row["repaired_build_ok"])),
        "removed_map_link_assignments": sum(int(row["removed_map_link_assignments"]) for row in rows),
        "rows": rows,
    }

    fields = [
        "name",
        "source",
        "compile_ok",
        "baseline_build_ok",
        "baseline_failure_class",
        "skeleton",
        "repair_needed",
        "repair_action",
        "removed_map_link_assignments",
        "repaired_build_ok",
        "binary",
        "oracle_passed",
    ]
    with (RESULTS / "struct_ops_skeleton_repair_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fields})

    write(RESULTS / "struct_ops_skeleton_repair_summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: summary[key] for key in summary if key != "rows"}, indent=2, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
