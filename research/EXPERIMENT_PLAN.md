Last updated: 2026-06-13
Stage at update: experiment-design
Source/command: top-systems experiment-design follow-up after struct_ops callback workload

# Experiment Plan: KernelScript Paper

## Thesis

KernelScript is useful for eBPF developers when a typed unified-source model
centralizes multi-artifact project structure and selected pre-load checks while
retaining ordinary libbpf-compatible artifacts with measurable compatibility and
runtime behavior.

## Paper Type

- Type: systems prototype and artifact evaluation.
- Target venue: top systems conference audience.
- Artifact status: public prototype plus reproducible paper harness.
- Main reviewer risk: runtime evidence and baselines are still too XDP-heavy and
  too narrow.

## Claim Ledger

| ID | Claim | Scope | Metric/evidence needed | Status |
|----|-------|-------|------------------------|--------|
| C1 | Unified source centralizes eBPF project structure. | Repository examples and generated artifacts. | Build matrix, feature coverage, SLOC expansion. | partial |
| C2 | Selected invalid programs are rejected before load/attach. | Covered static checks. | Unit/static check corpus. | partial |
| C3 | Generated eBPF objects remain compatible with the local kernel verifier, can attach for an XDP subset, and perf_event/ringbuf/struct_ops examples can complete local lifecycle, object-level, workload, callback-reachability, or generated-build compatibility checks. | Local kernel/toolchain, generated repository examples, verifier-clean single-section XDP subset, perf_event examples, one ringbuf XDP object workload, one tcp-congestion struct_ops object with loopback TCP and callback-flag workloads, and two generated struct_ops userspace build repairs. | Strict verifier matrix, isolated XDP attach matrix, perf_event generated-loader and counter workloads, ringbuf submitted/received/drop oracle, struct_ops load/attach/detach, TCP socket workload, callback-flag, and skeleton build-repair oracles. | partial |
| C4 | The observed XDP count runtime gap is caused by a specific map-update lowering choice, and generated objects can run matched local workloads for XDP, TC, perf_event counters, ringbuf emission, and tcp-congestion struct_ops checks. | XDP array-map count mechanism; local XDP/TC pass/count traffic including one longer stress rerun, perf_event page-fault counter, XDP ringbuf emission, tcp-congestion struct_ops load/attach/detach, loopback TCP transfer, callback-flag reachability for cong_avoid/cwnd_event, and local struct_ops generated-build repair only. | Hand-written C/eBPF baseline, compiler-source patch ablation, map-count correctness oracle, traffic and stress results, perf_event counter result, ringbuf event-rate/loss result, struct_ops direct compatibility, TCP workload, callback-flag workload, and skeleton repair results. | partial |

## System-Under-Test Model

- Components: KernelScript compiler, generated eBPF C, generated userspace C,
  Makefile, bpftool/libbpf/clang path, optional generated module code.
- Durable state: tracked source, result JSON/CSV, paper macros, build logs.
- Trust/failure boundaries: kernel verifier, libbpf skeleton API, bpftool, local
  kernel BTF, privileged attach path.
- Workloads: repository examples, static invalid programs, XDP pass/count
  microbenchmarks, XDP and TC traffic over veth/netns, perf_event loader
  lifecycle latency, longer XDP/TC traffic stress, perf_event page-fault counter
  workload, ringbuf event-emission workload, direct tcp-congestion struct_ops
  load/attach/detach compatibility, loopback TCP workload and callback flags
  for tcp-congestion struct_ops, and version-aware struct_ops skeleton build
  repair.
- Observability: compile logs, verifier logs, iproute2 attach state, bpftool map
  lookups, iperf3 JSON.
- Assumptions: local host is a valid reproducibility target but not a general
  performance environment.

## Experiment Matrix

