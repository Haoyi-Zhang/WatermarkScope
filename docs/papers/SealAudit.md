# SealAudit: Selective Triage for Watermarks as Security-Relevant Objects

Generated: `2026-05-08T10:57:51+00:00`

## One-Sentence Claim

SealAudit studies watermark-as-security-object selective triage. Watermark evaluation should include safety-relevant audit and abstention surfaces rather than treating every marker as harmless by construction.

## Abstract Draft

Source-code watermark evidence is fragile when claims are tied to surface tokens, unscoped provider behavior, or unverified safety assumptions. We present SealAudit, a scoped protocol for watermark-as-security-object selective triage. The method fixes its denominator, controls, and claim boundary before interpretation, then reports both positive evidence and failure/abstention surfaces. In the current locked evaluation, 320/960 decisive marker-hidden rows; 0/960 unsafe-pass rows; 320 visible-marker rows diagnostic-only. The result supports the scoped claim only; it does not license the forbidden claims listed below.

## Contributions

1. A scoped mechanism for watermark-as-security-object selective triage with explicit claim boundaries.
2. A fixed-denominator evaluation surface tied to hash-bound artifacts and final claim locks.
3. Negative-control, support-only, and failure-boundary reporting designed to prevent overclaiming.

## Method Framing

- The v5 conjunction checks marker-hidden evidence, support traces, executable conditions, threshold sensitivity, and visible-marker diagnostic boundaries.
- The audit reports coverage-risk frontier and unsafe-pass bound instead of forcing every ambiguous case into a class.
- Expert review is used only as anonymous role-based support and packet confirmation.

## Main Result Surface

- 320 cases, 960 marker-hidden claim rows, and 320 visible-marker diagnostic rows.
- 320/960 decisive marker-hidden rows and 0/960 unsafe-pass rows.
- Visible-marker rows remain diagnostic-only and cannot enter the main denominator.

Current main-table source artifacts:
- `results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v2_20260507.json`
- `results/SealAudit/artifacts/generated/sealaudit_v5_postrun_promotion_gate_v2_20260507.json`
- `results/SealAudit/artifacts/generated/sealaudit_v5_coverage_risk_frontier_v2_20260507.json`
- `results/SealAudit/artifacts/generated/sealaudit_v5_threshold_sensitivity_v2_20260507.json`
- `results/SealAudit/artifacts/generated/sealaudit_v5_visible_marker_diagnostic_boundary_v2_20260507.json`

## Publication Readiness Notes

- `coverage` (medium_high): Decisive coverage is 320/960. This is a selective triage result, not a full classifier. Recommended revision: Make coverage-risk frontier the core contribution; explicitly treat retained ambiguity as safety-preserving abstention.
- `human_support_boundary` (medium): Expert review can help credibility but becomes a liability if described as signed/named gold labels. Recommended revision: Use only anonymous role-based support and row-level packet confirmation wording.
- `security_overclaim` (high_if_written_wrong): Reviewers will reject any harmlessness guarantee or security certificate claim. Recommended revision: Write watermark-as-security-object audit/triage, not automatic safety classification.

## Limitations And Forbidden Claims

- This is selective triage, not an automatic safety classifier.
- The result is not a harmlessness guarantee or security certificate.
- Hard ambiguity and needs-review rows are retained as safety-preserving abstention.

Forbidden table uses:
- security certificate
- harmlessness guarantee
- automatic safety classifier

## Reviewer Response Anchors

- The main denominator is fixed before interpretation and bound to versioned artifacts.
- Support-only rows do not enter the main denominator.
- Zero-event and perfect-event results must be reported with finite confidence bounds.
- Claims are scoped to the provider/model/cell conditions in the final lock.

