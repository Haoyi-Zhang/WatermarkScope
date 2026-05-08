# WatermarkScope FYP Artifact

This repository is the submission and inspection artifact for the Final Year Project dissertation:

**WatermarkScope: A Benchmark-to-Audit Framework for Source-Code Watermarking in Code Generation Models**.

It contains the submitted dissertation PDF and LaTeX source, implementation snapshots, reproducibility scripts, preserved result manifests, and examiner-facing documentation for the five-stage WatermarkScope framework:

1. **CodeMarkBench**: executable benchmark foundation for source-code watermarking.
1. **SemCodebook**: structured white-box provenance watermarking under semantic rewrite.
2. **CodeDye**: conservative black-box curator-side contamination null-audit.
3. **ProbeTrace**: active-owner, source-bound attribution with false-owner controls.
4. **SealAudit**: watermark-as-security-object selective audit and triage.

The dissertation-level claim surface is fixed by the submitted PDF and `RESULT_MANIFEST.jsonl`. Research-continuation artifacts are retained for traceability, but they do not broaden the FYP claims unless a new admitted result surface is explicitly created.

The FYP scope is deliberately bounded. It does not license provider-general claims, universal watermarking claims, contamination accusations, or safety certificates.

## Repository Layout

```text
.
|-- dissertation/
|   |-- WatermarkScope_FYP_Dissertation.pdf
|   `-- latex/
|-- projects/
|   |-- CodeMarkBench/
|   |-- SemCodebook/
|   |-- CodeDye/
|   |-- ProbeTrace/
|   `-- SealAudit/
|-- results/
|   |-- SemCodebook/
|   |-- CodeDye/
|   |-- ProbeTrace/
|   |-- SealAudit/
|   |-- watermark_strict_reviewer_audit_v8_20260507.json
|   `-- watermark_submission_gap_diagnosis_v1_20260508.json
|-- docs/
|   |-- RUNBOOK.md
|   |-- RESULTS_SUMMARY.md
|   `-- SUBMISSION_NOTES.md
|-- CLAIM_BOUNDARIES.md
|-- PRESERVED_RESULT_MANIFEST.jsonl
|-- RESULT_MANIFEST.jsonl
`-- scripts/
```

For FYP marking, start with `dissertation/WatermarkScope_FYP_Dissertation.pdf`, then use `docs/EXAMINER_GUIDE.md`, `docs/TRACEABILITY_MATRIX.md`, and `RESULT_MANIFEST.jsonl` to connect the printed claims to code and artifacts.

## FYP Claim Surface

| Project | Locked claim | Main evidence surface | Current reviewer risk |
|---|---|---|---|
| CodeMarkBench | Executable benchmark foundation | 140/140 canonical model-method-source run inventory | Inventory completion is not a detector success rate |
| SemCodebook | Structured provenance over admitted white-box cells | 72,000 structured records; 23,342/24,000 positive recoveries; 0/48,000 negative hits; 43,200 ablation rows | Must stay within admitted white-box cells |
| CodeDye | DeepSeek-only curator-side sparse null-audit | 300 live rows; 6/300 sparse audit signals; 170/300 positive-control hits; 0/300 negative-control hits; 806 support rows excluded | Must not be framed as prevalence or accusation |
| ProbeTrace | Source-bound single-active-owner attribution | 300/300 APIS success events; 0/1,200 false-owner controls; 900 transfer support rows | Must not become provider-general or multi-owner attribution |
| SealAudit | Marker-hidden selective security triage | 81/960 decisive outcomes; 879/960 needs review; 0/960 unsafe pass | Must be framed as selective triage, not a safety certificate |

## Primary Artifacts

| Purpose | Artifact |
|---|---|
| Submitted FYP report | `dissertation/WatermarkScope_FYP_Dissertation.pdf` |
| Result manifest | `RESULT_MANIFEST.jsonl` |
| Portfolio strict audit | `results/watermark_strict_reviewer_audit_v8_20260507.json` |
| Submission gap diagnosis | `results/watermark_submission_gap_diagnosis_v1_20260508.json` |
| Main table source manifest | `results/watermark_submission_main_table_manifest_v1_20260508.json` |
| SemCodebook final lock | `results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v1_20260507.json` |
| CodeDye final lock | `results/CodeDye/artifacts/generated/codedye_final_claim_lock_v2_20260507.json` |
| ProbeTrace final lock | `results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v2_20260507.json` |
| SealAudit final lock | `results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v2_20260507.json` |
| Preservation policy | `PRESERVED_RESULT_MANIFEST.jsonl` and `docs/RESULT_PRESERVATION_POLICY.md` |

One full SemCodebook raw ablation output is larger than the ordinary GitHub single-file limit. It is registered in `EXTERNAL_LARGE_ARTIFACTS.json`; the compact claim-bearing ablation gate and summary remain in the repository and are the examiner-facing artifacts used by the dissertation.

## Quick Verification

Run these from the repository root:

```bash
python -B scripts/check_watermark_submission_gap_diagnosis_v1.py
python -B scripts/check_watermark_submission_main_table_manifest_v1.py
python -B scripts/check_strict_reviewer_audit_v8.py
python -B scripts/check_probetrace_multi_owner_postrun_promotion_gate_v2.py
python -B scripts/check_probetrace_final_claim_lock_v2.py
python -B scripts/check_preserved_results.py
```

These are integrity and claim-surface checks. They do not rerun GPU or live-provider experiments.

## Rerun Boundary

The current result set already exceeds a minimal "one white-box model plus DeepSeek-only black-box" check. Additional runs should not be launched blindly:

- SemCodebook: add only a support-only real-repo witness unless a new formal claim is introduced.
- CodeDye: freeze a new v4 evidence-enrichment protocol before any further DeepSeek run.
- ProbeTrace: no new DeepSeek run is needed; future value is mainly non-DeepSeek replication if keys are available.
- SealAudit: no new DeepSeek run is needed; improve paper framing and failure taxonomy.

## Forbidden Claims

The repository does not claim:

- provider-general black-box behavior beyond DeepSeek;
- universal code watermarking;
- contamination prevalence or provider wrongdoing;
- high-recall CodeDye detection;
- ProbeTrace cross-provider attribution;
- SealAudit harmlessness guarantee or security certificate;
- SemCodebook no-retry natural-generation guarantee.

Every main result must remain tied to its fixed denominator, control role, threshold/protocol version, and claim-bearing status.
