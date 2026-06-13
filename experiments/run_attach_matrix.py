#!/usr/bin/env python3
"""Attach verifier-clean XDP objects in an isolated network namespace."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
LOGS = RESULTS / "logs" / "attach_matrix"
VERIFIER_CSV = RESULTS / "verifier_matrix_summary.csv"


def run(
    argv: list[str],
    cwd: Path = ROOT,
    timeout: int = 60,
    sudo: bool = False,
) -> subprocess.CompletedProcess[str]:
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
    if run(["true"], sudo=True).returncode != 0:
        return "sudo -n unavailable"
    if not shutil.which("ip"):
        return "iproute2 ip command unavailable"
    if not VERIFIER_CSV.exists():
        return (
            f"missing {VERIFIER_CSV.relative_to(ROOT)}; "
            "run experiments/run_verifier_matrix.py first"
        )
    return None


def load_verifier_rows() -> list[dict[str, str]]:
    with VERIFIER_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def eligible_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row["load_status"] == "ok"
        and row["program_sections"] == "xdp"
        and row["section_kinds"] == "xdp"
        and row["program_count"] == "1"
    ]


def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def excerpt(text: str, max_lines: int = 10) -> str:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        low = line.lower()
        if "error" in low or "failed" in low or "cannot" in low:
            return "\n".join(lines[max(0, idx - 2) : idx + max_lines])
    return "\n".join(lines[:max_lines])


def cleanup_namespace(ns: str) -> None:
    run(["ip", "netns", "del", ns], sudo=True)


def attach_one(row: dict[str, str], idx: int) -> dict[str, object]:
    name = row["name"]
    safe = sanitize(name)
    ns = f"ksam{os.getpid()}_{idx}"
    host_dev = f"ksa{idx}h"
    ns_dev = f"ksa{idx}n"
    obj = ROOT / row["object"]
    logs = LOGS / safe

    cleanup_namespace(ns)
    setup_cmds = [
        ["ip", "netns", "add", ns],
        ["ip", "link", "add", host_dev, "type", "veth", "peer", "name", ns_dev],
        ["ip", "link", "set", ns_dev, "netns", ns],
        ["ip", "link", "set", host_dev, "up"],
        ["ip", "netns", "exec", ns, "ip", "link", "set", "lo", "up"],
        ["ip", "netns", "exec", ns, "ip", "link", "set", ns_dev, "up"],
    ]

    setup_outputs: list[str] = []
    attach_res: subprocess.CompletedProcess[str] | None = None
    show_res: subprocess.CompletedProcess[str] | None = None
    detach_res: subprocess.CompletedProcess[str] | None = None
    failure_text = ""

    try:
        for cmd in setup_cmds:
            res = run(cmd, sudo=True)
            setup_outputs.append(
                f"$ {' '.join(cmd)}\n"
                f"stdout:\n{res.stdout}\n"
                f"stderr:\n{res.stderr}\n"
                f"rc={res.returncode}\n"
            )
            if res.returncode != 0:
                failure_text = res.stdout + res.stderr
                return result_row(row, "setup_failed", False, "not_run", failure_text)

        attach_cmd = [
            "ip",
            "netns",
            "exec",
            ns,
            "ip",
            "link",
            "set",
            "dev",
            ns_dev,
            "xdp",
            "obj",
            str(obj),
            "sec",
            "xdp",
        ]
        attach_res = run(attach_cmd, sudo=True)
        if attach_res.returncode != 0:
            failure_text = attach_res.stdout + attach_res.stderr
            return result_row(row, "failed", False, "not_run", failure_text)

        show_res = run(
            ["ip", "netns", "exec", ns, "ip", "-d", "link", "show", "dev", ns_dev],
            sudo=True,
        )
        show_text = show_res.stdout + show_res.stderr
        has_xdp = show_res.returncode == 0 and "prog/xdp" in show_text

        detach_res = run(
            ["ip", "netns", "exec", ns, "ip", "link", "set", "dev", ns_dev, "xdp", "off"],
            sudo=True,
        )
        detach_status = "ok" if detach_res.returncode == 0 else "failed"
        failure_text = (
            ""
            if has_xdp and detach_status == "ok"
            else show_text
            + (detach_res.stdout if detach_res else "")
            + (detach_res.stderr if detach_res else "")
        )
        return result_row(row, "ok" if has_xdp else "show_failed", has_xdp, detach_status, failure_text)
    finally:
        write(logs / "setup.log", "\n".join(setup_outputs))
        if attach_res is not None:
            write(logs / "attach.stdout", attach_res.stdout)
            write(logs / "attach.stderr", attach_res.stderr)
        if show_res is not None:
            write(logs / "show.stdout", show_res.stdout)
            write(logs / "show.stderr", show_res.stderr)
        if detach_res is not None:
            write(logs / "detach.stdout", detach_res.stdout)
            write(logs / "detach.stderr", detach_res.stderr)
        cleanup_namespace(ns)


def result_row(
    row: dict[str, str],
    attach_status: str,
    show_has_xdp: bool,
    detach_status: str,
    failure_text: str,
) -> dict[str, object]:
    return {
        "name": row["name"],
        "source": row["source"],
        "object": row["object"],
        "program_sections": row["program_sections"],
        "attach_status": attach_status,
        "show_has_xdp": show_has_xdp,
        "detach_status": detach_status,
        "failure_excerpt": (
            "" if attach_status == "ok" and detach_status == "ok" else excerpt(failure_text)
        ),
    }


def main() -> int:
    reason = check_prerequisites()
    if reason:
        summary = {"status": "skipped", "reason": reason}
        write(RESULTS / "attach_matrix_summary.json", json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0

    if LOGS.exists():
        shutil.rmtree(LOGS)
    LOGS.mkdir(parents=True, exist_ok=True)

    rows = eligible_rows(load_verifier_rows())
    attach_rows = [attach_one(row, idx) for idx, row in enumerate(rows)]

    fields = [
        "name",
        "source",
        "object",
        "program_sections",
        "attach_status",
        "show_has_xdp",
        "detach_status",
        "failure_excerpt",
    ]
    with (RESULTS / "attach_matrix_summary.csv").open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in attach_rows:
            writer.writerow({k: row[k] for k in fields})

    attach_ok = sum(
        1
        for row in attach_rows
        if row["attach_status"] == "ok" and row["detach_status"] == "ok"
    )
    attach_failed = len(attach_rows) - attach_ok
    summary = {
        "status": "ok",
        "description": (
            "Isolated network-namespace XDP attach/detach matrix for "
            "verifier-clean single-section XDP objects."
        ),
        "eligible_xdp_objects": len(rows),
        "attach_ok": attach_ok,
        "attach_failed": attach_failed,
        "rows": attach_rows,
    }
    write(
        RESULTS / "attach_matrix_summary.json",
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps({k: summary[k] for k in summary if k != "rows"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
