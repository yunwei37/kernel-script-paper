# Q1 Published Bug Replay Results

Status: **ok**
Positive (ks_earlier) rows: 3 / 3

Stage vocabulary:
- `runtime_wrong`: C buggy object loads and the defect-specific map oracle holds
  (truncation or reinterpretation).
- `runtime_accept`: C buggy object loads and executes under BPF_PROG_TEST_RUN;
  used for the context case where non-zero field remapping is **not** claimed
  (`ctx_in` unsupported on this host).
- KS fixed controls run generate → `make ebpf-only` → verifier → shared oracle.

| Defect | Listing | KS buggy | C buggy | KS fixed | C fixed | Verdict |
|---|---|---|---|---|---|---|
| context | Heimdall Listing 5 | compile_reject ✓diag | runtime_accept | runtime_ok | runtime_ok | ks_earlier |
| oversized_update | Heimdall Listing 6 (BUG 1) | compile_reject ✓diag | runtime_wrong | runtime_ok | runtime_ok | ks_earlier |
| reinterpretation | Heimdall Listing 6 (BUG 2) | compile_reject ✓diag | runtime_wrong | runtime_ok | runtime_ok | ks_earlier |

## Claim cap

KernelScript rejects these three published verifier-accepted exemplars at
compile time while C/libbpf builds, loads, and runs them on this toolchain.
Map-schema rows reproduce wrong values; the context row only claims runtime
accept of the wrong-typed object (no non-zero remapping oracle).
No prevalence claim; no Aya comparison.

