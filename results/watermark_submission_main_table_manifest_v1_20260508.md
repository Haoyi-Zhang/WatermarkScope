# Watermark Submission Main Table Manifest v1

## SemCodebook
- Table role: `whitebox_main_and_ablation`
- Primary result: 23342/24000 positive recoveries; 0/48000 negative-control hits; 72000 admitted records
- Artifacts:
  - `results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v1_20260507.json`
  - `results/SemCodebook/artifacts/generated/semcodebook_whitebox_model_sufficiency_gate_20260505.json`
  - `results/SemCodebook/artifacts/generated/semcodebook_generation_changing_ablation_promotion_gate_20260505.json`
- Forbidden table uses:
  - no-retry natural-generation guarantee
  - validator-repair main claim

## CodeDye
- Table role: `deepseek_sparse_null_audit`
- Primary result: 4/300 sparse DeepSeek audit signals; 170/300 positive-control hits; 0/300 negative-control hits
- Artifacts:
  - `results/CodeDye/artifacts/generated/codedye_final_claim_lock_v2_20260507.json`
  - `results/CodeDye/artifacts/generated/codedye_v3_postrun_promotion_gate_v1_20260507_deepseek300_topup_v5_postrun.json`
  - `results/CodeDye/artifacts/generated/codedye_positive_miss_taxonomy_v2_20260507.json`
  - `results/CodeDye/artifacts/generated/codedye_negative_control_row_hash_manifest_v2_20260507.json`
- Forbidden table uses:
  - high-recall detection
  - provider accusation
  - contamination prevalence

## ProbeTrace
- Table role: `deepseek_multi_owner_attribution`
- Primary result: 6000 multi-owner rows; 750/750 positives; 0/5250 false-attribution controls; AUC 1.0
- Artifacts:
  - `results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v2_20260507.json`
  - `results/ProbeTrace/artifacts/generated/probetrace_multi_owner_postrun_promotion_gate_v2_20260507.json`
  - `results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_live_score_vectors_20260507_merged_v1_manifest.json`
  - `results/ProbeTrace/artifacts/generated/probetrace_latency_query_frontier_v1_20260507.json`
  - `results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_scan_v1_20260507.json`
- Forbidden table uses:
  - provider-general attribution
  - cross-provider attribution
  - unbounded transfer

## SealAudit
- Table role: `deepseek_marker_hidden_selective_triage`
- Primary result: 320/960 decisive marker-hidden rows; 0/960 unsafe-pass rows; 320 visible-marker rows diagnostic-only
- Artifacts:
  - `results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v2_20260507.json`
  - `results/SealAudit/artifacts/generated/sealaudit_v5_postrun_promotion_gate_v2_20260507.json`
  - `results/SealAudit/artifacts/generated/sealaudit_v5_coverage_risk_frontier_v2_20260507.json`
  - `results/SealAudit/artifacts/generated/sealaudit_v5_threshold_sensitivity_v2_20260507.json`
  - `results/SealAudit/artifacts/generated/sealaudit_v5_visible_marker_diagnostic_boundary_v2_20260507.json`
- Forbidden table uses:
  - security certificate
  - harmlessness guarantee
  - automatic safety classifier
