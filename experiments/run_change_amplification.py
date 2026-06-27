#!/usr/bin/env python3
"""Measure change amplification on matched micro-edits.

The experiment compares four small requirements changes across a single-file
KernelScript source and a hand-written C/libbpf split. The checked-in fixtures
are intentionally tiny and human-readable; the metrics are diff-based.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import statistics
import subprocess
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "experiments" / "change_amplification"
RESULTS = ROOT / "results"
BUILD = RESULTS / "build" / "change_amplification"
LOGS = RESULTS / "logs" / "change_amplification"
SUMMARY_JSON = RESULTS / "change_amplification_summary.json"
SUMMARY_CSV = RESULTS / "change_amplification_summary.csv"
COMPILER = ROOT / "kernelscript" / "_build" / "default" / "src" / "main.exe"


@dataclass(frozen=True)
class SyncSurface:
    kernel: bool
    userspace: bool
    skeleton_conventions: bool

    def count(self) -> int:
        return int(self.kernel) + int(self.userspace) + int(self.skeleton_conventions)

    def label(self) -> str:
        labels = []
        if self.kernel:
            labels.append("K")
        if self.userspace:
            labels.append("U")
        if self.skeleton_conventions:
            labels.append("S")
        return "/".join(labels) if labels else "-"


@dataclass(frozen=True)
class Case:
    name: str
    label: str
    note: str
    ks_sync: SyncSurface
    c_sync: SyncSurface


CASES = [
    Case(
        name="map_type_percpu_array",
        label="Map type array -> percpu_array",
        note="Change the counter map from array to percpu_array while keeping the counting logic.",
        ks_sync=SyncSurface(False, False, False),
        c_sync=SyncSurface(True, True, True),
    ),
    Case(
        name="program_xdp_to_tc",
        label="Program type @xdp -> @tc",
        note="Move the same pass-through logic from XDP to TC ingress.",
        ks_sync=SyncSurface(False, False, False),
        c_sync=SyncSurface(True, True, True),
    ),
    Case(
        name="attach_target_symbol",
        label="Attach target symbol change",
        note="Change a kprobe attach target from one nearby kernel symbol to another.",
        ks_sync=SyncSurface(False, False, False),
        c_sync=SyncSurface(True, True, False),
    ),
    Case(
        name="userspace_ringbuf_consumer",
        label="Add ringbuf reporting and userspace handling",
        note="Extend a counter-only XDP program with ringbuf event reporting plus userspace-side event and map handling.",
        ks_sync=SyncSurface(False, False, False),
        c_sync=SyncSurface(True, True, True),
    ),
]


def run(argv: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PWD"] = str(cwd)
    return subprocess.run(
        argv,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git_head(path: Path) -> str:
    res = run(["git", "rev-parse", "HEAD"], path)
    return res.stdout.strip() if res.returncode == 0 else "unavailable"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def check_prerequisites() -> str | None:
    if not COMPILER.exists():
        return f"missing KernelScript compiler at {COMPILER}"
    for cmd in ["bpftool", "clang", "gcc", "pkg-config"]:
        if not shutil.which(cmd):
            return f"{cmd} unavailable"
    if not Path("/sys/kernel/btf/vmlinux").exists():
        return "missing /sys/kernel/btf/vmlinux"
    return None


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="ignore").splitlines()


def file_metrics(before: Path, after: Path) -> tuple[int, int, int]:
    before_exists = before.exists()
    after_exists = after.exists()
    if not before_exists and not after_exists:
        return (0, 0, 0)
    if not before_exists:
        added = len(read_lines(after))
        return (1, added, 0)
    if not after_exists:
        deleted = len(read_lines(before))
        return (1, 0, deleted)

    before_lines = read_lines(before)
    after_lines = read_lines(after)
    matcher = SequenceMatcher(a=before_lines, b=after_lines)
    sites = 0
    added = 0
    deleted = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        sites += 1
        deleted += i2 - i1
        added += j2 - j1
    return (sites, added, deleted)


def dir_metrics(before_dir: Path, after_dir: Path) -> dict[str, int]:
    files = sorted(
        {
            path.relative_to(before_dir)
            for path in before_dir.rglob("*")
            if path.is_file()
        }
        | {
            path.relative_to(after_dir)
            for path in after_dir.rglob("*")
            if path.is_file()
        }
    )
    changed_files = 0
    edit_sites = 0
    added_loc = 0
    deleted_loc = 0
    for rel in files:
        sites, added, deleted = file_metrics(before_dir / rel, after_dir / rel)
        if sites == 0 and added == 0 and deleted == 0:
            continue
        changed_files += 1
        edit_sites += sites
        added_loc += added
        deleted_loc += deleted
    return {
        "changed_files": changed_files,
        "edit_sites": edit_sites,
        "added_loc": added_loc,
        "deleted_loc": deleted_loc,
        "changed_loc": added_loc + deleted_loc,
    }


def median_int(values: list[int]) -> int:
    return int(statistics.median(values)) if values else 0


def compile_ks_source(case: Case, variant: str, source: Path) -> dict[str, object]:
    out = BUILD / case.name / f"ks_{variant}"
    logs = LOGS / case.name / f"ks_{variant}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    res = run([str(COMPILER), "compile", str(source), "-o", str(out)])
    write(logs / "compile.stdout", res.stdout)
    write(logs / "compile.stderr", res.stderr)
    return {
        "case": case.name,
        "implementation": "kernelscript",
        "variant": variant,
        "artifact": source.name,
        "status": "ok" if res.returncode == 0 else "failed",
        "detail": "KernelScript source compile",
    }


def prepare_vmlinux_header(out: Path, logs: Path) -> None:
    btf = run(["bpftool", "btf", "dump", "file", "/sys/kernel/btf/vmlinux", "format", "c"])
    write(logs / "btf.stdout", btf.stdout)
    write(logs / "btf.stderr", btf.stderr)
    if btf.returncode != 0:
        raise RuntimeError("bpftool btf dump failed")
    write(out / "vmlinux.h", btf.stdout)


def compile_c_variant(case: Case, variant: str) -> list[dict[str, object]]:
    src_dir = FIXTURES / case.name / f"c_{variant}"
    out = BUILD / case.name / f"c_{variant}"
    logs = LOGS / case.name / f"c_{variant}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    prepare_vmlinux_header(out, logs)

    rows: list[dict[str, object]] = []
    ebpf_src = src_dir / "app.bpf.c"
    ebpf_obj = out / "app.bpf.o"
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
            str(ebpf_src),
            "-o",
            str(ebpf_obj),
        ]
    )
    write(logs / "clang.stdout", clang.stdout)
    write(logs / "clang.stderr", clang.stderr)
    rows.append(
        {
            "case": case.name,
            "implementation": "c_libbpf",
            "variant": variant,
            "artifact": ebpf_src.name,
            "status": "ok" if clang.returncode == 0 else "failed",
            "detail": "hand-written eBPF clang compile",
        }
    )
    if clang.returncode != 0:
        return rows

    user_src = src_dir / "app_user.c"
    if not user_src.exists():
        return rows

    if '#include "app.skel.h"' in user_src.read_text(encoding="utf-8", errors="ignore"):
        skeleton = run(["bpftool", "gen", "skeleton", str(ebpf_obj)])
        write(logs / "skeleton.stdout", skeleton.stdout)
        write(logs / "skeleton.stderr", skeleton.stderr)
        rows.append(
            {
                "case": case.name,
                "implementation": "c_libbpf",
                "variant": variant,
                "artifact": "app.skel.h",
                "status": "ok" if skeleton.returncode == 0 else "failed",
                "detail": "bpftool skeleton generation",
            }
        )
        if skeleton.returncode != 0:
            return rows
        write(out / "app.skel.h", skeleton.stdout)

    pkg = run(["pkg-config", "--libs", "libbpf"])
    write(logs / "pkgconfig.stdout", pkg.stdout)
    write(logs / "pkgconfig.stderr", pkg.stderr)
    if pkg.returncode != 0:
        rows.append(
            {
                "case": case.name,
                "implementation": "c_libbpf",
                "variant": variant,
                "artifact": user_src.name,
                "status": "failed",
                "detail": "pkg-config libbpf unavailable",
            }
        )
        return rows
    libs = pkg.stdout.strip().split() or ["-lbpf", "-lelf", "-lz"]

    gcc = run(
        [
            "gcc",
            "-O2",
            "-Wall",
            "-Wextra",
            "-I",
            str(out),
            "-o",
            str(out / "app_user"),
            str(user_src),
            *libs,
            "-lelf",
            "-lz",
        ]
    )
    write(logs / "gcc.stdout", gcc.stdout)
    write(logs / "gcc.stderr", gcc.stderr)
    rows.append(
        {
            "case": case.name,
            "implementation": "c_libbpf",
            "variant": variant,
            "artifact": user_src.name,
            "status": "ok" if gcc.returncode == 0 else "failed",
            "detail": "hand-written userspace gcc compile",
        }
    )
    return rows


def validate_case_compilation(case: Case) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for variant in ("before", "after"):
        ks_source = FIXTURES / case.name / f"ks_{variant}" / "app.ks"
        rows.append(compile_ks_source(case, variant, ks_source))
        rows.extend(compile_c_variant(case, variant))
    return rows


def summarize_case(case: Case) -> list[dict[str, object]]:
    base = FIXTURES / case.name
    ks = dir_metrics(base / "ks_before", base / "ks_after")
    c = dir_metrics(base / "c_before", base / "c_after")
    return [
        {
            "case": case.name,
            "label": case.label,
            "implementation": "kernelscript",
            **ks,
            "sync_kernel": case.ks_sync.kernel,
            "sync_userspace": case.ks_sync.userspace,
            "sync_skeleton_conventions": case.ks_sync.skeleton_conventions,
            "sync_surface_count": case.ks_sync.count(),
            "sync_surface_label": case.ks_sync.label(),
            "note": case.note,
        },
        {
            "case": case.name,
            "label": case.label,
            "implementation": "c_libbpf",
            **c,
            "sync_kernel": case.c_sync.kernel,
            "sync_userspace": case.c_sync.userspace,
            "sync_skeleton_conventions": case.c_sync.skeleton_conventions,
            "sync_surface_count": case.c_sync.count(),
            "sync_surface_label": case.c_sync.label(),
            "note": case.note,
        },
    ]


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    reason = check_prerequisites()
    if reason is not None:
        summary = {"status": "skipped", "reason": reason}
        SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    validation_rows: list[dict[str, object]] = []
    for case in CASES:
        validation_rows.extend(validate_case_compilation(case))
    failed_validations = [row for row in validation_rows if row["status"] != "ok"]
    if failed_validations:
        summary = {
            "status": "compile_failed",
            "reason": "one or more before/after fixtures failed to compile",
            "validation": {
                "policy": "compile all KernelScript and handwritten C/libbpf before/after fixtures before diff measurement",
                "rows": validation_rows,
            },
        }
        SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 1

    rows: list[dict[str, object]] = []
    for case in CASES:
        rows.extend(summarize_case(case))

    ks_rows = [row for row in rows if row["implementation"] == "kernelscript"]
    c_rows = [row for row in rows if row["implementation"] == "c_libbpf"]
    summary = {
        "status": "ok",
        "description": (
            "Diff-based change-amplification comparison for four matched "
            "cross-boundary micro-edits."
        ),
        "policy": {
            "metrics": [
                "changed_files",
                "edit_sites",
                "changed_loc",
                "manual sync surfaces",
            ],
            "edit_site_definition": "contiguous non-equal diff hunk within one source file",
            "changed_loc_definition": "added plus deleted source lines",
            "sync_surface_legend": {
                "K": "kernel artifact requires manual synchronized edits",
                "U": "userspace artifact requires manual synchronized edits",
                "S": "skeleton/section-name conventions require manual synchronized edits",
            },
        },
        "validation": {
            "policy": "compile all KernelScript and handwritten C/libbpf before/after fixtures before diff measurement",
            "rows": validation_rows,
        },
        "kernelscript_repo_head": git_head(ROOT / "kernelscript"),
        "case_count": len(CASES),
        "rows": rows,
        "aggregate": {
            "kernelscript": {
                "median_changed_files": median_int([int(row["changed_files"]) for row in ks_rows]),
                "median_edit_sites": median_int([int(row["edit_sites"]) for row in ks_rows]),
                "median_changed_loc": median_int([int(row["changed_loc"]) for row in ks_rows]),
                "kernel_sync_cases": sum(1 for row in ks_rows if bool(row["sync_kernel"])),
                "userspace_sync_cases": sum(1 for row in ks_rows if bool(row["sync_userspace"])),
                "skeleton_sync_cases": sum(1 for row in ks_rows if bool(row["sync_skeleton_conventions"])),
            },
            "c_libbpf": {
                "median_changed_files": median_int([int(row["changed_files"]) for row in c_rows]),
                "median_edit_sites": median_int([int(row["edit_sites"]) for row in c_rows]),
                "median_changed_loc": median_int([int(row["changed_loc"]) for row in c_rows]),
                "kernel_sync_cases": sum(1 for row in c_rows if bool(row["sync_kernel"])),
                "userspace_sync_cases": sum(1 for row in c_rows if bool(row["sync_userspace"])),
                "skeleton_sync_cases": sum(1 for row in c_rows if bool(row["sync_skeleton_conventions"])),
            },
        },
    }

    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    fields = [
        "case",
        "label",
        "implementation",
        "changed_files",
        "edit_sites",
        "added_loc",
        "deleted_loc",
        "changed_loc",
        "sync_kernel",
        "sync_userspace",
        "sync_skeleton_conventions",
        "sync_surface_count",
        "sync_surface_label",
        "note",
    ]
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})

    print(json.dumps(summary["aggregate"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
