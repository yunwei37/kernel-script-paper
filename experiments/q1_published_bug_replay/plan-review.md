# Plan Review: Q1 Heimdall Verifier-Gap Exemplar Replay

## Round 1 — BLOCK

The independent reviewer blocked execution because the initial plan combined Listing 6's oversized update and unrelated reinterpretation, left the runtime oracles under-specified, used an invalidly broad XDP context-input assumption, and overstated the result as a general Q1 or historical-bug claim.

Required repairs were:

- split Listing 6 into independent oversized-update and wrong-reinterpretation pairs;
- give every buggy case a corrected sibling and treat a control failure as invalid/inconclusive;
- create a real net device and valid RX queue for the XDP context input, clear maps between invocations, and save exact context/map bytes and assertions;
- assert the 8-byte truncation and native-endian reinterpretation separately;
- require defect-specific KernelScript diagnostics, with unrepresentable syntax reported by construction rather than counted as rejection;
- describe the inputs as published verifier-accepted exemplars, acknowledge Heimdall's Aya result, and cap the claim at three exemplars in two invariant families versus C/libbpf;
- replace the placeholder command with a runner that verifies the pinned repository and toolchain identities.

## Repair Applied

The current plan incorporates every item above. Execution remains blocked until a second independent plan-review round returns GO.
