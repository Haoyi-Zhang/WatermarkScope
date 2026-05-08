# SemCodebook: Structured Provenance Watermarks for Semantic Code Rewrites

Generated: `2026-05-08T10:57:51+00:00`

## One-Sentence Claim

SemCodebook studies structured white-box provenance watermarking. A code watermark should survive meaning-preserving rewrites by binding provenance to recoverable program structure rather than to surface tokens.

## Abstract Draft

Source-code watermark evidence is fragile when claims are tied to surface tokens, unscoped provider behavior, or unverified safety assumptions. We present SemCodebook, a scoped protocol for structured white-box provenance watermarking. The method fixes its denominator, controls, and claim boundary before interpretation, then reports both positive evidence and failure/abstention surfaces. In the current locked evaluation, 23342/24000 positive recoveries; 0/48000 negative-control hits; 72000 admitted records. The result supports the scoped claim only; it does not license the forbidden claims listed below.

## Contributions

1. A scoped mechanism for structured white-box provenance watermarking with explicit claim boundaries.
2. A fixed-denominator evaluation surface tied to hash-bound artifacts and final claim locks.
3. Negative-control, support-only, and failure-boundary reporting designed to prevent overclaiming.

## Method Framing

- The encoder distributes provenance over AST, CFG, and SSA carrier families under a keyed schedule.
- An error-correcting recovery layer aggregates carrier support and fails closed when evidence is insufficient.
- The detector records support family, support level, carrier coverage, ECC state, and abstention reasons instead of forcing labels.

## Main Result Surface

- 72,000 admitted white-box records over 10 models, 5 model families, and tiny/small/mid/large scale buckets.
- 23,342/24,000 positive recoveries and 0/48,000 negative-control hits.
- 43,200 generation-changing ablation rows bind AST/CFG/SSA/ECC/keyed-schedule contribution.

Current main-table source artifacts:
- `results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v1_20260507.json`
- `results/SemCodebook/artifacts/generated/semcodebook_whitebox_model_sufficiency_gate_20260505.json`
- `results/SemCodebook/artifacts/generated/semcodebook_generation_changing_ablation_promotion_gate_20260505.json`

## Publication Readiness Notes

- `method_theory` (medium): The mechanism is strong, but the paper must make AST/CFG/SSA/ECC/keyed schedule read as a compact theory of structured provenance rather than an artifact-heavy system. Recommended revision: Add formal definitions, recovery sufficient conditions, and component necessity lemmas tied directly to the generation-changing ablation.
- `baseline_positioning` (medium): Reviewers may question whether official watermark baselines are fully comparable to structured provenance under semantic rewrite. Recommended revision: Add a baseline-role table and a fairness paragraph that separates runnable official baselines, citation-only baselines, and non-equivalent comparators.
- `external_validity` (low_medium): 72k records cover model/family/scale breadth, but real-repo workflow examples would make the claim more memorable. Recommended revision: Add one non-main-table real-repo walkthrough with compile/test witness and failure-boundary discussion.

## Limitations And Forbidden Claims

- The claim is restricted to admitted white-box cells.
- The paper must not claim first-sample/no-retry natural generation.
- Baseline comparisons must distinguish official runnable baselines from citation-only or non-equivalent controls.

Forbidden table uses:
- no-retry natural-generation guarantee
- validator-repair main claim

## Reviewer Response Anchors

- The main denominator is fixed before interpretation and bound to versioned artifacts.
- Support-only rows do not enter the main denominator.
- Zero-event and perfect-event results must be reported with finite confidence bounds.
- Claims are scoped to the provider/model/cell conditions in the final lock.

