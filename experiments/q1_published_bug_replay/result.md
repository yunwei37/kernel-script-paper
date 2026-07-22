# Q1 Published Bug Replay Results

Status: **ok**
Positive (ks_earlier) rows: 3 / 3

| Defect | Listing | KS buggy | C buggy | KS fixed | C fixed | Verdict |
|---|---|---|---|---|---|---|
| context | Heimdall Listing 5 | compile_reject ✓diag | runtime_wrong | compile_accept | runtime_ok | ks_earlier |
| oversized_update | Heimdall Listing 6 (BUG 1) | compile_reject ✓diag | runtime_wrong | compile_accept | runtime_ok | ks_earlier |
| reinterpretation | Heimdall Listing 6 (BUG 2) | compile_reject ✓diag | runtime_wrong | compile_accept | runtime_ok | ks_earlier |

## Claim cap

KernelScript detects these published verifier-accepted exemplars from
two invariant families earlier than stock C/libbpf on this toolchain.
This run does not establish prevalence or an advantage over Aya.

