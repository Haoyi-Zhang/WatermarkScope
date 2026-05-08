# Traceability Matrix

This matrix connects the dissertation claims to implementation code, result artifacts, verification scripts, and safe interpretation. It is intended for supervisors who want to confirm that the report is backed by code and data.

## Cross-Repository Entry Points

| Item | Path | Purpose |
|---|---|---|
| Dissertation PDF | `dissertation/WatermarkScope_FYP_Dissertation.pdf` | Main submitted report |
| LaTeX source | `dissertation/latex/` | Rebuildable source for the report |
| Result manifest | `RESULT_MANIFEST.jsonl` | Claim-to-artifact binding with SHA-256 hashes |
| Claim boundaries | `CLAIM_BOUNDARIES.md` | Allowed and forbidden interpretations |
| Examiner check | `scripts/examiner_check.py` | One-command local verification |
| Integrity check | `scripts/repro_check.py` | Required files, hashes, denominators, stale wording, token scan |
| Result summary | `scripts/summarize_all.py` | Human-readable manifest summary |

## Module-Level Traceability

| Module | Dissertation section | Code path | Result path | Main checked claim |
|---|---|---|---|---|
| CodeMarkBench | Chapter 3 | `projects/CodeMarkBench/` | `projects/CodeMarkBench/results/tables/suite_all_models_methods/` | 140/140 canonical run-completion inventory; method leaderboard and tradeoff tables |
| SemCodebook | Chapter 4 | `projects/SemCodebook/` | `results/SemCodebook/artifacts/generated/` | 72,000 white-box rows; 23,342/24,000 positives; 0/48,000 negative hits; 43,200 ablation rows |
| CodeDye | Chapter 4 | `projects/CodeDye/` | `results/CodeDye/artifacts/generated/` | 6/300 sparse signals; 170/300 positive controls; 0/300 negative controls; 806 support rows excluded |
| ProbeTrace | Chapter 5 | `projects/ProbeTrace/` | `results/ProbeTrace/artifacts/generated/` | APIS-300 scoped attribution; 0/1,200 false-owner controls; 900 transfer support rows with task-cluster boundary |
| SealAudit | Chapter 5 | `projects/SealAudit/` | `results/SealAudit/artifacts/generated/` | 81/960 decisive marker-hidden rows; 879/960 needs review; 0/960 observed unsafe pass |

## What To Check In Code

| Module | Suggested code inspection target | Why |
|---|---|---|
| CodeMarkBench | `codemarkbench/`, `scripts/reviewer_workflow.py`, `docs/metrics.md` | Shows benchmark orchestration, score semantics, and release workflow |
| SemCodebook | `src/semcodebook/`, `scripts/`, `tests/` | Shows the packaged carrier/detector snapshot, method gates, and regression-test design; full rerun depends on original model/runtime environment |
| CodeDye | `scripts/`, `tests/` | Shows audit-record construction, control gates, and support-row boundaries; full live rerun depends on provider/API setup |
| ProbeTrace | `scripts/build_real_student_transfer_manifest_from_receipts.py`, `scripts/build_transfer_public_promotion_gate.py` | Shows transfer receipt and owner/source binding logic |
| SealAudit | `src/sealaudit/`, `scripts/build_v2_adjudication_promotion_gate.py`, `tests/test_benchmark_v2.py` | Shows triage benchmark and adjudication-gate snapshot; full rerun depends on original benchmark/adjudication environment |

## Main Anti-Overclaim Checks

| Risk | Where it is controlled |
|---|---|
| Treating run completion as watermark success | `CLAIM_BOUNDARIES.md`; Chapter 3; `docs/METHOD_INDEX.md` |
| Treating support rows as main rows | `RESULT_MANIFEST.jsonl`; `scripts/repro_check.py`; `docs/RESULTS_SUMMARY.md` |
| Treating zero events as zero risk | Wilson CI fields in `RESULT_MANIFEST.jsonl`; Chapter 6 |
| Treating ProbeTrace transfer rows as independent main tasks | `primary_independence_unit=task_cluster` in `RESULT_MANIFEST.jsonl` |
| Treating CodeDye as contamination accusation | `CLAIM_BOUNDARIES.md`; CodeDye result README; Chapter 4 |
| Treating SealAudit as a safety certificate | `CLAIM_BOUNDARIES.md`; Chapter 5; SealAudit result README |
