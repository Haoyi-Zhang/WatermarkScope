# Results Summary

This file summarizes the FYP submission-facing result surfaces. The authoritative dissertation surface is `dissertation/WatermarkScope_FYP_Dissertation.pdf` together with `RESULT_MANIFEST.jsonl`. Research-continuation locks are retained for traceability but do not broaden the submitted FYP denominators.

## FYP Status

| Field | Value |
|---|---:|
| Dissertation artifact | `dissertation/WatermarkScope_FYP_Dissertation.pdf` |
| Main body boundary | Chapter 6 conclusion ends on page 40; references start on page 41 |
| Manifest entries | 24 |
| Examiner checks | `scripts/examiner_check.py` |
| Claim policy | Scoped FYP claims only; continuation surfaces require separate admission |

## Main Result Table

| Project | Claim-bearing denominator | Observed result | Safe interpretation |
|---|---:|---:|---|
| SemCodebook positive recovery | 24,000 positives | 23,342 recovered; Wilson 95% CI 97.04%-97.46% | Structured provenance recovery in admitted white-box cells |
| SemCodebook negative controls | 48,000 controls | 0 hits; Wilson 95% upper bound 0.008% | Clean negative-control surface for the current denominator |
| SemCodebook ablation support | 43,200 generation-changing rows | Component contribution surface passed | Evidence for AST/CFG/SSA/ECC/keyed-schedule contribution, not a separate main denominator |
| CodeDye live audit | 300 DeepSeek rows | 6 sparse signals; Wilson 95% CI 0.92%-4.29% | Conservative sparse null-audit, not prevalence or high-recall detection |
| CodeDye positive controls | 300 controls | 170 hits; 130 misses retained | Known-contamination sensitivity surface, not live prevalence |
| CodeDye negative controls | 300 controls | 0 false positives | Current false-positive control surface |
| ProbeTrace APIS attribution | 300 APIS rows; 1,200 false-owner controls | 300/300 APIS success events; 0/1,200 false-owner hits | Single-active-owner, source-bound attribution only |
| ProbeTrace transfer support | 900 rows | 900/900 source-bound validation rows over 300 task clusters | Transfer-boundary support, not provider-general transfer |
| SealAudit marker-hidden triage | 960 rows over 320 cases | 81 decisive rows; 879 needs review; 0 unsafe-pass rows | Selective audit/triage and coverage-risk frontier |
| SealAudit visible-marker diagnostics | 320 rows | 0 rows admitted into claim surface | Visible-marker checks remain diagnostic-only |

## High-Risk Misreadings To Avoid

- CodeDye's sparse signal must not be described as high recall.
- ProbeTrace's strong DeepSeek result must not be described as provider-general attribution.
- SealAudit's unsafe-pass bound must not be described as a harmlessness guarantee.
- SemCodebook's admitted white-box cells must not be described as universal natural-generation watermarking.

## Primary Artifact Paths

| Project | Final lock |
|---|---|
| Dissertation | `dissertation/WatermarkScope_FYP_Dissertation.pdf` |
| Result manifest | `RESULT_MANIFEST.jsonl` |
| Traceability matrix | `docs/TRACEABILITY_MATRIX.md` |
| Examiner guide | `docs/EXAMINER_GUIDE.md` |

Continuation source artifacts for later paper work are bound separately in:

```text
results/watermark_submission_main_table_manifest_v1_20260508.json
results/watermark_submission_main_table_manifest_v1_20260508.md
```

## Continuation Gap Diagnosis

The continuation gap diagnosis is recorded in:

```text
results/watermark_submission_gap_diagnosis_v1_20260508.json
results/watermark_submission_gap_diagnosis_v1_20260508.md
```

The diagnosis recommends paper and artifact alignment before any further GPU/API spending.
