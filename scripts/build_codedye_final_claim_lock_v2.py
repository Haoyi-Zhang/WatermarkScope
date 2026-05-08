from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT = ROOT / f"results/CodeDye/artifacts/generated/codedye_final_claim_lock_v2_{DATE}.json"
OUT_MD = ROOT / f"results/CodeDye/artifacts/generated/codedye_final_claim_lock_v2_{DATE}.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(rel: str) -> dict[str, Any]:
    payload = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(rel)
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite additive artifact: {path.relative_to(ROOT)}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    postrun = load(f"results/CodeDye/artifacts/generated/codedye_v3_postrun_promotion_gate_v1_{DATE}_deepseek300_topup_v5_postrun.json")
    live = load(f"results/CodeDye/artifacts/generated/codedye_v3_live_results_{DATE}_topup_v5.json")
    positive = load(f"results/CodeDye/artifacts/generated/codedye_positive_miss_taxonomy_v2_{DATE}.json")
    negative = load(f"results/CodeDye/artifacts/generated/codedye_negative_control_row_hash_manifest_v2_{DATE}.json")
    support = load(f"results/CodeDye/artifacts/generated/codedye_v3_support_exclusion_gate_{DATE}.json")
    metrics = postrun["postrun_metrics"]
    blockers: list[str] = []
    if postrun.get("gate_pass") is not True or postrun.get("formal_v3_live_claim_allowed") is not True:
        blockers.append("v3_topup_postrun_not_passed")
    if metrics.get("record_count") != 300 or metrics.get("claim_denominator") != 300:
        blockers.append("v3_denominator_not_300")
    if metrics.get("missing_hash_rows") != 0 or metrics.get("mock_or_replay_rows") != 0:
        blockers.append("v3_hash_or_live_integrity_failure")
    if metrics.get("support_rows_in_candidate") != 0:
        blockers.append("v3_support_rows_in_main_candidate")
    if len(live.get("records", [])) != 300 or len({row.get("task_id") for row in live.get("records", [])}) != 300:
        blockers.append("v3_live_unique_task_denominator_not_300")
    if live.get("utility_topup_policy", {}).get("contamination_score_used_for_selection") is not False:
        blockers.append("topup_selection_not_utility_only")
    if positive.get("positive_control_denominator") != 300:
        blockers.append("positive_control_denominator_drift")
    if negative.get("false_positive_count") != 0 or negative.get("row_count") != 300:
        blockers.append("negative_control_drift")
    if support.get("gate_pass") is not True:
        blockers.append("support_exclusion_gate_not_passed")
    gate_pass = not blockers
    payload = {
        "schema_version": "codedye_final_claim_lock_v2",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "supersedes_for_continuation_planning": f"results/CodeDye/artifacts/generated/codedye_final_claim_lock_v1_{DATE}.json",
        "gate_pass": gate_pass,
        "bestpaper_ready": gate_pass,
        "bestpaper_ready_reason": (
            "CodeDye now has a fresh DeepSeek v3 300-task live postrun with complete hashes and no support rows in "
            "the main denominator. The effect remains intentionally sparse, so the paper claim is a conservative "
            "curator-side null-audit, not a high-recall detector."
        ),
        "allowed_current_claim": "DeepSeek-only curator-side sparse null-audit with frozen v3 protocol and hash-complete 300-task live evidence",
        "upgrade_claim_allowed": gate_pass,
        "formal_v3_live_claim_allowed": gate_pass,
        "formal_curator_side_null_audit_claim_allowed": gate_pass,
        "formal_high_recall_detection_claim_allowed": False,
        "formal_contamination_prevalence_claim_allowed": False,
        "formal_provider_accusation_claim_allowed": False,
        "source_artifacts": {
            "v3_live_topup": f"results/CodeDye/artifacts/generated/codedye_v3_live_results_{DATE}_topup_v5.json",
            "v3_postrun": f"results/CodeDye/artifacts/generated/codedye_v3_postrun_promotion_gate_v1_{DATE}_deepseek300_topup_v5_postrun.json",
            "positive_control": f"results/CodeDye/artifacts/generated/codedye_positive_miss_taxonomy_v2_{DATE}.json",
            "negative_control": f"results/CodeDye/artifacts/generated/codedye_negative_control_row_hash_manifest_v2_{DATE}.json",
            "support_exclusion": f"results/CodeDye/artifacts/generated/codedye_v3_support_exclusion_gate_{DATE}.json",
        },
        "locked_effect_surface": {
            "claim_rows": metrics["claim_denominator"],
            "final_signal": metrics["decision_counts"].get("contamination_signal_detected", 0),
            "final_signal_ci95": metrics["signal_ci95"],
            "null_not_rejected": metrics["decision_counts"].get("null_not_rejected", 0),
            "missing_hash_rows": metrics["missing_hash_rows"],
            "mock_or_replay_rows": metrics["mock_or_replay_rows"],
            "support_rows_in_candidate": metrics["support_rows_in_candidate"],
            "positive_control_detected": positive["positive_control_detected"],
            "positive_control_denominator": positive["positive_control_denominator"],
            "positive_control_missed": positive["positive_control_missed"],
            "positive_miss_taxonomy": positive["miss_bucket_counts"],
            "negative_control_false_positive": negative["false_positive_count"],
            "negative_control_rows": negative["row_count"],
            "utility_topup_policy": live["utility_topup_policy"],
        },
        "paper_table_requirements": [
            "Report 4/300 sparse audit signals with Wilson CI.",
            "Report 296/300 null-not-rejected as non-accusatory outcomes, not absence proof.",
            "Report positive-control sensitivity and miss taxonomy separately.",
            "Report 0/300 negative-control false positives.",
            "Disclose utility-only top-up and keep failed attempts in the repair ledger.",
        ],
        "forbidden_claims": [
            "high-recall contamination detector",
            "contamination prevalence estimate",
            "provider accusation",
            "claim that non-signals imply no contamination",
            "support/public rows as main-denominator evidence",
        ],
        "remaining_blockers": [],
        "blockers": blockers,
    }
    write_json(OUT, payload)
    lines = [
        "# CodeDye Final Claim Lock v2",
        "",
        f"- Gate pass: `{payload['gate_pass']}`",
        f"- Best-paper ready for scoped claim: `{payload['bestpaper_ready']}`",
        f"- Allowed claim: {payload['allowed_current_claim']}",
        f"- Signal: `{payload['locked_effect_surface']['final_signal']}/300`",
        "",
        "Forbidden claims:",
    ]
    lines.extend(f"- {item}" for item in payload["forbidden_claims"])
    if OUT_MD.exists():
        raise FileExistsError(f"Refusing to overwrite additive artifact: {OUT_MD.relative_to(ROOT)}")
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    print(f"[OK] Wrote {OUT_MD.relative_to(ROOT)}")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
