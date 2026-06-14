#!/usr/bin/env python3
"""Run a small external-source port/build/runtime check.

This experiment uses one pinned public xdp-tutorial program as the source
workload. It is not an automated translator or broad portability result. The
claim tested here is narrower: a manually written KernelScript port of the
external XDP map-counter example can build through the generated Makefile, while
the original external C/eBPF source can compile directly with clang. Both
objects then attach, run on traffic, and update the same XDP_PASS counter key.
"""

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
BUILD = RESULTS / "build" / "external_port"
LOGS = RESULTS / "logs" / "external_port"
SUMMARY_JSON = RESULTS / "external_port_summary.json"
SUMMARY_CSV = RESULTS / "external_port_summary.csv"
COMPILER = REPO / "_build" / "default" / "src" / "main.exe"

TRIALS = int(os.environ.get("KERNELSCRIPT_EXTERNAL_PORT_TRIALS", "5"))
SECONDS = int(os.environ.get("KERNELSCRIPT_EXTERNAL_PORT_SECONDS", "1"))
XDP_PASS_KEY = 2

XDP_TUTORIAL_URL = "https://github.com/xdp-project/xdp-tutorial.git"
XDP_TUTORIAL_COMMIT = "4e2bf5658434e8ae12f281b9b182bb188766a319"
EXTERNAL_WORKLOAD = "basic03-map-counter"
EXTERNAL_C_SOURCE = Path("basic03-map-counter") / "xdp_prog_kern.c"
KS_PORT_SOURCE = ROOT / "experiments" / "external_ports" / "xdp_tutorial_basic03.ks"


def run(argv: list[str], cwd: Path = ROOT, timeout: int = 120, sudo: bool = False) -> subprocess.CompletedProcess[str]:
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
        check=False,
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
    for cmd in ["bpftool", "clang", "gcc", "git", "ip", "iperf3", "make"]:
        if not shutil.which(cmd):
            return f"{cmd} unavailable"
    if not Path("/sys/kernel/btf/vmlinux").exists():
        return "missing /sys/kernel/btf/vmlinux"
    if not COMPILER.exists():
        return f"missing KernelScript compiler at {COMPILER}"
    if not KS_PORT_SOURCE.exists():
        return f"missing KernelScript port source at {KS_PORT_SOURCE}"
    return None


def prepare_external_repo() -> Path:
    repo_dir = BUILD / "xdp-tutorial"
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    repo_dir.mkdir(parents=True, exist_ok=True)
    check(run(["git", "init", "-q"], repo_dir), "git init xdp-tutorial")
    check(run(["git", "remote", "add", "origin", XDP_TUTORIAL_URL], repo_dir), "git remote xdp-tutorial")
    check(
        run(["git", "fetch", "--depth", "1", "origin", XDP_TUTORIAL_COMMIT], repo_dir, timeout=240),
        "git fetch xdp-tutorial",
    )
    check(run(["git", "checkout", "-q", "FETCH_HEAD"], repo_dir), "git checkout xdp-tutorial")
    return repo_dir


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


def compile_ks_port() -> Path:
    out = BUILD / "ks_xdp_tutorial_basic03"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    res = run([str(COMPILER), "compile", str(KS_PORT_SOURCE), "-o", str(out)])
    write(LOGS / "ks_port.compile.stdout", res.stdout)
    write(LOGS / "ks_port.compile.stderr", res.stderr)
    check(res, "KernelScript external port compile")
    make = run(["make", "ebpf-only"], out)
    write(LOGS / "ks_port.make.stdout", make.stdout)
    write(LOGS / "ks_port.make.stderr", make.stderr)
    check(make, "KernelScript external port eBPF build")
    objects = sorted(out.glob("*.ebpf.o"))
    if len(objects) != 1:
        raise RuntimeError(f"Expected one generated eBPF object in {out}, found {objects}")
    return objects[0]


def multiarch_include() -> list[str]:
    res = run(["gcc", "-print-multiarch"])
    if res.returncode != 0:
        return []
    include = Path("/usr/include") / res.stdout.strip()
    return ["-I", str(include)] if include.exists() else []


def compile_external_c(repo_dir: Path) -> Path:
    source = repo_dir / EXTERNAL_C_SOURCE
    if not source.exists():
        raise RuntimeError(f"missing external C source {source}")
    out_dir = BUILD / "external_c"
    out_dir.mkdir(parents=True, exist_ok=True)
    obj = out_dir / "xdp_prog_kern.o"
    cmd = [
        "clang",
        "-target",
        "bpf",
        "-O2",
        "-g",
        "-Wall",
        "-Wextra",
        *multiarch_include(),
        "-I",
        str(repo_dir / "basic03-map-counter"),
        "-I",
        str(repo_dir / "common"),
        "-c",
        str(source),
        "-o",
        str(obj),
    ]
    res = run(cmd)
    write(LOGS / "external_c.clang.stdout", res.stdout)
    write(LOGS / "external_c.clang.stderr", res.stderr)
    check(res, "external C/eBPF compile")
    return obj


