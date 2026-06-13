Last updated: 2026-06-13
Stage at update: claims
Source/command: auto-research-orchestrator resume on kernel-script-paper

# Claim Ledger

| ID | Claim | Scope | Metric/evidence needed | Status |
|----|-------|-------|------------------------|--------|
| C1 | KernelScript centralizes recurring multi-artifact eBPF project structure while preserving conventional libbpf-compatible outputs. | Repository examples at commit `ccb15b4` on the recorded host toolchain. | Example compile/build matrix, generated SLOC expansion, feature marker coverage, generated object inventory. | partial |
| C2 | KernelScript rejects selected verifier-relevant, lifecycle, signature, map, ringbuf, config-boundary, symbol, and type mistakes before kernel load/attach. | Covered compiler checks and 23-case static-check corpus only. | Unit tests, static negative corpus, stack-limit diagnostic, lifecycle/signature/map/ringbuf/config/type diagnostic checks. | partial |
| C3 | Generated eBPF objects remain compatible with the local kernel verifier, can attach for an XDP subset, and perf_event/ringbuf/struct_ops examples can complete local lifecycle or object-level compatibility checks. | Local Linux `6.15.11-061511-generic`, generated repository examples, verifier-clean single-section XDP subset, perf_event examples, one ringbuf XDP object workload, and one tcp-congestion struct_ops object. | Strict `bpftool prog loadall` matrix with pinned program check, isolated netns/veth XDP attach matrix, perf_event generated-loader lifecycle latency check, perf_event page-fault counter workload, ringbuf submitted/received/drop oracle, struct_ops direct load/attach/detach oracle. | partial |
| C4 | The observed XDP count runtime gap is caused by a specific map-update lowering choice rather than the unified-source model alone, and generated objects can run matched local workloads for XDP, TC, perf_event counters, ringbuf emission, and direct tcp-congestion struct_ops compatibility checks. | XDP array-map count mechanism; local XDP/TC pass/count traffic including one longer stress rerun, perf_event page-fault counter, XDP ringbuf emission, and tcp-congestion struct_ops load/attach/detach only. | Hand-written C/eBPF baseline, generated current object, compiler-source patch ablation, map-count correctness oracle, microbench, XDP/TC traffic-driven results, traffic stress result, perf_event counter result, ringbuf event-rate/loss result, struct_ops direct libbpf compatibility result. | partial |

## Open Questions

- Does the result hold for scheduler-extension struct_ops, workload-level
  struct_ops behavior, and broader perf_event workloads with matched C/libbpf
  baselines?
- Can generated loaders, beyond one perf_event lifecycle latency check, sustain representative traffic or dispatch-loop workloads?
- How do verifier failures and diagnostics compare against hand-written libbpf programs on the same workload set?
