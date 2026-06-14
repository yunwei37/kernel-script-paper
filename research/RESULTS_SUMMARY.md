Last updated: 2026-06-13
Stage at update: analyze
Source/command: `./experiments/run_xdp_traffic.py`, `./experiments/run_tc_traffic.py`, `./experiments/run_traffic_stress.py`, `./experiments/run_perf_event_loader.py`, `./experiments/run_perf_event_counter.py`, `./experiments/run_ringbuf_workload.py`, `./experiments/run_struct_ops_workload.py`, `./experiments/run_struct_ops_callback_workload.py`, and checked-in result summaries

# Results Summary

## Headline Result

The artifact now has a broader 23-case static rejection corpus, local
traffic-driven XDP and TC checks, one generated perf_event loader lifecycle
latency check, one perf_event page-fault counter workload, and one ringbuf
event-emission workload, direct tcp-congestion struct_ops load/attach/detach
compatibility, a loopback TCP workload through selected BPF tcp-congestion
algorithms, a callback-flag workload for cong_avoid/cwnd_event reachability, a
version-aware struct_ops skeleton build repair, and a longer XDP/TC traffic
stress rerun in addition to BPF_PROG_TEST_RUN microbenchmarks. On
fresh veth/netns
pairs with iperf3 TCP, KernelScript and hand-written C/eBPF pass/count objects
all pass the traffic oracles. XDP count medians are 17.4Gb/s for KernelScript
and 17.5Gb/s for C/eBPF. TC count medians are 87.0Gb/s for KernelScript and
90.6Gb/s for C/eBPF. The generated perf_event loader and the hand-written
C/libbpf loader both pass 20/20 attach, counter-read, and detach trials. Median
end-to-end invocation latencies are 11.1ms and 15.2ms, with p90 latencies of
44.1ms and 40.3ms, respectively. The
perf_event counter workload reports 1.13 million events/s for both generated
and hand-written objects with exact BPF/perf counter agreement. The ringbuf
workload reports 2.08 versus 2.14 million events/s with exact
submitted/received agreement and zero drops. The struct_ops compatibility
check loads, attaches, and detaches both generated and C/eBPF tcp-congestion
objects in 3/3 privileged trials without using generated skeletons. The
struct_ops TCP workload selects the registered generated and C/eBPF BPF
congestion-control algorithms on loopback sender sockets, transfers 1MiB, and
detaches in 10/10 trials for both variants. The callback-flag workload
transfers 4MiB and reaches cong_avoid plus cwnd_event in 10/10 trials for both
generated and C/eBPF variants. The
struct_ops skeleton repair changes the two original generated userspace build
failures from 0/2 to 2/2 repaired builds on this host by removing 2
version-incompatible map-link assignments. The stress
rerun uses three 5s iperf3 trials per XDP/TC pass/count variant; all oracles
pass, with XDP count medians of 17.8 versus 18.1Gb/s and TC count medians of
86.5 versus 91.1Gb/s for KernelScript and C/eBPF respectively.

## Completed Runs

