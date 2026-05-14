# WatermarkScope

This repository supports the submitted Final Year Project, **WatermarkScope: A Benchmark-to-Audit Framework for Source-Code Watermarking in Code Generation Models**, and the post-FYP paper-continuation workstreams built from the same implementation base.

For viva examination, use the submitted FYP snapshot below and the project page:

```text
https://Haoyi-Zhang.github.io/WatermarkScope/
```

| Viva-facing submitted FYP surface | Registered snapshot result |
|---|---|
| CodeMarkBench | 140/140 canonical runs |
| SemCodebook | 23,342/24,000 recoveries; 0/48,000 negative-control hits |
| CodeDye | 6/300 sparse live signals; 170/300 positive controls; 0/300 negative controls |
| ProbeTrace | 300/300 scoped decisions; 0/1,200 false-owner controls |
| SealAudit | 81/960 decisive triage outcomes; 0 observed unsafe passes |

Run the lightweight viva check from the repository root:

```bash
python scripts/viva_check.py
```

This check verifies repository consistency and inspectability. It does not rerun the full GPU/API experiments.

Viva preparation materials:

- `docs/VIVA_PREPARATION.md`: likely examiner questions and concise answers.
- `docs/VIVA_REHEARSAL_SCRIPT.md`: 8-10 minute speaking plan, demo route, and short Q&A answers.
- `docs/WatermarkScope_FYP_Viva.pptx`: editable viva slide deck.

The sections below describe the current paper-continuation artifact for four source-code watermarking papers. These continuation surfaces are preserved for traceability and future submission planning; they should not be confused with the registered FYP snapshot above.

It contains implementation snapshots, reproducibility scripts, hash-bound result artifacts, final claim locks, and reviewer-facing documentation for:

1. **SemCodebook**: structured white-box provenance watermarking under semantic rewrite.
2. **CodeDye**: conservative black-box curator-side contamination null-audit.
3. **ProbeTrace**: active-owner, source-bound commitment/witness verification with false-owner controls.
4. **SealAudit**: watermark-as-security-object selective audit and triage.

The active submission surface is locked by `ACTIVE_CLAIM_SURFACE.json` and `results/watermark_submission_main_table_manifest_v1_20260508.json`. Local preserved archive material remains in the working tree for traceability, but it is excluded from the EMNLP anonymous bundle profile.

Project independence boundary: the four papers share repository infrastructure and hash/reproducibility gates, but they do not share a claim denominator, task population, prompt protocol, evidence object, or promotion rule. SemCodebook is white-box local-model provenance recovery; CodeDye is black-box sparse null-audit; ProbeTrace is active-owner commitment/witness verification; SealAudit is selective security triage.

## Project Page

The repository includes a static reviewer navigation site in `docs/`:

```text
https://Haoyi-Zhang.github.io/WatermarkScope/
```

The page visualizes the benchmark-to-audit pipeline, links claim boundaries and traceability artifacts, and records planned submission targets without treating them as acceptance claims. Deployment notes are in `docs/PAGES_SETUP.md`.

## Repository Layout

```text
.
|-- projects/
|   |-- SemCodebook/
|   |-- CodeDye/
|   |-- ProbeTrace/
|   `-- SealAudit/
|-- results/
|   |-- SemCodebook/
|   |-- CodeDye/
|   |-- ProbeTrace/
|   |-- SealAudit/
|   |-- watermark_submission_main_table_manifest_v1_20260508.json
|   `-- watermark_submission_language_hygiene_gate_v1_20260510.json
|-- docs/
|   |-- RUNBOOK.md
|   |-- RESULTS_SUMMARY.md
|   `-- SUBMISSION_NOTES.md
|-- CLAIM_BOUNDARIES.md
`-- scripts/
```

## Active Claim Surface