| Block | Claim | Experiment | Baselines/variants | Metric(s) | Oracle | Figure/table | Priority |
|-------|-------|------------|--------------------|-----------|--------|--------------|----------|
| B1 | C1 | Example build and expansion matrix | Generated KernelScript artifacts | compile/build success, SLOC, feature markers | successful scripts and result files | Table build/features | done |
| B2 | C2 | Static rejection corpus | Expected pass/fail cases | matched diagnostics by category | expected outcome matcher | Static paragraph | done |
| B3 | C3 | Verifier and XDP attach matrices | Generated eBPF objects | load ok, attach ok | pinned program check, `prog/xdp` state | Compatibility paragraph | done |
| B4 | C4 | BPF_PROG_TEST_RUN microbench and compiler patch ablation | KS current, KS patched, C/eBPF | ns/op, instructions, map counts | exact map-count oracle | Microbench table | done |
| B5 | C4 | Traffic-driven XDP pass/count | KS current vs hand-written C/eBPF | receiver Gb/s, count-map Mpps, retransmits | iperf3 JSON plus positive map count | Runtime paragraph | done |
| B6 | C3/C4 | Traffic-driven TC ingress pass/count | KS current vs hand-written C/eBPF | receiver Gb/s, count-map Mpps, retransmits | iperf3 JSON plus positive map count | Runtime paragraph | done |
| B7 | C3 | Generated perf_event loader lifecycle latency | KS generated loader vs C/libbpf | attach/read/detach success, perf counter reads, invocation latency | positive page-fault counter, clean detach, and latency distribution | Runtime paragraph | done |
| B8 | C3/C4 | Perf_event page-fault counter workload | KS vs C/eBPF | event rate, BPF/perf count agreement | exact map/perf counter equality | Runtime paragraph | done |
| B9 | C3/C4 | Ringbuf event-emission workload | KS vs C/eBPF | event rate, loss | submitted equals received, zero drops | Runtime paragraph | done |
| B10 | C3/C4 | Struct_ops direct compatibility | KS vs C/eBPF | load status, attach status, skeleton-header support | direct libbpf load/attach/detach oracle | Runtime paragraph | done |
| B11 | C4 | Longer XDP/TC traffic stress | KS vs C/eBPF | receiver Gb/s, map Mpps, retransmits | iperf3 JSON plus positive map count | Runtime paragraph | done |
| B12 | C3 | Struct_ops skeleton repair | Generated userspace before/after repair | build status, removed assignments, header support | repaired generated userspace build status | Runtime paragraph | done |
| B13 | C3/C4 | Struct_ops TCP workload | KS vs C/libbpf | TCP algorithm selection, bytes transferred, detach status | socket-level TCP_CONGESTION and byte-count oracle | Runtime paragraph | done |
| B14 | C3/C4 | Callback-flag tcp-congestion struct_ops workload | KS vs C/libbpf | TCP algorithm selection, bytes transferred, required callback flags | cong_avoid and cwnd_event flags set by workload | Runtime paragraph | done |
| B15 | C3/C4 | Scheduler-extension or broader callback-level struct_ops | KS vs C/libbpf | scheduler behavior or broader callback counters | workload-specific checker | Future table | planned |

## Run Order

| Run ID | Stage | Purpose | Config | Seed/reps | Decision gate | Cost | Risk |
|--------|-------|---------|--------|-----------|---------------|------|------|
| R000 | sanity | Static rejection corpus | `./experiments/run_static_checks.py` | 28 cases | all expected diagnostics match | low | done |
| R001 | sanity | Strict verifier matrix | `./experiments/run_verifier_matrix.py` | full corpus | no empty program false positives | low | done |
| R002 | sanity | XDP attach matrix | `./experiments/run_attach_matrix.py` | full eligible subset | all eligible attach/detach | low | done |
| R003 | main | XDP traffic baseline | `./experiments/run_xdp_traffic.py` | 10 trials, 1s TCP by default | KS and C pass traffic; count maps increase | low | done |
| R004 | supplement | TC traffic baseline | `./experiments/run_tc_traffic.py` | 10 trials, 1s TCP by default | KS and C pass traffic; count maps increase | medium | done |
| R005 | supplement | Perf_event loader lifecycle latency | `./experiments/run_perf_event_loader.py` | 20 trials | generated and C loaders attach, read counters, detach, and record invocation latency | low | done |
| R006 | supplement | Perf_event page-fault counter workload | `./experiments/run_perf_event_counter.py` | 10 trials, 65536 pages x 4 rounds | BPF map counts equal perf counter reads | low | done |
| R007 | supplement | Ringbuf event-emission workload | `./experiments/run_ringbuf_workload.py` | 10 trials, 50000 events/trial | submitted equals received; zero drops | low | done |
| R008 | supplement | Struct_ops direct load/attach/detach compatibility | `./experiments/run_struct_ops_compat.py` | 3 trials | generated and C/eBPF tcp-congestion objects load, attach, and detach | low | done |
| R009 | supplement | Longer XDP/TC traffic stress rerun | `./experiments/run_traffic_stress.py` | 3 trials, 5s TCP by default | all XDP/TC pass/count stress oracles pass | medium | done |
| R010 | supplement | Version-aware struct_ops skeleton repair | `./experiments/run_struct_ops_skeleton_repair.py` | 2 generated examples | original generated userspace failures are repaired when local libbpf lacks map-link support | low | done |
| R011 | supplement | Loopback TCP struct_ops workload | `./experiments/run_struct_ops_workload.py` | 10 trials, 1MiB per variant | generated and C/eBPF objects are selected with TCP_CONGESTION, transfer all bytes, and detach | low | done |
| R012 | supplement | Callback-flag tcp-congestion struct_ops workload | `./experiments/run_struct_ops_callback_workload.py` | 10 trials, 4MiB per variant | generated and C/eBPF objects transfer all bytes and set cong_avoid plus cwnd_event flags | low | done |
| R013 | supplement | Scheduler-extension or broader callback-level struct_ops baseline | to be implemented | 10 trials | matched C/libbpf exists and reports scheduler behavior or broader per-callback behavior | medium | planned |

