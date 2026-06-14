#!/usr/bin/env python3
"""Scan a pinned external eBPF source corpus for feature overlap.

The scan is intentionally source-only. It does not claim that KernelScript can
translate, build, or run these external applications. It records whether public
eBPF application/example sources exercise feature families that the paper's
local artifact also studies.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
BUILD = RESULTS / "build" / "external_corpus"
SUMMARY_JSON = RESULTS / "external_corpus_summary.json"
SUMMARY_CSV = RESULTS / "external_corpus_summary.csv"
AUDIT_CSV = RESULTS / "external_corpus_audit.csv"


@dataclass(frozen=True)
class RepoSpec:
    name: str
    url: str
    commit: str
    include_globs: tuple[str, ...]
    exclude_parts: tuple[str, ...] = ()


REPOS = [
    RepoSpec(
        name="libbpf-bootstrap",
        url="https://github.com/libbpf/libbpf-bootstrap.git",
        commit="fac4e8ddf011aead8e14962bf8db74542331264b",
        include_globs=("examples/c/*.c", "examples/c/*.h"),
    ),
    RepoSpec(
        name="xdp-tutorial",
        url="https://github.com/xdp-project/xdp-tutorial.git",
        commit="4e2bf5658434e8ae12f281b9b182bb188766a319",
        include_globs=(
            "advanced03-AF_XDP/*.c",
            "basic*/*.c",
            "common/*.c",
            "common/*.h",
            "experiment01-tailgrow/*.c",
            "experiment01-tailgrow/*.h",
            "packet*/*.c",
            "tracing*/*.c",
        ),
    ),
    RepoSpec(
        name="scx",
        url="https://github.com/sched-ext/scx.git",
        commit="0f3df692e2bd733b0ea54add470ba4288b9bd3b2",
        include_globs=(
            "scheds/experimental/*/src/bpf/**/*.c",
            "scheds/experimental/*/src/bpf/**/*.h",
            "scheds/rust/*/src/bpf/**/*.c",
            "scheds/rust/*/src/bpf/**/*.h",
            "tools/*/src/bpf/**/*.c",
            "tools/*/src/bpf/**/*.h",
        ),
        exclude_parts=("vmlinux", "target", "build"),
    ),
]

FEATURES = [
    "xdp",
    "tc",
    "tracepoint",
    "kprobe",
    "uprobe",
    "perf_event",
    "lsm",
    "iterator",
    "socket",
    "maps",
    "ringbuf",
    "tail_call",
    "struct_ops",
    "sched_ext",
    "kfunc",
]


AUDIT_SAMPLES = [
    {
        "repo": "libbpf-bootstrap",
        "path": "examples/c/bootstrap.bpf.c",
        "expected_features": ("maps", "ringbuf", "tracepoint"),
        "rationale": "tracepoint example with map and ring-buffer use",
    },
    {
        "repo": "libbpf-bootstrap",
        "path": "examples/c/fentry.bpf.c",
        "expected_features": (),
        "rationale": "negative control for untracked fentry/fexit sections",
    },
    {
        "repo": "libbpf-bootstrap",
        "path": "examples/c/tc.bpf.c",
        "expected_features": ("tc",),
        "rationale": "traffic-control section example",
    },
    {
        "repo": "xdp-tutorial",
        "path": "basic03-map-counter/xdp_prog_kern.c",
        "expected_features": ("maps", "xdp"),
        "rationale": "XDP map-counter tutorial example",
    },
    {
        "repo": "xdp-tutorial",
        "path": "tracing02-xdp-monitor/trace_prog_kern.c",
        "expected_features": ("maps", "tracepoint", "xdp"),
        "rationale": "XDP tracepoint monitor example",
    },
    {
        "repo": "scx",
        "path": "scheds/rust/scx_cake/src/bpf/cake.bpf.c",
        "expected_features": ("iterator", "kfunc", "maps", "ringbuf", "sched_ext", "struct_ops"),
        "rationale": "scheduler-extension example with maps, ringbuf, iterator, and kfunc use",
    },
    {
        "repo": "scx",
        "path": "tools/scxtop/src/bpf/main.bpf.c",
        "expected_features": ("iterator", "kfunc", "kprobe", "maps", "perf_event", "ringbuf", "sched_ext", "uprobe"),
        "rationale": "observability tool with mixed probe, perf-event, ringbuf, and scheduler markers",
    },
]


def run(argv: list[str], cwd: Path = ROOT, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def check(cmd: subprocess.CompletedProcess[str], label: str) -> None:
    if cmd.returncode != 0:
        raise SystemExit(f"{label} failed\nstdout:\n{cmd.stdout}\nstderr:\n{cmd.stderr}")


def prepare_repo(spec: RepoSpec) -> Path:
    repo_dir = BUILD / spec.name
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    repo_dir.mkdir(parents=True, exist_ok=True)
    check(run(["git", "init", "-q"], repo_dir), f"git init {spec.name}")
    check(run(["git", "remote", "add", "origin", spec.url], repo_dir), f"git remote {spec.name}")
    check(
        run(["git", "fetch", "--depth", "1", "origin", spec.commit], repo_dir, timeout=240),
        f"git fetch {spec.name} {spec.commit}",
    )
    check(run(["git", "checkout", "-q", "FETCH_HEAD"], repo_dir), f"git checkout {spec.name}")
    return repo_dir


def candidate_files(repo_dir: Path, spec: RepoSpec) -> list[Path]:
    files: set[Path] = set()
    for pattern in spec.include_globs:
        for path in repo_dir.glob(pattern):
            if path.is_file() and path.suffix in {".c", ".h"}:
                rel = path.relative_to(repo_dir).as_posix()
                if any(part in rel.split("/") for part in spec.exclude_parts):
                    continue
                files.add(path)
    return sorted(files)


def nonblank_noncomment_sloc(path: Path) -> int:
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


def section_names(text: str) -> list[str]:
    return sorted(set(re.findall(r'SEC\s*\(\s*"([^"]+)"\s*\)', text)))


def file_role(path: Path, text: str) -> str:
    rel = path.as_posix()
    if path.suffix == ".h":
        return "header"
    if ".bpf.c" in path.name or "/bpf/" in rel or "_kern.c" in path.name or section_names(text):
        return "kernel"
    return "userspace"


def detect_features(path: Path, text: str, sections: list[str]) -> dict[str, bool]:
    rel = path.as_posix().lower()
    low = text.lower()
    sec_join = " ".join(sections).lower()
    return {
        "xdp": "xdp" in sec_join or "xdp_" in low or "/xdp" in rel or "xdp_" in rel,
        "tc": "tc/" in sec_join or "classifier" in sec_join or "__sk_buff" in low or "/tc" in rel or "tc_" in rel,
        "tracepoint": "tracepoint" in sec_join or "raw_tracepoint" in sec_join or "tp/" in sec_join or "trace_" in rel,
        "kprobe": "kprobe" in sec_join or "kretprobe" in sec_join or "ksyscall" in sec_join,
        "uprobe": "uprobe" in sec_join or "uretprobe" in sec_join or "usdt" in sec_join,
        "perf_event": "perf_event" in sec_join or "profile" in sec_join or "bpf_perf_event" in low,
        "lsm": "lsm" in sec_join,
        "iterator": "iter/" in sec_join or "bpf_iter" in low,
        "socket": (
            "socket" in sec_join
            or "sock" in sec_join
            or "sk_skb" in sec_join
            or "sock_ops" in sec_join
            or "cgroup_skb" in sec_join
        ),
        "maps": 'sec(".maps")' in low or "bpf_map_type" in low or "__uint(type" in low or "bpf_map" in low,
        "ringbuf": "ringbuf" in low or "ring_buffer" in low or "bpf_ringbuf" in low,
        "tail_call": "bpf_tail_call" in low or "bpf_map_type_prog_array" in low,
        "struct_ops": "struct_ops" in sec_join or "struct_ops" in low or "sched_ext_ops" in low,
        "sched_ext": "sched_ext_ops" in low or "scx_bpf_" in low or "/scx_" in rel,
        "kfunc": "bpf_kfunc" in low or "scx_bpf_" in low or "bpf_obj_new" in low or "bpf_obj_drop" in low,
    }


def short_commit(commit: str) -> str:
    return commit[:12]


def repo_rows(spec: RepoSpec, repo_dir: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in candidate_files(repo_dir, spec):
        rel = path.relative_to(repo_dir).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        sections = section_names(text)
        features = detect_features(Path(rel), text, sections)
        row: dict[str, object] = {
            "repo": spec.name,
            "repo_commit": short_commit(spec.commit),
            "path": rel,
            "role": file_role(Path(rel), text),
            "sloc": nonblank_noncomment_sloc(path),
            "sections": " ".join(sections),
        }
        row.update({f"feature_{name}": features[name] for name in FEATURES})
        rows.append(row)
    return rows


def count_rows(rows: Iterable[dict[str, object]], predicate) -> int:
    return sum(1 for row in rows if predicate(row))


def classifier_audit(rows: list[dict[str, object]]) -> dict[str, object]:
    by_key = {(str(row["repo"]), str(row["path"])): row for row in rows}
    samples = []
    total_false_positives = 0
    total_false_negatives = 0
    for sample in AUDIT_SAMPLES:
        key = (str(sample["repo"]), str(sample["path"]))
        row = by_key.get(key)
        if row is None:
            raise SystemExit(f"classifier audit sample missing from scanned corpus: {key}")
        expected = sorted(str(feature) for feature in sample["expected_features"])
        detected = sorted(feature for feature in FEATURES if bool(row[f"feature_{feature}"]))
        false_positives = sorted(set(detected) - set(expected))
        false_negatives = sorted(set(expected) - set(detected))
        total_false_positives += len(false_positives)
        total_false_negatives += len(false_negatives)
        samples.append(
            {
                "repo": sample["repo"],
                "path": sample["path"],
                "rationale": sample["rationale"],
                "expected_features": expected,
                "detected_features": detected,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "matched": not false_positives and not false_negatives,
            }
        )
    matched_samples = count_rows(samples, lambda row: bool(row["matched"]))
    return {
        "status": "ok" if matched_samples == len(samples) else "mismatch",
        "interpretation": "small manual spot-check of the lexical feature classifier, not a statistical precision/recall estimate",
        "sample_count": len(samples),
        "matched_samples": matched_samples,
        "false_positive_count": total_false_positives,
        "false_negative_count": total_false_negatives,
        "samples": samples,
    }


def main() -> int:
    if not shutil.which("git"):
        raise SystemExit("git unavailable")
    RESULTS.mkdir(parents=True, exist_ok=True)
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, object]] = []
    repos_summary: list[dict[str, object]] = []
    for spec in REPOS:
        repo_dir = prepare_repo(spec)
        rows = repo_rows(spec, repo_dir)
        all_rows.extend(rows)
        repos_summary.append(
            {
                "name": spec.name,
                "url": spec.url,
                "commit": spec.commit,
                "commit_short": short_commit(spec.commit),
                "files": len(rows),
                "sloc": sum(int(row["sloc"]) for row in rows),
                "kernel_files": count_rows(rows, lambda row: row["role"] == "kernel"),
                "userspace_files": count_rows(rows, lambda row: row["role"] == "userspace"),
                "header_files": count_rows(rows, lambda row: row["role"] == "header"),
            }
        )

    feature_file_counts = {
        name: count_rows(all_rows, lambda row, feature=name: bool(row[f"feature_{feature}"]))
        for name in FEATURES
    }
    feature_repo_counts = {
        name: sum(
            1
            for spec in REPOS
            if any(row["repo"] == spec.name and bool(row[f"feature_{name}"]) for row in all_rows)
        )
        for name in FEATURES
    }
    roles = {
        role: count_rows(all_rows, lambda row, wanted=role: row["role"] == wanted)
        for role in ["kernel", "userspace", "header"]
    }
    sloc_by_role = {
        role: sum(int(row["sloc"]) for row in all_rows if row["role"] == role)
        for role in ["kernel", "userspace", "header"]
    }
    sections = sorted(
        {
            section
            for row in all_rows
            for section in str(row["sections"]).split()
            if section
        }
    )
    audit = classifier_audit(all_rows)
    summary = {
        "status": "ok",
        "description": "Pinned source-only scan of external eBPF application/example repositories.",
        "scope": {
            "included": "application/example BPF C, userspace C, and local headers from selected public repositories",
            "excluded": "vendored vmlinux headers, generated files, build outputs, Rust userspace, and repository-wide support libraries outside the selected application/example paths",
            "interpretation": "external source-corpus feature context, not translation, build, verifier, attach, or runtime evidence",
        },
        "repos": repos_summary,
        "repo_count": len(REPOS),
        "file_count": len(all_rows),
        "total_sloc": sum(int(row["sloc"]) for row in all_rows),
        "roles": roles,
        "sloc_by_role": sloc_by_role,
        "feature_file_counts": feature_file_counts,
        "feature_repo_counts": feature_repo_counts,
        "feature_count": sum(1 for value in feature_file_counts.values() if value > 0),
        "section_count": len(sections),
        "section_samples": sections[:40],
        "classifier_audit": audit,
        "rows": all_rows,
    }

    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    fields = [
        "repo",
        "repo_commit",
        "path",
        "role",
        "sloc",
        "sections",
        *[f"feature_{name}" for name in FEATURES],
    ]
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in all_rows:
            writer.writerow({key: row[key] for key in fields})

    audit_fields = [
        "repo",
        "path",
        "rationale",
        "expected_features",
        "detected_features",
        "false_positives",
        "false_negatives",
        "matched",
    ]
    with AUDIT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=audit_fields, lineterminator="\n")
        writer.writeheader()
        for row in audit["samples"]:
            writer.writerow(
                {
                    key: " ".join(row[key]) if isinstance(row[key], list) else row[key]
                    for key in audit_fields
                }
            )

    printable = {key: summary[key] for key in summary if key != "rows"}
    print(json.dumps(printable, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
