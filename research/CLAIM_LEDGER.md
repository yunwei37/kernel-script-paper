Last updated: 2026-06-13
Stage at update: claims
Source/command: auto-research-orchestrator resume on kernel-script-paper

# Claim Ledger

| ID | Claim | Scope | Metric/evidence needed | Status |
|----|-------|-------|------------------------|--------|
| C1 | KernelScript centralizes recurring multi-artifact eBPF project structure while preserving conventional libbpf-compatible outputs. | Repository examples at commit `ccb15b4` on the recorded host toolchain. | Example compile/build matrix, generated SLOC expansion, feature marker coverage, generated object inventory. | partial |
| C2 | KernelScript rejects selected verifier-relevant and lifecycle/context mistakes before kernel load/attach. | Covered compiler checks and static-check corpus only. | Unit tests, static negative corpus, stack-limit diagnostic, lifecycle/context diagnostic checks. | partial |
| C3 | Generated eBPF objects remain compatible with the local kernel verifier, can attach for an XDP subset, and perf_event examples can complete local lifecycle/counter runs. | Local Linux `6.15.11-061511-generic`, generated repository examples, verifier-clean single-section XDP subset, perf_event examples. | Strict `bpftool prog loadall` matrix with pinned program check, isolated netns/veth XDP attach matrix, perf_event generated-loader lifecycle smoke, perf_event page-fault counter workload. | partial |
| C4 | The observed XDP count runtime gap is caused by a specific map-update lowering choice rather than the unified-source model alone, and generated pass/count programs can run matched local traffic for XDP, TC, and perf_event page-fault counters. | XDP array-map count mechanism; local XDP/TC pass/count traffic and perf_event page-fault counter only. | Hand-written C/eBPF baseline, generated current object, compiler-source patch ablation, map-count correctness oracle, microbench, XDP/TC traffic-driven results, perf_event counter result. | partial |

## Open Questions

- Does the result hold for ringbuf, struct_ops, and broader perf_event workloads with matched C/libbpf baselines?
- Can generated loaders, not only object-level attachment, sustain representative traffic?
- How do verifier failures and diagnostics compare against hand-written libbpf programs on the same workload set?
