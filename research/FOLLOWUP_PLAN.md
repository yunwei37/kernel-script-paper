# Follow-up Plan

Date: 2026-06-13

## Current Verdict

The artifact is stronger after adding strict verifier-load accounting, the
isolated XDP attach matrix, local XDP and TC traffic benchmarks, one generated
perf_event loader lifecycle latency check, a perf_event page-fault counter
workload, a ringbuf event-emission workload, a direct tcp-congestion struct_ops
load/attach/detach compatibility check, a loopback TCP workload through selected
BPF tcp-congestion algorithms, a callback-flag workload with clean and
loss-injected reachability profiles, a local struct_ops skeleton build repair,
a scheduler-extension load-only verifier diagnostic, and a broader 28-case static
negative corpus. It now also includes a longer XDP/TC traffic stress rerun.
It is closer to a top-systems weak accept, but still not there. The main
remaining gap is representative runtime evidence after the scheduler-extension
verifier-load fix, broader callback-level struct_ops behavior,
generated-dispatch-loop throughput beyond one perf_event lifecycle loader
workload, broader skeleton version coverage and compiler integration, and
non-local or longer-duration deployment methodology.

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
  lifecycle oracle and timing check: attach two perf_event programs, read
  counters, detach, and record end-to-end invocation latency over 20 trials.
- Added `experiments/run_perf_event_counter.py`, which compares generated and
  hand-written perf_event page-fault counter objects under a shared libbpf
  runner and requires BPF map counts to match perf counter reads.
- Added `experiments/run_ringbuf_workload.py`, which compares generated and
  hand-written XDP ringbuf event-emission objects under a shared libbpf runner
  and requires submitted events to equal received events with zero drops.
- Added `experiments/run_struct_ops_compat.py`, which compares generated and
  hand-written tcp-congestion struct_ops objects under a shared libbpf runner
  and requires load, attach, and detach success without generated skeletons.
- Added `experiments/run_struct_ops_workload.py`, which selects the generated
  and hand-written BPF tcp-congestion algorithms on loopback TCP sender sockets,
  transfers 1MiB, and requires byte-count and detach success.
- Added `experiments/run_struct_ops_callback_workload.py`, which instruments
  generated and hand-written tcp-congestion callbacks with BPF map flags,
  transfers 4MiB over clean loopback TCP and requires cong_avoid plus
  cwnd_event to be reached before detach. It also applies 5% loopback loss and
  requires ssthresh, cong_avoid, set_state, and cwnd_event in 5/5 trials per
  variant.
- Added `experiments/run_traffic_stress.py`, which reruns matched XDP and TC
  pass/count traffic checks for three 5s trials per variant while preserving
  the headline 1s summaries.
- Added `experiments/run_struct_ops_skeleton_repair.py`, which detects the
  local libbpf skeleton map-link mismatch, removes two generated map-link
  assignments, and repairs both affected generated struct_ops userspace builds.
- Added `experiments/run_sched_ext_verifier.py`, which compiles generated and
  hand-written scheduler-extension struct_ops objects, uses verifier loadall
  only, confirms the C/eBPF baseline pins 5 programs, confirms the generated
  object pins 12 programs, and leaves sched_ext disabled.
- Expanded `experiments/run_static_checks.py` to 28 deterministic cases,
  including 27 expected rejections across lifecycle, signature, map, type,
  symbol, config, helper-scope, kernel-context, perf-event group, ringbuf, and
  safety categories.
- Updated the paper-number generator, paper, README, and research plan so the
  verifier, attach, XDP traffic, TC traffic, perf_event loader latency, and
  perf_event counter/ringbuf/struct_ops/scheduler-extension/static-check
  results are generated from checked-in JSON summaries.

## Remaining Experiments For Weak-Accept Bar

1. Add a no-surprises scheduler-extension attach/workload baseline; also add broader callback-level
   struct_ops programs, broader skeleton version coverage with
   compiler-integrated generation, broader perf_event event types, and
   generated-dispatch-loop throughput.
2. Larger XDP and TC stress runs using isolated network
   namespaces, `xdp-bench`, `pktgen`, a controlled packet generator, or a
   non-local VM/NIC setup.
3. Packet-behavior checks for the XDP attach-matrix objects, not only
   attach/detach.
4. Further expand the static negative corpus beyond the current targeted
   28-case suite, especially kfunc signature mismatch and more attach/detach
   ordering variants.
5. Non-XDP workload balance beyond TC pass/count, perf_event lifecycle latency,
   page-fault counters, ringbuf emission, and loopback tcp-congestion checks so
   benchmark claims do not rest mostly on XDP programs.
