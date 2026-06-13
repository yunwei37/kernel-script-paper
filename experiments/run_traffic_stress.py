#!/usr/bin/env python3
"""Run longer XDP and TC traffic checks without replacing headline summaries."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
LOGS = RESULTS / "logs" / "traffic_stress"
TRIALS = int(os.environ.get("KERNELSCRIPT_TRAFFIC_STRESS_TRIALS", "3"))
SECONDS = int(os.environ.get("KERNELSCRIPT_TRAFFIC_STRESS_SECONDS", "5"))
LABEL = os.environ.get("KERNELSCRIPT_TRAFFIC_STRESS_LABEL", "stress")
OUT_JSON = RESULTS / "traffic_stress_summary.json"
OUT_CSV = RESULTS / "traffic_stress_summary.csv"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_script(script: str, env_update: dict[str, str], timeout: int) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(env_update)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "experiments" / script)],
        cwd=str(ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    write(LOGS / f"{script}.stdout", proc.stdout)
    write(LOGS / f"{script}.stderr", proc.stderr)
    return proc


def load_json(name: str) -> dict[str, object]:
    path = RESULTS / name
    if not path.exists():
        raise RuntimeError(f"missing result file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_rows(summary: dict[str, object], family: str) -> list[dict[str, object]]:
    map_key = "xdp_map_mpps_samples" if family == "xdp" else "tc_map_mpps_samples"
    median_map_key = "median_xdp_map_mpps" if family == "xdp" else "median_tc_map_mpps"
    rows = []
    for row in summary["rows"]:
        rows.append(
            {
                "family": family,
                "name": row["name"],
                "bench": row["bench"],
                "implementation": row["implementation"],
                "object": row["object"],
                "trials": row["trials"],
                "seconds_per_trial": row["seconds_per_trial"],
                "median_receiver_gbps": row["median_receiver_gbps"],
                "min_receiver_gbps": row["min_receiver_gbps"],
                "max_receiver_gbps": row["max_receiver_gbps"],
                "median_sender_gbps": row["median_sender_gbps"],
                "median_map_mpps": row[median_map_key],
                "total_retransmits": sum(int(value) for value in row["retransmits_samples"]),
                "oracle_passed": bool(row["oracle_passed"]),
                "receiver_gbps_samples": row["receiver_gbps_samples"],
                "sender_gbps_samples": row["sender_gbps_samples"],
                "retransmits_samples": row["retransmits_samples"],
                "map_mpps_samples": row[map_key],
            }
        )
    return rows


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    timeout = TRIALS * SECONDS * 8 + 240

    children = [
        (
            "xdp",
            "run_xdp_traffic.py",
            {
                "KERNELSCRIPT_XDP_TRAFFIC_LABEL": LABEL,
                "KERNELSCRIPT_TRAFFIC_TRIALS": str(TRIALS),
                "KERNELSCRIPT_TRAFFIC_SECONDS": str(SECONDS),
            },
            f"xdp_traffic_{LABEL}_summary.json",
        ),
        (
            "tc",
            "run_tc_traffic.py",
            {
                "KERNELSCRIPT_TC_TRAFFIC_LABEL": LABEL,
                "KERNELSCRIPT_TC_TRAFFIC_TRIALS": str(TRIALS),
                "KERNELSCRIPT_TC_TRAFFIC_SECONDS": str(SECONDS),
            },
            f"tc_traffic_{LABEL}_summary.json",
        ),
    ]

    child_results: dict[str, dict[str, object]] = {}
    for family, script, env_update, result_name in children:
        proc = run_script(script, env_update, timeout)
        if proc.returncode != 0:
            summary = {
                "status": "failed",
                "failed_family": family,
                "failed_script": script,
                "returncode": proc.returncode,
                "trials": TRIALS,
                "seconds_per_trial": SECONDS,
            }
            write(OUT_JSON, json.dumps(summary, indent=2, sort_keys=True) + "\n")
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 1
        child_results[family] = load_json(result_name)

    rows = normalize_rows(child_results["xdp"], "xdp") + normalize_rows(child_results["tc"], "tc")
    status = "ok" if all(result.get("status") == "ok" for result in child_results.values()) else "failed"
    summary = {
        "status": status,
        "description": "longer iperf3 TCP stress checks for XDP and TC pass/count objects",
        "run_label": LABEL,
        "trials": TRIALS,
        "seconds_per_trial": SECONDS,
        "rows": rows,
        "comparisons": {
            "xdp": child_results["xdp"]["comparisons"],
            "tc": child_results["tc"]["comparisons"],
        },
        "source_results": {
            "xdp": f"results/xdp_traffic_{LABEL}_summary.json",
            "tc": f"results/tc_traffic_{LABEL}_summary.json",
        },
    }

    fields = [
        "family",
        "name",
        "bench",
        "implementation",
        "object",
        "trials",
        "seconds_per_trial",
        "median_receiver_gbps",
        "min_receiver_gbps",
        "max_receiver_gbps",
        "median_sender_gbps",
        "median_map_mpps",
        "total_retransmits",
        "oracle_passed",
        "receiver_gbps_samples",
        "sender_gbps_samples",
        "retransmits_samples",
        "map_mpps_samples",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            for key in ["receiver_gbps_samples", "sender_gbps_samples", "retransmits_samples", "map_mpps_samples"]:
                out[key] = " ".join(str(value) for value in row[key])
            writer.writerow({key: out[key] for key in fields})

    write(OUT_JSON, json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: summary[key] for key in summary if key != "rows"}, indent=2, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
