Last updated: 2026-06-13
Stage at update: audit
Source/command: manual/fallback experiment audit after struct_ops callback workload evidence
Completeness: complete

# Experiment Audit

## Overall Verdict

Warn, accepted limitations. The checked-in result files, generated paper
numbers, and paper build are internally consistent, and the paper preserves the
current local-artifact scope. The warning is not an integrity failure: it
records that the evidence remains local-host and prototype-scoped rather than a
general runtime-equivalence or production-deployment claim.

## Mechanical Checks

| Check | Evidence | Result |
|---|---|---|
| Required result files exist | Python audit over `results/*.json` inputs used by `experiments/update_paper_numbers.py` | pass |
| Required status fields are clean | `smoke`, `microbench`, `static`, `lowering`, `compiler_patch`, `verifier`, `attach`, `xdp_traffic`, `tc_traffic`, `traffic_stress`, `perf_event_loader`, `perf_event_counter`, `ringbuf`, `struct_ops`, `struct_ops_workload`, `struct_ops_callback_workload`, and `struct_ops_skeleton_repair` summaries all report `ok` | pass |
| Example corpus present | `results/examples_summary.json` contains 44 rows | pass |
| Paper macro coverage | Parsed `paper/kernelscript-paper.tex` and `results/paper_numbers.tex`: all used `KS...` macros are defined | pass |
| Paper-number reproducibility | `./experiments/update_paper_numbers.py && git diff --exit-code -- results/paper_numbers.tex` | pass |
| Paper build | `make -C paper` | pass |
| Repository object integrity | `git fsck --full` | pass |
| Forbidden keyword content scan | `rg -n -i ...` excluding build/log/PDF paths | pass |
| Forbidden keyword filename scan | Prohibited venue-token filename pattern check | pass |

## Result File Inventory

The audit checked these paper-number inputs:

- `results/environment.json`
- `results/unit_tests_summary.json`
- `results/evaluation_summary.json`
- `results/examples_summary.json`
- `results/smoke_summary.json`
- `results/microbench_summary.json`
- `results/static_checks_summary.json`
- `results/lowering_ablation_summary.json`
- `results/compiler_patch_ablation_summary.json`
- `results/verifier_matrix_summary.json`
- `results/attach_matrix_summary.json`
- `results/xdp_traffic_summary.json`
- `results/tc_traffic_summary.json`
- `results/traffic_stress_summary.json`
- `results/perf_event_loader_summary.json`
- `results/perf_event_counter_summary.json`
- `results/ringbuf_workload_summary.json`
- `results/struct_ops_compat_summary.json`
- `results/struct_ops_workload_summary.json`
- `results/struct_ops_callback_workload_summary.json`
- `results/struct_ops_skeleton_repair_summary.json`

## Number-To-Paper Consistency

The paper imports all numerical claims through `results/paper_numbers.tex`.
The macro audit found no undefined `KS...` macros in the LaTeX source. The
paper-number generator re-ran without changing the checked-in macro file, so
the current paper numbers match the checked-in JSON/CSV summaries. The PDF
build completes from those macros.

## Oracle Provenance

- Compiler and example results come from `dune`, the KernelScript compiler,
  generated Makefiles, and recorded per-example rows.
- Static checks use explicit expected pass/fail programs and diagnostic
  category matching.
- Verifier-load results use `bpftool prog loadall` and require at least one
  pinned BPF program to avoid empty-object false positives.
- XDP attach results use isolated network namespaces, veth devices, iproute2
  attach state, detach, and namespace cleanup.
- XDP/TC traffic and traffic-stress results use iperf3 JSON, positive receiver
  bytes, and positive count-map values for count variants.
- Perf-event loader results check attach/read/detach text plus positive
  page-fault counters and branch-miss reads.
- Perf-event counter results require BPF map counts to equal perf counter reads.
- Ring-buffer results require submitted events to equal received events with
  zero drops and no bad markers or return values.
- Struct_ops compatibility results require direct libbpf load, attach, and
  detach success for generated and C/eBPF tcp-congestion objects.
- Struct_ops workload results require socket-level TCP congestion-control
  algorithm selection, full loopback byte transfer, client success, and detach
  success for generated and C/eBPF tcp-congestion objects.
- Struct_ops callback workload results require the same loopback byte-transfer
  oracle plus callback-map flags for cong_avoid and cwnd_event before detach
  in the clean profile. The loss-injected profile also requires byte transfer
  plus ssthresh, cong_avoid, set_state, and cwnd_event before detach.
- Struct_ops skeleton repair results require the original generated userspace
  failures to match the local map-link field mismatch and the repaired
  generated userspace projects to build successfully.

## Metric And Normalization Review

The paper reports absolute counts, medians, ranges, and local median differences
from result files. Ratios and percentage differences are derived against matched
C/eBPF baselines and are labeled as local comparisons. The audit found no
headline claim that normalizes by KernelScript's own output distribution. The
paper keeps generated SLOC expansion separate from developer-effort claims.

## Scope Language Review

The paper explicitly states that it does not establish broad runtime
equivalence, NIC-rate performance, scheduler-extension struct_ops portability,
or full generated-dispatch-loop throughput. It also labels traffic results as
local-host veth evidence, labels the direct struct_ops result as object
compatibility, labels the struct_ops workload as socket-level loopback evidence,
labels the callback workload as clean and loss-injected local reachability
evidence rather than full callback coverage, and labels the skeleton repair as
a local generated-userspace build repair rather than cross-version portability.

## Accepted Warnings

1. The traffic and stress results are local veth/TCP measurements. They are
   useful deployment sanity checks but not NIC-rate or long-duration soak
   evidence.
2. The perf-event loader workload records generated-loader invocation latency,
   but the perf-event counter and ring-buffer workloads use shared libbpf
   runners, so they do not measure broader generated userspace dispatch-loop
   throughput.
3. The struct_ops checks cover tcp-congestion object load/attach/detach, a
   loopback socket workload, clean cong_avoid/cwnd_event callback flags, and
   loss-injected ssthresh/cong_avoid/set_state/cwnd_event flags. The skeleton
   repair covers local generated userspace builds only. These checks do not
   cover scheduler-extension struct_ops, every tcp-congestion callback path,
   running the repaired binaries, or broad libbpf-version portability.
4. The generated-structure result is a corpus artifact result, not a
   developer-effort study against an expert C implementation.

## Gate Status

The result-integrity audit passes with accepted warnings. The whole-paper logic
review has no known must-fix claim/evidence gaps after the latest edits; the
remaining blockers are evidence limits recorded in `research/STATE.md` and
`research/FOLLOWUP_PLAN.md`.
