Last updated: 2026-06-13
Stage at update: analyze
Source/command: `./experiments/run_source_footprint.py`, `./experiments/run_change_amplification.py`, `./experiments/run_external_corpus.py`, `./experiments/run_external_port.py`, `./experiments/run_xdp_traffic.py`, `./experiments/run_tc_traffic.py`, `./experiments/run_traffic_stress.py`, `./experiments/run_perf_event_loader.py`, `./experiments/run_perf_event_counter.py`, `./experiments/run_ringbuf_workload.py`, `./experiments/run_struct_ops_workload.py`, `./experiments/run_struct_ops_callback_workload.py`, `./experiments/run_sched_ext_verifier.py`, `./experiments/run_sched_ext_attach.py --allow-host-scheduler`, and checked-in result summaries

# Results Summary

## Headline Result

The artifact now has a matched source-footprint proxy, a broader 28-case static
rejection corpus, local
traffic-driven XDP and TC checks, one generated perf_event loader lifecycle
latency check, one perf_event page-fault counter workload, and one ringbuf
event-emission workload, direct tcp-congestion struct_ops load/attach/detach
compatibility, a loopback TCP workload through selected BPF tcp-congestion
algorithms, a callback-flag workload with clean and loss-injected reachability
profiles, a version-aware struct_ops skeleton build repair, a scheduler-extension
struct_ops verifier diagnostic, an opt-in scheduler-extension attach/workload
check, and a longer XDP/TC traffic stress rerun in addition to
BPF_PROG_TEST_RUN microbenchmarks. The source-footprint proxy covers 11 local
workload rows: unique maintained KernelScript application sources total 203
nonblank noncomment lines, the matching hand-written C/eBPF object sources
total 254 lines, and the C/libbpf baseline source footprint totals 1105 lines
when runner or loader files are included. This is matched source-footprint evidence,
not a developer-time study. A separate checked-in change-amplification study
applies 5 matched micro-edits to BPFScript and hand-written C/libbpf fixtures:
the medians are 1 changed file, 2 edit sites, and 6 changed lines for
KernelScript versus 2 changed files, 7 edit sites, and 30 changed lines for
the hand-written split. None of the 5 KernelScript edits require manual
kernel/userspace/skeleton synchronization, while the C/libbpf versions require
userspace synchronization in 5/5 cases, kernel synchronization in 4/5 cases,
and skeleton or section-convention synchronization in 3/5 cases. The external source-corpus scan covers 3 pinned
public eBPF repositories, 166 selected C/header files, 34843 nonblank noncomment
lines, and 14 tracked feature families; a 7-file manual spot-check matches the
expected classifier markers with zero false-positive or false-negative feature
labels. It is source-only feature context, not translation, build, verifier,
attach, or runtime evidence. A separate manual external portfolio ports
`xdp-tutorial/basic01-xdp-pass`, `basic02-prog-by-name`, and
`basic03-map-counter` to KernelScript. The ports build through generated
Makefiles, while the original external C/eBPF sources compile directly to BPF
objects with clang. All 6 variants attach as XDP programs and pass five
one-second iperf3 traffic trials; the map-counter pair also increments the
XDP_PASS map key. The KernelScript ports and original C/eBPF bodies each total
45 SLOC. These numbers are descriptive local samples, not a performance
ranking. On
fresh veth/netns
pairs with iperf3 TCP, KernelScript and hand-written C/eBPF pass/count objects
all pass the traffic oracles. XDP count medians are 17.2 Gb/s for KernelScript
and 17.3 Gb/s for C/eBPF. TC count medians are 93.0 Gb/s for KernelScript and
90.7 Gb/s for C/eBPF. The generated perf_event loader and the hand-written
C/libbpf loader both pass 20/20 attach, counter-read, and detach trials. Median
end-to-end invocation latencies are 15.7ms and 18.2ms, with p90 latencies of
20.6ms and 21.1ms, respectively. The
perf_event counter workload reports 1.02 versus 1.05 million events/s for
generated and hand-written objects with exact BPF/perf counter agreement. The
ringbuf workload reports 2.09 versus 2.18 million events/s with exact
submitted/received agreement and zero drops, and the generated `.ebpf.c`
contains the expected `bpf_ringbuf_reserve_dynptr` / `bpf_dynptr_data` /
`bpf_dynptr_write` / `bpf_ringbuf_submit_dynptr` helper pattern. The struct_ops compatibility
check loads, attaches, and detaches both generated and C/eBPF tcp-congestion
objects in 3/3 privileged trials without using generated skeletons. The
struct_ops TCP workload selects the registered generated and C/eBPF BPF
congestion-control algorithms on loopback sender sockets, transfers 1MiB, and
detaches in 10/10 trials for both variants. The clean callback-flag workload
transfers 4MiB and reaches cong_avoid plus cwnd_event in 10/10 trials for both
generated and C/eBPF variants. Its 5% loss-injected profile transfers 4MiB in
5/5 trials per variant and reaches ssthresh, cong_avoid, set_state, and
cwnd_event for both variants. The
struct_ops skeleton repair changes the two original generated userspace build
failures from 0/2 to 2/2 repaired builds on this host by removing 2
version-incompatible map-link assignments. The scheduler-extension diagnostics
show that the five-callback hand-written C/eBPF control baseline
verifier-loads and pins 5 programs, while the generated `sched_ext_simple`
object verifier-loads and pins 12 programs without scheduler attachment. The
separate opt-in attach harness registers both toy FIFO schedulers, runs a
bounded 0.75s CPU workload for five trials per variant, records per-worker
iteration progress, unregisters both, and returns `/sys/kernel/sched_ext/state`
to disabled with zero rejected sched_ext tasks. Median total worker-loop
iterations are about 37M for the generated scheduler and about 32M for the C/eBPF
control, with median per-trial worker-count coefficient of variation below 0.01
for both variants.
The stress
rerun uses three 5s iperf3 trials per XDP/TC pass/count variant; all oracles
pass, with XDP count medians of 17.3 versus 15.3 Gb/s and TC count medians of
89.5 versus 86.1 Gb/s for KernelScript and C/eBPF respectively.