| Project | Locked claim | Main evidence surface | Current reviewer risk |
|---|---|---|---|
| SemCodebook | Structured provenance over admitted white-box cells | 93,600 structured records; 30,330/31,200 support-retry/materialized protocol recoveries; 0/62,400 fixed negative-control hits; 0/62,400 blind replay hits; 43,200 ablation rows | Fixed controls and blind replay are separate gates; 352 no-retry-origin positives are disclosed as a non-promoted origin subset; no first-sample/no-retry claim |
| CodeDye | DeepSeek-only curator-side active memory-probe null-audit calibration | 3,600/3,600 live rows over 1,200 triads; fresh live signal 0/300; positive memory calibration 272/300; negative memory-control FP 0/300; retrieval-confound FP 0/300; 806 older support rows excluded; v2/current300 and v4-v12 are retained as lineage/support, not active denominators | Must not be framed as prevalence, accusation, high-recall detection, or absence proof |
| ProbeTrace | DeepSeek-only five-owner source-bound commitment/witness verification | 6,000 five-owner rows; 750/750 true-owner positives; 0/5,250 wrong/null/random/same-provider controls; AUC 1.0; APIS-300 and 900 transfer rows remain support-only | Must not become provider-general or cross-provider attribution; perfect scores require anti-leakage and commitment-oracle boundary evidence |
| SealAudit | DeepSeek-only marker-hidden security-relevant selective triage | 320/960 decisive marker-hidden rows; 80 confirmed benign; 240 confirmed latent risk with support-evidence binding; latent risk decomposes as 1 marker-hidden-live decisive risk plus 239 code-aware-support-bound risk rows; 0/960 provider-flag unsafe pass; 320 visible-marker rows diagnostic-only; v7 completed 960/960 live rows but failed promotion at 260/960 decisive; v8 completed 960/960 live evidence-packet rows with integrity pass but failed coverage promotion at 77/960 decisive; v9 completed 960/960 no-prior-verdict live rows with integrity pass, 882/960 actionable triage rows, 78/960 expert-review rows, 0/960 unsafe-pass rows, and 0/960 confirmed decisive rows, so it remains support-only | Must be framed as selective triage, not a classifier, independent gold-label set, or safety certificate |

## Primary Artifacts

