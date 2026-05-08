# CodeDye Result Artifacts

This directory contains sanitized dissertation evidence artifacts for CodeDye.

## Scope

CodeDye studies a conservative black-box contamination null-audit protocol. This sanitized package preserves prompt hashes, raw-response hashes, structured-response hashes, detector versions, threshold versions, and fixed control roles. Large or provider-specific raw payload material is represented by hash-bound evidence and external/large-artifact manifests rather than embedded directly in the main repository.

## Result Surface

- DeepSeek live audit rows: 300.
- Sparse audit signals: 6/300 = 2.00%, Wilson 95% CI 0.92%-4.29%.
- Positive contamination controls: 170/300 = 56.67%, Wilson 95% CI 51.01%-62.15%; this is moderate known-control sensitivity, not high-recall detection.
- Negative controls: 0/300, Wilson 95% upper bound 1.26%.
- Support/public rows excluded from the main denominator: 806.

## Claim Boundary

Allowed interpretation: a conservative null-audit can preserve sparse evidence and calibrated controls.

Forbidden interpretation: contamination accusation, contamination prevalence estimate, proof of no contamination, or high-recall detection claim.

## Key Files

- `REPRODUCIBILITY_MANIFEST.json`
- `ANONYMIZATION_AUDIT.json`
- `LARGE_ARTIFACTS_MANIFEST.json`
- `artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json`
- `artifacts/generated/codedye_positive_contamination_control_300_gate_20260505.json`
- `artifacts/generated/codedye_negative_control_300plus_gate_20260505.json`
- `artifacts/generated/codedye_v2_dual_evidence_protocol_freeze_gate_20260506.json`
- `artifacts/generated/statistics_repro_gate.json`
