# SemCodebook Result Artifacts

This directory contains sanitized dissertation evidence artifacts for SemCodebook.

## Scope

SemCodebook studies structured provenance watermarking in admitted white-box model cells. The method uses AST, CFG, and SSA carrier families with keyed scheduling and ECC-style recovery.

## Result Surface

- White-box workload: 72,000 records across 10 admitted models, 5 families, and all target scale buckets.
- Positive recovery: 23,342/24,000 = 97.26%.
- Negative controls: 0/48,000 hits; Wilson 95% upper bound 0.008%.
- Generation-changing ablation support: 43,200 rows. This supports method interpretation; it is not a first-sample/no-retry or universal causal claim.

## Claim Boundary

Allowed interpretation: strong structured provenance recovery within the admitted white-box family and scale cells.

Forbidden interpretation: universal code watermarking, natural first-sample/no-retry success, validator-repair success, or claims outside the admitted cells.

## Key Files

- `REPRODUCIBILITY_MANIFEST.json`
- `ANONYMIZATION_AUDIT.json`
- `LARGE_ARTIFACTS_MANIFEST.json`
- `artifacts/generated/semcodebook_whitebox_main_denominator_source_manifest_20260505.json`
- `artifacts/generated/semcodebook_whitebox_model_sufficiency_gate_20260505.json`
- `artifacts/generated/semcodebook_whitebox_effect_authenticity_gate_20260505.json`
- `artifacts/generated/semcodebook_generation_changing_ablation_promotion_gate_20260505.json`
- `artifacts/generated/semcodebook_ablation_compact_summary_fyp.json`
