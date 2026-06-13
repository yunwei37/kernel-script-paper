# Follow-up Plan

Date: 2026-06-13

## Current Verdict

The artifact is stronger after adding strict verifier-load accounting and the
isolated XDP attach matrix plus a local XDP traffic benchmark, but it is not
yet a top-systems weak accept. The main remaining gap is representative runtime
evidence across non-XDP workloads and stronger traffic/stress methodology.

## Completed In This Iteration

- Tightened `experiments/run_verifier_matrix.py` so a load is successful only
  when `bpftool prog loadall` succeeds and pins at least one BPF program.
- Added `experiments/run_attach_matrix.py`, which attaches and detaches
  verifier-clean single-section XDP objects on fresh veth devices inside
  isolated network namespaces.
- Added `experiments/run_xdp_traffic.py`, which compares matched KernelScript
  and hand-written C/eBPF XDP pass/count objects under iperf3 TCP traffic on
  fresh veth/netns pairs and reads the `counts` map as an execution oracle.
- Updated the paper-number generator, paper, README, and research plan so the
  new verifier, attach, and traffic results are generated from checked-in JSON
  summaries.

## Remaining Experiments For Weak-Accept Bar

1. Matched C/libbpf runtime baselines for at least XDP pass/drop/count,
   TC ingress, perf_event, and ringbuf programs.
2. Longer XDP stress runs and TC traffic benchmarks using isolated network
   namespaces, `xdp-bench`, `pktgen`, or a controlled packet generator.
3. Packet-behavior checks for the XDP attach-matrix objects, not only
   attach/detach.
4. Expanded static negative corpus for map type mismatch, invalid helper
   contexts, bad detach ordering, ringbuf misuse, and kfunc signature mismatch.
5. Non-XDP workload balance so example and benchmark claims do not rest mostly
   on XDP programs.
