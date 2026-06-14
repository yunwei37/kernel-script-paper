# KernelScript Paper Research Plan

## Claim

KernelScript explores a typed, compiler-checked unified-source programming
model for eBPF. The scientific claim is that a language-level model can
centralize recurring eBPF project structure and reject some verifier-relevant
errors before kernel loading, while preserving a low-level compilation path to
conventional libbpf-compatible artifacts.

## Research Questions

RQ1. Can a unified source model cover the eBPF domains exercised by the
repository examples?

Evidence: compile and build every repository example, then classify each example
by program type and language feature.

RQ2. How much low-level generated project structure does the language centralize?

Evidence: compare KernelScript source SLOC with generated userspace C, eBPF C,
kernel-module C, and Makefile SLOC. This is not a hand-written C baseline. It is
a conservative expansion-factor measurement showing the amount of generated
artifact a developer does not have to maintain by hand.

RQ3. Which classes of errors are rejected before load/attach time?

Evidence: run the full compiler test suite and a targeted static-check corpus.
The corpus includes lifecycle API misuse, program-signature violations, map
type and symbol errors, general type errors, config-boundary violations,
helper-scope violations, kernel-context allocation violations, perf-event group
bound violations, ring-buffer API misuse, an eBPF stack-limit violation, and
one positive control.

RQ4. Do generated artifacts remain compatible with the local kernel toolchain?

Evidence: compile generated eBPF objects, generate libbpf skeletons with
`bpftool`, link userspace loaders, and build generated kernel modules when
present. Then run `bpftool prog loadall` on each generated eBPF object to
classify which objects pass kernel verifier loading and actually pin at least
one BPF program, without attaching them.

RQ5. Can generated XDP artifacts attach and detach in an isolated deployment
setting?

Evidence: `experiments/run_smoke.sh` compiles `smoke_lo.ks`, builds the generated
project, and uses `sudo -n` to attach/detach an XDP pass program on the loopback
interface. `experiments/run_attach_matrix.py` then filters the verifier-clean
single-section XDP objects, creates a fresh network namespace and veth pair for
each object, attaches it with iproute2, confirms `prog/xdp` in `ip -d link
show`, detaches it, and removes the namespace. `experiments/run_perf_event_loader.py`
also checks one generated perf_event loader against a hand-written C/libbpf
loader baseline with an attach, counter-read, and detach oracle.
`experiments/run_perf_event_counter.py` adds a sustained page-fault perf_event
map-counter workload for generated and hand-written eBPF objects.
`experiments/run_ringbuf_workload.py` adds a matched XDP ring-buffer
event-emission workload with submitted/received/drop oracles.
`experiments/run_struct_ops_compat.py` adds a direct libbpf load/attach/detach
check for the generated tcp-congestion struct_ops object and a hand-written
C/eBPF object with the same minimal function set, without relying on generated
skeleton code. `experiments/run_struct_ops_workload.py` adds a loopback TCP
socket workload that selects the registered BPF congestion-control algorithm,
transfers a fixed byte count, and detaches. `experiments/run_struct_ops_skeleton_repair.py`
rebuilds the two generated struct_ops userspace projects before and after a
version-aware generated-skeleton repair for the local libbpf map-link mismatch.
`experiments/run_struct_ops_callback_workload.py` adds a callback-flag variant
of that TCP workload and checks that cong_avoid plus cwnd_event are reached in
clean loopback transfers, then adds a loss-injected profile that reaches
ssthresh, cong_avoid, set_state, and cwnd_event in both generated and C/eBPF
objects. `experiments/run_sched_ext_verifier.py` adds a scheduler-extension
struct_ops verifier diagnostic that compiles `sched_ext_simple.ks` and a
five-callback hand-written C/eBPF control baseline, runs `bpftool prog loadall`
only, records `/sys/kernel/sched_ext` state before and after, and does not
attach a scheduler.

RQ6. Is the XDP map-update gap caused by the unified source model or by a
specific lowering choice?

