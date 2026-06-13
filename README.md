# KernelScript Paper Artifact

This directory contains a cloned KernelScript repository, reproducible
evaluation scripts, generated results, and a paper draft.

## Layout

- `kernelscript/`: cloned upstream repository.
- `experiments/run_evaluation.py`: compiler/test/example build evaluation.
- `experiments/run_verifier_matrix.py`: bpftool verifier-load matrix for
  generated eBPF objects.
- `experiments/run_static_checks.py`: positive and negative static-check corpus.
- `experiments/run_smoke.sh`: privileged attach/detach smoke test on `lo`.
- `experiments/run_microbench.py`: XDP BPF_PROG_TEST_RUN microbenchmarks
  against hand-written C/eBPF baselines.
- `experiments/run_compiler_patch_ablation.py`: applies a tracked
  compiler-source patch for array-map increment lowering and reruns the XDP
  count benchmark.
- `experiments/run_lowering_ablation.py`: generated-C map-update lowering
  cross-check for the XDP count benchmark.
- `experiments/patches/`: tracked compiler patch used by the ablation.
- `experiments/programs/smoke_lo.ks`: minimal smoke-test KernelScript program.
- `results/`: tracked CSV/JSON summaries and paper macros. Local reruns also
  create ignored build outputs and logs under `results/build/` and
  `results/logs/`.
- `paper/`: LaTeX paper source and build files.
- `RESEARCH_PLAN.md`: research questions, methodology, and threat model.

## Reproduce

Install the dependencies listed in the KernelScript README:

```bash
sudo apt-get install -y opam ocaml ocaml-dune menhir libalcotest-ocaml-dev \
  libbpf-dev libelf-dev zlib1g-dev pkg-config bpftool clang gcc make
```

Run the main evaluation:

```bash
./experiments/run_evaluation.py
```

Run the verifier-load matrix, which requires `sudo -n` and the generated
example build outputs from `run_evaluation.py`:

```bash
./experiments/run_verifier_matrix.py
```

Run the static-check corpus:

```bash
./experiments/run_static_checks.py
```

Run the optional smoke test, which requires passwordless sudo or a prior sudo
credential. The paper-number generator requires the checked-in smoke summary to
have status `ok`.

```bash
./experiments/run_smoke.sh
```

Run the optional runtime microbenchmarks, which also require `sudo -n`. The
paper-number generator requires the checked-in microbenchmark summary to have
status `ok`.

```bash
./experiments/run_microbench.py
```

Run the compiler-patch lowering ablation, which also requires `sudo -n`:

```bash
./experiments/run_compiler_patch_ablation.py
```

Run the generated-C lowering cross-check, which also requires `sudo -n`:

```bash
./experiments/run_lowering_ablation.py
```

Build the paper:

```bash
make -C paper
```

## Current Result Snapshot

The current run evaluates KernelScript commit `ccb15b4` on Linux
`6.15.11-061511-generic`.

- Unit tests: 85 suites, 1095 tests, 0 reported failures.
- Examples: 44 total, 43 KernelScript compile successes, 41 full generated
  C/eBPF build successes.
- Verifier-load matrix: 39 of 43 generated eBPF objects load with
  `bpftool prog loadall`. Among the 41 objects from full generated-project
  build successes, 38 load successfully and 3 fail with recorded reference
  ownership, map-creation, or local BTF-symbol diagnostics.
- Static checks: 6 total cases, including 5 expected compiler rejections and
  1 positive control, all matching expected outcomes.
- Safety: `safety_demo.ks` is rejected before C generation for 608 bytes of
  stack usage against the 512-byte eBPF limit.
- Compatibility limit: two struct_ops examples build eBPF objects but fail when
  compiling generated skeleton userspace code against libbpf 1.3.0.
- Smoke test: `smoke_lo` attaches and detaches an XDP pass program on `lo`.
- Microbenchmarks: XDP pass has the same median as C/eBPF in this harness
  at 5ns average runtime and 2 instructions. XDP array-map count is 13ns and 21
  instructions for KernelScript versus 9ns and 11 instructions for
  hand-written C/eBPF.
- Compiler-patch lowering ablation: applying
  `experiments/patches/kernelscript-map-increment-lowering.patch` to a copied
  KernelScript compiler tree reduces the count object from 21 to 11
  instructions and from 12ns to 9ns median, matching the hand-written C/eBPF
  baseline in this harness. Each trial resets and reads the `counts` map to
  verify the expected 100000 increments.
- The 13ns count value comes from the standalone `run_microbench.py` baseline
  run. The paper's count rows come from the compiler-patch ablation rerun so
  current, patched, and C objects share one timing run.
