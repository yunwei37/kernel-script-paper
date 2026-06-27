Last updated: 2026-06-13
Stage at update: audit
Source/command: manual/fallback experiment audit after external port check
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
| Required status fields are clean | `smoke`, `microbench`, `source_footprint`, `change_amplification`, `external_corpus`, `external_port`, `static`, `lowering`, `compiler_patch`, `verifier`, `attach`, `xdp_traffic`, `tc_traffic`, `traffic_stress`, `perf_event_loader`, `perf_event_counter`, `ringbuf`, `struct_ops`, `struct_ops_workload`, `struct_ops_callback_workload`, `struct_ops_skeleton_repair`, `sched_ext_verifier`, and `sched_ext_attach` summaries all report `ok` | pass |
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
- `results/source_footprint_summary.json`
- `results/change_amplification_summary.json`
- `results/external_corpus_summary.json`
- `results/external_corpus_audit.csv`
- `results/external_port_summary.json`
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
- `results/sched_ext_verifier_summary.json`
- `results/sched_ext_attach_summary.json`

## Number-To-Paper Consistency

The paper imports all numerical claims through `results/paper_numbers.tex`.
The macro audit found no undefined `KS...` macros in the LaTeX source. The
paper-number generator re-ran without changing the checked-in macro file, so
the current paper numbers match the checked-in JSON/CSV summaries. The PDF
build completes from those macros.

## Oracle Provenance

- Compiler and example results come from `dune`, the KernelScript compiler,
  generated Makefiles, and recorded per-example rows.
- Source-footprint results count nonblank noncomment maintained source files
  listed in `results/source_footprint_summary.json`; generated C, generated
  Makefiles, generated `vmlinux.h`, skeleton headers, KernelScript library
  headers, and Python experiment harnesses are excluded.
- Change-amplification results use checked-in before/after KernelScript and
  hand-written C/libbpf fixtures, compute file-level diff hunks as edit sites,
  count added plus deleted lines as changed LOC, and record whether each edit
  requires manual kernel, userspace, or skeleton/section synchronization.
- External source-corpus results clone pinned public repository commits and scan
  selected C/header paths for file roles, SLOC, `SEC()` sections, and feature
  markers; they exclude vendored `vmlinux` headers, generated files, build
  outputs, Rust userspace, and support libraries outside the selected paths. The
  classifier audit compares seven manually selected files against expected
  feature markers and records false-positive and false-negative feature labels.
- External port results clone a pinned `xdp-tutorial` commit, build three manual
  KernelScript ports through generated Makefiles, compile the corresponding
  original external C/eBPF sources directly with clang, attach all 6 objects on
  isolated veth devices, run iperf3 traffic, and require the XDP_PASS map key to
  increase for the map-counter pair.
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
- Scheduler-extension verifier diagnostic results require the five-callback
  C/eBPF control object and generated object to verifier-load and pin programs,
  and confirm no scheduler attach is attempted.
- Scheduler-extension attach results require explicit opt-in, a disabled
  starting state, successful struct_ops registration, sched_ext still enabled
  after each of five bounded CPU workload trials, positive progress from every
  worker, recorded fairness dispersion, successful unregister, return to
  disabled, and zero rejected sched_ext tasks for both generated and C/eBPF toy
  schedulers.

## Metric And Normalization Review

The paper reports absolute counts, medians, ranges, and local median differences
from result files. Ratios and percentage differences are derived against matched
C/eBPF baselines and are labeled as local comparisons. The audit found no
headline claim that normalizes by KernelScript's own output distribution. The
paper keeps generated SLOC expansion and matched source-footprint accounting
separate from developer-time claims. External source-corpus numbers are labeled
as source-only feature context rather than portability, build, verifier,
attach, or runtime results. The classifier audit is labeled as a spot-check of
selected marker rules rather than a statistical precision/recall estimate.
External port numbers are labeled as a small manual XDP port/build/runtime
portfolio rather than a performance ranking, automated translation, or broad
portability evidence.

## Scope Language Review

The paper explicitly states that it does not establish broad runtime
equivalence, NIC-rate performance, scheduler-extension policy/performance or
portability, or full generated-dispatch-loop throughput. It also labels traffic results as
local-host veth evidence, labels the direct struct_ops result as object
compatibility, labels the struct_ops workload as socket-level loopback evidence,
labels the callback workload as clean and loss-injected local reachability
evidence rather than full callback coverage, labels the skeleton repair as a
local generated-userspace build repair rather than cross-version portability,
and labels the scheduler-extension attach result as one toy bounded
progress/fairness proxy rather than scheduler-policy or performance evidence.
The source-footprint result is labeled as a local matched source-footprint proxy
rather than a developer-time study, and the external source-corpus result is
labeled as source-only feature context rather than application portability or
runtime evidence.

## Accepted Warnings

1. The traffic and stress results are local veth/TCP measurements. They are
   useful deployment sanity checks but not NIC-rate or long-duration soak
   evidence.
2. The perf-event loader workload records generated-loader invocation latency,
   but the perf-event counter and ring-buffer workloads use shared libbpf
   runners, so they do not measure broader generated userspace dispatch-loop
   throughput.
3. The struct_ops checks cover tcp-congestion object load/attach/detach, a
   loopback socket workload, clean cong_avoid/cwnd_event callback flags,
   loss-injected ssthresh/cong_avoid/set_state/cwnd_event flags, and one
   scheduler-extension verifier diagnostic where both the five-callback C/eBPF
   control object and generated object load, plus one toy scheduler-extension
   attach/progress workload. The skeleton repair covers local generated userspace builds
   only. These checks do not cover scheduler-extension policy quality or
   performance, every tcp-congestion callback path, running the repaired
   binaries, or broad libbpf-version portability.
4. The generated-structure, source-footprint, and external source-corpus results
   are corpus artifact results. The external scan adds source-only feature
   context but is not a developer-effort study, translation/build corpus, or
   runtime portability result.
5. The external port check adds runtime evidence for three hand-ported XDP
   tutorial workloads, but it is not an automated translator, broad external
   corpus, or developer-effort result.

## Gate Status

The result-integrity audit passes with accepted warnings. The whole-paper logic
review has no known must-fix claim/evidence gaps after the latest edits; the
remaining blockers are evidence limits recorded in `research/STATE.md` and
`research/FOLLOWUP_PLAN.md`.
