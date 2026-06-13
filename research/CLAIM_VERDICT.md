Last updated: 2026-06-13
Stage at update: claim-gate
Source/command: result-to-claim comparison after `./experiments/run_static_checks.py`, `./experiments/run_xdp_traffic.py`, `./experiments/run_tc_traffic.py`, `./experiments/run_traffic_stress.py`, `./experiments/run_perf_event_loader.py`, `./experiments/run_perf_event_counter.py`, `./experiments/run_ringbuf_workload.py`, `./experiments/run_struct_ops_compat.py`, and `./experiments/run_struct_ops_skeleton_repair.py`

# Claim Verdict

| Claim | Verdict | Evidence | Supported wording | Missing evidence |
|-------|---------|----------|-------------------|------------------|
| C1 | partial | `results/evaluation_summary.json`, `results/examples_summary.csv`, `results/paper_numbers.tex` | KernelScript centralizes generated C/eBPF/userspace/build structure for the repository example corpus. | External application corpus and developer-effort baseline. |
| C2 | partial | `results/static_checks_summary.json`, unit-test summary, safety rejection row | KernelScript rejects selected covered lifecycle, program-signature, map-type, ringbuf-API, config-boundary, symbol-validation, type-system, and stack-limit errors before load/attach. | Formal lifecycle coverage, helper-contract coverage, and verifier-failure equivalence against hand-written C/libbpf. |
| C3 | partial | `results/verifier_matrix_summary.json`, `results/attach_matrix_summary.json`, `results/perf_event_loader_summary.json`, `results/perf_event_counter_summary.json`, `results/ringbuf_workload_summary.json`, `results/struct_ops_compat_summary.json`, `results/struct_ops_skeleton_repair_summary.json` | On the local host, most generated build-success objects load under a strict pinned-program criterion, 27/27 verifier-clean single-section XDP objects attach/detach in isolated namespaces, one generated perf_event loader completes 20/20 attach/read/detach trials with 11.1ms median end-to-end invocation latency, matched perf_event counter objects execute a page-fault workload, matched ringbuf objects submit and receive 50,000 events/trial with zero drops, generated plus C/eBPF tcp-congestion struct_ops objects load, attach, and detach in 3/3 direct libbpf trials, and the two generated struct_ops userspace build failures repair from 0/2 to 2/2 on this host. | Broader generated-loader dispatch-loop checks, upstream-integrated and cross-version skeleton generation, scheduler-extension struct_ops workloads, and non-local deployment workloads. |
| C4 | partial | `results/compiler_patch_ablation_summary.json`, `results/microbench_summary.json`, `results/xdp_traffic_summary.json`, `results/tc_traffic_summary.json`, `results/traffic_stress_summary.json`, `results/perf_event_loader_summary.json`, `results/perf_event_counter_summary.json`, `results/ringbuf_workload_summary.json`, `results/struct_ops_compat_summary.json`, `results/struct_ops_skeleton_repair_summary.json` | For the XDP array-map count benchmark, the main gap is a map-update lowering choice; a compiler patch matches C/eBPF in BPF_PROG_TEST_RUN. Local checks now cover XDP and TC pass/count, a longer 3 x 5s XDP/TC stress rerun, perf_event generated-loader lifecycle latency, perf_event page-fault counters, ringbuf event emission, direct tcp-congestion struct_ops load/attach/detach compatibility, and a local generated struct_ops skeleton build repair. The stress rerun passes all oracles; in this local run, XDP-count and TC-count medians differ by 2.0% and 5.0%. | Larger stress/load sweeps, workload-level struct_ops matched baselines, broader perf_event workloads, generated-dispatch-loop throughput, upstreamed lowering, and broader skeleton version coverage. |

## Overall Gate

The paper should still avoid general runtime equivalence claims. The strongest
defensible wording is an artifact/prototype claim with measured example
coverage, strict verifier-load results, XDP attachability, local XDP/TC traffic
sanity checks plus a short stress rerun, one perf_event generated-loader
lifecycle latency check, one perf_event page-fault counter workload, one ringbuf
event-emission workload, one direct struct_ops compatibility check, one local
struct_ops skeleton build repair, and one mechanism-isolating compiler patch.
