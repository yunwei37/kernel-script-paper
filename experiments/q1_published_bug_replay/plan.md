# Experiment Plan: Q1 Heimdall Verifier-Gap Exemplar Replay

## Research Question
- RQ exactly as written in the paper: Does each typed cross-boundary invariant trigger a compile-time diagnostic?
- Specific uncertainty tested here: Beyond author-constructed static tests, does KernelScript reject published, verifier-accepted hook/context and map-schema defects before code generation?
- Why the answer matters: The current four-case comparison gives KernelScript one earlier detection and three ties. Q1 needs independently defined cases that exercise the cross-boundary contracts central to KernelScript.

## Paper-Value Admission
- Planned role: decisive for the early-detection comparison, complementary for the RQ-wide coverage claim.
- Largest credible paper story this experiment could unlock: KernelScript rejects three published verifier-accepted exemplars at compile time while matched C/libbpf programs build, verifier-load, and reproduce the published semantic failure.
- Strongest reviewer reject argument or load-bearing uncertainty addressed: The existing diagnostics may be tautological compiler tests, and the sole differential win may be an artificial wrong-context program whose body never reads the context.
- Independent evidence added beyond existing runs and published results: Exact defect definitions come from Heimdall (arXiv:2605.25411v1, Listings 5 and 6); this run evaluates KernelScript on those externally defined defects and replays their C behavior on the paper's recorded Linux/libbpf toolchain.
- Why the result is not tautological, already settled, or dominated: KernelScript was not evaluated in Heimdall. A positive row requires the C program to pass clang and the kernel verifier, a defect-specific runtime oracle, an exact KernelScript diagnostic, and a corrected sibling that traverses the same harness.
- Paper decision if positive: Replace the four hand-written mistakes with the three published exemplars as the early-detection comparison. Retain the 28-case static suite only as evidence that every declared invariant has a test.
- Paper decision if contradictory, mixed, or inconclusive: Report every terminal row, narrow Q1 to the bug classes actually rejected, and do not claim general early detection from failed or unrepresentable cases.
- Best alternative experiment and why this one has higher decision value: Repository-history mining offers stronger prevalence evidence but may yield few changes aligned with the declared invariants. These published exemplars are independently defined, known to pass the verifier, and directly target the load-bearing Q1 mechanism.

## Expected And Alternative Outcomes
- Current expected answer: KernelScript rejects the hook/context mismatch, oversized typed-map update, and unrelated typed-map reinterpretation before code generation; clang and the kernel verifier accept the three C counterparts.
- Strongest competing explanation: KernelScript rejects only because an adapter uses unsupported syntax, or a C counterpart fails on this toolchain before the semantic defect occurs.
- Result that would contradict the expectation: A published defect passes KernelScript's typed surface, or its C counterpart fails at clang/verifier for a defect-relevant reason.

## Published Precedent And Real Assets
- Closest published protocol: Heimdall: Formally Verified Automated Migration of Legacy eBPF Programs to Rust, arXiv:2605.25411v1, Section 2.1 and Appendix Listings 5 and 6.
- Official system/model/data/benchmark/tool and version: Heimdall arXiv v1 source; KernelScript commit `3b19cd2bfa1db0428da6d735864a31d6ea62c7cd`; clang 18; bpftool 7.7; Linux 6.15.11; libbpf 1.3.0.
- What is reused: The published defect expressions and type declarations, KernelScript's official compiler, clang, libbpf, bpftool, and `BPF_PROG_TEST_RUN`.
- Necessary deviations or custom glue: Replace only the publication's output sinks with array-map observation sinks so a common libbpf runner can read deterministic values. Preserve Listing 5's `SEC("xdp")`, `struct __sk_buff *`, `skb->protocol`, and `skb->queue_mapping`; isolate Listing 6's two defects into separate programs. Add corrected siblings solely as harness controls.
- Published comparison not rerun: Heimdall reports that Aya's typed interfaces prevent these cases at compile time. This experiment does not claim or test an advantage over Aya.

## Comparison
- Proposed system or method: KernelScript's attributed program signatures and typed map operations.
- Main baseline and competing position: Hand-written C/libbpf represents current practice and the position that clang plus the kernel verifier catch the same defects early enough.
- Why the baseline needs a matched run: Detection stage and verifier behavior depend on compiler/kernel versions, while the runtime oracles establish that the accepted object exhibits the intended wrong interpretation.
- Controls or ablations, labeled separately: Every buggy C and KernelScript cell has a corrected sibling. A control must compile/generate, verifier-load, test-run, and satisfy its declared output oracle. Exact expected diagnostic classes prevent incidental KernelScript rejection from counting.
- Conclusion if the baseline matches or wins: C compile/verifier rejection is a negative row for KernelScript's claimed stage advantage. A buggy KernelScript program that builds contradicts the relevant type-system claim.
- Information, tuning, and compute fairness: Each buggy/corrected pair differs only in the defect-relevant type or operation. Observation glue is identical within a pair, and no case receives repair feedback.
- Split or leakage rule: Cases are fixed by the external publication before this run.

