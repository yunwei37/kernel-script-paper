#!/usr/bin/env python3
"""Q1 published verifier-accepted exemplar replay (Heimdall Listings 5–6).

For each defect family, compare:
  - KernelScript: exact expected compile-time diagnostic on the buggy source;
    successful compile on the corrected sibling.
  - C/libbpf: clang build, kernel verifier load, and a defect-specific runtime
    oracle via BPF_PROG_TEST_RUN (10 trials).

Outputs:
  experiments/q1_published_bug_replay/results/*.json logs
  results/q1_published_bug_replay_summary.{json,csv}
  experiments/q1_published_bug_replay/result.md
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXP = Path(__file__).resolve().parent
CASES = EXP / "cases"
RESULTS_ROOT = Path(os.environ.get("KERNELSCRIPT_RESULTS", ROOT / "results")).resolve()
BUILD = RESULTS_ROOT / "build" / "q1_published_bug_replay"
LOGS = RESULTS_ROOT / "logs" / "q1_published_bug_replay"
LOCAL_RESULTS = EXP / "results"
PINNED = Path(
    os.environ.get(
        "KERNELSCRIPT_REPO",
        ROOT / "results" / "build" / "kernelscript-pinned",
    )
).resolve()
COMPILER_CANDIDATES = [
    Path(os.environ["KERNELSCRIPT_COMPILER"])
    if os.environ.get("KERNELSCRIPT_COMPILER")
    else None,
    PINNED / "_build" / "default" / "src" / "main.exe",
    ROOT / "kernelscript" / "_build" / "default" / "src" / "main.exe",
    ROOT / "results" / "build" / "kernelscript-pinned" / "_build" / "default" / "src" / "main.exe",
]
PINNED_COMMIT = "3b19cd2bfa1db0428da6d735864a31d6ea62c7cd"
EXPECTED_DIAG = {
    "context": "xdp attributed function must have signature",
    "oversized_update": "Map value type mismatch",
    "reinterpretation": "Type mismatch in declaration",
}


@dataclass(frozen=True)
class Pair:
    name: str
    family: str
    listing: str
    note: str


PAIRS = [
    Pair(
        "context",
        "signature/domain",
        "Heimdall Listing 5",
        "XDP section with __sk_buff context; misnamed field reads",
    ),
    Pair(
        "oversized_update",
        "representation",
        "Heimdall Listing 6 (BUG 1)",
        "16-byte big written into 8-byte conn map value",
    ),
    Pair(
        "reinterpretation",
        "representation",
        "Heimdall Listing 6 (BUG 2)",
        "conn map lookup reinterpreted as unrelated stats u64",
    ),
]


def run(
    argv: list[str],
    cwd: Path = ROOT,
    timeout: int = 180,
    sudo: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    full = ["sudo", "-n", *argv] if sudo else argv
    e = os.environ.copy()
    if env:
        e.update(env)
    e["PWD"] = str(cwd)
    return subprocess.run(
        full,
        cwd=str(cwd),
        env=e,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def sudo_ok() -> bool:
    try:
        return run(["true"], sudo=True, timeout=10).returncode == 0
    except Exception:
        return False


def find_compiler() -> Path:
    for c in COMPILER_CANDIDATES:
        if c is not None and c.exists():
            return c
    raise RuntimeError(
        "KernelScript compiler not found; set KERNELSCRIPT_COMPILER or build "
        "results/build/kernelscript-pinned"
    )


def record_identity(compiler: Path) -> dict[str, object]:
    env = {
        "compiler": str(compiler),
        "pinned_commit_expected": PINNED_COMMIT,
        "kernel": os.uname().release,
        "clang": run(["clang", "--version"]).stdout.splitlines()[0]
        if have("clang")
        else None,
        "bpftool": run(["bpftool", "version"]).stdout.splitlines()[0]
        if have("bpftool")
        else None,
    }
    # Prefer git identity of the pinned tree when available.
    repo = compiler
    for _ in range(8):
        if (repo / ".git").exists() or (repo / "dune-project").exists():
            break
        repo = repo.parent
    if (repo / ".git").exists():
        head = run(["git", "rev-parse", "HEAD"], cwd=repo)
        if head.returncode == 0:
            env["kernelscript_git_head"] = head.stdout.strip()
    write(LOCAL_RESULTS / "environment.json", json.dumps(env, indent=2) + "\n")
    write(LOGS / "environment.json", json.dumps(env, indent=2) + "\n")
    return env


def ensure_vmlinux(inc: Path) -> Path:
    header = inc / "vmlinux.h"
    if header.exists() and header.stat().st_size > 0:
        return header
    btf = run(["bpftool", "btf", "dump", "file", "/sys/kernel/btf/vmlinux", "format", "c"])
    if btf.returncode != 0:
        raise RuntimeError("bpftool btf dump failed")
    write(header, btf.stdout)
    return header


def build_oracle() -> Path:
    out = BUILD / "q1_runtime_oracle"
    src = EXP / "q1_runtime_oracle.c"
    cmd = [
        "gcc",
        "-O2",
        "-Wall",
        "-Wextra",
        str(src),
        "-o",
        str(out),
    ]
    # libbpf via pkg-config when available.
    pc = run(["pkg-config", "--cflags", "--libs", "libbpf"])
    if pc.returncode == 0:
        cmd[1:1] = pc.stdout.split()
        # pkg-config flags belong after source for some linkers; rebuild cleanly.
        cmd = ["gcc", "-O2", "-Wall", "-Wextra", str(src), "-o", str(out)] + pc.stdout.split()
    else:
        cmd += ["-lbpf", "-lelf", "-lz"]
    res = run(cmd, timeout=60)
    write(LOGS / "oracle.build.stdout", res.stdout)
    write(LOGS / "oracle.build.stderr", res.stderr)
    if res.returncode != 0:
        raise RuntimeError(f"oracle build failed: {res.stderr}")
    return out


def ks_compile(compiler: Path, src: Path, out: Path) -> tuple[int, str]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    res = run([str(compiler), "compile", str(src), "-o", str(out)], timeout=120)
    text = res.stdout + res.stderr
    write(LOGS / f"{src.stem}.ks.compile.log", text)
    return res.returncode, text


def ks_make_ebpf(out: Path, stem: str) -> tuple[int, str, Path | None]:
    """Build the generated eBPF object for a successful KernelScript compile."""
    make = run(["make", "ebpf-only"], cwd=out, timeout=180)
    text = make.stdout + make.stderr
    write(LOGS / f"{stem}.ks.make.log", text)
    if make.returncode != 0:
        return make.returncode, text, None
    objs = sorted(out.glob("*.ebpf.o"))
    if not objs:
        return 1, text + "\nmissing *.ebpf.o after make ebpf-only\n", None
    return 0, text, objs[0]


def clang_build(src: Path, obj: Path, inc: Path) -> tuple[int, str]:
    obj.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "clang",
        "-target",
        "bpf",
        "-O2",
        "-g",
        "-Wall",
        "-Wextra",
        "-fno-builtin",
        "-I",
        str(inc),
        "-c",
        str(src),
        "-o",
        str(obj),
    ]
    res = run(cmd, timeout=120)
    text = res.stdout + res.stderr
    write(LOGS / f"{src.stem}.c.clang.log", text)
    return res.returncode, text


def verifier_load(obj: Path, tag: str) -> tuple[str, str]:
    pin = Path("/sys/fs/bpf") / f"q1_{tag}"
    prog_pin = str(pin / "progs")
    map_pin = str(pin / "maps")
    run(["rm", "-rf", str(pin)], sudo=True)
    run(["mkdir", "-p", str(pin)], sudo=True)
    res = run(
        ["bpftool", "prog", "loadall", str(obj), prog_pin, "pinmaps", map_pin],
        sudo=True,
        timeout=60,
    )
    text = res.stdout + res.stderr
    write(LOGS / f"{tag}.verifier.log", text)
    pinned = run(["find", prog_pin, "-type", "f"], sudo=True)
    has_prog = bool(pinned.stdout.strip())
    run(["rm", "-rf", str(pin)], sudo=True)
    if res.returncode == 0 and has_prog:
        return "verifier_accept", "loaded; verifier accepted the program"
    return "verifier_reject", text[:500]


def run_oracle(oracle: Path, obj: Path, case: str) -> tuple[bool, dict]:
    res = run([str(oracle), str(obj), case], sudo=True, timeout=60)
    write(LOGS / f"{case}.oracle.stdout", res.stdout)
    write(LOGS / f"{case}.oracle.stderr", res.stderr)
    payload: dict = {"raw_stdout": res.stdout.strip(), "raw_stderr": res.stderr.strip()}
    if res.returncode == 0:
        try:
            payload.update(json.loads(res.stdout.strip().splitlines()[-1]))
        except Exception:
            pass
        return True, payload
    return False, payload


def match_diag(text: str, expected: str) -> bool:
    return expected.lower() in text.lower()


def c_bug_stage_for(pair_name: str, oracle_ok: bool) -> tuple[str, str]:
    """Honest stage labels for C buggy objects that load and run.

    Map-schema cases reproduce a concrete wrong value (truncation /
    reinterpretation). The context case only proves the wrong-typed XDP object
    executes under BPF_PROG_TEST_RUN; host test-run rejects XDP ctx_in, so we
    do not claim non-zero misnamed-field remapping.
    """
    if not oracle_ok:
        return "runtime_oracle_fail", "runtime oracle failed"
    if pair_name == "context":
        return (
            "runtime_accept",
            "verifier accepted; executed under BPF_PROG_TEST_RUN "
            "(no non-zero field-remapping oracle; ctx_in unsupported)",
        )
    if pair_name == "oversized_update":
        return (
            "runtime_wrong",
            "verifier accepted; map value truncated to native {1,2} in 8B slot",
        )
    if pair_name == "reinterpretation":
        return (
            "runtime_wrong",
            "verifier accepted; conn{1,2} reinterpreted as native-endian u64",
        )
    return "runtime_accept", "verifier accepted; runtime oracle passed"


def evaluate_pair(
    pair: Pair,
    compiler: Path,
    inc: Path,
    oracle: Path,
) -> dict:
    bug_ks = CASES / f"{pair.name}_bug.ks"
    fix_ks = CASES / f"{pair.name}_fixed.ks"
    bug_c = CASES / f"{pair.name}_bug.c"
    fix_c = CASES / f"{pair.name}_fixed.c"

    row: dict[str, object] = {
        "name": pair.name,
        "family": pair.family,
        "listing": pair.listing,
        "note": pair.note,
        "defect_oracle": (
            "map_value"
            if pair.name in {"oversized_update", "reinterpretation"}
            else "runtime_accept_only"
        ),
    }

    # --- KernelScript buggy (compile-time reject with exact diagnostic) ---
    rc, text = ks_compile(compiler, bug_ks, BUILD / "ks" / f"{pair.name}_bug")
    expected = EXPECTED_DIAG[pair.name]
    ks_bug_ok = rc != 0 and match_diag(text, expected)
    row["ks_bug_stage"] = "compile_reject" if rc != 0 else "compile_accept"
    row["ks_bug_expected_diag"] = expected
    row["ks_bug_diag_match"] = ks_bug_ok
    row["ks_bug_detail"] = text.strip().splitlines()[-1] if text.strip() else ""

    # --- KernelScript fixed: compile → make ebpf → verifier → same oracle ---
    ks_out = BUILD / "ks" / f"{pair.name}_fixed"
    rc_f, text_f = ks_compile(compiler, fix_ks, ks_out)
    if rc_f != 0:
        row["ks_fixed_stage"] = "compile_reject"
        row["ks_fixed_ok"] = False
        row["ks_fixed_detail"] = text_f.strip().splitlines()[-1] if text_f.strip() else ""
    else:
        mrc, mtext, ks_obj = ks_make_ebpf(ks_out, f"{pair.name}_fixed")
        if mrc != 0 or ks_obj is None:
            row["ks_fixed_stage"] = "build_fail"
            row["ks_fixed_ok"] = False
            row["ks_fixed_detail"] = mtext[:400]
        else:
            vstage, vdetail = verifier_load(ks_obj, f"ks_{pair.name}_fixed")
            if vstage != "verifier_accept":
                row["ks_fixed_stage"] = "verifier_reject"
                row["ks_fixed_ok"] = False
                row["ks_fixed_detail"] = vdetail
            else:
                ok, payload = run_oracle(oracle, ks_obj, f"{pair.name}_fixed")
                row["ks_fixed_stage"] = "runtime_ok" if ok else "runtime_oracle_fail"
                row["ks_fixed_ok"] = ok
                row["ks_fixed_oracle"] = payload
                row["ks_fixed_detail"] = (
                    "KS fixed control: generate/load/run oracle passed"
                    if ok
                    else payload.get("raw_stderr", "oracle failed")
                )

    # --- C buggy ---
    obj_bug = BUILD / "c" / f"{pair.name}_bug.o"
    rc_c, text_c = clang_build(bug_c, obj_bug, inc)
    if rc_c != 0:
        row["c_bug_stage"] = "compile_reject"
        row["c_bug_detail"] = text_c[:400]
        row["c_bug_runtime_ok"] = False
    else:
        vstage, vdetail = verifier_load(obj_bug, f"{pair.name}_bug")
        if vstage != "verifier_accept":
            row["c_bug_stage"] = "verifier_reject"
            row["c_bug_detail"] = vdetail
            row["c_bug_runtime_ok"] = False
        else:
            ok, payload = run_oracle(oracle, obj_bug, f"{pair.name}_bug")
            stage, detail = c_bug_stage_for(pair.name, ok)
            row["c_bug_stage"] = stage
            row["c_bug_runtime_ok"] = ok
            row["c_bug_oracle"] = payload
            row["c_bug_detail"] = detail if ok else payload.get("raw_stderr", vdetail)

    # --- C fixed ---
    obj_fix = BUILD / "c" / f"{pair.name}_fixed.o"
    rc_cf, text_cf = clang_build(fix_c, obj_fix, inc)
    if rc_cf != 0:
        row["c_fixed_stage"] = "compile_reject"
        row["c_fixed_ok"] = False
        row["c_fixed_detail"] = text_cf[:400]
    else:
        vstage, vdetail = verifier_load(obj_fix, f"{pair.name}_fixed")
        if vstage != "verifier_accept":
            row["c_fixed_stage"] = "verifier_reject"
            row["c_fixed_ok"] = False
            row["c_fixed_detail"] = vdetail
        else:
            ok, payload = run_oracle(oracle, obj_fix, f"{pair.name}_fixed")
            row["c_fixed_stage"] = "runtime_ok" if ok else "runtime_oracle_fail"
            row["c_fixed_ok"] = ok
            row["c_fixed_oracle"] = payload
            row["c_fixed_detail"] = "control passed" if ok else payload.get("raw_stderr", "")

    # Positive: KS rejects with expected diag; both fixed controls pass the
    # shared runtime path; C buggy reaches a post-verifier runtime stage
    # (runtime_wrong for map schema, runtime_accept for context).
    c_bug_later = row.get("c_bug_stage") in {"runtime_wrong", "runtime_accept"}
    positive = (
        bool(row["ks_bug_diag_match"])
        and bool(row.get("ks_fixed_ok"))
        and bool(row.get("c_fixed_ok"))
        and c_bug_later
        and bool(row.get("c_bug_runtime_ok"))
    )
    if positive:
        row["verdict"] = "ks_earlier"
    elif row["ks_bug_stage"] == "compile_accept":
        row["verdict"] = "ks_miss"
    elif row.get("c_bug_stage") in {"compile_reject", "verifier_reject"}:
        row["verdict"] = "c_not_later"
    elif not row.get("c_fixed_ok") or not row.get("ks_fixed_ok"):
        row["verdict"] = "invalid_control"
    else:
        row["verdict"] = "inconclusive"

    write(LOCAL_RESULTS / f"{pair.name}.json", json.dumps(row, indent=2) + "\n")
    return row


def write_result_md(rows: list[dict], summary: dict) -> None:
    lines = [
        "# Q1 Published Bug Replay Results",
        "",
        f"Status: **{summary['status']}**",
        f"Positive (ks_earlier) rows: {summary['ks_earlier']} / {summary['total']}",
        "",
        "Stage vocabulary:",
        "- `runtime_wrong`: C buggy object loads and the defect-specific map oracle holds",
        "  (truncation or reinterpretation).",
        "- `runtime_accept`: C buggy object loads and executes under BPF_PROG_TEST_RUN;",
        "  used for the context case where non-zero field remapping is **not** claimed",
        "  (`ctx_in` unsupported on this host).",
        "- KS fixed controls run generate → `make ebpf-only` → verifier → shared oracle.",
        "",
        "| Defect | Listing | KS buggy | C buggy | KS fixed | C fixed | Verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['name']} | {r['listing']} | {r['ks_bug_stage']}"
            f"{' ✓diag' if r.get('ks_bug_diag_match') else ''} | {r.get('c_bug_stage')} | "
            f"{r.get('ks_fixed_stage')} | {r.get('c_fixed_stage')} | {r.get('verdict')} |"
        )
    lines += [
        "",
        "## Claim cap",
        "",
        "KernelScript rejects these three published verifier-accepted exemplars at",
        "compile time while C/libbpf builds, loads, and runs them on this toolchain.",
        "Map-schema rows reproduce wrong values; the context row only claims runtime",
        "accept of the wrong-typed object (no non-zero remapping oracle).",
        "No prevalence claim; no Aya comparison.",
        "",
    ]
    write(EXP / "result.md", "\n".join(lines) + "\n")


def main() -> int:
    if not have("clang") or not have("bpftool") or not have("gcc"):
        raise SystemExit("need clang, bpftool, and gcc")
    if not sudo_ok():
        raise SystemExit("sudo -n required for verifier load and test-run")

    LOGS.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    LOCAL_RESULTS.mkdir(parents=True, exist_ok=True)
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)

    compiler = find_compiler()
    identity = record_identity(compiler)
    head = str(identity.get("kernelscript_git_head", ""))
    if head and head != PINNED_COMMIT:
        # Soft warning only: pinned tree may live without .git.
        write(LOGS / "commit_mismatch.txt", f"expected {PINNED_COMMIT} got {head}\n")

    inc = BUILD / "include"
    ensure_vmlinux(inc)
    # Case sources include "vmlinux.h" via -I include dir.
    oracle = build_oracle()

    rows = [evaluate_pair(p, compiler, inc, oracle) for p in PAIRS]
    counts = {"ks_earlier": 0, "ks_miss": 0, "c_not_later": 0, "invalid_control": 0, "inconclusive": 0}
    for r in rows:
        counts[str(r["verdict"])] = counts.get(str(r["verdict"]), 0) + 1

    status = "ok" if counts["ks_earlier"] == len(rows) else "partial"
    summary = {
        "status": status,
        "description": "Heimdall published verifier-accepted exemplar replay for Q1",
        "source": "Heimdall arXiv:2605.25411v1 Listings 5 and 6",
        "total": len(rows),
        "ks_earlier": counts.get("ks_earlier", 0),
        "ks_miss": counts.get("ks_miss", 0),
        "c_not_later": counts.get("c_not_later", 0),
        "invalid_control": counts.get("invalid_control", 0),
        "inconclusive": counts.get("inconclusive", 0),
        "identity": identity,
        "rows": rows,
    }

    write(RESULTS_ROOT / "q1_published_bug_replay_summary.json", json.dumps(summary, indent=2) + "\n")
    write(LOCAL_RESULTS / "summary.json", json.dumps(summary, indent=2) + "\n")

    cols = [
        "name",
        "family",
        "listing",
        "ks_bug_stage",
        "ks_bug_diag_match",
        "c_bug_stage",
        "ks_fixed_stage",
        "c_fixed_stage",
        "verdict",
    ]
    csv_path = RESULTS_ROOT / "q1_published_bug_replay_summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    write_result_md(rows, summary)
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "status",
                    "total",
                    "ks_earlier",
                    "ks_miss",
                    "c_not_later",
                    "invalid_control",
                    "inconclusive",
                )
            },
            indent=2,
        )
    )
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