| Purpose | Artifact |
|---|---|
| Main table source manifest | `results/watermark_submission_main_table_manifest_v1_20260508.json` |
| Submission language hygiene gate | `results/watermark_submission_language_hygiene_gate_v1_20260510.json` |
| Full-repo anonymity boundary gate | `results/watermark_full_repo_anonymity_boundary_gate_v1_20260510.json` |
| Reviewer effect scorecard | `results/watermark_reviewer_effect_scorecard_v1_20260509.json` |
| Overfit resistance audit | `results/watermark_overfit_resistance_audit_v1_20260509.json` |
| Claim discipline matrix | `results/watermark_claim_discipline_matrix_v1_20260512.json` |
| Continuation attempt ledger | `results/watermark_continuation_attempt_ledger_v1_20260512.json` |
| Project independence gate | `results/watermark_project_independence_gate_v1_20260512.json` |
| Strict multi-reviewer scorecard | `results/watermark_strict_review_scorecard_v2_20260512.json` |
| Final gap closure packet | `results/watermark_final_gap_closure_packet_v1_20260513.json` |
| SemCodebook queued-cell admission policy | `results/SemCodebook/artifacts/generated/semcodebook_queued_cell_admission_policy_gate_v1_20260510.json` |
| SemCodebook miss/ablation boundary | `results/SemCodebook/artifacts/generated/semcodebook_miss_ablation_boundary_packet_v1_20260510.json` |
| SemCodebook source artifact availability | `results/SemCodebook/artifacts/generated/semcodebook_source_artifact_availability_gate_v1_20260510.json` |
| SemCodebook blind negative replay | `results/SemCodebook/artifacts/generated/semcodebook_blind_negative_replay_gate_v1_20260510.json` |
| SemCodebook no-retry role reconciliation | `results/SemCodebook/artifacts/generated/semcodebook_no_retry_role_reconciliation_gate_v1_20260511.json` |
| SemCodebook no-retry miss boundary | `results/SemCodebook/artifacts/generated/semcodebook_no_retry_miss_boundary_upgrade_gate_v1_20260512.json` |
| CodeDye reviewer calibration | `results/CodeDye/artifacts/generated/codedye_reviewer_calibration_pack_v1_20260510.json` |
| CodeDye calibration boundary | `results/CodeDye/artifacts/generated/codedye_calibration_boundary_packet_v1_20260510.json` |
| CodeDye v4 negative-boundary failure | `results/CodeDye/artifacts/generated/codedye_v4_negative_boundary_failure_audit_v1_20260510.json` |
| CodeDye v5 precision-hardening postrun | `results/CodeDye/artifacts/generated/codedye_v5_dual_evidence_postrun_gate_v1_20260510.json` |
| CodeDye v6 retrieval-confound launch contract | `results/CodeDye/artifacts/generated/codedye_v6_fresh_retrieval_confound_launch_contract_v1_20260511.json` |
| CodeDye v6 retrieval-confound postrun | `results/CodeDye/artifacts/generated/codedye_v6_retrieval_confound_postrun_gate_v1_20260511.json` |
| CodeDye v6 prompt-role audit | `results/CodeDye/artifacts/generated/codedye_v6_prompt_role_audit_v1_20260511.json` |
| CodeDye v7 role-separated launch contract | `results/CodeDye/artifacts/generated/codedye_v7_role_separated_launch_contract_v1_20260511.json` |
| CodeDye v8 blinded-control support postrun | `results/CodeDye/artifacts/generated/codedye_v8_blinded_control_postrun_gate_v1_20260511.json` |
| CodeDye v9 preregistered effect-hardening postrun | `results/CodeDye/artifacts/generated/codedye_v9_preregistered_effect_hardening_postrun_gate_v1_20260512.json` |
| CodeDye v10 dual-channel launch contract | `results/CodeDye/artifacts/generated/codedye_v10_dual_channel_launch_contract_v1_20260512.json` |
| CodeDye v10 dual-channel postrun nonpromotion | `results/CodeDye/artifacts/generated/codedye_v10_dual_channel_postrun_gate_v1_20260512.json` |
| CodeDye v11 tri-channel merge gate | `results/CodeDye/artifacts/generated/codedye_v11_tri_channel_shard_merge_gate_v1_20260512.json` |
| CodeDye v11 tri-channel postrun nonpromotion | `results/CodeDye/artifacts/generated/codedye_v11_tri_channel_postrun_gate_v1_20260512.json` |
| ProbeTrace commitment-oracle gate | `results/ProbeTrace/artifacts/generated/probetrace_commitment_shortcut_oracle_gate_v1_20260510.json` |
| ProbeTrace owner/split boundary | `results/ProbeTrace/artifacts/generated/probetrace_owner_split_boundary_table_v1_20260510.json` |
| ProbeTrace source-integrity gate | `results/ProbeTrace/artifacts/generated/probetrace_source_artifact_integrity_gate_v1_20260510.json` |
| ProbeTrace transfer support boundary | `results/ProbeTrace/artifacts/generated/probetrace_transfer_support_boundary_gate_v1_20260510.json` |
| ProbeTrace raw release sanitization | `results/ProbeTrace/artifacts/generated/probetrace_raw_release_sanitization_gate_v1_20260510.json` |
| SealAudit support/abstention decomposition | `results/SealAudit/artifacts/generated/sealaudit_support_dependence_and_abstention_decomposition_v1_20260510.json` |
| SealAudit selective decision packet | `results/SealAudit/artifacts/generated/sealaudit_selective_decision_packet_v1_20260510.json` |
| SealAudit second-stage coverage-risk support postrun | `results/SealAudit/artifacts/generated/sealaudit_second_stage_coverage_risk_postrun_gate_v1_20260510.json` |
| SealAudit v7 coverage-risk upgrade postrun | `results/SealAudit/artifacts/generated/sealaudit_v7_coverage_risk_upgrade_postrun_gate_v1_20260512.json` |
| SealAudit v8 evidence-packet prerun contract | `results/SealAudit/artifacts/generated/sealaudit_v8_evidence_packet_coverage_prerun_gate_v1_20260512.json` (superseded by completed postrun nonpromotion) |
| SealAudit v8 evidence-packet postrun gate | `results/SealAudit/artifacts/generated/sealaudit_v8_evidence_packet_coverage_postrun_gate_v1_20260512.json` |
| Reviewer objection index | `results/watermark_reviewer_objection_index_v1_20260510.json` |
| Active claim surface | `ACTIVE_CLAIM_SURFACE.json` |
| Artifact role/supersession ledger | `results/watermark_artifact_supersession_ledger_v1_20260509.json` |
| SemCodebook final lock | `results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v5_current_miss_binding_20260511.json` |
| CodeDye final lock | `results/CodeDye/artifacts/generated/codedye_final_claim_lock_v3_20260513.json` |
| ProbeTrace final lock | `results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v4_20260511.json` |
| SealAudit final lock | `results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v2_20260507.json` |
| Preservation policy | `docs/RESULT_PRESERVATION_POLICY.md` |

Large SemCodebook source-chain outputs are registered in `EXTERNAL_LARGE_ARTIFACTS.json` and excluded from the anonymous GitHub bundle until a separate content-release scan passes. The compact claim-bearing gates, summaries, hashes, and source-chain manifests remain in the repository and are the reviewer-facing artifacts.

## Quick Verification

Run these from the repository root:

