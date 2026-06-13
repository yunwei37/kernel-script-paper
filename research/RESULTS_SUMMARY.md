Last updated: 2026-06-13
Stage at update: analyze
Source/command: `./experiments/run_xdp_traffic.py`, `./experiments/run_tc_traffic.py`, `./experiments/run_perf_event_loader.py`, and checked-in result summaries

# Results Summary

## Headline Result

The artifact now has local traffic-driven XDP and TC checks plus one generated
perf_event loader lifecycle check in addition to BPF_PROG_TEST_RUN
microbenchmarks. On fresh veth/netns pairs with iperf3 TCP, KernelScript and
hand-written C/eBPF pass/count objects all pass the traffic oracles. XDP count
medians are 17.4Gb/s for KernelScript and 17.5Gb/s for C/eBPF. TC count medians
are 87.0Gb/s for KernelScript and 90.6Gb/s for C/eBPF. The generated
perf_event loader and the hand-written C/libbpf loader both pass 5/5 attach,
counter-read, and detach trials.

## Completed Runs

| Run ID | Result file | Status | Key result |
|--------|-------------|--------|------------|
| R001 | `results/verifier_matrix_summary.json` | ok | 38/43 generated objects load and pin at least one program; build-success subset is 37/41. |
| R002 | `results/attach_matrix_summary.json` | ok | 27/27 verifier-clean single-section XDP objects attach/detach in isolated namespaces. |
| R003 | `results/xdp_traffic_summary.json` | ok | XDP pass/count KS and C baselines all pass iperf3 traffic; count gap is 0.6% in this local setup. |
| R004 | `results/tc_traffic_summary.json` | ok | TC ingress pass/count KS and C baselines all pass iperf3 traffic; count gap is 4.0% in this local setup. |
| R005 | `results/perf_event_loader_summary.json` | ok | Generated perf_event loader and C/libbpf baseline both pass 5/5 lifecycle trials with positive page-fault counters. |

## Anomalies And Negative Results

- The stricter verifier matrix reclassifies `local_global_vars` as
  `no_program_pinned`: `bpftool` returned success but pinned only maps because
  the XDP section was empty.
- The XDP traffic pass result includes one low KernelScript outlier
  (4.7Gb/s), so the pass range is a noise indicator rather than a performance
  comparison claim.
- The traffic experiments do not exercise ring buffers or struct_ops, and the
  perf_event run is lifecycle evidence rather than throughput evidence.

## Figure/Table Candidates

- Keep the current microbenchmark table for instruction-level mechanism
  isolation.
- Add or retain a short traffic paragraph rather than a full table until TC and
  other non-XDP workloads exist.

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
