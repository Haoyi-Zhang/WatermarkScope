# Claim Boundaries

This file records the submission-facing interpretation boundary for the five-stage WatermarkScope FYP artifact. It supersedes older local writing summaries for examiner-facing use. All claims remain scoped to the dissertation PDF and `RESULT_MANIFEST.jsonl`.

## SemCodebook

- **Paper role:** structured white-box provenance watermarking under semantic rewrite.
- **Primary denominator:** 72,000 white-box records, consisting of 24,000 positive recovery rows and 48,000 negative-control rows.
- **Main evidence:** `results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v1_20260507.json`.
- **Allowed claim:** SemCodebook recovers structured provenance over admitted white-box model cells with the reported positive recovery and negative-control bounds.
- **Forbidden claim:** no universal semantic watermarking guarantee, no first-sample/no-retry guarantee, no validator-repair main claim, and no provider-general claim outside admitted white-box cells.

## CodeDye

- **Paper role:** conservative black-box curator-side contamination null-audit.
- **Primary denominator:** 300 claim-bearing live DeepSeek audit rows, with separate positive-control and negative-control denominators.
- **Main evidence:** `results/CodeDye/artifacts/generated/codedye_final_claim_lock_v2_20260507.json`.
- **Allowed claim:** CodeDye provides a sparse, hash-complete, fixed-protocol DeepSeek null-audit surface with support-row exclusion and clean negative controls.
- **Forbidden claim:** no contamination accusation, no contamination prevalence estimate, no high-recall detector claim, and no claim that non-signals prove absence of contamination.

## ProbeTrace

- **Paper role:** active-owner, source-bound attribution protocol.
- **Primary denominator:** 300 APIS attribution rows in the scoped single-active-owner setting, with 1,200 false-owner/abstain-aware controls.
- **Supporting surfaces:** 900 source-bound transfer rows are support-only receipt/source-binding evidence over 300 task clusters.
- **Main evidence:** `results/ProbeTrace/artifacts/generated/apis300_live_attribution_evidence.json` and `results/ProbeTrace/artifacts/generated/probetrace_abstain_aware_attribution_gate_20260506.json`.
- **Allowed claim:** ProbeTrace supports scoped single-active-owner, source-bound attribution under the APIS-300 protocol with explicit false-owner controls and support-only transfer binding.
- **Forbidden claim:** no provider-general attribution, no cross-provider attribution, no claim-bearing multi-owner attribution in the FYP denominator, no unbounded student-transfer generalization, and no claim that perfect scores alone prove absence of shortcut risk.

## SealAudit

- **Paper role:** watermark-as-security-object selective audit and triage.
- **Primary denominator:** 960 marker-hidden claim rows over 320 cases.
- **Main evidence:** `results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v2_20260507.json`.
- **Allowed claim:** SealAudit supports DeepSeek-only marker-hidden v5 selective audit/triage with support-evidence binding, coverage-risk reporting, and unsafe-pass tracking.
- **Forbidden claim:** no automatic safety classifier, no harmlessness guarantee, no security certificate, no visible-marker main evidence, and no named/signed expert-label claim.

## Cross-Project Rule

Diagnostic, support-only, canary, scaffold, and stress rows may be retained as engineering evidence, but they do not change the main denominators unless a versioned manifest explicitly promotes them into the claim-bearing surface before interpretation.

Black-box claims are DeepSeek-only unless a future provider-specific artifact passes its own pre-run, postrun, and claim-lock gates.
