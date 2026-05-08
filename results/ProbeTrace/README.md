# ProbeTrace Result Artifacts

This directory contains sanitized dissertation evidence artifacts for ProbeTrace.

## Scope

ProbeTrace studies active-owner, source-bound attribution. The claim is tied to a fixed owner registry, source split, witness protocol, and false-owner controls.

## Result Surface

- APIS-300 attribution records: 300/300 observed successes in the scoped owner setting; Wilson 95% lower bound 98.74%.
- False-owner controls: 0/1,200 false attributions; Wilson 95% upper bound 0.32%.
- Transfer evidence: 900 source-bound support rows across SFT, LoRA, and quantized students. These rows are receipt-complete transfer support, not 900 independent primary attribution tasks.
- Transfer receipts: dataset SHA, owner/source split, validation hash, and training receipt hash are recorded.

## Claim Boundary

Allowed interpretation: scoped single-active-owner/source-bound attribution under the evaluated protocol. Transfer rows support the source-bound transfer boundary and should be read separately from the APIS-300 primary attribution denominator.

Forbidden interpretation: provider-general authorship, multi-owner attribution, unbounded transfer generalization, or threshold-free authorship proof.

## Key Files

- `REPRODUCIBILITY_MANIFEST.json`
- `ANONYMIZATION_AUDIT.json`
- `LARGE_ARTIFACTS_MANIFEST.json`
- `artifacts/generated/apis300_live_attribution_evidence.json`
- `artifacts/generated/probetrace_abstain_aware_attribution_gate_20260506.json`
- `artifacts/generated/probetrace_owner_margin_control_audit_gate_20260505.json`
- `artifacts/generated/student_transfer_live_validation_results.owner_witness_v6_clean_holdout.json`
- `artifacts/generated/probetrace_transfer_row_binding_manifest_gate_20260505.json`