## Workloads And Metrics
- Real tasks: Heimdall Listing 5 hook/context mismatch; Listing 6 oversized map-value update; Listing 6 unrelated map-value reinterpretation.
- Primary metric: Earliest detection stage per defect (`KernelScript compile`, `clang build`, `kernel verifier`, `runtime wrong`, `undetected`, or `invalid/inconclusive`) and the paired stage difference from C/libbpf.
- Correctness ground truth:
  - `context`: create a deterministic veth, select a valid RX queue, clear the observation map before every invocation, pass `(rx_queue_index, ingress_ifindex)` through `xdp_md`, and assert the buggy program records them under the misnamed `protocol` and `queue_mapping` fields. Save context input/output, map bytes, and the assertion for every invocation.
  - `oversized-update`: update an 8-byte `conn {u32,u32}` map value with `big {1,2,3,4}`. Assert the loaded map reports `value_size=8` and contains exactly the native-endian bytes for the first two `u32`s. This program contains no unrelated lookup cast.
  - `wrong-reinterpretation`: initialize the map with a correct `conn {1,2}`, cast only the lookup result to `stats {u64}`, and assert the observed `u64` equals the host-native concatenation of those two `u32`s. Record host endianness. This program contains no oversized update.
  - Corrected controls must satisfy their own declared values through the same load/test-run/readback path. Any corrected-control failure invalidates its pair.
- KernelScript diagnostics: `context` must report the `@xdp` signature mismatch; `oversized-update` must report `Map value type mismatch`; `wrong-reinterpretation` must report `Type mismatch in declaration` for `var s: Stats = data[key]`. A parser failure or unrelated diagnostic is invalid. If the unrelated cast cannot be expressed in KernelScript, report `unrepresentable by construction`, not a diagnostic win.
- Repetitions and uncertainty: Deterministic compilation and verifier load once per cell; ten test-run/readback invocations for every runtime-observable variant. Repetitions test stability only; no statistical inference.
- Cost estimate: Under ten minutes on the recorded local host.

## Planned Runs
| Pair | Role | System | Defect-relevant operation | Repetitions | Valid positive condition |
|---|---|---|---|---:|---|
| context | buggy baseline | C/libbpf | XDP section with `__sk_buff *`; read `protocol` and `queue_mapping` | 10 | clang/verifier accept; all reads equal valid XDP queue/ifindex under wrong names |
| context | buggy proposed | KernelScript | `@xdp` function with `*__sk_buff` | 1 | exact XDP-signature diagnostic before codegen |
| context | corrected controls | C and KernelScript | `xdp_md *`; read `rx_queue_index` and `ingress_ifindex` | 10 each | generate/load/run; all reads equal queue/ifindex |
| oversized-update | buggy baseline | C/libbpf | write 16-byte `big` through 8-byte `conn` map schema | 10 | clang/verifier accept; value size is 8 and readback is `{1,2}` |
| oversized-update | buggy proposed | KernelScript | assign `Big` to `array<u32, Conn>` | 1 | `Map value type mismatch` before codegen |
| oversized-update | corrected controls | C and KernelScript | assign `Conn` to `array<u32, Conn>` | 10 each | generate/load/run; readback is `{1,2}` |
| wrong-reinterpretation | buggy baseline | C/libbpf | initialize `Conn`, reinterpret lookup as `Stats` | 10 | clang/verifier accept; readback u64 equals native concatenation |
| wrong-reinterpretation | buggy proposed | KernelScript | `var s: Stats = data[key]` | 1 | `Type mismatch in declaration` before codegen, or explicitly `unrepresentable by construction` |
| wrong-reinterpretation | corrected controls | C and KernelScript | lookup as declared `Conn` | 10 each | generate/load/run; declared observation oracle holds |

## Execution
- Authoritative command: `./experiments/q1_published_bug_replay/run.py`
- Runner setup contract: The runner obtains the official KernelScript repository in an ignored build directory, checks out and verifies exact commit `3b19cd2bfa1db0428da6d735864a31d6ea62c7cd`, records tool/kernel versions, verifies passwordless privilege for BPF and veth setup, and fails closed on identity mismatch.
- Real preflight: Execute one `context` buggy C invocation and its corrected C control through clang, verifier load, test-run, and readback; compile both KernelScript counterparts and check the expected buggy diagnostic plus corrected generation. Verify the chosen veth ifindex and RX queue are valid before the full run.
- Full completion rule: Every planned buggy and corrected cell reaches a terminal stage; all compiler, verifier, context, map-byte, and assertion logs are saved; no case is silently dropped.
- Raw-result path: `experiments/q1_published_bug_replay/results/`; derived summary at `experiments/q1_published_bug_replay/result.md`.
- Checkpoint or recovery: Each cell has a separate log and result record. The command recreates generated build outputs but preserves raw logs; no partial prefix is interpreted.

## Interpretation
- Positive result: All three published verifier-accepted exemplars are rejected by KernelScript before code generation while C/libbpf accepts them through the verifier and every defect-specific runtime oracle reproduces the wrong interpretation.
- Negative or contradictory result: KernelScript misses a defect or C catches it no later; report the row and narrow the claim.
- Mixed or inconclusive result: Report per-defect stages without a universal aggregate. Infrastructure, glue, or corrected-control failures are invalid/inconclusive, never scientific negatives.
- Maximum supported claim: KernelScript detects these three external exemplars from two invariant families earlier than stock C/libbpf on this toolchain. The run does not establish prevalence, an advantage over Aya, or that every invariant is covered; the static suite remains the evidence for `each invariant`.
- Target paper table: Publication/listing, invariant family, semantic consequence, C/libbpf outcome, KernelScript outcome, and control status.

## Reproducibility Notes
- Software and data versions: Versions are pinned above and copied from `results/environment.json`; the external benchmark source is the arXiv v1 source archive.
- Config and seed: Ten deterministic test-run invocations per runtime variant; no tuning or random seed.
- Known deviations: Observation sinks are instrumentation adapters, not part of the compared type mechanism. The experiment evaluates published verifier-accepted exemplars, not historical production bugs or prevalence in arbitrary repositories.
