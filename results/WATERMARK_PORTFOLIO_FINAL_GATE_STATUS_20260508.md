# Watermark Portfolio Final Gate Status 2026-05-08

This status note is non-claim-bearing. It summarizes the additive gate artifacts generated after recovering the js3 mirror and closing the remaining ProbeTrace multi-owner blocker.

## Portfolio Verdict

- Strict reviewer audit: `results/watermark_strict_reviewer_audit_v8_20260507.json`
- Portfolio verdict: `bestpaper_ready_by_strict_artifact_gate`
- Remaining P1/P2: `0 / 0`
- Portfolio mean strict score: `4.78`
- Formal full experiment allowed: `true`, but only for the locked scoped surfaces below.

## Locked Scoped Claims

- SemCodebook: structured provenance watermark over admitted white-box model cells.
- CodeDye: DeepSeek-only curator-side sparse null-audit with frozen v3 protocol and hash-complete 300-task live evidence.
- ProbeTrace: DeepSeek-only five-owner source-bound active-owner attribution with owner/task-heldout margin evidence.
- SealAudit: DeepSeek-only marker-hidden v5 selective audit/triage with support-evidence binding.

## Newly Closed Blocker

ProbeTrace multi-owner evidence was recovered on js3 and closed additively:

- `results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_live_score_vectors_20260507_merged_v1.jsonl`
- `results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_live_score_vectors_20260507_merged_v1_manifest.json`
- `results/ProbeTrace/artifacts/generated/probetrace_multi_owner_postrun_promotion_gate_v2_20260507.json`
- `results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v2_20260507.json`
- `results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v2_20260507.md`

The merge is deterministic: the partial canonical main output contributes only canonical input indices `0..2599`; tail shard outputs contribute `2600..5999`. The merge policy is source-order/input-index based and does not filter rows by score or result.

## Still Forbidden

- Provider-general black-box claims without OpenAI/Claude/Qwen evidence.
- Support/canary/diagnostic rows in main denominators.
- SealAudit security certificate or harmlessness guarantee.
- CodeDye high-recall contamination detection or provider accusation.
- ProbeTrace cross-provider attribution or unbounded student-transfer generalization.
- SemCodebook no-retry natural-generation guarantee.

## Verification Commands

```powershell
python -B scripts\check_probetrace_multi_owner_postrun_promotion_gate_v2.py
python -B scripts\check_probetrace_final_claim_lock_v2.py
python -B scripts\check_strict_reviewer_audit_v8.py
python -B scripts\check_preserved_results.py
```

All four checks pass locally and on js3.