## Completed Runs

| Run ID | Result file | Status | Key result |
|--------|-------------|--------|------------|
| R000 | `results/static_checks_summary.json` | ok | 28/28 static cases match expectation, including 27 expected rejections across lifecycle, signature, map, type, symbol, config, helper-scope, kernel-context, perf-event group, ringbuf, and safety categories. |
| R001 | `results/verifier_matrix_summary.json` | ok | 39/43 generated objects load and pin at least one program; build-success subset is 37/41. |
| R002 | `results/attach_matrix_summary.json` | ok | 27/27 verifier-clean single-section XDP objects attach/detach in isolated namespaces. |
| R003 | `results/xdp_traffic_summary.json` | ok | XDP pass/count KS and C baselines all pass iperf3 traffic; count gap is 0.6% in this local setup. |
| R004 | `results/tc_traffic_summary.json` | ok | TC ingress pass/count KS and C baselines all pass iperf3 traffic; count medians are within 2.5% in this local setup, with this run favoring KernelScript. |
| R005 | `results/perf_event_loader_summary.json` | ok | Generated perf_event loader and C/libbpf baseline both pass 20/20 lifecycle trials; median invocation latencies are 15.7ms and 18.2ms, with p90 latencies of 20.6ms and 21.1ms. |
| R006 | `results/perf_event_counter_summary.json` | ok | Perf_event page-fault counter objects both pass 10/10 trials; median BPF map counts exactly match perf counts at 262147 events. |
| R007 | `results/ringbuf_workload_summary.json` | ok | Ringbuf event-emission objects both pass 10/10 trials; submitted and received counts match at 50000 events with zero drops, and the generated source contains the expected dynptr helper lowering pattern. |
| R008 | `results/struct_ops_compat_summary.json` | ok | Generated and C/eBPF tcp-congestion struct_ops objects both load, attach, and detach in 3/3 trials through one direct libbpf runner. |
| R009 | `results/traffic_stress_summary.json` | ok | Longer 3 x 5s XDP/TC traffic stress rerun passes all oracles; in this local setup, XDP and TC count medians are within 13.0% and 3.9% respectively, with this run favoring KernelScript. |
| R010 | `results/struct_ops_skeleton_repair_summary.json` | ok | Original generated struct_ops userspace builds are 0/2; after a local version-aware skeleton header repair, 2/2 generated userspace projects build. |
| R011 | `results/struct_ops_workload_summary.json` | ok | Generated and C/eBPF tcp-congestion objects each complete 10/10 loopback TCP workload trials with algorithm selection, full byte transfer, and detach success. |
| R012 | `results/struct_ops_callback_workload_summary.json` | ok | Generated and C/eBPF tcp-congestion objects each complete 10/10 clean 4MiB loopback TCP trials with cong_avoid plus cwnd_event, then complete 5/5 5% loss-injected 4MiB trials with ssthresh, cong_avoid, set_state, and cwnd_event. |
| R013 | `results/sched_ext_verifier_summary.json` | ok | Five-callback C/eBPF scheduler-extension control object verifier-loads and pins 5 programs; generated `sched_ext_simple` verifier-loads and pins 12 programs; no scheduler attach is attempted and sched_ext state remains disabled. |
| R014 | `results/sched_ext_attach_summary.json` | ok | Opt-in scheduler-extension attach harness registers the C/eBPF and generated toy FIFO schedulers, keeps sched_ext enabled during five bounded 0.75s CPU progress trials, records per-worker iteration counts, unregisters both, and returns sched_ext to disabled with zero rejected tasks. |
| R015 | `results/source_footprint_summary.json` | ok | Matched source-footprint proxy covers 11 local workload rows; unique maintained KernelScript sources total 203 SLOC, C/eBPF objects alone total 254 SLOC, and C/libbpf sources total 1105 SLOC with runner/loader files included. |
| R016 | `results/change_amplification_summary.json` | ok | Change-amplification study covers 5 matched micro-edits; medians are 1 changed file, 2 edit sites, and 6 changed lines for KernelScript versus 2 changed files, 7 edit sites, and 30 changed lines for hand-written C/libbpf, with manual userspace synchronization required in 5/5 C/libbpf edits and 0/5 KernelScript edits. |
| R017 | `results/external_corpus_summary.json` | ok | External source-corpus scan covers 3 pinned public eBPF repositories, 166 selected C/header files, 34843 SLOC, and 14 tracked feature families; the 7-file classifier spot-check has zero false-positive or false-negative feature labels; no external application is translated, built, verifier-loaded, attached, or run. |
| R018 | `results/external_port_summary.json` | ok | Manual KernelScript ports of three pinned `xdp-tutorial` XDP workloads build through generated Makefiles; the original external C/eBPF sources compile directly with clang; all 6 objects attach and pass 5 x 1s iperf3 trials, and the `basic03-map-counter` pair increments the same XDP_PASS map key. |

