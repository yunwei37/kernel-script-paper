#!/usr/bin/env python3
"""Compare KernelScript source footprint with matched C/libbpf baselines.

This is a conservative maintenance-surface proxy, not a developer-time study.
It counts only repository-maintained source files used by the local matched
experiments. Generated vmlinux headers, bpftool skeletons, generated C, and
KernelScript library headers are intentionally excluded.
"""

from __future__ import annotations

import csv
import json
import statistics
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SUMMARY_JSON = RESULTS / "source_footprint_summary.json"
SUMMARY_CSV = RESULTS / "source_footprint_summary.csv"


@dataclass(frozen=True)
class Workload:
    name: str
    domain: str
    ks_sources: tuple[str, ...]
    c_ebpf_sources: tuple[str, ...]
    c_user_sources: tuple[str, ...] = ()
    note: str = ""


WORKLOADS = [
    Workload(
        "xdp_pass",
        "xdp",
        ("experiments/programs/perf_pass.ks",),
        ("experiments/baselines/xdp_pass.c",),
        note="traffic harness supplies attach path for both variants",
    ),
    Workload(
        "xdp_count",
        "xdp",
        ("experiments/programs/perf_count.ks",),
        ("experiments/baselines/xdp_count.c",),
        note="traffic harness supplies attach path for both variants",
    ),
    Workload(
        "tc_pass",
        "tc",
        ("experiments/programs/tc_pass.ks",),
        ("experiments/baselines/tc_pass.c",),
        note="traffic harness supplies attach path for both variants",
    ),
    Workload(
        "tc_count",
        "tc",
        ("experiments/programs/tc_count.ks",),
        ("experiments/baselines/tc_count.c",),
        note="traffic harness supplies attach path for both variants",
    ),
    Workload(
        "perf_event_loader",
        "perf_event",
        ("kernelscript/examples/perf_page_fault.ks",),
        ("experiments/baselines/perf_event_loader.ebpf.c",),
        ("experiments/baselines/perf_event_loader_user.c",),
        note="counts a hand-written loader because the experiment compares loader lifecycle",
    ),
    Workload(
        "perf_event_counter",
        "perf_event",
        ("experiments/programs/perf_event_count.ks",),
        ("experiments/baselines/perf_event_count.c",),
        ("experiments/baselines/perf_event_counter_user.c",),
        note="counts the shared C/libbpf counter runner used by both objects",
    ),
    Workload(
        "ringbuf_emit",
        "ringbuf",
        ("experiments/programs/ringbuf_emit.ks",),
        ("experiments/baselines/ringbuf_emit.c",),
        ("experiments/baselines/ringbuf_counter_user.c",),
        note="counts the shared C/libbpf ring-buffer runner used by both objects",
    ),
    Workload(
        "struct_ops_direct",
        "struct_ops",
        ("kernelscript/examples/struct_ops_simple.ks",),
        ("experiments/baselines/struct_ops_tcp_cc.c",),
        ("experiments/baselines/struct_ops_loader_user.c",),
        note="direct load/attach/detach baseline without generated skeletons",
    ),
    Workload(
        "struct_ops_loopback",
        "struct_ops",
        ("kernelscript/examples/struct_ops_simple.ks",),
        ("experiments/baselines/struct_ops_tcp_cc.c",),
        ("experiments/baselines/struct_ops_tcp_workload_user.c",),
        note="loopback TCP workload baseline without generated skeletons",
    ),
    Workload(
        "struct_ops_callback_flags",
        "struct_ops",
        ("experiments/programs/struct_ops_callback_count.ks",),
        ("experiments/baselines/struct_ops_tcp_callback_flags.c",),
        ("experiments/baselines/struct_ops_tcp_workload_user.c",),
        note="callback reachability baseline reuses the TCP workload runner",
    ),
    Workload(
        "sched_ext_fifo",
        "sched_ext",
        ("kernelscript/examples/sched_ext_simple.ks",),
        ("experiments/baselines/sched_ext_simple.c",),
        note="bpftool registers both struct_ops objects in the attach harness",
    ),
]


