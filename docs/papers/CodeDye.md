# CodeDye: A Conservative Curator-Side Null-Audit for Code Contamination Evidence

Generated: `2026-05-08T10:57:51+00:00`

## One-Sentence Claim

CodeDye studies black-box sparse null-audit. A curator-side audit can preserve low-false-positive contamination evidence without turning sparse signals into provider accusations.

## Abstract Draft

Source-code watermark evidence is fragile when claims are tied to surface tokens, unscoped provider behavior, or unverified safety assumptions. We present CodeDye, a scoped protocol for black-box sparse null-audit. The method fixes its denominator, controls, and claim boundary before interpretation, then reports both positive evidence and failure/abstention surfaces. In the current locked evaluation, 4/300 sparse DeepSeek audit signals; 170/300 positive-control hits; 0/300 negative-control hits. The result supports the scoped claim only; it does not license the forbidden claims listed below.

## Contributions

1. A scoped mechanism for black-box sparse null-audit with explicit claim boundaries.
2. A fixed-denominator evaluation surface tied to hash-bound artifacts and final claim locks.
3. Negative-control, support-only, and failure-boundary reporting designed to prevent overclaiming.

## Method Framing

- The protocol freezes task hashes, prompt hashes, raw provider transcript hashes, structured payload hashes, and support-row exclusion before interpretation.
- The decision rule separates sparse audit signal, positive-control sensitivity, and negative-control false-positive evidence.
- Utility-only top-up preserves the 300-row denominator without selecting records by contamination score.

## Main Result Surface

- 300 claim-bearing DeepSeek live rows with complete hash retention.
- 4/300 sparse audit signals, 170/300 positive-control hits, and 0/300 negative-control hits.
- Support/public rows remain outside the main denominator.

Current main-table source artifacts:
- `results/CodeDye/artifacts/generated/codedye_final_claim_lock_v2_20260507.json`
- `results/CodeDye/artifacts/generated/codedye_v3_postrun_promotion_gate_v1_20260507_deepseek300_topup_v5_postrun.json`
- `results/CodeDye/artifacts/generated/codedye_positive_miss_taxonomy_v2_20260507.json`
- `results/CodeDye/artifacts/generated/codedye_negative_control_row_hash_manifest_v2_20260507.json`

## Publication Readiness Notes

- `effect_size` (high_for_detection_framing_low_for_scoped_audit): Main DeepSeek signal is sparse: 4/300. This is acceptable for a conservative null-audit paper but weak for a Publication-style detection narrative. Recommended revision: Frame sparse yield as the point of a low-false-positive audit protocol; add utility and query-budget curves instead of inflating recall.
- `positive_control_sensitivity` (medium): Positive-control sensitivity is 170/300, with 130 witness-ablation misses. Reviewers will ask whether the protocol misses known contamination too often. Recommended revision: Add miss taxonomy examples and a frozen v4 evidence-enrichment design; rerun only if thresholds are preregistered before execution.
- `claim_boundary` (medium): The paper can be rejected if it sounds like a provider contamination accusation or high-recall detector. Recommended revision: Keep the title/abstract as curator-side null-audit; report non-signals as non-accusatory outcomes, not absence proof.

## Limitations And Forbidden Claims

- This is not a high-recall contamination detector.
- Non-signals are non-accusatory outcomes, not evidence of absence.
- Any v4 sensitivity improvement requires a frozen protocol before execution.

Forbidden table uses:
- high-recall detection
- provider accusation
- contamination prevalence

## Reviewer Response Anchors

- The main denominator is fixed before interpretation and bound to versioned artifacts.
- Support-only rows do not enter the main denominator.
- Zero-event and perfect-event results must be reported with finite confidence bounds.
- Claims are scoped to the provider/model/cell conditions in the final lock.

