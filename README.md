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
- `experiments/run_traffic_stress.py`: longer XDP and TC traffic stress rerun
  that writes separate stress summaries without replacing headline results.
- `experiments/run_perf_event_loader.py`: generated perf_event loader lifecycle
  latency check against a hand-written C/libbpf loader baseline.
- `experiments/run_perf_event_counter.py`: perf_event page-fault map-counter
  workload against a hand-written C/eBPF baseline.
- `experiments/run_ringbuf_workload.py`: XDP ring-buffer event-emission
  workload against a hand-written C/eBPF baseline.
- `experiments/run_struct_ops_compat.py`: direct struct_ops load/attach/detach
  compatibility check against a hand-written C/eBPF baseline.
- `experiments/run_struct_ops_workload.py`: loopback TCP workload using selected
  BPF tcp-congestion struct_ops algorithms.
- `experiments/run_struct_ops_callback_workload.py`: loopback TCP workload that
  verifies selected tcp-congestion callbacks are reached with BPF map flags.
- `experiments/run_struct_ops_skeleton_repair.py`: version-aware generated
  struct_ops skeleton build repair for local libbpf header mismatches.
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

Run the optional longer traffic stress rerun, which also requires `sudo -n`,
`iperf3`, and local veth/netns support:

```bash
./experiments/run_traffic_stress.py
```

Run the optional perf_event generated-loader lifecycle latency check, which
requires `sudo -n`:

```bash
./experiments/run_perf_event_loader.py
```

Run the optional perf_event page-fault counter workload, which also requires
`sudo -n`:

```bash
./experiments/run_perf_event_counter.py
```

Run the optional ring-buffer event-emission workload, which also requires
`sudo -n`:

```bash
./experiments/run_ringbuf_workload.py
```

Run the optional struct_ops compatibility check, which also requires
`sudo -n`:

```bash
./experiments/run_struct_ops_compat.py
```

Run the optional struct_ops TCP workload check, which also requires `sudo -n`:

```bash
./experiments/run_struct_ops_workload.py
```

Run the optional struct_ops callback workload check, which also requires
`sudo -n`:

```bash
./experiments/run_struct_ops_callback_workload.py
```

Run the optional struct_ops skeleton repair check:

```bash
./experiments/run_struct_ops_skeleton_repair.py
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
- Static checks: 28 total cases, including 27 expected compiler rejections and
  1 positive control, all matching expected outcomes across lifecycle,
  signature, map, type, symbol, config, helper-scope, kernel-context,
  perf-event group, ringbuf, and safety categories.
- Safety: `safety_demo.ks` is rejected before C generation for 608 bytes of
  stack usage against the 512-byte eBPF limit.
- Compatibility limit: two struct_ops examples build eBPF objects but fail when
  compiling generated skeleton userspace code against libbpf 1.3.0.
- Struct_ops skeleton repair: on this host, original generated userspace builds
  succeed for 0 of 2 affected struct_ops examples; after removing 2
  version-incompatible map-link assignments from the generated skeleton headers,
  2 of 2 generated userspace projects build.
- Struct_ops TCP workload: over ten privileged trials, both the generated
  tcp-congestion object and the C/eBPF object are selected with `TCP_CONGESTION`
  on a loopback sender socket, transfer 1MiB, and detach successfully in 10 of
  10 trials.
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
- Longer traffic stress: over three 5s iperf3 TCP trials per variant, all XDP
  and TC pass/count stress oracles pass. XDP count medians are 17.8Gb/s for
  KernelScript and 18.1Gb/s for C/eBPF. TC count medians are 86.5Gb/s for
  KernelScript and 91.1Gb/s for C/eBPF.
- Perf_event generated-loader lifecycle latency: over twenty privileged trials,
  both the generated `perf_page_fault` loader and a hand-written C/libbpf loader
  attach two perf_event programs, read positive page-fault counters, read
  branch-miss counters, and detach cleanly. Median end-to-end invocation
  latencies are 11.1ms and 15.2ms, with p90 latencies of 44.1ms and 40.3ms,
  respectively.
- Perf_event page-fault counter workload: over ten privileged trials, both
  KernelScript and C/eBPF objects report median 262147 BPF map updates matching
  perf counter reads. Median event rates are 1.13 and 1.13 million events/s,
  respectively.
- Ring-buffer event-emission workload: over ten privileged trials, both
  KernelScript and C/eBPF objects submit and receive 50000 events per trial with
  zero drops. Median event rates are 2.08 and 2.14 million events/s,
  respectively.
- Struct_ops compatibility: over three privileged trials, one direct libbpf
  runner loads, attaches, and detaches both the generated tcp-congestion
  struct_ops object and a minimal C/eBPF object with the same function set. The
  unmodified generated skeleton build still fails because bpftool v7.7
  skeletons require map-link fields absent from libbpf-dev 1.3.0.
- Struct_ops skeleton repair: `run_struct_ops_skeleton_repair.py` detects that
  libbpf-dev 1.3.0 lacks skeleton map-link field support, removes one generated
  map-link assignment from each affected skeleton header, and rebuilds both
  generated userspace projects successfully. This is a local build repair, not
  a scheduler workload or cross-version portability claim.
- Struct_ops TCP workload: `run_struct_ops_workload.py` attaches the generated
  and C/eBPF tcp-congestion objects, selects the registered BPF algorithm on a
  loopback TCP sender socket, transfers 1MiB, and detaches. This is a local
  socket-level workload oracle, not a production TCP throughput claim.
- Struct_ops callback workload: `run_struct_ops_callback_workload.py` attaches
  callback-flag variants of the generated and C/eBPF tcp-congestion objects,
  transfers 4MiB on loopback, and confirms `cong_avoid` plus `cwnd_event` are
  reached in 10/10 trials for both variants. This is callback-reachability
  evidence for this workload, not coverage of every TCP callback.
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
