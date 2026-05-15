# Traceability Matrix

This matrix connects the submitted FYP viva claims to implementation code, result artifacts, verification scripts, and safe interpretation. Later paper-continuation artifacts are preserved in the repository, but they do not rewrite the dissertation-facing denominator.

## Cross-Repository Entry Points

| Item | Path | Purpose |
|---|---|---|
| Claim boundaries | `CLAIM_BOUNDARIES.md` | Allowed and forbidden interpretations |
| Active claim surface | `ACTIVE_CLAIM_SURFACE.json` | Paper-continuation scope; use the project page and dissertation abstract for viva-facing submitted results |
| Main-table manifest | `results/watermark_submission_main_table_manifest_v1_20260508.json` | Claim-to-artifact binding with SHA-256 hashes |
| Viva integrity check | `scripts/viva_check.py` | Lightweight viva-facing document and manifest inspection |

## Module-Level Traceability

| Module | Code path | Result path | Main checked claim |
|---|---|---|---|
| SemCodebook | `projects/SemCodebook/` | `results/SemCodebook/artifacts/generated/` | 93,600 white-box rows; 30,330/31,200 positives; 870 positive misses retained; 352 no-retry-origin positives remain non-promoted; 0/62,400 fixed negative-control hits; 0/62,400 blind replay hits; 43,200 paired component-delta ablation rows |
| CodeDye | `projects/CodeDye/` | `results/CodeDye/artifacts/generated/` | Submitted FYP null-audit surface: 4/300 sparse live signals; 170/300 positive controls; 0/300 negative controls; no prevalence, accusation, high-recall, or absence-proof claim |
| ProbeTrace | `projects/ProbeTrace/` | `results/ProbeTrace/artifacts/generated/` | APIS-300 plus 6,000 DeepSeek five-owner source-bound commitment/witness rows; 750/750 true-owner positives; 0/5,250 controls; 900 transfer support rows with task-cluster boundary |
| SealAudit | `projects/SealAudit/` | `results/SealAudit/artifacts/generated/` | Submitted FYP marker-hidden triage surface: 320/960 decisive rows; 0/960 observed provider-flag unsafe pass; nondecisive rows retained as abstention or review load |

## What To Check In Code

| Module | Suggested code inspection target | Why |
|---|---|---|
| SemCodebook | `src/semcodebook/`, `scripts/`, `tests/` | Shows the packaged carrier/detector snapshot, method gates, and regression-test design; full rerun depends on original model/runtime environment |
| CodeDye | `scripts/`, `tests/` | Shows audit-record construction, control gates, and support-row boundaries; full live rerun depends on provider/API setup |
| ProbeTrace | `scripts/build_real_student_transfer_manifest_from_receipts.py`, `scripts/build_transfer_public_promotion_gate.py` | Shows transfer receipt and owner/source binding logic |
| SealAudit | `src/sealaudit/`, `scripts/build_v2_adjudication_promotion_gate.py`, `tests/test_benchmark_v2.py` | Shows triage benchmark and adjudication-gate snapshot; full rerun depends on original benchmark/adjudication environment |

## Main Anti-Overclaim Checks

| Risk | Where it is controlled |
|---|---|
| Treating run completion as watermark success | `CLAIM_BOUNDARIES.md`; Chapter 3; `docs/METHOD_INDEX.md` |
| Treating support rows as main rows | `ACTIVE_CLAIM_SURFACE.json`; `scripts/repro_check_emnlp.py`; `docs/RESULTS_SUMMARY.md` |
| Treating zero events as zero risk | Wilson CI fields in final claim locks and main-table source artifacts |
| Treating ProbeTrace transfer rows as independent main tasks | `primary_independence_unit=task_cluster` in the transfer integrity artifacts |
| Treating CodeDye as contamination accusation | `CLAIM_BOUNDARIES.md`; CodeDye result README; Chapter 4 |
| Treating SealAudit as a safety certificate | `CLAIM_BOUNDARIES.md`; Chapter 5; SealAudit result README |
