# Follow-up Plan

Date: 2026-06-13

## Current Verdict

The artifact is stronger after adding strict verifier-load accounting and the
isolated XDP attach matrix, but it is not yet a top-systems weak accept. The
main remaining gap is representative runtime evidence with matched C/libbpf
baselines and real traffic.

## Completed In This Iteration

- Tightened `experiments/run_verifier_matrix.py` so a load is successful only
  when `bpftool prog loadall` succeeds and pins at least one BPF program.
- Added `experiments/run_attach_matrix.py`, which attaches and detaches
  verifier-clean single-section XDP objects on fresh veth devices inside
  isolated network namespaces.
- Updated the paper-number generator, paper, README, and research plan so the
  new verifier and attach results are generated from checked-in JSON summaries.

## Remaining Experiments For Weak-Accept Bar

1. Matched C/libbpf runtime baselines for at least XDP pass/drop/count,
   TC ingress, perf_event, and ringbuf programs.
2. Traffic-driven XDP and TC benchmarks using isolated network namespaces,
   `xdp-bench`, `pktgen`, or a controlled packet generator.
3. Packet-behavior checks for the XDP attach-matrix objects, not only
   attach/detach.
4. Expanded static negative corpus for map type mismatch, invalid helper
   contexts, bad detach ordering, ringbuf misuse, and kfunc signature mismatch.
5. Non-XDP workload balance so example and benchmark claims do not rest mostly
   on XDP programs.
