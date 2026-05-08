# SealAudit Result Artifacts

This directory contains sanitized dissertation evidence artifacts for SealAudit.

## Scope

SealAudit studies watermark mechanisms as security-relevant objects. The dissertation reports marker-hidden selective triage with explicit abstention and unsafe-pass boundaries.

## Result Surface

- Canonical cases: 320.
- Marker-hidden claim rows: 960.
- Marker-visible diagnostic-only rows: 320.
- Decisive outcomes: 81/960 = 8.44%, Wilson 95% CI 6.84%-10.37%.
- Needs-review outcomes: 879/960.
- Unsafe-pass outcomes: 0/960 observed, Wilson 95% upper bound 0.40%.

## Claim Boundary

Allowed interpretation: conservative selective triage with explicit coverage and abstention.

Forbidden interpretation: automatic safety classifier, harmlessness certificate, or security certificate for all watermarking mechanisms.

## Key Files

- `REPRODUCIBILITY_MANIFEST.json`
- `ANONYMIZATION_AUDIT.json`
- `LARGE_ARTIFACTS_MANIFEST.json`
- `artifacts/generated/canonical_claim_surface_results.json`
- `artifacts/generated/sealaudit_coverage_risk_frontier_gate_20260505.json`
- `artifacts/generated/sealaudit_second_stage_v4_side_by_side_resolver_gate_20260505.json`
- `artifacts/generated/sealaudit_second_stage_claim_promotion_stability_gate_20260506.json`

Second-stage v4 artifacts are support/gate evidence in this package. They should not be read as a promoted replacement for the marker-hidden v3 claim surface unless a future fresh side-by-side rerun explicitly promotes them.
