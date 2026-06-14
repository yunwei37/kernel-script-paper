Last updated: 2026-06-13
Stage at update: execute
Source/command: auto-research-orchestrator tracker initialization

# Experiment Tracker

| Run ID | Claim | Purpose | Command/config | Commit | Machine | Seed/reps | Result path | Status |
|---|---|---|---|---|---|---|---|---|
| R000 | C2 | Targeted static rejection corpus | `./experiments/run_static_checks.py` | `ccb15b4` KernelScript / working tree after static-corpus expansion | `results/environment.json` | 28 cases, deterministic | `results/static_checks_summary.json` | done |
| R001 | C3 | Strict verifier-load matrix | `./experiments/run_verifier_matrix.py` | `ccb15b4` KernelScript / `f9af9b2` paper harness | `results/environment.json` | full generated object corpus | `results/verifier_matrix_summary.json` | done |
| R002 | C3 | Isolated XDP attach matrix | `./experiments/run_attach_matrix.py` | `ccb15b4` KernelScript / `f9af9b2` paper harness | `results/environment.json` | all verifier-clean single-section XDP objects | `results/attach_matrix_summary.json` | done |
| R003 | C4 | Traffic-driven XDP matched baseline | `./experiments/run_xdp_traffic.py` | `ccb15b4` KernelScript / working tree after `f9af9b2` paper harness | `results/environment.json` | 10 trials, 1 second TCP per trial | `results/xdp_traffic_summary.json` | done |
| R004 | C3/C4 | Traffic-driven TC ingress matched baseline | `./experiments/run_tc_traffic.py` | `ccb15b4` KernelScript / working tree after `c0e0d4a` paper harness | `results/environment.json` | 10 trials, 1 second TCP per trial | `results/tc_traffic_summary.json` | done |
| R005 | C3 | Generated perf_event loader lifecycle latency | `./experiments/run_perf_event_loader.py` | `ccb15b4` KernelScript / working tree after generated-loader latency harness | `results/environment.json` | 20 privileged trials | `results/perf_event_loader_summary.json` | done |
| R006 | C3/C4 | Perf_event page-fault map-counter workload | `./experiments/run_perf_event_counter.py` | `ccb15b4` KernelScript / working tree after perf loader harness | `results/environment.json` | 10 trials, 65536 pages x 4 rounds | `results/perf_event_counter_summary.json` | done |
| R007 | C3/C4 | Ringbuf event-emission workload | `./experiments/run_ringbuf_workload.py` | `ccb15b4` KernelScript / working tree after perf counter harness | `results/environment.json` | 10 trials, 50000 events/trial | `results/ringbuf_workload_summary.json` | done |
| R008 | C3/C4 | Struct_ops direct load/attach/detach compatibility | `./experiments/run_struct_ops_compat.py` | `ccb15b4` KernelScript / working tree after struct_ops compatibility harness | `results/environment.json` | 3 privileged trials | `results/struct_ops_compat_summary.json` | done |
| R009 | C4 | Longer XDP/TC traffic stress rerun | `./experiments/run_traffic_stress.py` | `ccb15b4` KernelScript / working tree after traffic-stress harness | `results/environment.json` | 3 trials, 5 seconds TCP per variant | `results/traffic_stress_summary.json` | done |
| R010 | C3 | Version-aware struct_ops skeleton repair | `./experiments/run_struct_ops_skeleton_repair.py` | `ccb15b4` KernelScript / working tree after skeleton-repair harness | `results/environment.json` | 2 generated struct_ops examples | `results/struct_ops_skeleton_repair_summary.json` | done |
| R011 | C3/C4 | Loopback TCP struct_ops workload | `./experiments/run_struct_ops_workload.py` | `ccb15b4` KernelScript / working tree after struct_ops workload harness | `results/environment.json` | 10 trials, 1MiB loopback TCP per variant | `results/struct_ops_workload_summary.json` | done |
| R012 | C3/C4 | Callback-flag tcp-congestion struct_ops workload | `./experiments/run_struct_ops_callback_workload.py` | `ccb15b4` KernelScript / working tree after callback-flag struct_ops harness | `results/environment.json` | 10 clean 4MiB trials plus 5 loss-injected 4MiB trials per variant | `results/struct_ops_callback_workload_summary.json` | done |
| R013 | C3/C4 | Scheduler-extension struct_ops verifier diagnostic | `./experiments/run_sched_ext_verifier.py` | `ccb15b4` KernelScript / working tree after scheduler-extension verifier harness | `results/environment.json` | one generated scheduler-extension object plus one matched C/eBPF baseline, no attach | `results/sched_ext_verifier_summary.json` | done |
