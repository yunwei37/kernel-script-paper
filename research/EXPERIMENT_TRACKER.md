Last updated: 2026-06-13
Stage at update: execute
Source/command: auto-research-orchestrator tracker initialization

# Experiment Tracker

| Run ID | Claim | Purpose | Command/config | Commit | Machine | Seed/reps | Result path | Status |
|---|---|---|---|---|---|---|---|---|
| R001 | C3 | Strict verifier-load matrix | `./experiments/run_verifier_matrix.py` | `ccb15b4` KernelScript / `f9af9b2` paper harness | `results/environment.json` | full generated object corpus | `results/verifier_matrix_summary.json` | done |
| R002 | C3 | Isolated XDP attach matrix | `./experiments/run_attach_matrix.py` | `ccb15b4` KernelScript / `f9af9b2` paper harness | `results/environment.json` | all verifier-clean single-section XDP objects | `results/attach_matrix_summary.json` | done |
| R003 | C4 | Traffic-driven XDP matched baseline | `./experiments/run_xdp_traffic.py` | `ccb15b4` KernelScript / working tree after `f9af9b2` paper harness | `results/environment.json` | 10 trials, 1 second TCP per trial | `results/xdp_traffic_summary.json` | done |