Evidence: apply a tracked compiler-source patch to a copied KernelScript
compiler tree, rebuild the patched compiler, compile the same XDP count
benchmark, and rerun the same BPF_PROG_TEST_RUN harness against the current
compiler object and hand-written C/eBPF. The patch lowers constant increments
on integer array maps from lookup-plus-update to checked lookup plus in-place
atomic add. The harness resets and reads the `counts` map on every trial to
verify that all variants perform the same 100000 increments. Then run matched
KernelScript and hand-written C/eBPF XDP and TC pass/count objects over iperf3
TCP traffic on isolated veth pairs, repeat the XDP/TC traffic checks with
longer per-trial stress runs, plus matched ring-buffer event emission through
one libbpf runner.

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
   - Verifies lifecycle API, program signature, map type/symbol, type-system,
     config-boundary, helper-scope, kernel-context allocation, perf-event
     group-bound, ringbuf API, symbol-validation, and stack-limit diagnostics.
   - Writes `results/static_checks_summary.csv` and
     `results/static_checks_summary.json`.

3. `experiments/run_verifier_matrix.py`
   - Reads `results/examples_summary.csv` after `run_evaluation.py`.
   - Attempts `bpftool prog loadall` for every generated eBPF object under
     `results/build/examples`.
   - Counts an object as loadable only when `bpftool` succeeds and at least one
     program is pinned under `/sys/fs/bpf/kernelscript-paper`.
   - Removes pins after each attempt and keeps raw bpftool logs under
     `results/logs/verifier_matrix`.
   - Writes `results/verifier_matrix_summary.csv` and
     `results/verifier_matrix_summary.json`.

4. `experiments/run_attach_matrix.py`
   - Reads `results/verifier_matrix_summary.csv`.
   - Selects verifier-clean, single-section XDP objects.
   - Creates a fresh network namespace and veth pair per object.
   - Attaches with `ip link set ... xdp obj ... sec xdp`, confirms `prog/xdp`,
     detaches, and cleans the namespace.
   - Writes `results/attach_matrix_summary.csv` and
     `results/attach_matrix_summary.json`.

5. `experiments/run_smoke.sh`
   - Compiles and builds `experiments/programs/smoke_lo.ks`.
   - Runs the generated binary with `sudo -n`.
   - Writes `results/smoke_summary.json` and logs under `results/logs/`.

6. `experiments/run_microbench.py`
   - Compiles two KernelScript XDP microbenchmarks and two hand-written C/eBPF
     baselines.
   - Loads each object with `bpftool prog load`.
   - Runs each object with `bpftool prog run ... repeat 100000` for seven
     trials.
   - Writes `results/microbench_summary.csv` and
     `results/microbench_summary.json`.

7. `experiments/run_compiler_patch_ablation.py`
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

8. `experiments/run_xdp_traffic.py`
   - Compiles the same KernelScript XDP pass/count programs and hand-written
     C/eBPF baselines.
   - Creates a fresh network namespace and veth pair for each trial.
   - Attaches each XDP object to the receiver-side veth and runs iperf3 TCP
     traffic through the path.
   - Reads the `counts` map for count variants as a positive execution oracle.
   - Writes `results/xdp_traffic_summary.csv` and
     `results/xdp_traffic_summary.json`.

9. `experiments/run_tc_traffic.py`
   - Compiles KernelScript TC ingress pass/count programs and hand-written
     C/eBPF baselines.
   - Creates a fresh network namespace and veth pair for each trial.
   - Attaches each object with `tc qdisc clsact` and a direct-action BPF filter.
   - Reads the `counts` map for count variants as a positive execution oracle.
   - Writes `results/tc_traffic_summary.csv` and
     `results/tc_traffic_summary.json`.

10. `experiments/run_perf_event_loader.py`
   - Compiles `kernelscript/examples/perf_page_fault.ks` into a generated
     loader.
   - Compiles a matched hand-written C/libbpf perf_event loader baseline.
   - Runs both binaries with `sudo -n` for twenty trials.
   - Requires two perf_event attaches, a positive page-fault counter, a
     branch-miss counter read, and clean detach.
   - Writes `results/perf_event_loader_summary.csv` and
     `results/perf_event_loader_summary.json`.

11. `experiments/run_traffic_stress.py`
   - Runs the XDP and TC traffic harnesses with a separate `stress` result
     label.
   - Uses 3 trials of 5 seconds by default for each XDP/TC pass/count variant.
   - Preserves the headline 1s traffic summaries while writing
     `results/xdp_traffic_stress_summary.json`,
     `results/tc_traffic_stress_summary.json`, and
     `results/traffic_stress_summary.json`.
   - Requires all XDP and TC traffic oracles to pass.

