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
kernel-module C, and Makefile SLOC. This is not a hand-written C baseline. It is
a conservative expansion-factor measurement showing the amount of generated
artifact a developer does not have to maintain by hand.

RQ3. Which classes of errors are rejected before load/attach time?

Evidence: run the full compiler test suite and a small static-check corpus. The
corpus includes lifecycle API misuse, a perf_event context-signature mismatch,
an eBPF stack-limit violation, and one positive control.

RQ4. Do generated artifacts remain compatible with the local kernel toolchain?

Evidence: compile generated eBPF objects, generate libbpf skeletons with
`bpftool`, link userspace loaders, and build generated kernel modules when
present. Then run `bpftool prog loadall` on each generated eBPF object to
classify which objects pass kernel verifier loading without attaching them.

RQ5. Can at least one generated loader execute end to end?

Evidence: `experiments/run_smoke.sh` compiles `smoke_lo.ks`, builds the generated
project, and uses `sudo -n` to attach/detach an XDP pass program on the loopback
interface.

RQ6. Is the XDP map-update gap caused by the unified source model or by a
specific lowering choice?

Evidence: apply a tracked compiler-source patch to a copied KernelScript
compiler tree, rebuild the patched compiler, compile the same XDP count
benchmark, and rerun the same BPF_PROG_TEST_RUN harness against the current
compiler object and hand-written C/eBPF. The patch lowers constant increments
on integer array maps from lookup-plus-update to checked lookup plus in-place
atomic add. The harness resets and reads the `counts` map on every trial to
verify that all variants perform the same 100000 increments.

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

3. `experiments/run_verifier_matrix.py`
   - Reads `results/examples_summary.csv` after `run_evaluation.py`.
   - Attempts `bpftool prog loadall` for every generated eBPF object under
     `results/build/examples`.
   - Pins programs and maps under `/sys/fs/bpf/kernelscript-paper`, removes pins
     after each attempt, and keeps raw bpftool logs under
     `results/logs/verifier_matrix`.
   - Writes `results/verifier_matrix_summary.csv` and
     `results/verifier_matrix_summary.json`.

4. `experiments/run_smoke.sh`
   - Compiles and builds `experiments/programs/smoke_lo.ks`.
   - Runs the generated binary with `sudo -n`.
   - Writes `results/smoke_summary.json` and logs under `results/logs/`.

5. `experiments/run_microbench.py`
   - Compiles two KernelScript XDP microbenchmarks and two hand-written C/eBPF
     baselines.
   - Loads each object with `bpftool prog load`.
   - Runs each object with `bpftool prog run ... repeat 100000` for seven
     trials.
   - Writes `results/microbench_summary.csv` and
     `results/microbench_summary.json`.

6. `experiments/run_compiler_patch_ablation.py`
   - Copies the KernelScript compiler source tree into `results/build`.
   - Applies `experiments/patches/kernelscript-map-increment-lowering.patch`.
   - Builds the patched compiler with `dune build`.
   - Compiles the KernelScript XDP count benchmark with both the current and
     patched compilers.
   - Rebuilds the generated eBPF objects and compares them with hand-written
     C/eBPF using BPF_PROG_TEST_RUN.
   - Resets and reads the pinned `counts` map on every trial as a correctness
     oracle.
   - Writes `results/compiler_patch_ablation_summary.csv` and
     `results/compiler_patch_ablation_summary.json`.

7. `experiments/run_lowering_ablation.py`
   - Compiles the KernelScript XDP count benchmark.
   - Copies the generated project and patches the map update lowering from
     lookup plus update helper to in-place atomic add.
   - Rebuilds the patched eBPF object and compares it with the unpatched object
     and hand-written C/eBPF using BPF_PROG_TEST_RUN.
   - Resets and reads the pinned `counts` map on every trial as a correctness
     oracle.
   - Writes `results/lowering_ablation_summary.csv` and
     `results/lowering_ablation_summary.json`.

8. `experiments/update_paper_numbers.py`
   - Checks that unit tests, static checks, smoke test, microbenchmarks, and
     verifier matrix plus both lowering ablations have successful summaries.
   - Writes `results/paper_numbers.tex` for the LaTeX paper.

## Current Results

At commit `ccb15b4`, on Linux `6.15.11-061511-generic`:

- 85 unit test suites and 1095 unit tests pass.
- 43 of 44 examples compile from KernelScript.
- 41 examples build fully into generated C/eBPF artifacts.
- The verifier-load matrix loads 39 of 43 generated eBPF objects. Among the 41
  objects from full generated-project build successes, 38 load successfully and
  3 expose reference-ownership, map-creation, or local BTF-symbol failures.
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
- The compiler-patch lowering ablation reduces the generated count object from
  21 to 11 instructions and from 12ns to 9ns median, matching the hand-written
  C/eBPF baseline in this harness while preserving the expected 100000 count
  updates in every trial.

## Threats and Next Experiments

The current runtime evaluation is a microbenchmark study, not a packet-rate
performance study. A full runtime comparison should add matched hand-written
C/libbpf baselines for XDP, TC, perf_event, ring buffer, and struct_ops
programs. It should run traffic with `pktgen` or `xdp-bench` and report
throughput, tail latency, verifier log size, and CPU utilization. The current compiler-source patch
should be upstreamed or otherwise integrated, semantically generalized beyond
constant array-map increments where safe, and retested across hash, per-CPU, and
structured map values. The current artifact is still useful as a systems
prototype study because it grounds claims about example marker coverage,
generated structure, compatibility, small-program runtime overhead, and one
concrete lowering optimization in reproducible evidence.
