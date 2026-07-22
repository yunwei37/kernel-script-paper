# Plan Review: Q1 Heimdall Verifier-Gap Exemplar Replay

## Round 1 — BLOCK (addressed in plan.md)

## Execution — GO (re-run 2026-07-22, honesty fix)

Runner: `experiments/q1_published_bug_replay/run.py`  
Summary: `results/q1_published_bug_replay_summary.json` status `ok`, `ks_earlier` 3/3.

### Honest stage labels (post-fix)

| Defect | C buggy stage | What is claimed |
|---|---|---|
| context | `runtime_accept` | Wrong-typed XDP object loads and executes; **no** non-zero field-remapping oracle (`ctx_in` unsupported) |
| oversized_update | `runtime_wrong` | Truncation to `{1,2}` in 8B slot over 10 trials |
| reinterpretation | `runtime_wrong` | `conn{1,2}` reinterpreted as native-endian u64 over 10 trials |

### KS fixed controls

Each corrected KernelScript sibling runs:
`compile → make ebpf-only → bpftool loadall → shared BPF_PROG_TEST_RUN oracle`
and must reach `runtime_ok`. Cases use `headers/xdp.kh` so generated C does not
redefine vmlinux enums.

### Deviations from ideal plan.md

- XDP `BPF_PROG_TEST_RUN` `ctx_in` unsupported on this host; context does not
  assert non-zero queue/ifindex under misnamed fields.
- Claim cap unchanged: three exemplars, two families, vs C/libbpf only.