| Run ID | Result file | Status | Key result |
|--------|-------------|--------|------------|
| R000 | `results/static_checks_summary.json` | ok | 23/23 static cases match expectation, including 22 expected rejections across lifecycle, signature, map, type, symbol, config, ringbuf, and safety categories. |
| R001 | `results/verifier_matrix_summary.json` | ok | 38/43 generated objects load and pin at least one program; build-success subset is 37/41. |
| R002 | `results/attach_matrix_summary.json` | ok | 27/27 verifier-clean single-section XDP objects attach/detach in isolated namespaces. |
| R003 | `results/xdp_traffic_summary.json` | ok | XDP pass/count KS and C baselines all pass iperf3 traffic; count gap is 0.6% in this local setup. |
| R004 | `results/tc_traffic_summary.json` | ok | TC ingress pass/count KS and C baselines all pass iperf3 traffic; count gap is 4.0% in this local setup. |
| R005 | `results/perf_event_loader_summary.json` | ok | Generated perf_event loader and C/libbpf baseline both pass 20/20 lifecycle trials; median invocation latencies are 11.1ms and 15.2ms, with p90 latencies of 44.1ms and 40.3ms. |
| R006 | `results/perf_event_counter_summary.json` | ok | Perf_event page-fault counter objects both pass 10/10 trials; median BPF map counts exactly match perf counts at 262147 events. |
| R007 | `results/ringbuf_workload_summary.json` | ok | Ringbuf event-emission objects both pass 10/10 trials; submitted and received counts match at 50000 events with zero drops. |
| R008 | `results/struct_ops_compat_summary.json` | ok | Generated and C/eBPF tcp-congestion struct_ops objects both load, attach, and detach in 3/3 trials through one direct libbpf runner. |
| R009 | `results/traffic_stress_summary.json` | ok | Longer 3 x 5s XDP/TC traffic stress rerun passes all oracles; XDP count gap is 2.0%, TC count gap is 5.0% in this local setup. |
| R010 | `results/struct_ops_skeleton_repair_summary.json` | ok | Original generated struct_ops userspace builds are 0/2; after a local version-aware skeleton header repair, 2/2 generated userspace projects build. |
| R011 | `results/struct_ops_workload_summary.json` | ok | Generated and C/eBPF tcp-congestion objects each complete 10/10 loopback TCP workload trials with algorithm selection, full byte transfer, and detach success. |
| R012 | `results/struct_ops_callback_workload_summary.json` | ok | Generated and C/eBPF tcp-congestion objects each complete 10/10 4MiB loopback TCP workload trials and set cong_avoid plus cwnd_event flags in 10/10 trials. |

## Anomalies And Negative Results

- The stricter verifier matrix reclassifies `local_global_vars` as
  `no_program_pinned`: `bpftool` returned success but pinned only maps because
  the XDP section was empty.
- The XDP traffic pass result includes one low KernelScript outlier
  (4.7Gb/s), so the pass range is a noise indicator rather than a performance
  comparison claim.
- The longer stress rerun still uses local veth TCP rather than NIC-rate
  traffic. It records local retransmits in the XDP stress variants and one TC
  KernelScript count trial, so the stress result supports stability/oracle
  claims more strongly than precise throughput ranking.
- The struct_ops workload exercises socket-level TCP algorithm selection and
  byte transfer, and the callback-flag workload confirms cong_avoid/cwnd_event
  reachability for that loopback transfer. It still does not measure production
  TCP performance, cover every tcp-congestion callback, or cover
  scheduler-extension struct_ops. The skeleton repair validates one local
  generated-userspace build fix, but it does not run the generated binaries or
  prove portability across libbpf versions. The perf_event counter, ringbuf,
  and direct struct_ops runs are object checks through a shared libbpf runner,
  and the generated-loader latency check is one perf_event lifecycle workload
  rather than a broad generated-dispatch-loop throughput study.

## Figure/Table Candidates

- Keep the current microbenchmark table for instruction-level mechanism
  isolation.
- Keep compact runtime paragraphs for ringbuf and struct_ops rather than full
  tables; the draft remains space-bound.

## Result Files Used

- `results/evaluation_summary.json`
- `results/static_checks_summary.json`
- `results/verifier_matrix_summary.json`
- `results/attach_matrix_summary.json`
- `results/microbench_summary.json`
- `results/compiler_patch_ablation_summary.json`
- `results/xdp_traffic_summary.json`
- `results/tc_traffic_summary.json`
- `results/perf_event_loader_summary.json`
- `results/perf_event_counter_summary.json`
- `results/ringbuf_workload_summary.json`
- `results/struct_ops_compat_summary.json`
- `results/struct_ops_workload_summary.json`
- `results/struct_ops_callback_workload_summary.json`
- `results/struct_ops_skeleton_repair_summary.json`
- `results/traffic_stress_summary.json`
- `results/xdp_traffic_stress_summary.json`
- `results/tc_traffic_stress_summary.json`