12. `experiments/run_perf_event_counter.py`
   - Compiles a KernelScript perf_event page-fault counter and a matched
     hand-written C/eBPF object.
   - Uses one libbpf runner to attach both objects to a software page-fault perf
     event.
   - Touches 65536 pages for 4 rounds per trial and reads the `counts` map.
   - Requires the BPF map count to equal the perf counter read in every trial.
   - Writes `results/perf_event_counter_summary.csv` and
     `results/perf_event_counter_summary.json`.

13. `experiments/run_ringbuf_workload.py`
   - Compiles a KernelScript XDP ringbuf event emitter and a matched
     hand-written C/eBPF object.
   - Uses one libbpf runner to execute both objects through BPF_PROG_TEST_RUN
     and consume the ring buffer.
   - Requires submitted events to equal received events with zero drops, bad
     markers, bad return values, or runner errors.
   - Writes `results/ringbuf_workload_summary.csv` and
     `results/ringbuf_workload_summary.json`.

14. `experiments/run_struct_ops_compat.py`
   - Compiles `kernelscript/examples/struct_ops_simple.ks` with `make
     ebpf-only`.
   - Compiles a hand-written tcp-congestion struct_ops C/eBPF object with the
     same minimal function set.
   - Uses one libbpf runner to load each object, find the struct_ops map,
     attach it with `bpf_map__attach_struct_ops`, and destroy the returned
     link.
   - Records the bpftool/libbpf version skew and whether the installed
     `struct bpf_map_skeleton` header supports map-link fields.
   - Writes `results/struct_ops_compat_summary.csv` and
     `results/struct_ops_compat_summary.json`.

15. `experiments/run_struct_ops_workload.py`
   - Compiles the same generated and hand-written tcp-congestion struct_ops
     objects as the direct compatibility check.
   - Uses one libbpf runner to load and attach each object.
   - Creates a loopback TCP client/server pair, selects the registered BPF
     algorithm with `TCP_CONGESTION` on the sender socket, and transfers a fixed
     byte count.
   - Requires algorithm selection, full byte transfer, successful client exit,
     and detach in every trial.
   - Writes `results/struct_ops_workload_summary.csv` and
     `results/struct_ops_workload_summary.json`.

16. `experiments/run_struct_ops_callback_workload.py`
   - Compiles callback-flag generated and hand-written tcp-congestion
     struct_ops objects.
   - Uses one libbpf runner to load and attach each object, reset callback
     flags, run clean and loss-injected loopback TCP transfers, read callback
     flags, and detach.
   - Requires full byte transfer plus cong_avoid and cwnd_event flags in every
     clean trial, and full byte transfer plus ssthresh, cong_avoid, set_state,
     and cwnd_event flags in every loss-injected trial.
   - Writes `results/struct_ops_callback_workload_summary.csv` and
     `results/struct_ops_callback_workload_summary.json`.

17. `experiments/run_struct_ops_skeleton_repair.py`
   - Compiles `kernelscript/examples/struct_ops_simple.ks` and
     `kernelscript/examples/sched_ext_simple.ks` into generated projects.
   - Records the original generated userspace build status and classifies the
     local map-link field mismatch.
   - Detects whether the installed `struct bpf_map_skeleton` header supports
     map-link fields.
   - Removes the generated map-link assignments only when that field is absent,
     then rebuilds the generated userspace projects.
   - Writes `results/struct_ops_skeleton_repair_summary.csv` and
     `results/struct_ops_skeleton_repair_summary.json`.

18. `experiments/run_sched_ext_verifier.py`
   - Compiles `kernelscript/examples/sched_ext_simple.ks` with KernelScript and
     a five-callback hand-written scheduler-extension C/eBPF control baseline.
   - Uses `bpftool prog loadall` only, with no scheduler attach or registration.
   - Requires the C/eBPF baseline to verifier-load and records generated-object
     load status, failure class, pinned-program counts, and sched_ext state
     before and after the diagnostic.
   - Writes `results/sched_ext_verifier_summary.csv` and
     `results/sched_ext_verifier_summary.json`.

19. `experiments/run_lowering_ablation.py`
   - Compiles the KernelScript XDP count benchmark.
   - Copies the generated project and patches the map update lowering from
     lookup plus update helper to in-place atomic add.
   - Rebuilds the patched eBPF object and compares it with the unpatched object
     and hand-written C/eBPF using BPF_PROG_TEST_RUN.
   - Resets and reads the pinned `counts` map on every trial as a correctness
     oracle.
   - Writes `results/lowering_ablation_summary.csv` and
     `results/lowering_ablation_summary.json`.

