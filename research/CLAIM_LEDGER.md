Last updated: 2026-06-13
Stage at update: claims
Source/command: auto-research-orchestrator resume on kernel-script-paper

# Claim Ledger

| ID | Claim | Scope | Metric/evidence needed | Status |
|----|-------|-------|------------------------|--------|
| C1 | KernelScript centralizes recurring multi-artifact eBPF project structure while preserving conventional libbpf-compatible outputs. | Repository examples and matched local workload sources at commit `3b19cd2` on the recorded host toolchain, plus pinned public eBPF source trees for source-only feature context and one manual external XDP map-counter port. | Example compile/build matrix, generated SLOC expansion, matched source-footprint proxy, external source-corpus feature scan with manual classifier spot-check, external port/build/runtime check, feature marker coverage, generated object inventory. | partial |
| C2 | KernelScript rejects selected verifier-relevant, lifecycle, signature, map, ringbuf, config-boundary, helper-scope, kernel-context, perf-event group, symbol, and type mistakes before kernel load/attach. | Covered compiler checks and 28-case static-check corpus only. | Unit tests, static negative corpus, stack-limit diagnostic, lifecycle/signature/map/ringbuf/config/helper/kernel-context/perf-group/type diagnostic checks. | partial |
| C3 | Generated eBPF objects remain compatible with the local kernel verifier, can attach for an XDP subset, and perf_event/ringbuf/struct_ops examples can complete local lifecycle, object-level, workload, callback-reachability, generated-build, or boundary-diagnostic checks. | Local Linux `6.15.11-061511-generic`, generated repository examples, verifier-clean single-section XDP subset, perf_event examples, one ringbuf XDP object workload, one tcp-congestion struct_ops object with clean and loss-injected loopback TCP callback-flag workloads, two generated struct_ops userspace build repairs, one scheduler-extension five-callback control verifier diagnostic, and one opt-in scheduler-extension attach/progress workload for a toy FIFO policy. | Strict `bpftool prog loadall` matrix with pinned program check, isolated netns/veth XDP attach matrix, perf_event generated-loader lifecycle latency check, perf_event page-fault counter workload, ringbuf submitted/received/drop oracle, struct_ops direct load/attach/detach oracle, struct_ops TCP socket workload oracle, struct_ops clean and loss-injected callback-flag oracles, version-aware skeleton build-repair oracle, scheduler-extension generated-vs-five-callback-control verifier diagnostic, and scheduler-extension register/progress/unregister oracle. | partial |
| C4 | The observed XDP count runtime gap is caused by a specific map-update lowering choice rather than the unified-source model alone, and generated objects can run matched local workloads for XDP, TC, perf_event counters, ringbuf emission, tcp-congestion struct_ops checks, and one toy scheduler-extension attach/progress workload. | XDP array-map count mechanism; local XDP/TC pass/count traffic including one longer stress rerun, perf_event page-fault counter, XDP ringbuf emission, tcp-congestion struct_ops load/attach/detach, loopback TCP transfer, clean callback flags for cong_avoid/cwnd_event, loss-injected callback flags for ssthresh/cong_avoid/set_state/cwnd_event, local struct_ops generated-build repair, scheduler-extension verifier diagnostic, and one bounded scheduler-extension CPU progress/fairness proxy. | Hand-written C/eBPF baseline, generated current object, compiler-source patch ablation, map-count correctness oracle, microbench, XDP/TC traffic-driven results, traffic stress result, perf_event counter result, ringbuf event-rate/loss result, struct_ops direct libbpf compatibility result, struct_ops TCP workload result, struct_ops callback workload result, struct_ops skeleton repair result, scheduler-extension loadall diagnostic, and scheduler-extension attach/progress summary. | partial |

## Open Questions

- Does the scheduler-extension toy workload result hold for richer scheduler
  policies and performance-sensitive workloads, and does the result hold for every
  tcp-congestion callback path beyond the clean and loss-injected profiles,
  broader libbpf versions, and broader perf_event workloads with matched
  C/libbpf baselines?
- The source-footprint proxy now has external source-only feature context and one
  manual external XDP map-counter port/build/runtime check, but does the result
  hold across a broader external application corpus, automated translation, and
  controlled developer study showing lower implementation, debugging, or review
  effort rather than only fewer maintained source lines?
- Can generated loaders, beyond one perf_event lifecycle latency check, sustain representative traffic or dispatch-loop workloads?
- How do verifier failures and diagnostics compare against hand-written libbpf programs on the same workload set?
