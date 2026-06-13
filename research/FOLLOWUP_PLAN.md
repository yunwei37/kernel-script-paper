# Follow-up Plan

Date: 2026-06-13

## Current Verdict

The artifact is stronger after adding strict verifier-load accounting, the
isolated XDP attach matrix, local XDP and TC traffic benchmarks, and one
generated perf_event loader lifecycle smoke test plus a perf_event page-fault
counter workload, but it is not yet a top-systems weak accept. The main
remaining gap is representative runtime evidence across ringbuf/struct_ops
workloads, generated-loader throughput, and stronger traffic/stress methodology.

## Completed In This Iteration

- Tightened `experiments/run_verifier_matrix.py` so a load is successful only
  when `bpftool prog loadall` succeeds and pins at least one BPF program.
- Added `experiments/run_attach_matrix.py`, which attaches and detaches
  verifier-clean single-section XDP objects on fresh veth devices inside
  isolated network namespaces.
- Added `experiments/run_xdp_traffic.py`, which compares matched KernelScript
  and hand-written C/eBPF XDP pass/count objects under iperf3 TCP traffic on
  fresh veth/netns pairs and reads the `counts` map as an execution oracle.
- Added `experiments/run_tc_traffic.py`, which compares matched KernelScript
  and hand-written C/eBPF TC ingress pass/count objects under iperf3 TCP traffic
  on fresh veth/netns pairs and reads the `counts` map as an execution oracle.
- Added `experiments/run_perf_event_loader.py`, which compares a generated
  KernelScript perf_event loader with a hand-written C/libbpf loader under a
  lifecycle oracle: attach two perf_event programs, read counters, and detach.
- Added `experiments/run_perf_event_counter.py`, which compares generated and
  hand-written perf_event page-fault counter objects under a shared libbpf
  runner and requires BPF map counts to match perf counter reads.
- Updated the paper-number generator, paper, README, and research plan so the
  new verifier, attach, XDP traffic, TC traffic, perf_event loader, and
  perf_event counter results are generated from checked-in JSON summaries.

## Remaining Experiments For Weak-Accept Bar

1. Sustained matched C/libbpf runtime baselines for ringbuf and struct_ops
   programs, plus broader perf_event event types.
2. Longer XDP and TC stress runs using isolated network
   namespaces, `xdp-bench`, `pktgen`, or a controlled packet generator.
3. Packet-behavior checks for the XDP attach-matrix objects, not only
   attach/detach.
4. Expanded static negative corpus for map type mismatch, invalid helper
   contexts, bad detach ordering, ringbuf misuse, and kfunc signature mismatch.
5. Non-XDP workload balance beyond TC pass/count, perf_event lifecycle smoke,
   and page-fault counters so benchmark claims do not rest mostly on XDP
   programs.