def run(argv: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git_head(path: Path) -> str:
    res = run(["git", "rev-parse", "HEAD"], path)
    return res.stdout.strip() if res.returncode == 0 else "unavailable"


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


def sloc_sum(paths: Iterable[str]) -> int:
    total = 0
    for rel in paths:
        path = ROOT / rel
        if not path.exists():
            raise SystemExit(f"missing source file: {rel}")
        total += nonblank_noncomment_sloc(path)
    return total


def rel_join(paths: Iterable[str]) -> str:
    return " ".join(paths)


def summarize_workload(workload: Workload) -> dict[str, object]:
    ks_sloc = sloc_sum(workload.ks_sources)
    c_ebpf_sloc = sloc_sum(workload.c_ebpf_sources)
    c_user_sloc = sloc_sum(workload.c_user_sources)
    c_total_sloc = c_ebpf_sloc + c_user_sloc
    return {
        "name": workload.name,
        "domain": workload.domain,
        "ks_sources": list(workload.ks_sources),
        "c_ebpf_sources": list(workload.c_ebpf_sources),
        "c_user_sources": list(workload.c_user_sources),
        "ks_sloc": ks_sloc,
        "c_ebpf_sloc": c_ebpf_sloc,
        "c_user_sloc": c_user_sloc,
        "c_total_sloc": c_total_sloc,
        "c_to_ks_ratio": round(c_total_sloc / ks_sloc, 3) if ks_sloc else 0.0,
        "ks_smaller": ks_sloc < c_total_sloc,
        "note": workload.note,
    }


def unique_sloc(rows: list[dict[str, object]], key: str) -> tuple[int, list[str]]:
    sources: set[str] = set()
    for row in rows:
        for item in row[key]:
            sources.add(str(item))
    ordered = sorted(sources)
    return sloc_sum(ordered), ordered


def median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = [summarize_workload(workload) for workload in WORKLOADS]
    ks_sum = sum(int(row["ks_sloc"]) for row in rows)
    c_sum = sum(int(row["c_total_sloc"]) for row in rows)
    unique_ks_sloc, unique_ks_sources = unique_sloc(rows, "ks_sources")
    unique_c_ebpf_sloc, unique_c_ebpf_sources = unique_sloc(rows, "c_ebpf_sources")
    unique_c_user_sloc, unique_c_user_sources = unique_sloc(rows, "c_user_sources")
    unique_c_sloc = unique_c_ebpf_sloc + unique_c_user_sloc
    summary = {
        "status": "ok",
        "description": (
            "Nonblank, noncomment source-footprint proxy for matched local "
            "KernelScript and hand-written C/libbpf baselines."
        ),
        "policy": {
            "counts": "repository-maintained KernelScript, C/eBPF, and C/libbpf runner source files",
            "excludes": [
                "generated C",
                "generated Makefiles",
                "generated vmlinux.h",
                "generated skeleton headers",
                "KernelScript library headers",
                "experiment harness Python code",
            ],
            "interpretation": "maintenance-surface proxy, not developer-time measurement",
        },
        "kernelscript_repo_head": git_head(ROOT / "kernelscript"),
        "workload_count": len(rows),
        "rows": rows,
        "aggregate_workload_rows": {
            "ks_sloc": ks_sum,
            "c_total_sloc": c_sum,
            "c_ebpf_sloc": sum(int(row["c_ebpf_sloc"]) for row in rows),
            "c_user_sloc": sum(int(row["c_user_sloc"]) for row in rows),
            "c_to_ks_ratio": round(c_sum / ks_sum, 3) if ks_sum else 0.0,
            "ks_smaller_rows": sum(1 for row in rows if bool(row["ks_smaller"])),
            "ks_not_smaller_rows": sum(1 for row in rows if not bool(row["ks_smaller"])),
            "median_ks_sloc": median([float(row["ks_sloc"]) for row in rows]),
            "median_c_total_sloc": median([float(row["c_total_sloc"]) for row in rows]),
            "median_c_to_ks_ratio": median([float(row["c_to_ks_ratio"]) for row in rows]),
        },
        "aggregate_unique_sources": {
            "ks_sources": unique_ks_sources,
            "c_ebpf_sources": unique_c_ebpf_sources,
            "c_user_sources": unique_c_user_sources,
            "ks_sloc": unique_ks_sloc,
            "c_ebpf_sloc": unique_c_ebpf_sloc,
            "c_user_sloc": unique_c_user_sloc,
            "c_total_sloc": unique_c_sloc,
            "c_to_ks_ratio": round(unique_c_sloc / unique_ks_sloc, 3) if unique_ks_sloc else 0.0,
        },
    }

    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    fields = [
        "name",
        "domain",
        "ks_sources",
        "c_ebpf_sources",
        "c_user_sources",
        "ks_sloc",
        "c_ebpf_sloc",
        "c_user_sloc",
        "c_total_sloc",
        "c_to_ks_ratio",
        "ks_smaller",
        "note",
    ]
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["ks_sources"] = rel_join(out["ks_sources"])
            out["c_ebpf_sources"] = rel_join(out["c_ebpf_sources"])
            out["c_user_sources"] = rel_join(out["c_user_sources"])
            writer.writerow({key: out[key] for key in fields})

    print(json.dumps({key: summary[key] for key in summary if key != "rows"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
