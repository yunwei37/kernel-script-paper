Last updated: 2026-06-13
Stage at update: claim-gate
Source/command: result-to-claim comparison after `./experiments/run_xdp_traffic.py`, `./experiments/run_tc_traffic.py`, `./experiments/run_perf_event_loader.py`, `./experiments/run_perf_event_counter.py`, and `./experiments/run_ringbuf_workload.py`

# Claim Verdict

| Claim | Verdict | Evidence | Supported wording | Missing evidence |
|-------|---------|----------|-------------------|------------------|
| C1 | partial | `results/evaluation_summary.json`, `results/examples_summary.csv`, `results/paper_numbers.tex` | KernelScript centralizes generated C/eBPF/userspace/build structure for the repository example corpus. | External application corpus and developer-effort baseline. |
| C2 | partial | `results/static_checks_summary.json`, unit-test summary, safety rejection row | KernelScript rejects selected covered lifecycle, context-signature, and stack-limit errors before load/attach. | Larger negative corpus and formal lifecycle coverage. |
| C3 | partial | `results/verifier_matrix_summary.json`, `results/attach_matrix_summary.json`, `results/perf_event_loader_summary.json`, `results/perf_event_counter_summary.json`, `results/ringbuf_workload_summary.json` | On the local host, most generated build-success objects load under a strict pinned-program criterion, 27/27 verifier-clean single-section XDP objects attach/detach in isolated namespaces, one generated perf_event loader completes attach/read/detach checks, matched perf_event counter objects execute a page-fault workload, and matched ringbuf objects submit and receive 50,000 events/trial with zero drops. | Broader generated-loader checks, struct_ops workloads, and non-local deployment workloads. |
| C4 | partial | `results/compiler_patch_ablation_summary.json`, `results/microbench_summary.json`, `results/xdp_traffic_summary.json`, `results/tc_traffic_summary.json`, `results/perf_event_counter_summary.json`, `results/ringbuf_workload_summary.json` | For the XDP array-map count benchmark, the main gap is a map-update lowering choice; a compiler patch matches C/eBPF in BPF_PROG_TEST_RUN. Local workloads now cover XDP and TC pass/count, perf_event page-fault counters, and ringbuf event emission, with 0.6%, 4.0%, 0.3%, and 2.8% local gaps respectively. | Longer stress/load sweeps, struct_ops matched baselines, broader perf_event workloads, generated-loader throughput, and upstreamed lowering. |

## Overall Gate

The paper should still avoid general runtime equivalence claims. The strongest
defensible wording is an artifact/prototype claim with measured example
coverage, strict verifier-load results, XDP attachability, local XDP/TC traffic
sanity checks, one perf_event generated-loader lifecycle check, one perf_event
page-fault counter workload, one ringbuf event-emission workload, and one
mechanism-isolating compiler patch.
