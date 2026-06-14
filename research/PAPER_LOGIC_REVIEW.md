Last updated: 2026-06-13
Stage at update: paper-logic review
Source/command: main-agent review plus delegated read-only reviewer, followed by
paper edits and `make -C paper`
Completeness: complete for the current draft after scheduler-extension verifier diagnostic

# Paper Logic Review

## Verdict

Warn, fixed for current known must-fix issues. The review found no evidence that
the paper's main artifact/prototype claim outruns the checked-in results after
the latest edits. The largest weaknesses were headline hygiene and
reviewer-facing reconstructability: several abstract and conclusion claims
omitted denominators, one struct_ops abstract sentence used the trial-count
macro where it should use success macros, zero-drop ring-buffer language lacked
trial and variant scope, and the methodology scattered the roles of generated
objects, generated loaders, shared runners, baselines, and oracles. A later
delegated review also found stale research-state artifacts after adding the
struct_ops skeleton repair, later followed by loopback struct_ops TCP workload,
callback-flag workload results, and a scheduler-extension verifier diagnostic.

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
8. Integrated the struct_ops skeleton repair as a local generated-userspace
   build repair, updated research-state artifacts, and changed the methodology
   outcome count from nine to ten.
9. Integrated the loopback struct_ops TCP workload as socket-level algorithm
   selection and byte-transfer evidence, while preserving the non-production
   throughput scope.
10. Integrated the callback-flag struct_ops workload as cong_avoid/cwnd_event
    reachability evidence, while preserving the limits around production TCP
    performance, scheduler-extension struct_ops, and broader callback behavior.
11. Integrated the expanded 28-case static corpus into the contribution,
    result-map, static-result, discussion, and table-caption wording after a
    delegated top-systems review found no must-fix contradictions but flagged
    stale static-category summaries and an implicit generated-code-size
    denominator.
12. Expanded the callback-flag struct_ops workload into clean and loss-injected
    profiles: clean loopback keeps the cong_avoid/cwnd_event oracle, while 5%
    loopback loss adds ssthresh/set_state reachability for generated and C/eBPF
    objects without claiming complete TCP callback coverage.
13. Re-ran a targeted whole-paper logic pass for the loss-injected profile,
    verified the new macros against `results/struct_ops_callback_workload_summary.json`,
    and removed remaining semicolon-joined clauses introduced near the
    struct_ops result text.
14. Applied a delegated top-systems writing and experiment review after the
    loss-injected callback profile. The follow-up pass tightened the abstract
    and conclusion, clarified that the loss profile is a callback trigger rather
    than robustness evidence, corrected the stale static-check count in the
    experiment plan, changed generated-SLOC wording away from developer-effort
    savings, and renamed the runner's clean-profile callback field so the JSON
    profile oracle is not easy to misread.
15. Integrated the scheduler-extension struct_ops verifier diagnostic as
    load-only evidence: the paper now says a five-callback C/eBPF control
    object and the generated object both verifier-load, and no scheduler
    attach, workload evidence, or full callback-set equivalence is claimed.
16. Applied a delegated top-systems review after the scheduler-extension
    diagnostic. The follow-up pass corrected the scheduler-extension baseline
    wording from matched callback-set language to a five-callback control
    baseline, and updated the method summary to the then-current measurement
    script and outcome counts.
17. Applied a delegated top-systems review after the scheduler-extension
    verifier-load fix. The follow-up pass removed the scheduler "generalizes"
    framing, split overloaded struct_ops claim-scope rows, refreshed stale
    research-plan numbers, added the stress outlier/retransmit caveat, narrowed
    generated-loader and skeleton-repair claims, and anonymized the paper-facing
    KernelScript artifact reference.
18. Added an opt-in scheduler-extension attach/workload harness. The paper now
    distinguishes the load-only verifier diagnostic from the bounded toy FIFO
    attach workload, and keeps scheduler-policy quality and performance as
    remaining limits.
19. Extended the scheduler-extension attach harness into a five-trial
    progress/fairness oracle and refreshed the method summary to 20 measurement
    scripts and fourteen outcomes.

## Remaining Accepted Limits

- Runtime evidence remains local-host evidence rather than NIC-rate or
  long-duration deployment evidence.
- The perf-event loader workload records one generated-loader invocation
  latency distribution, but perf-event counter and ring-buffer workloads use
  shared libbpf runners, so they do not measure broader generated userspace
  dispatch-loop throughput.
- Struct_ops evidence covers tcp-congestion object load/attach/detach, a
  loopback TCP socket workload, clean cong_avoid/cwnd_event callback flags,
  loss-injected ssthresh/cong_avoid/set_state/cwnd_event flags, and a local
  generated-userspace skeleton build repair. Scheduler-extension evidence now
  includes one toy bounded attach workload, but not scheduler-policy quality or
  performance. The paper still does not cover every callback path, running
  repaired generated binaries, production TCP performance, or broad
  libbpf-version portability.
- Generated-structure evidence is a corpus artifact result, not a developer
  effort study against expert-written C/libbpf.

## Follow-Up Gate

The next scientific-strength gate is additional evidence rather than prose:
broader generated-dispatch-loop throughput, scheduler-extension attach/workload
evidence after the verifier-load fix, every
tcp-congestion callback path beyond the two tested profiles,
upstream-integrated skeleton generation across libbpf versions, or non-local
deployment/longer-duration workload evidence.
