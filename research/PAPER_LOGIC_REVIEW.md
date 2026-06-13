Last updated: 2026-06-13
Stage at update: paper-logic review
Source/command: main-agent review plus delegated read-only reviewer, followed by
paper edits and `make -C paper`
Completeness: complete for the current draft

# Paper Logic Review

## Verdict

Warn, fixed for current known must-fix issues. The review found no evidence that
the paper's main artifact/prototype claim outruns the checked-in results after
the latest edits. The largest weaknesses were headline hygiene and
reviewer-facing reconstructability: several abstract and conclusion claims
omitted denominators, one struct_ops abstract sentence used the trial-count
macro where it should use success macros, zero-drop ring-buffer language lacked
trial and variant scope, and the methodology scattered the roles of generated
objects, generated loaders, shared runners, baselines, and oracles.

## Must-Fix Findings Applied

1. Added denominators to headline verifier-load and XDP attach claims in the
   abstract and conclusion.
2. Changed the abstract struct_ops compatibility result to use generated and
   C/eBPF success macros rather than the trial-count macro as the numerator.
3. Scoped the ring-buffer zero-drop claim to `\KSRingbufTrials{}` trials and to
   both generated and C/eBPF object variants.

## Should-Fix Findings Applied

1. Restored the "selected" qualifier for the cross-boundary invariant claim in
   the introduction.
2. Added a direct bridge from the motivation's lifecycle, representation, and
   compatibility complexities to the design principles.
3. Replaced noisy local "gap" language with median-difference wording and
   overlapping-range caveats for XDP, TC, traffic stress, perf-counter, and
   ring-buffer measurements.
4. Clarified that the compiler-source patch ablation is the reported canonical
   mechanism-isolation result.
5. Reworked the claim-scope table into an artifact/baseline/oracle/boundary
   table so the evaluation roles are reconstructable in one place.
6. Expanded key first-use terms: domain-specific language, Express Data Path,
   traffic control, BPF Type Format, TCX as a traffic-control attach path,
   source lines of code, and Compile Once, Run Everywhere.
7. Replaced the stress-run "all oracles pass" sentence with explicit iperf3 and
   map-count oracle criteria.

## Remaining Accepted Limits

- Runtime evidence remains local-host evidence rather than NIC-rate or
  long-duration deployment evidence.
- Perf-event counter and ring-buffer workloads use shared libbpf runners, so
  they do not measure generated userspace dispatch-loop throughput.
- Struct_ops evidence covers tcp-congestion object load/attach/detach, not a TCP
  workload, scheduler-extension struct_ops, or generated-skeleton portability.
- Generated-structure evidence is a corpus artifact result, not a developer
  effort study against expert-written C/libbpf.

## Follow-Up Gate

The next scientific-strength gate is additional evidence rather than prose:
generated-loader throughput, scheduler-extension struct_ops, version-aware
skeleton handling, or non-local deployment/longer-duration workload evidence.