20. `experiments/update_paper_numbers.py`
   - Checks that unit tests, static checks, smoke test, microbenchmarks, and
     XDP traffic, TC traffic, traffic stress, perf_event loader lifecycle,
     perf_event counter, ringbuf workload, struct_ops compatibility, struct_ops
     workload, struct_ops callback workload, struct_ops skeleton repair,
     scheduler-extension verifier diagnostic, verifier matrix, attach matrix,
     and both lowering ablations have successful summaries.
   - Writes `results/paper_numbers.tex` for the LaTeX paper.

## Current Results

At commit `ccb15b4`, on Linux `6.15.11-061511-generic`:

- 85 unit test suites and 1095 unit tests pass.
- 43 of 44 examples compile from KernelScript.
- 41 examples build fully into generated C/eBPF artifacts.
- The verifier-load matrix loads 38 of 43 generated eBPF objects and confirms
  that each loadable object pins at least one BPF program. Among the 41 objects
  from full generated-project build successes, 37 load successfully and 4 expose
  reference-ownership, map-creation, local BTF-symbol, or no-program-pinned
  failures. Across all generated objects, one additional struct_ops object
  exposes an argument-type rejection.
- The isolated attach matrix attaches and detaches 27 of 27 verifier-clean
  single-section XDP objects on fresh veth devices inside network namespaces.
- The one KernelScript rejection is an intentional safety rejection for stack
  usage above the eBPF limit.
- The static-check corpus has 28 cases, including 27 expected compiler
  rejections and 1 positive control across lifecycle, signature, map, type,
  symbol, config, helper-scope, kernel-context, perf-event group, ringbuf, and
  safety categories, all matching expected outcomes.
- The two generated build failures are struct_ops examples whose generated
  skeletons expect a `struct bpf_map_skeleton.link` field unavailable in the
  installed libbpf 1.3.0 headers.
- The direct struct_ops compatibility check loads, attaches, and detaches both
  the generated tcp-congestion object and a minimal C/eBPF object in 3 of 3
  privileged trials, separating object compatibility from the generated
  skeleton/header mismatch on this host.
- The struct_ops TCP workload check selects the generated and C/eBPF BPF
  congestion-control algorithms on loopback sender sockets, transfers 1MiB, and
  detaches successfully in 10 of 10 privileged trials for both variants.
- The struct_ops callback workload check transfers 4MiB on clean loopback and
  confirms cong_avoid plus cwnd_event flags in 10 of 10 privileged trials for
  both generated and C/eBPF variants. Its 5% loss-injected profile transfers
  4MiB in 5 of 5 trials per variant and confirms ssthresh, cong_avoid,
  set_state, and cwnd_event for both variants.
- The struct_ops skeleton repair check confirms the original generated
  userspace builds succeed for 0 of 2 affected examples, removes 2 local
  version-incompatible map-link assignments from generated skeleton headers,
  and rebuilds 2 of 2 generated userspace projects successfully.
- The scheduler-extension struct_ops verifier diagnostic confirms that a
  five-callback hand-written C/eBPF control baseline verifier-loads and pins 5
  programs while the generated `sched_ext_simple` object fails before pinning
  with a `struct_ops_task_arg_type` diagnostic. The script does not attach a
  scheduler: `/sys/kernel/sched_ext/state` remains `disabled`, and `enable_seq`
  remains `0`.
- Successful examples have median 31 KernelScript SLOC and median 472 generated
  source/build SLOC, a median expansion factor of 11.3x.
- The smoke test successfully attaches and detaches an XDP program on `lo`.
- XDP microbenchmarks show 0ns median overhead for a trivial pass program
  compared with hand-written C/eBPF, and 4ns median overhead for an array-map
  counter because the generated code emits a lookup plus update helper rather
  than an in-place atomic add.
- The XDP traffic benchmark runs matched KernelScript and hand-written C/eBPF
  pass/count objects over iperf3 TCP on fresh veth/netns pairs. Pass medians are
  17.8Gb/s for KernelScript and 18.1Gb/s for C/eBPF. Count medians are 17.4Gb/s
  for KernelScript and 17.5Gb/s for C/eBPF, with positive count-map invocation
  rates of 1.51 and 1.52 Mpps respectively.
