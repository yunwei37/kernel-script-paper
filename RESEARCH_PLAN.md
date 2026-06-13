# KernelScript Paper Research Plan

## Claim

KernelScript explores a typed, compiler-checked unified-source programming
model for eBPF. The scientific claim is that a language-level model can
centralize recurring eBPF project structure and reject some verifier-relevant
errors before kernel loading, while preserving a low-level compilation path to
conventional libbpf-compatible artifacts.

## Research Questions

RQ1. Can a unified source model cover representative eBPF programming domains?

Evidence: compile and build every repository example, then classify each example
by program type and language feature.

RQ2. How much low-level generated project structure does the language centralize?

Evidence: compare KernelScript source SLOC with generated userspace C, eBPF C,
kernel-module C, and Makefile SLOC. This is not a hand-written C baseline; it is
a conservative expansion-factor measurement showing the amount of generated
artifact a developer does not have to maintain by hand.

RQ3. Which classes of errors are rejected before load/attach time?

Evidence: run the full compiler test suite and a small static-check corpus. The
corpus includes lifecycle API misuse, a perf_event context-signature mismatch,
an eBPF stack-limit violation, and one positive control.

RQ4. Do generated artifacts remain compatible with the local kernel toolchain?

Evidence: compile generated eBPF objects, generate libbpf skeletons with
`bpftool`, link userspace loaders, and build generated kernel modules when
present.

RQ5. Can at least one generated loader execute end to end?

Evidence: `experiments/run_smoke.sh` compiles `smoke_lo.ks`, builds the generated
project, and uses `sudo -n` to attach/detach an XDP pass program on the loopback
interface.

## Implemented Experiments

1. `experiments/run_evaluation.py`
   - Builds the KernelScript compiler with `dune build`.
   - Runs `dune runtest --force`.
   - Compiles every `kernelscript/examples/*.ks` program.
   - Runs `make` for each generated project.
   - Records SLOC, build times, feature flags, eBPF object sizes, and instruction
     counts when `llvm-objdump` is available.
   - Writes `results/evaluation_summary.json`, `results/examples_summary.csv`,
     and `results/unit_tests_summary.json`.

2. `experiments/run_static_checks.py`
   - Compiles a static-check corpus with expected success or expected failure
     outcomes.
   - Verifies lifecycle API, context signature, and stack-limit diagnostics.
   - Writes `results/static_checks_summary.csv` and
     `results/static_checks_summary.json`.

3. `experiments/run_smoke.sh`
   - Compiles and builds `experiments/programs/smoke_lo.ks`.
   - Runs the generated binary with `sudo -n`.
   - Writes `results/smoke_summary.json` and logs under `results/logs/`.

4. `experiments/run_microbench.py`
   - Compiles two KernelScript XDP microbenchmarks and two hand-written C/eBPF
     baselines.
   - Loads each object with `bpftool prog load`.
   - Runs each object with `bpftool prog run ... repeat 100000` for seven
     trials.
   - Writes `results/microbench_summary.csv` and
     `results/microbench_summary.json`.

5. `experiments/update_paper_numbers.py`
   - Checks that unit tests, static checks, smoke test, and microbenchmarks have
     successful summaries.
   - Writes `results/paper_numbers.tex` for the LaTeX paper.

## Current Results

At commit `6f9e6e8`, on Linux `6.15.11-061511-generic`:

- 85 unit test suites and 1092 unit tests pass.
- 43 of 44 examples compile from KernelScript.
- 41 examples build fully into generated C/eBPF artifacts.
- The one KernelScript rejection is an intentional safety rejection for stack
  usage above the eBPF limit.
- The static-check corpus has 6 cases, including 5 expected compiler
  rejections and 1 positive control, all matching expected outcomes.
- The two generated build failures are struct_ops examples whose generated
  skeletons expect a `struct bpf_map_skeleton.link` field unavailable in the
  installed libbpf 1.3.0 headers.
- Successful examples have median 31 KernelScript SLOC and median 472 generated
  source/build SLOC, a median expansion factor of 11.3x.
- The smoke test successfully attaches and detaches an XDP program on `lo`.
- XDP microbenchmarks show 0ns median overhead for a trivial pass program
  compared with hand-written C/eBPF, and 4ns median overhead for an array-map
  counter because the generated code emits a lookup plus update helper rather
  than an in-place atomic add.

## Threats and Next Experiments

The current runtime evaluation is a microbenchmark study, not a packet-rate
performance study. A full runtime comparison should add matched hand-written
C/libbpf baselines for XDP, TC, perf_event, ring buffer, and struct_ops programs;
run traffic with `pktgen` or `xdp-bench`; and report throughput, tail latency,
verifier log size, and CPU utilization. The current artifact is still useful as
a systems prototype study because it grounds claims about expressiveness,
generated structure, compatibility, and small-program runtime overhead in
reproducible evidence.
