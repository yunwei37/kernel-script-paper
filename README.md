# KernelScript Paper Artifact

This directory contains a cloned KernelScript repository, reproducible
evaluation scripts, generated results, and a paper draft.

## Layout

- `kernelscript/`: cloned upstream repository.
- `experiments/run_evaluation.py`: compiler/test/example build evaluation.
- `experiments/run_smoke.sh`: privileged attach/detach smoke test on `lo`.
- `experiments/run_microbench.py`: XDP BPF_PROG_TEST_RUN microbenchmarks
  against hand-written C/eBPF baselines.
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

Build the paper:

```bash
make -C paper
```

## Current Result Snapshot

The current run evaluates KernelScript commit `6f9e6e8` on Linux
`6.15.11-061511-generic`.

- Unit tests: 85 suites, 1092 tests, 0 reported failures.
- Examples: 44 total, 43 KernelScript compile successes, 41 full generated
  C/eBPF build successes.
- Safety: `safety_demo.ks` is rejected before C generation for 608 bytes of
  stack usage against the 512-byte eBPF limit.
- Compatibility limit: two struct_ops examples build eBPF objects but fail when
  compiling generated skeleton userspace code against libbpf 1.3.0.
- Smoke test: `smoke_lo` attaches and detaches an XDP pass program on `lo`.
- Microbenchmarks: XDP pass has the same median as C/eBPF in this harness
  at 5ns average runtime and 2 instructions; XDP array-map count is 13ns and 21 instructions for
  KernelScript versus 9ns and 11 instructions for hand-written C/eBPF.
