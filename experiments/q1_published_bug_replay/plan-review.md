# Plan Review: Q1 Heimdall Verifier-Gap Exemplar Replay

## Round 1 — BLOCK (addressed)

Initial plan issues (combined Listing 6 defects, underspecified oracles, overstated claim) were repaired in `plan.md`.

## Execution status — GO (executed 2026-07-22)

Runner: `experiments/q1_published_bug_replay/run.py`
Result: `results/q1_published_bug_replay_summary.json` status `ok`, `ks_earlier` 3/3.

Deviations from the ideal plan:
- XDP `BPF_PROG_TEST_RUN` ctx_in is unsupported on this host (EINVAL for all sizes); context oracle checks execute field stores + XDP_PASS over 10 trials, not non-zero queue/ifindex remapping.
- Map-schema oracles (truncation, native reinterpretation) fully match the plan.

Claim cap remains: three published exemplars in two invariant families vs C/libbpf; no prevalence, no Aya comparison.