## Anomalies And Negative Results

- The stricter verifier matrix reclassifies `local_global_vars` as
  `no_program_pinned`: `bpftool` returned success but pinned only maps because
  the XDP section was empty.
- The XDP stress pass result includes one low generated sample (1.3 Gb/s), so
  the stress pass range is a noise indicator rather than a performance
  comparison claim.
- The longer stress rerun still uses local veth TCP rather than NIC-rate
  traffic. It records retransmits in the XDP stress variants, while the current
  TC stress count rows have zero retransmits. The stress result supports
  short-run sanity/oracle claims more strongly than precise throughput ranking.
- The struct_ops workload exercises socket-level TCP algorithm selection and
  byte transfer. The callback-flag workload confirms cong_avoid/cwnd_event
  reachability for clean loopback transfer and ssthresh/cong_avoid/set_state/
  cwnd_event reachability under 5% loopback loss. It still does not measure
  production TCP performance or cover every tcp-congestion callback path. The
  scheduler-extension verifier diagnostic is load-only evidence, while the
  separate attach harness exercises only one toy FIFO scheduler policy with a
  bounded progress/fairness proxy and does not measure scheduler quality or
  production performance. The skeleton repair validates
  one local generated-userspace build
  fix, but it does not run the
  generated binaries or prove portability across libbpf versions. The
  perf_event counter, ringbuf, and direct struct_ops runs are object checks
  through a shared libbpf runner, and the generated-loader latency check is one
  perf_event lifecycle workload rather than a broad generated-dispatch-loop
  throughput study.
- The source-footprint proxy is not an external application corpus and does not
  measure developer time, debugging effort, or code review effort. It should be
  read as local matched source-footprint evidence only.
- The change-amplification study uses checked-in micro-edits rather than real
  revision histories. It is strong evidence about cross-boundary maintenance
  surfaces, but still not a direct developer-time or debugging-effort study.
- The external source-corpus scan is source-only feature context. It finds no
  tail-call marker in the selected paths and does not translate, build,
  verifier-load, attach, or run any external application.
- The external port check covers three hand-written KernelScript ports from one
  pinned XDP tutorial repository. It is useful external build/runtime evidence
  but not a performance ranking, automated translation result, exact
  packet-count equivalence result, or broad external-application portability
  claim.

## Figure/Table Candidates

- Keep the current microbenchmark table for instruction-level mechanism
  isolation.
- Keep compact runtime paragraphs for ringbuf and struct_ops rather than full
  tables; the draft remains space-bound.

## Result Files Used

- `results/evaluation_summary.json`
- `results/source_footprint_summary.json`
- `results/change_amplification_summary.json`
- `results/external_corpus_summary.json`
- `results/external_corpus_audit.csv`
- `results/external_port_summary.json`
- `results/static_checks_summary.json`
- `results/verifier_matrix_summary.json`
- `results/attach_matrix_summary.json`
- `results/microbench_summary.json`
- `results/compiler_patch_ablation_summary.json`
- `results/xdp_traffic_summary.json`
- `results/tc_traffic_summary.json`
- `results/perf_event_loader_summary.json`
- `results/perf_event_counter_summary.json`
- `results/ringbuf_workload_summary.json`
- `results/struct_ops_compat_summary.json`
- `results/struct_ops_workload_summary.json`
- `results/struct_ops_callback_workload_summary.json`
- `results/struct_ops_skeleton_repair_summary.json`
- `results/sched_ext_verifier_summary.json`
- `results/sched_ext_attach_summary.json`
- `results/traffic_stress_summary.json`
- `results/xdp_traffic_stress_summary.json`
- `results/tc_traffic_stress_summary.json`
