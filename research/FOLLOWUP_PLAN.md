# Follow-up Plan

Date: 2026-06-13

## Current Verdict

The artifact is stronger after adding strict verifier-load accounting, the
isolated XDP attach matrix, local XDP and TC traffic benchmarks, one generated
perf_event loader lifecycle smoke test, a perf_event page-fault counter
workload, a ringbuf event-emission workload, a direct tcp-congestion struct_ops
load/attach/detach compatibility check, and a broader 23-case static negative
corpus.
It is still not yet a top-systems weak accept. The main remaining gap is
representative runtime evidence across scheduler-extension or workload-level
struct_ops, generated-loader throughput, and stronger traffic/stress
methodology.

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
- Added `experiments/run_ringbuf_workload.py`, which compares generated and
  hand-written XDP ringbuf event-emission objects under a shared libbpf runner
  and requires submitted events to equal received events with zero drops.
- Added `experiments/run_struct_ops_compat.py`, which compares generated and
  hand-written tcp-congestion struct_ops objects under a shared libbpf runner
  and requires load, attach, and detach success without generated skeletons.
- Expanded `experiments/run_static_checks.py` to 23 deterministic cases,
  including 22 expected rejections across lifecycle, signature, map, type,
  symbol, config, ringbuf, and safety categories.
- Updated the paper-number generator, paper, README, and research plan so the
  new verifier, attach, XDP traffic, TC traffic, perf_event loader, and
  perf_event counter/ringbuf/struct_ops/static-check results are generated from
  checked-in JSON summaries.

## Remaining Experiments For Weak-Accept Bar

1. Sustained matched C/libbpf runtime baselines for scheduler-extension or
   workload-level struct_ops programs, plus broader perf_event event types and
   generated-loader throughput.
2. Longer XDP and TC stress runs using isolated network
   namespaces, `xdp-bench`, `pktgen`, or a controlled packet generator.
3. Packet-behavior checks for the XDP attach-matrix objects, not only
   attach/detach.
4. Expanded static negative corpus beyond the current targeted 23-case suite,
   especially invalid helper contracts, kfunc signature mismatch, and more
   attach/detach ordering variants.
5. Non-XDP workload balance beyond TC pass/count, perf_event lifecycle smoke,
   and page-fault counters so benchmark claims do not rest mostly on XDP
   programs.