- The TC traffic benchmark runs matched KernelScript and hand-written C/eBPF
  ingress pass/count objects over iperf3 TCP on fresh veth/netns pairs. Pass
  medians are 86.7Gb/s for KernelScript and 87.4Gb/s for C/eBPF. Count medians
  are 87.0Gb/s for KernelScript and 90.6Gb/s for C/eBPF, with positive
  count-map invocation rates of 0.25 and 0.26 Mpps respectively.
- The longer traffic stress rerun uses 3 trials of 5s per XDP/TC pass/count
  variant. All stress oracles pass. XDP count medians are 17.8Gb/s for
  KernelScript and 18.1Gb/s for C/eBPF, and TC count medians are 86.5Gb/s for
  KernelScript and 91.1Gb/s for C/eBPF.
- The perf_event loader lifecycle test runs a generated KernelScript loader and
  a hand-written C/libbpf loader for 20 privileged trials. Both attach two
  perf_event programs, read counters, and detach cleanly in every trial.
- The perf_event page-fault counter workload runs matched KernelScript and
  hand-written C/eBPF objects for 10 privileged trials. Both report median
  262147 BPF map updates matching perf counter reads, at 1.13 and 1.13 million
  events/s respectively.
- The ring-buffer event-emission workload runs matched KernelScript and
  hand-written C/eBPF objects for 10 privileged trials. Both submit and receive
  50000 events per trial with zero drops, at 2.08 and 2.14 million events/s
  respectively.
- The compiler-patch lowering ablation reduces the generated count object from
  21 to 11 instructions and from 12ns to 9ns median, matching the hand-written
  C/eBPF baseline in this harness while preserving the expected 100000 count
  updates in every trial.

## Threats and Next Experiments

The current runtime evaluation combines attach/detach checks,
BPF_PROG_TEST_RUN microbenchmarks, local veth/TCP traffic benchmarks for XDP and
TC, one longer local XDP/TC traffic stress rerun, one generated perf_event
loader lifecycle latency test, a perf_event page-fault map-counter workload, a
ring-buffer event-emission workload, one direct struct_ops compatibility check,
one loopback struct_ops TCP workload, one callback-flag tcp-congestion
workload, and one local struct_ops skeleton build repair.
The attach matrix confirms that verifier-clean single-section XDP objects can
be installed and removed on isolated veth devices, and the traffic benchmark
checks matched XDP and TC pass/count objects under real TCP traffic. The
stress rerun extends that check to three 5s trials per variant while retaining
the same oracles. The perf_event lifecycle test checks one generated
repository-example loader against a matched C/libbpf loader, the counter
workload checks one sustained page-fault event path, and the ring-buffer
workload checks object-level event delivery and loss. The struct_ops TCP
workload checks socket-level algorithm selection and byte transfer, and the
callback-flag workload checks clean-loopback cong_avoid/cwnd_event reachability
and loss-injected ssthresh/cong_avoid/set_state/cwnd_event reachability. The
repair checks one local generated userspace build fix but does not run the
repaired binaries. The scheduler-extension verifier diagnostic shows that the
local kernel/toolchain accepts a five-callback C/eBPF control object but rejects
the generated object before any scheduler attach. The evaluation still does not validate
NIC-rate throughput, scheduler-extension workload behavior, every
tcp-congestion callback path, broader skeleton version coverage, broader
perf_event workloads, or generated-loader throughput.
A full runtime comparison should add scheduler-extension workload evidence
after fixing the generated lowering gap, more tcp-congestion callback coverage,
upstream-integrated skeleton generation across libbpf versions, broader
perf_event workloads, and larger or non-local XDP/TC stress runs with `pktgen`
or `xdp-bench` that report throughput, tail latency, verifier log size, and CPU
utilization.
The current compiler-source patch should be
upstreamed or otherwise integrated, semantically generalized beyond constant
array-map increments where safe, and retested across hash, per-CPU, and
structured map values. The current artifact is still useful as a systems
prototype study because it grounds claims about example marker coverage,
generated structure, compatibility, attachability for an XDP subset,
small-program runtime overhead, local XDP/TC traffic behavior, ring-buffer
event delivery, local tcp-congestion struct_ops workload and callback-flag
behavior, local struct_ops skeleton repair, and one concrete lowering optimization in
reproducible evidence.