## Tracker Handoff

- Update path: `research/EXPERIMENT_TRACKER.md`
- Result path convention: `results/<experiment>_summary.{json,csv}` and
  `results/logs/<experiment>/`
- Required tracker columns: Run ID, Claim, Purpose, Command/config, Commit,
  Machine, Seed/reps, Result path, Status

## Baseline Fairness

- Named baselines: hand-written C/eBPF programs compiled with the same clang,
  BTF, and local kernel as the generated KernelScript objects.
- Tuning policy: keep program semantics matched; do not hand-optimize the C
  baseline beyond idiomatic libbpf/eBPF for the same operation.
- What each baseline proves: C/eBPF establishes the ordinary low-level artifact
  path and isolates overhead due to generated code/lowering choices.
- Baselines intentionally omitted and why: bpftrace, Aya, and cilium/ebpf are
  not matched for the current XDP C-level codegen question; they remain related
  systems for a broader developer-effort study.

## Reproducibility

- Hardware/software versions: recorded in `results/environment.json`.
- Seeds/repetitions: deterministic scripts; traffic scripts record trial count
  and seconds.
- Workload generation: iperf3 TCP over isolated veth/netns for XDP and TC
  traffic runs plus a longer stress rerun; perf_event software and hardware
  counters for loader lifecycle; page-fault workload for perf_event counter
  runs; BPF_PROG_TEST_RUN plus ring-buffer consumption for ringbuf event runs;
  direct libbpf load/attach/detach, loopback TCP socket transfer, and
  callback-flag reads for tcp-congestion struct_ops objects;
  generated userspace rebuild before and after skeleton header repair for two
  struct_ops examples.
- Data/traces: JSON/CSV summaries plus raw logs under `results/logs/`.
- Scripts/configs: all paper-number inputs are checked into the repository.
- Result file paths: generated under `results/` and referenced by paper macros.

## Residual Uncertainty

- The plan still does not test broad production eBPF applications or developer
  effort.
- The XDP and TC traffic experiments are local-host evidence, not NIC-rate
  benchmarks.
- Scheduler-extension struct_ops, broader callback-level TCP behavior beyond
  cong_avoid/cwnd_event flags, broader libbpf-version coverage for skeleton
  generation, broader perf_event workloads, broader generated-dispatch-loop
  throughput, and larger or non-local stress runs remain necessary before
  claiming general runtime equivalence.

## Claim Gate After Results

| Claim | Evidence file(s) | Verdict | Supported wording |
|-------|------------------|---------|-------------------|
| C1 | `results/evaluation_summary.json`, `results/examples_summary.csv` | partial | Centralizes generated project structure for repository examples. |
| C2 | `results/static_checks_summary.json` | partial | Rejects 22 selected invalid programs before load/attach across lifecycle, signature, map, type, symbol, config, ringbuf, and safety categories. |
| C3 | `results/verifier_matrix_summary.json`, `results/attach_matrix_summary.json`, `results/perf_event_loader_summary.json`, `results/perf_event_counter_summary.json`, `results/ringbuf_workload_summary.json`, `results/struct_ops_compat_summary.json`, `results/struct_ops_workload_summary.json`, `results/struct_ops_callback_workload_summary.json`, `results/struct_ops_skeleton_repair_summary.json` | partial | Most generated build-success objects load; verifier-clean single-section XDP objects attach; one generated perf_event loader completes 20 attach/read/detach trials with invocation timing; perf_event counter objects run a page-fault workload; ringbuf objects deliver 50000 events/trial with zero drops; tcp-congestion struct_ops objects load, attach, and detach in 3/3 direct libbpf trials; the generated and C/eBPF tcp-congestion objects each complete 10/10 loopback TCP workload trials and 10/10 callback-flag trials for cong_avoid/cwnd_event; the two generated struct_ops userspace build failures repair to 2/2 on this host. |
| C4 | `results/compiler_patch_ablation_summary.json`, `results/xdp_traffic_summary.json`, `results/tc_traffic_summary.json`, `results/traffic_stress_summary.json`, `results/perf_event_counter_summary.json`, `results/ringbuf_workload_summary.json`, `results/struct_ops_compat_summary.json`, `results/struct_ops_workload_summary.json`, `results/struct_ops_callback_workload_summary.json`, `results/struct_ops_skeleton_repair_summary.json` | partial | XDP count gap is tied to map-update lowering; local checks cover XDP and TC pass/count plus a longer stress rerun, a perf_event counter workload, ringbuf event emission, direct tcp-congestion struct_ops load/attach/detach compatibility, a loopback TCP struct_ops workload, callback flags for cong_avoid/cwnd_event, and a local struct_ops skeleton build repair, but broader runtime equivalence remains unproven. |