def hex_bytes(value: int, width: int) -> list[str]:
    return [f"{byte:02x}" for byte in value.to_bytes(width, byteorder="little", signed=False)]


def cleanup_namespace(ns: str) -> None:
    pids = run(["ip", "netns", "pids", ns], sudo=True)
    for pid in pids.stdout.split():
        run(["kill", pid], sudo=True)
    run(["ip", "netns", "del", ns], sudo=True)


def setup_namespace(idx: int) -> tuple[str, str, str, int]:
    pid = os.getpid() % 10000
    ns = f"ksext{pid}_{idx}"
    host_dev = f"ke{pid:04d}{idx:02d}h"
    peer_dev = f"ke{pid:04d}{idx:02d}n"
    host_ip = f"10.254.{idx}.1"
    peer_ip = f"10.254.{idx}.2"
    port = 37000 + ((os.getpid() + idx) % 20000)

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
    return ns, peer_dev, peer_ip, port


def attach_xdp(ns: str, peer_dev: str, obj: Path) -> int:
    attach = run(
        ["ip", "netns", "exec", ns, "ip", "link", "set", "dev", peer_dev, "xdp", "obj", str(obj), "sec", "xdp"],
        sudo=True,
    )
    check(attach, f"attach {obj}")
    show = run(["ip", "netns", "exec", ns, "ip", "-d", "link", "show", "dev", peer_dev], sudo=True)
    check(show, f"show {peer_dev}")
    match = re.search(r"prog/xdp id ([0-9]+)", show.stdout + show.stderr)
    if not match:
        raise RuntimeError(f"attached program id not found in ip output:\n{show.stdout}\n{show.stderr}")
    return int(match.group(1))


def detach_xdp(ns: str, peer_dev: str) -> None:
    run(["ip", "netns", "exec", ns, "ip", "link", "set", "dev", peer_dev, "xdp", "off"], sudo=True)


def map_ids_for_prog(prog_id: int) -> list[int]:
    res = run(["bpftool", "-j", "prog", "show", "id", str(prog_id)], sudo=True)
    check(res, f"bpftool prog show id {prog_id}")
    return [int(value) for value in json.loads(res.stdout).get("map_ids", [])]


def reset_rx_packets(map_id: int) -> None:
    res = run(
        [
            "bpftool",
            "map",
            "update",
            "id",
            str(map_id),
            "key",
            *hex_bytes(XDP_PASS_KEY, 4),
            "value",
            *hex_bytes(0, 8),
            "any",
        ],
        sudo=True,
    )
    check(res, f"reset map id {map_id}")


def decode_rx_packets(decoded: object) -> int:
    if isinstance(decoded, int):
        return decoded
    if isinstance(decoded, list):
        raw = bytes(int(part, 16) if isinstance(part, str) else int(part) for part in decoded)
        return int.from_bytes(raw[:8], byteorder="little", signed=False)
    if isinstance(decoded, dict):
        if "rx_packets" in decoded:
            return int(decoded["rx_packets"])
        if "value" in decoded:
            return decode_rx_packets(decoded["value"])
        for value in decoded.values():
            try:
                return decode_rx_packets(value)
            except (TypeError, ValueError, KeyError):
                continue
    raise ValueError(f"cannot decode rx_packets from {decoded!r}")


def read_rx_packets(map_id: int) -> int:
    res = run(
        ["bpftool", "-j", "map", "lookup", "id", str(map_id), "key", *hex_bytes(XDP_PASS_KEY, 4)],
        sudo=True,
    )
    check(res, f"lookup map id {map_id}")
    decoded = json.loads(res.stdout)
    if "formatted" in decoded:
        try:
            return decode_rx_packets(decoded["formatted"])
        except ValueError:
            pass
    return decode_rx_packets(decoded)


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


