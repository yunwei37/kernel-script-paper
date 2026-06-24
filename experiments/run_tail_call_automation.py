#!/usr/bin/env python3
"""Measure matched tail-call boilerplate handled automatically by KernelScript.

This experiment compares two local XDP tail-call workloads against small
hand-written C/libbpf baselines. It focuses on buildable source footprint and
on the generated tail-call plumbing that disappears from KernelScript source:
prog-array maps, bpf_tail_call() call sites, fallback returns, and userspace
prog-array registration updates.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("KERNELSCRIPT_REPO", ROOT / "kernelscript")).resolve()
RESULTS = ROOT / "results"
ARTIFACT_ROOT = Path(
    os.environ.get("KERNELSCRIPT_TAIL_CALL_ARTIFACT_ROOT", str(ROOT / ".tail_call_automation"))
).resolve()
BUILD = ARTIFACT_ROOT / "build"
LOGS = ARTIFACT_ROOT / "logs"
SUMMARY_JSON = RESULTS / "tail_call_automation_summary.json"
SUMMARY_CSV = RESULTS / "tail_call_automation_summary.csv"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"


@dataclass(frozen=True)
class Workload:
    name: str
    ks_source: Path
    generated_base: str
    hand_bpf_source: Path
    hand_user_source: Path
    hand_base: str


WORKLOADS = [
    Workload(
        name="tail_call_dispatch",
        ks_source=REPO / "examples" / "tail_call.ks",
        generated_base="tail_call",
        hand_bpf_source=ROOT / "experiments" / "baselines" / "tail_call_dispatch.bpf.c",
        hand_user_source=ROOT / "experiments" / "baselines" / "tail_call_dispatch_user.c",
        hand_base="tail_call_dispatch",
    ),
    Workload(
        name="basic_match_tailcall",
        ks_source=REPO / "examples" / "basic_match.ks",
        generated_base="basic_match",
        hand_bpf_source=ROOT / "experiments" / "baselines" / "basic_match_tailcall.bpf.c",
        hand_user_source=ROOT / "experiments" / "baselines" / "basic_match_tailcall_user.c",
        hand_base="basic_match_tailcall",
    ),
]


def run(argv: list[str], cwd: Path = ROOT, timeout: int = 120) -> subprocess.CompletedProcess[str]:
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
        check=False,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def check(cmd: subprocess.CompletedProcess[str], label: str) -> None:
    if cmd.returncode != 0:
        raise RuntimeError(f"{label} failed\nstdout:\n{cmd.stdout}\nstderr:\n{cmd.stderr}")


def check_prerequisites() -> str | None:
    if not COMPILER.exists():
        return f"missing KernelScript compiler at {COMPILER}"
    for tool in ("bpftool", "clang", "gcc", "pkg-config", "make"):
        if not shutil.which(tool):
            return f"{tool} unavailable"
    if not Path("/sys/kernel/btf/vmlinux").exists():
        return "missing /sys/kernel/btf/vmlinux"
    for workload in WORKLOADS:
        for path in (workload.ks_source, workload.hand_bpf_source, workload.hand_user_source):
            if not path.exists():
                return f"missing source file: {path}"
    return None


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


def count_regex(path: Path, pattern: str) -> int:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return len(re.findall(pattern, text, flags=re.MULTILINE))


def parse_prog_array_entries(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"__uint\(max_entries,\s*(\d+)\s*\);", text)
    return int(match.group(1)) if match else 0


def pkg_config_flags() -> list[str]:
    res = run(["pkg-config", "--cflags", "--libs", "libbpf"])
    check(res, "pkg-config libbpf")
    return shlex.split(res.stdout.strip())


def multiarch_include() -> list[str]:
    res = run(["gcc", "-print-multiarch"])
    if res.returncode != 0:
        return []
    include = Path("/usr/include") / res.stdout.strip()
    return ["-I", str(include)] if include.exists() else []


def prepare_vmlinux_header() -> Path:
    hand_root = BUILD / "handwritten"
    hand_root.mkdir(parents=True, exist_ok=True)
    vmlinux = hand_root / "vmlinux.h"
    res = run(["bpftool", "btf", "dump", "file", "/sys/kernel/btf/vmlinux", "format", "c"], ROOT, timeout=240)
    check(res, "bpftool btf dump")
    write(vmlinux, res.stdout)
    return vmlinux


def compile_kernelscript(workload: Workload) -> dict[str, object]:
    out_dir = BUILD / f"ks_{workload.name}"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    compile_res = run([str(COMPILER), "compile", str(workload.ks_source), "-o", str(out_dir)], ROOT, timeout=240)
    write(LOGS / f"{workload.name}.ks.compile.stdout", compile_res.stdout)
    write(LOGS / f"{workload.name}.ks.compile.stderr", compile_res.stderr)
    check(compile_res, f"{workload.name} KernelScript compile")

    make_res = run(["make"], out_dir, timeout=240)
    write(LOGS / f"{workload.name}.ks.make.stdout", make_res.stdout)
    write(LOGS / f"{workload.name}.ks.make.stderr", make_res.stderr)
    check(make_res, f"{workload.name} KernelScript make")

    ebpf_c = out_dir / f"{workload.generated_base}.ebpf.c"
    user_c = out_dir / f"{workload.generated_base}.c"
    if not ebpf_c.exists() or not user_c.exists():
        raise RuntimeError(f"missing generated artifacts in {out_dir}")

    return {
        "out_dir": out_dir,
        "ebpf_c": ebpf_c,
        "user_c": user_c,
    }


def compile_handwritten(workload: Workload, vmlinux: Path, libbpf_flags: list[str]) -> dict[str, object]:
    out_dir = BUILD / "handwritten" / workload.name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(vmlinux, out_dir / "vmlinux.h")

    obj = out_dir / f"{workload.hand_base}.o"
    clang_cmd = [
        "clang",
        "-target",
        "bpf",
        "-O2",
        "-g",
        "-Wall",
        "-Wextra",
        *multiarch_include(),
        "-I",
        str(out_dir),
        "-c",
        str(workload.hand_bpf_source),
        "-o",
        str(obj),
    ]
    clang_res = run(clang_cmd, ROOT, timeout=240)
    write(LOGS / f"{workload.name}.hand.clang.stdout", clang_res.stdout)
    write(LOGS / f"{workload.name}.hand.clang.stderr", clang_res.stderr)
    check(clang_res, f"{workload.name} handwritten eBPF compile")

    skel = out_dir / f"{workload.hand_base}.skel.h"
    skel_res = run(["bpftool", "gen", "skeleton", str(obj)], ROOT, timeout=240)
    write(LOGS / f"{workload.name}.hand.skel.stdout", skel_res.stdout)
    write(LOGS / f"{workload.name}.hand.skel.stderr", skel_res.stderr)
    check(skel_res, f"{workload.name} handwritten skeleton generation")
    write(skel, skel_res.stdout)

    binary = out_dir / workload.hand_base
    gcc_cmd = [
        "gcc",
        "-O2",
        "-g",
        "-Wall",
        "-Wextra",
        "-I",
        str(out_dir),
        str(workload.hand_user_source),
        "-o",
        str(binary),
        *libbpf_flags,
    ]
    gcc_res = run(gcc_cmd, ROOT, timeout=240)
    write(LOGS / f"{workload.name}.hand.gcc.stdout", gcc_res.stdout)
    write(LOGS / f"{workload.name}.hand.gcc.stderr", gcc_res.stderr)
    check(gcc_res, f"{workload.name} handwritten userspace compile")

    return {
        "out_dir": out_dir,
        "object": obj,
        "skeleton": skel,
        "binary": binary,
    }


def summarize_workload(workload: Workload, ks_artifacts: dict[str, object], hand_artifacts: dict[str, object]) -> dict[str, object]:
    ks_ebpf_c = Path(str(ks_artifacts["ebpf_c"]))
    ks_user_c = Path(str(ks_artifacts["user_c"]))

    ks_sloc = nonblank_noncomment_sloc(workload.ks_source)
    hand_bpf_sloc = nonblank_noncomment_sloc(workload.hand_bpf_source)
    hand_user_sloc = nonblank_noncomment_sloc(workload.hand_user_source)
    hand_total_sloc = hand_bpf_sloc + hand_user_sloc

    return {
        "name": workload.name,
        "ks_source": str(workload.ks_source.relative_to(ROOT)),
        "hand_bpf_source": str(workload.hand_bpf_source.relative_to(ROOT)),
        "hand_user_source": str(workload.hand_user_source.relative_to(ROOT)),
        "ks_sloc": ks_sloc,
        "hand_bpf_sloc": hand_bpf_sloc,
        "hand_user_sloc": hand_user_sloc,
        "hand_total_sloc": hand_total_sloc,
        "hand_to_ks_ratio": round(hand_total_sloc / ks_sloc, 3) if ks_sloc else 0.0,
        "generated_ebpf_c_sloc": nonblank_noncomment_sloc(ks_ebpf_c),
        "generated_user_c_sloc": nonblank_noncomment_sloc(ks_user_c),
        "generated_prog_array_maps": count_regex(ks_ebpf_c, r"BPF_MAP_TYPE_PROG_ARRAY"),
        "generated_prog_array_entries": parse_prog_array_entries(ks_ebpf_c),
        "generated_tail_call_sites": count_regex(ks_ebpf_c, r"\bbpf_tail_call\s*\("),
        "generated_fallback_sites": count_regex(ks_ebpf_c, r"tail call fallback"),
        "generated_loader_update_sites": count_regex(ks_user_c, r"bpf_map_update_elem\(prog_array_fd"),
        "hand_prog_array_maps": count_regex(workload.hand_bpf_source, r"BPF_MAP_TYPE_PROG_ARRAY"),
        "hand_prog_array_entries": parse_prog_array_entries(workload.hand_bpf_source),
        "hand_tail_call_sites": count_regex(workload.hand_bpf_source, r"\bbpf_tail_call\s*\("),
        "hand_fallback_sites": count_regex(workload.hand_bpf_source, r"tail call fallback"),
        "hand_loader_update_sites": count_regex(workload.hand_user_source, r"\bbpf_map_update_elem\s*\("),
        "ks_build_ok": True,
        "hand_build_ok": True,
        "generated_dir": str(Path(str(ks_artifacts["out_dir"])).relative_to(ROOT)),
        "hand_build_dir": str(Path(str(hand_artifacts["out_dir"])).relative_to(ROOT)),
    }


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)

    prereq = check_prerequisites()
    if prereq:
        summary = {"status": "skipped", "reason": prereq}
        write(SUMMARY_JSON, json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0

    libbpf_flags = pkg_config_flags()
    vmlinux = prepare_vmlinux_header()

    rows = []
    for workload in WORKLOADS:
        ks_artifacts = compile_kernelscript(workload)
        hand_artifacts = compile_handwritten(workload, vmlinux, libbpf_flags)
        rows.append(summarize_workload(workload, ks_artifacts, hand_artifacts))

    aggregate = {
        "workload_count": len(rows),
        "ks_sloc": sum(int(row["ks_sloc"]) for row in rows),
        "hand_bpf_sloc": sum(int(row["hand_bpf_sloc"]) for row in rows),
        "hand_user_sloc": sum(int(row["hand_user_sloc"]) for row in rows),
        "hand_total_sloc": sum(int(row["hand_total_sloc"]) for row in rows),
        "generated_prog_array_maps": sum(int(row["generated_prog_array_maps"]) for row in rows),
        "generated_prog_array_max_entries": max(int(row["generated_prog_array_entries"]) for row in rows),
        "generated_tail_call_sites": sum(int(row["generated_tail_call_sites"]) for row in rows),
        "generated_fallback_sites": sum(int(row["generated_fallback_sites"]) for row in rows),
        "generated_loader_update_sites": sum(int(row["generated_loader_update_sites"]) for row in rows),
        "hand_prog_array_maps": sum(int(row["hand_prog_array_maps"]) for row in rows),
        "hand_tail_call_sites": sum(int(row["hand_tail_call_sites"]) for row in rows),
        "hand_fallback_sites": sum(int(row["hand_fallback_sites"]) for row in rows),
        "hand_loader_update_sites": sum(int(row["hand_loader_update_sites"]) for row in rows),
        "ks_build_ok": sum(1 for row in rows if row["ks_build_ok"]),
        "hand_build_ok": sum(1 for row in rows if row["hand_build_ok"]),
    }
    aggregate["hand_to_ks_ratio"] = round(
        aggregate["hand_total_sloc"] / aggregate["ks_sloc"], 3
    ) if aggregate["ks_sloc"] else 0.0

    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        fields = [
            "name",
            "ks_source",
            "hand_bpf_source",
            "hand_user_source",
            "ks_sloc",
            "hand_bpf_sloc",
            "hand_user_sloc",
            "hand_total_sloc",
            "hand_to_ks_ratio",
            "generated_ebpf_c_sloc",
            "generated_user_c_sloc",
            "generated_prog_array_maps",
            "generated_prog_array_entries",
            "generated_tail_call_sites",
            "generated_fallback_sites",
            "generated_loader_update_sites",
            "hand_prog_array_maps",
            "hand_prog_array_entries",
            "hand_tail_call_sites",
            "hand_fallback_sites",
            "hand_loader_update_sites",
            "generated_dir",
            "hand_build_dir",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})

    summary = {
        "status": "ok",
        "description": (
            "Matched tail-call boilerplate case study for two local XDP dispatch workloads. "
            "Compares KernelScript source footprint against hand-written C/libbpf baselines "
            "and inspects generated prog-array, tail-call, fallback, and loader-registration sites."
        ),
        "policy": {
            "counts": "nonblank, noncomment repository-maintained source lines",
            "interpretation": "matched source-footprint and code-generation evidence, not developer-time or throughput evidence",
        },
        "rows": rows,
        "aggregate": aggregate,
    }
    write(SUMMARY_JSON, json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
