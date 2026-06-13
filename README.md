# KernelScript Paper Artifact

This directory contains a cloned KernelScript repository, reproducible
evaluation scripts, generated results, and a paper draft.

## Layout

- `kernelscript/`: cloned upstream repository.
- `experiments/run_evaluation.py`: compiler/test/example build evaluation.
- `experiments/run_verifier_matrix.py`: bpftool verifier-load matrix for
  generated eBPF objects.
- `experiments/run_attach_matrix.py`: isolated network-namespace XDP
  attach/detach matrix for verifier-clean single-section XDP objects.
- `experiments/run_static_checks.py`: positive and negative static-check corpus.
- `experiments/run_smoke.sh`: privileged attach/detach smoke test on `lo`.
- `experiments/run_microbench.py`: XDP BPF_PROG_TEST_RUN microbenchmarks
  against hand-written C/eBPF baselines.
- `experiments/run_xdp_traffic.py`: iperf3-over-veth XDP pass/count traffic
  benchmark against hand-written C/eBPF baselines.
- `experiments/run_tc_traffic.py`: iperf3-over-veth TC ingress pass/count
  traffic benchmark against hand-written C/eBPF baselines.
- `experiments/run_perf_event_loader.py`: generated perf_event loader lifecycle
  check against a hand-written C/libbpf loader baseline.
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

Run the isolated XDP attach matrix, which requires `sudo -n`, `ip`, and the
verifier summary from `run_verifier_matrix.py`:

```bash
./experiments/run_attach_matrix.py
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

Run the optional traffic-driven XDP benchmark, which requires `sudo -n`,
`iperf3`, and the same local veth/netns support as the attach matrix:

```bash
./experiments/run_xdp_traffic.py
```

Run the optional traffic-driven TC ingress benchmark, which has the same
requirements and uses `tc qdisc clsact` plus direct-action BPF filters:

```bash
./experiments/run_tc_traffic.py
```

Run the optional perf_event generated-loader lifecycle check, which requires
`sudo -n`:

```bash
./experiments/run_perf_event_loader.py
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
- Verifier-load matrix: 38 of 43 generated eBPF objects load with
  `bpftool prog loadall` and pin at least one BPF program. Among the 41 objects
  from full generated-project build successes, 37 load successfully and 4 fail
  with recorded reference ownership, map-creation, local BTF-symbol, or
  no-program-pinned diagnostics. Across all generated objects, one additional
  struct_ops object exposes an argument-type rejection.
- Attach matrix: 27 of 27 verifier-clean single-section XDP objects attach and
  detach on a fresh veth inside an isolated network namespace.
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
- Traffic-driven XDP benchmark: over ten 1s iperf3 TCP trials on fresh
  veth/netns pairs, pass medians are 17.8Gb/s for KernelScript and 18.1Gb/s for
  hand-written C/eBPF. Count medians are 17.4Gb/s for KernelScript and 17.5Gb/s
  for C/eBPF, with positive `counts` map invocation rates at 1.51 and 1.52 Mpps
  respectively.
- Traffic-driven TC benchmark: over ten 1s iperf3 TCP trials on fresh
  veth/netns pairs, pass medians are 86.7Gb/s for KernelScript and 87.4Gb/s for
  C/eBPF. Count medians are 87.0Gb/s for KernelScript and 90.6Gb/s for C/eBPF,
  with positive `counts` map invocation rates at 0.25 and 0.26 Mpps
  respectively.
- Perf_event generated-loader lifecycle: over five privileged trials, both the
  generated `perf_page_fault` loader and a hand-written C/libbpf loader attach
  two perf_event programs, read positive page-fault counters, read branch-miss
  counters, and detach cleanly.
- Compiler-patch lowering ablation: applying
  `experiments/patches/kernelscript-map-increment-lowering.patch` to a copied
  KernelScript compiler tree reduces the count object from 21 to 11
  instructions and from 12ns to 9ns median, matching the hand-written C/eBPF
  baseline in this harness. Each trial resets and reads the `counts` map to
  verify the expected 100000 increments.
- The standalone `run_microbench.py` count row reports 13ns, while the
  compiler-patch ablation rerun reports 12ns for the current KernelScript count
  object. The paper's count rows intentionally come from the ablation rerun so
  current, patched, and C objects share one timing run.