def trial(name: str, obj: Path, idx: int) -> dict[str, object]:
    ns, peer_dev, peer_ip, port = setup_namespace(idx)
    try:
        prog_id = attach_xdp(ns, peer_dev, obj)
        map_ids = map_ids_for_prog(prog_id)
        if len(map_ids) != 1:
            raise RuntimeError(f"{name} expected exactly one map, program {prog_id} has {map_ids}")
        map_id = map_ids[0]
        reset_rx_packets(map_id)
        result = run_iperf_trial(ns, peer_ip, port, LOGS / f"{name}.trial{idx}")
        rx_packets = read_rx_packets(map_id)
        result.update(
            {
                "prog_id": prog_id,
                "map_id": map_id,
                "xdp_pass_key": XDP_PASS_KEY,
                "rx_packets": rx_packets,
                "rx_mpps": rx_packets / result["seconds"] / 1_000_000.0,
                "oracle_passed": result["receiver_bytes"] > 0 and rx_packets > 0,
            }
        )
        return result
    finally:
        detach_xdp(ns, peer_dev)
        cleanup_namespace(ns)


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def summarize(name: str, implementation: str, obj: Path, offset: int) -> dict[str, object]:
    samples = [trial(name, obj, offset + i) for i in range(TRIALS)]
    receiver_gbps = [float(row["receiver_bps"]) / 1_000_000_000.0 for row in samples]
    rx_mpps = [float(row["rx_mpps"]) for row in samples]
    return {
        "name": name,
        "implementation": implementation,
        "object": str(obj.relative_to(ROOT)),
        "trials": TRIALS,
        "seconds_per_trial": SECONDS,
        "receiver_gbps_samples": receiver_gbps,
        "retransmits_samples": [int(row["retransmits"]) for row in samples],
        "rx_packet_samples": [int(row["rx_packets"]) for row in samples],
        "rx_mpps_samples": rx_mpps,
        "median_receiver_gbps": median(receiver_gbps),
        "min_receiver_gbps": min(receiver_gbps),
        "max_receiver_gbps": max(receiver_gbps),
        "median_rx_mpps": median(rx_mpps),
        "oracle_passed": all(bool(row["oracle_passed"]) for row in samples),
    }


def comparison(rows: dict[str, dict[str, object]]) -> dict[str, float]:
    ks = float(rows["kernelscript_port"]["median_receiver_gbps"])
    external_c = float(rows["external_c"]["median_receiver_gbps"])
    return {
        "ks_median_receiver_gbps": ks,
        "external_c_median_receiver_gbps": external_c,
        "delta_gbps": ks - external_c,
        "ks_over_external_c_ratio": (ks / external_c) if external_c else 0.0,
    }


def main() -> int:
    reason = check_prerequisites()
    if reason:
        summary = {"status": "skipped", "reason": reason}
        write(SUMMARY_JSON, json.dumps(summary, indent=2, sort_keys=True) + "\n")
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if BUILD.exists():
        shutil.rmtree(BUILD)
    if LOGS.exists():
        shutil.rmtree(LOGS)
    BUILD.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    external_repo = prepare_external_repo()
    external_source = external_repo / EXTERNAL_C_SOURCE
    objects = {
        "kernelscript_port": compile_ks_port(),
        "external_c": compile_external_c(external_repo),
    }

    row_list = [
        summarize("kernelscript_port", "kernelscript", objects["kernelscript_port"], 10),
        summarize("external_c", "original_external_c", objects["external_c"], 30),
    ]
    rows = {row["name"]: row for row in row_list}
    status = "ok" if all(row["oracle_passed"] for row in row_list) else "failed"
    summary = {
        "status": status,
        "description": "Manual KernelScript port of a pinned xdp-tutorial XDP map-counter example, checked against the original external C/eBPF source under traffic.",
        "scope": {
            "source_repo": XDP_TUTORIAL_URL,
            "source_commit": XDP_TUTORIAL_COMMIT,
            "source_workload": EXTERNAL_WORKLOAD,
            "external_c_source": str(EXTERNAL_C_SOURCE),
            "kernelscript_port_source": str(KS_PORT_SOURCE.relative_to(ROOT)),
            "interpretation": "one manual external application port/build/runtime check, not an automated translation, performance ranking, or broad portability claim",
        },
        "semantic_oracle": "Both objects attach as XDP programs, pass iperf3 traffic, and increment map key XDP_PASS for rx_packets.",
        "trials": TRIALS,
        "seconds_per_trial": SECONDS,
        "source_sloc": {
            "external_c_ebpf_sloc": nonblank_noncomment_sloc(external_source),
            "kernelscript_port_sloc": nonblank_noncomment_sloc(KS_PORT_SOURCE),
        },
        "rows": row_list,
        "comparison": comparison(rows),
    }

    fields = [
        "name",
        "implementation",
        "object",
        "trials",
        "seconds_per_trial",
        "median_receiver_gbps",
        "min_receiver_gbps",
        "max_receiver_gbps",
        "median_rx_mpps",
        "oracle_passed",
        "receiver_gbps_samples",
        "rx_packet_samples",
        "rx_mpps_samples",
        "retransmits_samples",
    ]
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in row_list:
            out = dict(row)
            for key in ["receiver_gbps_samples", "rx_packet_samples", "rx_mpps_samples", "retransmits_samples"]:
                out[key] = " ".join(str(value) for value in row[key])
            writer.writerow({key: out[key] for key in fields})

    write(SUMMARY_JSON, json.dumps(summary, indent=2, sort_keys=True) + "\n")
    printable = {key: summary[key] for key in summary if key != "rows"}
    print(json.dumps(printable, indent=2, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
