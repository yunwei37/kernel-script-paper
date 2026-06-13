Last updated: 2026-06-13
Stage at update: experiment-design
Source/command: top-systems experiment-design follow-up after isolated XDP attach matrix

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
| C3 | Generated objects are verifier/attach compatible on the local host. | Local kernel/toolchain and XDP subset. | Strict verifier matrix and attach matrix. | partial |
| C4 | XDP count overhead is a lowering issue. | XDP array-map counter. | C baseline, compiler patch ablation, traffic result. | partial |

## System-Under-Test Model

- Components: KernelScript compiler, generated eBPF C, generated userspace C,
  Makefile, bpftool/libbpf/clang path, optional generated module code.
- Durable state: tracked source, result JSON/CSV, paper macros, build logs.
- Trust/failure boundaries: kernel verifier, libbpf skeleton API, bpftool, local
  kernel BTF, privileged attach path.
- Workloads: repository examples, static invalid programs, XDP pass/count
  microbenchmarks, XDP and TC traffic over veth/netns, perf_event loader
  lifecycle smoke, perf_event page-fault counter workload, ringbuf
  event-emission workload.
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
| B7 | C3 | Generated perf_event loader lifecycle | KS generated loader vs C/libbpf | attach/read/detach success, perf counter reads | positive page-fault counter and clean detach | Runtime paragraph | done |
| B8 | C3/C4 | Perf_event page-fault counter workload | KS vs C/eBPF | event rate, BPF/perf count agreement | exact map/perf counter equality | Runtime paragraph | done |
| B9 | C3/C4 | Ringbuf event-emission workload | KS vs C/eBPF | event rate, loss | submitted equals received, zero drops | Runtime paragraph | done |
| B10 | C3/C4 | Struct_ops throughput workload | KS vs C/libbpf | event rate, load/build status | workload-specific checker | Future table | planned |

## Run Order

| Run ID | Stage | Purpose | Config | Seed/reps | Decision gate | Cost | Risk |
|--------|-------|---------|--------|-----------|---------------|------|------|
| R000 | sanity | Static rejection corpus | `./experiments/run_static_checks.py` | 23 cases | all expected diagnostics match | low | done |
| R001 | sanity | Strict verifier matrix | `./experiments/run_verifier_matrix.py` | full corpus | no empty program false positives | low | done |
| R002 | sanity | XDP attach matrix | `./experiments/run_attach_matrix.py` | full eligible subset | all eligible attach/detach | low | done |
| R003 | main | XDP traffic baseline | `./experiments/run_xdp_traffic.py` | 10 trials, 1s TCP by default | KS and C pass traffic; count maps increase | low | done |
| R004 | supplement | TC traffic baseline | `./experiments/run_tc_traffic.py` | 10 trials, 1s TCP by default | KS and C pass traffic; count maps increase | medium | done |
| R005 | supplement | Perf_event loader lifecycle | `./experiments/run_perf_event_loader.py` | 5 trials | generated and C loaders attach, read counters, detach | low | done |
| R006 | supplement | Perf_event page-fault counter workload | `./experiments/run_perf_event_counter.py` | 10 trials, 65536 pages x 4 rounds | BPF map counts equal perf counter reads | low | done |
| R007 | supplement | Ringbuf event-emission workload | `./experiments/run_ringbuf_workload.py` | 10 trials, 50000 events/trial | submitted equals received; zero drops | low | done |
| R008 | supplement | Struct_ops throughput baseline | to be implemented | 10 trials | matched C/libbpf exists | medium | planned |

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
  traffic runs; perf_event software and hardware counters for loader lifecycle;
  page-fault workload for perf_event counter runs; BPF_PROG_TEST_RUN plus
  ring-buffer consumption for ringbuf event runs.
- Data/traces: JSON/CSV summaries plus raw logs under `results/logs/`.
- Scripts/configs: all paper-number inputs are checked into the repository.
- Result file paths: generated under `results/` and referenced by paper macros.

## Residual Uncertainty

- The plan still does not test broad production eBPF applications or developer
  effort.
- The XDP and TC traffic experiments are local-host evidence, not NIC-rate
  benchmarks.
- Struct_ops, broader perf_event workloads, generated-loader throughput, and
  longer stress runs remain necessary before claiming general runtime
  equivalence.

## Claim Gate After Results

| Claim | Evidence file(s) | Verdict | Supported wording |
|-------|------------------|---------|-------------------|
| C1 | `results/evaluation_summary.json`, `results/examples_summary.csv` | partial | Centralizes generated project structure for repository examples. |
| C2 | `results/static_checks_summary.json` | partial | Rejects 22 selected invalid programs before load/attach across lifecycle, signature, map, type, symbol, config, ringbuf, and safety categories. |
| C3 | `results/verifier_matrix_summary.json`, `results/attach_matrix_summary.json`, `results/perf_event_loader_summary.json`, `results/perf_event_counter_summary.json`, `results/ringbuf_workload_summary.json` | partial | Most generated build-success objects load; verifier-clean single-section XDP objects attach; one generated perf_event loader completes attach/read/detach; perf_event counter objects run a page-fault workload; ringbuf objects deliver 50000 events/trial with zero drops. |
| C4 | `results/compiler_patch_ablation_summary.json`, `results/xdp_traffic_summary.json`, `results/tc_traffic_summary.json`, `results/perf_event_counter_summary.json`, `results/ringbuf_workload_summary.json` | partial | XDP count gap is tied to map-update lowering; local workloads cover XDP and TC pass/count, a perf_event counter workload, and ringbuf event emission, but broader runtime equivalence remains unproven. |
