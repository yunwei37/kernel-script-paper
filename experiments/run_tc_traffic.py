#!/usr/bin/env python3
"""Run traffic-driven TC ingress benchmarks against matched C/eBPF baselines."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("KERNELSCRIPT_REPO", ROOT / "kernelscript")).resolve()
RESULTS = ROOT / "results"
RUN_LABEL = os.environ.get("KERNELSCRIPT_TC_TRAFFIC_LABEL", os.environ.get("KERNELSCRIPT_TRAFFIC_LABEL", "")).strip()
if RUN_LABEL and not re.fullmatch(r"[A-Za-z0-9_]+", RUN_LABEL):
    raise SystemExit("KERNELSCRIPT_TC_TRAFFIC_LABEL must contain only letters, digits, and underscores")
RUN_NAME = "tc_traffic" if not RUN_LABEL else f"tc_traffic_{RUN_LABEL}"
BUILD = RESULTS / "build" / RUN_NAME
LOGS = RESULTS / "logs" / RUN_NAME
SUMMARY_JSON = RESULTS / f"{RUN_NAME}_summary.json"
SUMMARY_CSV = RESULTS / f"{RUN_NAME}_summary.csv"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"
TRIALS = int(os.environ.get("KERNELSCRIPT_TC_TRAFFIC_TRIALS", "10"))
SECONDS = int(os.environ.get("KERNELSCRIPT_TC_TRAFFIC_SECONDS", "1"))


def run(
    argv: list[str],
    cwd: Path = ROOT,
    timeout: int = 120,
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


def check(cmd: subprocess.CompletedProcess[str], label: str) -> None:
    if cmd.returncode != 0:
        raise RuntimeError(f"{label} failed\nstdout:\n{cmd.stdout}\nstderr:\n{cmd.stderr}")


def check_prerequisites() -> str | None:
    if run(["true"], sudo=True).returncode != 0:
        return "sudo -n unavailable"
    for cmd in ["bpftool", "clang", "ip", "iperf3", "make", "tc"]:
        if not shutil.which(cmd):
            return f"{cmd} unavailable"
    if not Path("/sys/kernel/btf/vmlinux").exists():
        return "missing /sys/kernel/btf/vmlinux"
    if not COMPILER.exists():
        return f"missing KernelScript compiler at {COMPILER}"
    return None


def compile_ks(name: str, source: Path) -> Path:
    out = BUILD / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    res = run([str(COMPILER), "compile", str(source), "-o", str(out)])
    write(LOGS / f"{name}.ks.stdout", res.stdout)
    write(LOGS / f"{name}.ks.stderr", res.stderr)
    check(res, f"{name} KernelScript compile")
    make = run(["make", "ebpf-only"], out)
    write(LOGS / f"{name}.make.stdout", make.stdout)
    write(LOGS / f"{name}.make.stderr", make.stderr)
    check(make, f"{name} eBPF build")
    objects = sorted(out.glob("*.ebpf.o"))
    if len(objects) != 1:
        raise RuntimeError(f"Expected one eBPF object in {out}, found {objects}")
    return objects[0]


def compile_c(name: str, source: Path, hand_dir: Path) -> Path:
    obj = hand_dir / f"{name}.o"
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
        str(hand_dir),
        "-c",
        str(source),
        "-o",
        str(obj),
    ]
    res = run(cmd)
    write(LOGS / f"{name}.clang.stdout", res.stdout)
    write(LOGS / f"{name}.clang.stderr", res.stderr)
    check(res, f"{name} clang")
    return obj


def prepare_handwritten() -> dict[str, Path]:
    hand_dir = BUILD / "handwritten"
    if hand_dir.exists():
        shutil.rmtree(hand_dir)
    hand_dir.mkdir(parents=True, exist_ok=True)
    btf = run(["bpftool", "btf", "dump", "file", "/sys/kernel/btf/vmlinux", "format", "c"])
    write(LOGS / "handwritten.btf.stdout", btf.stdout)
    write(LOGS / "handwritten.btf.stderr", btf.stderr)
    check(btf, "bpftool btf dump")
    write(hand_dir / "vmlinux.h", btf.stdout)
    return {
        "c_pass": compile_c("c_pass", ROOT / "experiments" / "baselines" / "tc_pass.c", hand_dir),
        "c_count": compile_c("c_count", ROOT / "experiments" / "baselines" / "tc_count.c", hand_dir),
    }


def hex_bytes(value: int, width: int) -> list[str]:
    return [f"{byte:02x}" for byte in value.to_bytes(width, byteorder="little", signed=False)]


def cleanup_namespace(ns: str) -> None:
    pids = run(["ip", "netns", "pids", ns], sudo=True)
    for pid in pids.stdout.split():
        run(["kill", pid], sudo=True)
    run(["ip", "netns", "del", ns], sudo=True)


def setup_namespace(idx: int) -> tuple[str, str, str, str, str, int]:
    pid = os.getpid() % 10000
    ns = f"kstctraf{pid}_{idx}"
    host_dev = f"kc{pid:04d}{idx:02d}h"
    peer_dev = f"kc{pid:04d}{idx:02d}n"
    host_ip = f"10.253.{idx}.1"
    peer_ip = f"10.253.{idx}.2"
    port = 34000 + ((os.getpid() + idx) % 20000)

    cleanup_namespace(ns)
    cmds = [
        ["ip", "netns", "add", ns],
        ["ip", "link", "add", host_dev, "type", "veth", "peer", "name", peer_dev],
        ["ip", "link", "set", peer_dev, "netns", ns],
        ["ip", "addr", "add", f"{host_ip}/24", "dev", host_dev],
        ["ip", "link", "set", host_dev, "up"],
        ["ip", "netns", "exec", ns, "ip", "addr", "add", f"{peer_ip}/24", "dev", peer_dev],
        ["ip", "netns", "exec", ns, "ip", "link", "set", "lo", "up"],
        ["ip", "netns", "exec", ns, "ip", "link", "set", peer_dev, "up"],
    ]
    for cmd in cmds:
        check(run(cmd, sudo=True), " ".join(cmd))
    run(["ping", "-c", "1", "-W", "1", peer_ip], timeout=5)
    return ns, host_dev, peer_dev, host_ip, peer_ip, port


def attach_tc(ns: str, peer_dev: str, obj: Path) -> int:
    check(
        run(["ip", "netns", "exec", ns, "tc", "qdisc", "add", "dev", peer_dev, "clsact"], sudo=True),
        f"tc qdisc add {peer_dev}",
    )
    attach = run(
        [
            "ip",
            "netns",
            "exec",
            ns,
            "tc",
            "filter",
            "add",
            "dev",
            peer_dev,
            "ingress",
            "bpf",
            "direct-action",
            "obj",
            str(obj),
            "sec",
            "tc/ingress",
        ],
        sudo=True,
    )
    check(attach, f"tc filter attach {obj}")
    show = run(["ip", "netns", "exec", ns, "tc", "filter", "show", "dev", peer_dev, "ingress"], sudo=True)
    check(show, f"tc filter show {peer_dev}")
    match = re.search(r"\bid ([0-9]+)\b", show.stdout + show.stderr)
    if not match:
        raise RuntimeError(f"attached TC program id not found:\n{show.stdout}\n{show.stderr}")
    return int(match.group(1))


def detach_tc(ns: str, peer_dev: str) -> None:
    run(["ip", "netns", "exec", ns, "tc", "qdisc", "del", "dev", peer_dev, "clsact"], sudo=True)


def map_ids_for_prog(prog_id: int) -> list[int]:
    res = run(["bpftool", "-j", "prog", "show", "id", str(prog_id)], sudo=True)
    check(res, f"bpftool prog show id {prog_id}")
    return [int(value) for value in json.loads(res.stdout).get("map_ids", [])]


def reset_count_map(map_id: int) -> None:
    res = run(
        [
            "bpftool",
            "map",
            "update",
            "id",
            str(map_id),
            "key",
            *hex_bytes(0, 4),
            "value",
            *hex_bytes(0, 8),
            "any",
        ],
        sudo=True,
    )
    check(res, f"reset map id {map_id}")


def read_count_map(map_id: int) -> int:
    res = run(
        ["bpftool", "-j", "map", "lookup", "id", str(map_id), "key", *hex_bytes(0, 4)],
        sudo=True,
    )
    check(res, f"lookup map id {map_id}")
    decoded = json.loads(res.stdout)
    formatted = decoded.get("formatted", {})
    if "value" in formatted:
        return int(formatted["value"])
    raw = bytes(int(part, 16) for part in decoded["value"])
    return int.from_bytes(raw, byteorder="little", signed=False)


def run_iperf_trial(ns: str, peer_ip: str, port: int, log_prefix: Path) -> dict[str, object]:
    server_stdout = (log_prefix.parent / f"{log_prefix.name}.server.stdout").open("w", encoding="utf-8")
    server_stderr = (log_prefix.parent / f"{log_prefix.name}.server.stderr").open("w", encoding="utf-8")
    server = subprocess.Popen(
        ["sudo", "-n", "ip", "netns", "exec", ns, "iperf3", "-s", "-1", "-J", "-p", str(port)],
        cwd=str(ROOT),
        text=True,
        stdout=server_stdout,
        stderr=server_stderr,
    )
    try:
        time.sleep(0.4)
        client = run(["iperf3", "-c", peer_ip, "-J", "-t", str(SECONDS), "-p", str(port)], timeout=SECONDS + 20)
        write(log_prefix.parent / f"{log_prefix.name}.client.stdout", client.stdout)
        write(log_prefix.parent / f"{log_prefix.name}.client.stderr", client.stderr)
        check(client, f"iperf3 client {peer_ip}:{port}")
        server_rc = server.wait(timeout=SECONDS + 20)
        if server_rc != 0:
            raise RuntimeError(f"iperf3 server failed with rc={server_rc}")
    finally:
        if server.poll() is None:
            server.kill()
            server.wait(timeout=5)
        server_stdout.close()
        server_stderr.close()

    parsed = json.loads(client.stdout)
    sent = parsed["end"]["sum_sent"]
    received = parsed["end"].get("sum_received", sent)
    return {
        "sender_bps": float(sent.get("bits_per_second", 0.0)),
        "receiver_bps": float(received.get("bits_per_second", 0.0)),
        "sender_bytes": int(sent.get("bytes", 0)),
        "receiver_bytes": int(received.get("bytes", 0)),
        "seconds": float(received.get("seconds", sent.get("seconds", SECONDS))),
        "retransmits": int(sent.get("retransmits", 0)),
    }


def trial(name: str, obj: Path, idx: int, needs_count: bool) -> dict[str, object]:
    ns, _host_dev, peer_dev, _host_ip, peer_ip, port = setup_namespace(idx)
    map_id: int | None = None
    try:
        prog_id = attach_tc(ns, peer_dev, obj)
        map_ids = map_ids_for_prog(prog_id)
        if needs_count:
            if not map_ids:
                raise RuntimeError(f"{name} expected a count map but program {prog_id} has none")
            map_id = map_ids[0]
            reset_count_map(map_id)
        result = run_iperf_trial(ns, peer_ip, port, LOGS / f"{name}.trial{idx}")
        if map_id is not None:
            count = read_count_map(map_id)
            result["tc_map_count"] = count
            result["tc_map_mpps"] = count / result["seconds"] / 1_000_000.0
        else:
            result["tc_map_count"] = ""
            result["tc_map_mpps"] = ""
        result["prog_id"] = prog_id
        result["map_id"] = map_id or ""
        result["oracle_passed"] = result["receiver_bytes"] > 0 and (
            not needs_count or int(result["tc_map_count"]) > 0
        )
        return result
    finally:
        detach_tc(ns, peer_dev)
        cleanup_namespace(ns)


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def summarize(name: str, bench: str, implementation: str, obj: Path, needs_count: bool, offset: int) -> dict[str, object]:
    samples = [trial(name, obj, offset + i, needs_count) for i in range(TRIALS)]
    receiver_gbps = [float(row["receiver_bps"]) / 1_000_000_000.0 for row in samples]
    sender_gbps = [float(row["sender_bps"]) / 1_000_000_000.0 for row in samples]
    map_mpps = [float(row["tc_map_mpps"]) for row in samples if row["tc_map_mpps"] != ""]
    return {
        "name": name,
        "bench": bench,
        "implementation": implementation,
        "object": str(obj.relative_to(ROOT)),
        "trials": TRIALS,
        "seconds_per_trial": SECONDS,
        "receiver_gbps_samples": receiver_gbps,
        "sender_gbps_samples": sender_gbps,
        "retransmits_samples": [int(row["retransmits"]) for row in samples],
        "tc_map_count_samples": [row["tc_map_count"] for row in samples],
        "tc_map_mpps_samples": map_mpps,
        "median_receiver_gbps": median(receiver_gbps),
        "min_receiver_gbps": min(receiver_gbps),
        "max_receiver_gbps": max(receiver_gbps),
        "median_sender_gbps": median(sender_gbps),
        "median_tc_map_mpps": median(map_mpps),
        "oracle_passed": all(bool(row["oracle_passed"]) for row in samples),
    }


def comparison(rows: dict[str, dict[str, object]], ks_name: str, c_name: str) -> dict[str, float]:
    ks = float(rows[ks_name]["median_receiver_gbps"])
    c = float(rows[c_name]["median_receiver_gbps"])
    return {
        "ks_median_receiver_gbps": ks,
        "c_median_receiver_gbps": c,
        "delta_gbps": ks - c,
        "ks_over_c_ratio": (ks / c) if c else 0.0,
        "overhead_pct": ((c - ks) / c * 100.0) if c else 0.0,
    }


def main() -> int:
    reason = check_prerequisites()
    if reason:
        summary = {"status": "skipped", "reason": reason}
        write(SUMMARY_JSON, json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return 0

    if BUILD.exists():
        shutil.rmtree(BUILD)
    if LOGS.exists():
        shutil.rmtree(LOGS)
    BUILD.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    objects = {
        "ks_pass": compile_ks("ks_pass", ROOT / "experiments" / "programs" / "tc_pass.ks"),
        "ks_count": compile_ks("ks_count", ROOT / "experiments" / "programs" / "tc_count.ks"),
    }
    objects.update(prepare_handwritten())

    row_list = [
        summarize("ks_pass", "pass", "kernelscript", objects["ks_pass"], False, 10),
        summarize("c_pass", "pass", "handwritten_c", objects["c_pass"], False, 20),
        summarize("ks_count", "count", "kernelscript", objects["ks_count"], True, 30),
        summarize("c_count", "count", "handwritten_c", objects["c_count"], True, 40),
    ]
    rows = {row["name"]: row for row in row_list}
    comparisons = {
        "pass": comparison(rows, "ks_pass", "c_pass"),
        "count": comparison(rows, "ks_count", "c_count"),
    }
    status = "ok" if all(row["oracle_passed"] for row in row_list) else "failed"
    summary = {
        "status": status,
        "description": "iperf3 TCP over veth/netns with TC ingress objects attached on the receiver-side veth.",
        "run_label": RUN_LABEL or "default",
        "trials": TRIALS,
        "seconds_per_trial": SECONDS,
        "rows": row_list,
        "comparisons": comparisons,
    }

    fields = [
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
        "median_tc_map_mpps",
        "oracle_passed",
        "receiver_gbps_samples",
        "sender_gbps_samples",
        "retransmits_samples",
        "tc_map_count_samples",
        "tc_map_mpps_samples",
    ]
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in row_list:
            out = dict(row)
            for key in [
                "receiver_gbps_samples",
                "sender_gbps_samples",
                "retransmits_samples",
                "tc_map_count_samples",
                "tc_map_mpps_samples",
            ]:
                out[key] = " ".join(str(value) for value in row[key])
            writer.writerow({key: out[key] for key in fields})

    write(SUMMARY_JSON, json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: summary[key] for key in summary if key != "rows"}, indent=2, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
