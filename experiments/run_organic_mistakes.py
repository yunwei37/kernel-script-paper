#!/usr/bin/env python3
"""Differential failure-stage study: realistic mistakes injected into working
XDP map-counter programs, applied identically to KernelScript and to matched
hand-written C/eBPF, recording the earliest stage each toolchain catches them.

This is the *organic* counterpart to run_static_checks.py. The static corpus
shows KernelScript's checks are wired; this study asks the comparative question
the paper's early-checking claim needs: for the same mistake, does KernelScript
fail strictly earlier than the C/libbpf path?

Failure-stage ladder (shared ordinal), lower = caught earlier:
    compile_reject (1) < build_fail (2) < verifier_reject (3)
        < attach_fail (4) < runtime_wrong (5) < undetected (6)

Per case we record (ks_stage, c_stage) and a verdict: ks_earlier / tie /
ks_later / inconclusive (when a stage could not be tested, e.g. no sudo for the
kernel verifier). The catalog is pre-registered: each mutation is a committed
source pair under experiments/organic_mistakes/.

Scope (v1): four kernel-side mistakes whose injection is *literally identical*
in both toolchains. map_undeclared is the honest tie (both reject at compile).
The verifier-semantics control (a mistake KernelScript should NOT win, both
failing at the verifier) and the lifecycle pair (attach-before-load, needing a
matched C loader) are the documented next additions.

Numbers must be produced on the canonical evaluation host (same commit/kernel
and matched bpftool/libbpf) to stay consistent with the rest of the paper; on a
host without passwordless sudo the verifier stage is reported as untested.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("KERNELSCRIPT_REPO", ROOT / "kernelscript")).resolve()
RESULTS = Path(os.environ.get("KERNELSCRIPT_RESULTS", ROOT / "results")).resolve()
BUILD = RESULTS / "build" / "organic_mistakes"
LOGS = RESULTS / "logs" / "organic_mistakes"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"
CASES_DIR = ROOT / "experiments" / "organic_mistakes"

STAGE_ORDINAL = {
    "compile_reject": 1,
    "build_fail": 2,
    "verifier_reject": 3,
    "attach_fail": 4,
    "runtime_wrong": 5,
    "undetected": 6,
}


@dataclass(frozen=True)
class Case:
    name: str
    coupling: str
    note: str


# Pre-registered catalog. The source pair for each lives at
# experiments/organic_mistakes/<name>.ks and <name>.c
CASES = [
    Case("wrong_context", "signature/domain",
         "@xdp entry point given a *__sk_buff context instead of *xdp_md"),
    Case("map_undeclared", "representation",
         "entry point references a map that was never declared (tie expected)"),
    Case("map_value_type", "representation",
         "string stored into a u64 map value"),
    Case("stack_overflow", "safety",
         "600-byte stack buffer exceeds the 512-byte eBPF limit"),
]


def run(argv, cwd: Path = ROOT, timeout: int = 120, sudo: bool = False):
    env = os.environ.copy()
    env["PWD"] = str(cwd)
    full = ["sudo", "-n", *argv] if sudo else argv
    return subprocess.run(
        full, cwd=str(cwd), env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def excerpt(text: str, max_lines: int = 6) -> str:
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    for idx, ln in enumerate(lines):
        low = ln.lower()
        if "error" in low or "mismatch" in low or "stack overflow" in low:
            return "\n".join(lines[max(0, idx - 1): idx + max_lines])
    return "\n".join(lines[:max_lines])


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def sudo_ok() -> bool:
    try:
        return run(["true"], sudo=True, timeout=10).returncode == 0
    except Exception:
        return False


def ensure_compiler() -> None:
    if COMPILER.exists():
        return
    build = run(["dune", "build"], REPO, timeout=240)
    write(LOGS / "dune_build.stdout", build.stdout)
    write(LOGS / "dune_build.stderr", build.stderr)
    if build.returncode != 0:
        raise RuntimeError("dune build failed; see results/logs/organic_mistakes/")


def ensure_vmlinux() -> Path:
    inc = BUILD / "include"
    header = inc / "vmlinux.h"
    if header.exists() and header.stat().st_size > 0:
        return inc
    btf = run(["bpftool", "btf", "dump", "file", "/sys/kernel/btf/vmlinux", "format", "c"])
    if btf.returncode != 0:
        raise RuntimeError("bpftool btf dump failed; cannot build C baselines")
    write(header, btf.stdout)
    return inc


def bpftool_load(obj: Path, tag: str, sudo: bool):
    """Strict verifier-load: success only if bpftool returns 0 and at least one
    program is pinned. Returns 'undetected' (passed verifier), 'verifier_reject',
    or None if the stage could not be tested."""
    if not (sudo and have("bpftool")):
        return None, "verifier stage not tested (no sudo/bpftool)"
    pin = Path("/sys/fs/bpf") / f"organic_{tag}"
    prog_pin, map_pin = str(pin / "progs"), str(pin / "maps")
    run(["rm", "-rf", str(pin)], sudo=True)
    run(["mkdir", "-p", str(pin)], sudo=True)  # bpftool needs the parent pin dir
    res = run(["bpftool", "prog", "loadall", str(obj), prog_pin, "pinmaps", map_pin],
              sudo=True, timeout=60)
    pinned = run(["find", prog_pin, "-type", "f"], sudo=True)
    has_prog = bool(pinned.stdout.strip())
    run(["rm", "-rf", str(pin)], sudo=True)
    if res.returncode == 0 and has_prog:
        return "undetected", "loaded; verifier accepted the program"
    return "verifier_reject", excerpt(res.stdout + res.stderr)


def ks_ladder(case: Case, sudo: bool):
    src = CASES_DIR / f"{case.name}.ks"
    out = BUILD / "ks" / case.name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    comp = run([str(COMPILER), "compile", str(src), "-o", str(out)])
    write(LOGS / f"{case.name}.ks.compile.log", comp.stdout + comp.stderr)
    if comp.returncode != 0:
        return "compile_reject", excerpt(comp.stdout + comp.stderr)

    if not have("make"):
        return None, "compiled; build stage not tested (no make)"
    mk = run(["make"], out, timeout=180)
    write(LOGS / f"{case.name}.ks.make.log", mk.stdout + mk.stderr)
    if mk.returncode != 0:
        return "build_fail", excerpt(mk.stdout + mk.stderr)

    objs = sorted(out.glob("*.ebpf.o"))
    if not objs:
        return None, "built; no eBPF object found to load"
    return bpftool_load(objs[0], f"ks_{case.name}", sudo)


def c_ladder(case: Case, incdir: Path, sudo: bool):
    src = CASES_DIR / f"{case.name}.c"
    obj = BUILD / "c" / f"{case.name}.o"
    obj.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["clang", "-target", "bpf", "-O2", "-g", "-Wall", "-Wextra",
           "-fno-builtin", "-I", str(incdir), "-c", str(src), "-o", str(obj)]
    cc = run(cmd, timeout=120)
    write(LOGS / f"{case.name}.c.clang.log", cc.stdout + cc.stderr)
    if cc.returncode != 0:
        return "compile_reject", excerpt(cc.stdout + cc.stderr)
    return bpftool_load(obj, f"c_{case.name}", sudo)


def verdict(ks_stage, c_stage) -> str:
    if ks_stage is None or c_stage is None:
        return "inconclusive"
    ks, c = STAGE_ORDINAL[ks_stage], STAGE_ORDINAL[c_stage]
    if ks < c:
        return "ks_earlier"
    if ks == c:
        return "tie"
    return "ks_later"


def run_case(case: Case, incdir: Path, sudo: bool) -> dict:
    ks_stage, ks_detail = ks_ladder(case, sudo)
    c_stage, c_detail = c_ladder(case, incdir, sudo)
    v = verdict(ks_stage, c_stage)
    return {
        "name": case.name,
        "coupling": case.coupling,
        "note": case.note,
        "ks_stage": ks_stage or "untested",
        "ks_ordinal": STAGE_ORDINAL.get(ks_stage),
        "c_stage": c_stage or "untested",
        "c_ordinal": STAGE_ORDINAL.get(c_stage),
        "verdict": v,
        "ks_detail": ks_detail,
        "c_detail": c_detail,
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    cols = ["name", "coupling", "ks_stage", "ks_ordinal", "c_stage",
            "c_ordinal", "verdict"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    if not have("clang"):
        raise SystemExit("clang not found; cannot build C baselines")
    ensure_compiler()
    LOGS.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)

    sudo = sudo_ok()
    incdir = ensure_vmlinux()
    rows = [run_case(case, incdir, sudo) for case in CASES]

    counts = {k: 0 for k in ("ks_earlier", "tie", "ks_later", "inconclusive")}
    for r in rows:
        counts[r["verdict"]] += 1

    summary = {
        "status": "ok",
        "description": "differential failure-stage study of injected eBPF mistakes",
        "verifier_tested": sudo and have("bpftool"),
        "total": len(rows),
        "ks_earlier": counts["ks_earlier"],
        "tie": counts["tie"],
        "ks_later": counts["ks_later"],
        "inconclusive": counts["inconclusive"],
        "rows": rows,
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    write_csv(RESULTS / "organic_mistakes_summary.csv", rows)
    write(RESULTS / "organic_mistakes_summary.json",
          json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: summary[k] for k in
                      ("status", "verifier_tested", "total", "ks_earlier",
                       "tie", "ks_later", "inconclusive")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