```bash
python3 -B scripts/repro_check_emnlp.py
python3 -B scripts/check_active_claim_surface_v1.py
python3 -B scripts/check_emnlp_anonymous_bundle_profile_v1.py
python3 -B scripts/check_anonymous_bundle_strict_secret_scan_v1.py
python3 -B scripts/check_pilot_not_in_main_claim_manifest_v1.py
python3 -B scripts/check_watermark_submission_main_table_manifest_v1.py
python3 -B scripts/check_submission_facing_claims_v1.py
python3 -B scripts/check_historical_stale_artifact_quarantine_v1.py
python3 -B scripts/check_metric_lineage_and_skepticism_report_v1.py
python3 -B scripts/check_baseline_control_role_table_v1.py
python3 -B scripts/check_reviewer_response_ledger_v1.py
python3 -B scripts/check_reviewer_reproducibility_manifests_v1.py
python3 -B scripts/check_watermark_artifact_supersession_ledger_v1.py
python3 -B scripts/check_watermark_reviewer_effect_scorecard_v1.py
python3 -B scripts/check_watermark_overfit_resistance_audit_v1.py
python3 -B scripts/check_watermark_claim_discipline_matrix_v1.py
python3 -B scripts/check_watermark_continuation_attempt_ledger_v1.py
python3 -B scripts/check_watermark_project_independence_gate_v1.py
python3 -B scripts/check_watermark_strict_review_scorecard_v2.py
python3 -B scripts/check_watermark_final_gap_closure_packet_v1.py
python3 -B scripts/check_watermark_submission_language_hygiene_gate_v1.py
python3 -B scripts/check_watermark_full_repo_anonymity_boundary_gate_v1.py
python3 -B scripts/check_semcodebook_queued_candidate_quarantine_gate_v1.py
python3 -B scripts/check_semcodebook_interrupted_candidate_recovery_gate_v1.py
python3 -B scripts/check_semcodebook_miss_ablation_boundary_packet_v1.py
python3 -B scripts/check_codedye_reviewer_calibration_pack_v1.py
python3 -B scripts/check_codedye_calibration_boundary_packet_v1.py
python3 -B scripts/check_probetrace_commitment_shortcut_oracle_gate_v1.py
python3 -B scripts/check_probetrace_owner_split_boundary_table_v1.py
python3 -B scripts/check_probetrace_source_artifact_integrity_gate_v1.py
python3 -B scripts/check_probetrace_raw_release_sanitization_gate_v1.py
python3 -B scripts/check_sealaudit_support_dependence_and_abstention_decomposition_v1.py
python3 -B scripts/check_sealaudit_selective_decision_packet_v1.py
python3 -B scripts/check_watermark_reviewer_objection_index_v1.py
python3 -B scripts/check_project_metadata_claim_consistency_v1.py
python3 -B scripts/check_semcodebook_active_final_claim_lock_v1.py
python3 -B scripts/check_semcodebook_active_queued_manifest_refresh_v1.py
python3 -B scripts/check_semcodebook_active_queued_refresh_submission_integration_v1.py
python3 -B scripts/check_semcodebook_source_artifact_availability_gate_v1.py
python3 -B scripts/check_semcodebook_blind_negative_replay_gate_v1.py
python3 -B scripts/check_semcodebook_no_retry_role_reconciliation_gate_v1.py
python3 -B scripts/check_semcodebook_no_retry_miss_boundary_upgrade_gate_v1.py
python3 -B scripts/check_codedye_sparse_audit_operating_characteristic_v1.py
python3 -B scripts/check_probetrace_perfect_score_stress_gate_v1.py
python3 -B scripts/check_sealaudit_selective_triage_risk_formalization_v1.py
```

These are integrity and claim-surface checks. They do not rerun GPU or live-provider experiments.
To regenerate manifests after intentional reviewer-facing edits, follow `docs/RUNBOOK.md`; the default verification path above is check-only.

## Rerun Boundary

The locked scoped surface is ready for reviewer inspection under the stated claim boundaries, and continuation runs may be launched only when they are preregistered and additive. Current policy:

- SemCodebook: a queued public-model white-box cell may run as a non-claim candidate; partial rows do not enter the main table, and a completed cell needs a 7,200-row postrun gate plus manifest refresh before any claim update.
- CodeDye: the v13 memory-probe surface is the active scoped lock. Further DeepSeek runs must preserve the null-audit interpretation, keep fresh/positive/negative/retrieval roles separated before interpretation, and avoid high-recall, prevalence, accusation, or absence-proof wording.
- ProbeTrace: any further DeepSeek run must preserve owner/task-heldout and wrong/null/random/same-provider controls; no provider-general claim is allowed.
- SealAudit: the 2026-05-10 second-stage continuation, v7 coverage-risk upgrade, and v8 evidence-packet continuation are support-only because they kept unsafe-pass at 0 but did not improve the locked 320/960 decisive coverage. Any coverage update now requires a new frozen protocol, postrun promotion gate, and final lock.

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
