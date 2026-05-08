from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v2_{DATE}.json"
OUT_MD = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v2_{DATE}.md"


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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_md(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite additive artifact: {path.relative_to(ROOT)}")
    metrics = payload["locked_effect_surface"]
    lines = [
        "# ProbeTrace Final Claim Lock v2",
        "",
        "This additive claim lock supersedes v1 for continuation planning. It does not overwrite v1 or any raw result.",
        "",
        f"- Gate pass: `{payload['gate_pass']}`",
        f"- Best-paper ready for scoped claim: `{payload['bestpaper_ready']}`",
        f"- Allowed current claim: {payload['allowed_current_claim']}",
        f"- Multi-owner claim allowed: `{payload['formal_multi_owner_claim_allowed']}`",
        f"- Provider-general claim allowed: `{payload['formal_provider_general_claim_allowed']}`",
        "",
        "Locked effect surface:",
        f"- APIS-300 attribution: `{metrics['apis300_attribution']['k']}/{metrics['apis300_attribution']['n']}`",
        f"- Transfer validation: `{metrics['transfer_validation']['k']}/{metrics['transfer_validation']['n']}`",
        f"- Multi-owner live rows: `{metrics['multi_owner_row_count']}`",
        f"- Multi-owner owners/languages: `{metrics['multi_owner_owner_count']}` / `{metrics['multi_owner_language_count']}`",
        f"- Multi-owner positives/controls: `{metrics['multi_owner_positive_rows']}` / `{metrics['multi_owner_control_rows']}`",
        f"- Multi-owner margin AUC: `{metrics['multi_owner_margin_auc']}`",
        f"- Multi-owner global TPR: `{metrics['multi_owner_global_tpr_ci95']}`",
        f"- Multi-owner global FPR: `{metrics['multi_owner_global_fpr_ci95']}`",
        "",
        "Forbidden claims:",
    ]
    lines.extend(f"- {item}" for item in payload["forbidden_claims"])
    lines.extend(["", "Remaining blockers:"])
    lines.extend(f"- {item}" for item in payload["remaining_blockers"]) if payload["remaining_blockers"] else lines.append("- None.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    v1 = load(f"results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v1_{DATE}.json")
    postrun = load(f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_postrun_promotion_gate_v2_{DATE}.json")
    package = load(f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_package_{DATE}.json")
    latency = load(f"results/ProbeTrace/artifacts/generated/probetrace_latency_query_frontier_v1_{DATE}.json")
    anti_leakage = load(f"results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_scan_v1_{DATE}.json")
    metrics = postrun.get("postrun_metrics", {})

    blockers: list[str] = []
    if v1.get("gate_pass") is not True:
        blockers.append("v1_single_owner_claim_lock_not_clean")
    if postrun.get("gate_pass") is not True or postrun.get("formal_multi_owner_claim_allowed") is not True:
        blockers.append("multi_owner_postrun_v2_not_passed")
    if int(metrics.get("row_count", 0) or 0) != 6000:
        blockers.append("multi_owner_row_count_not_6000")
    if int(metrics.get("owner_count", 0) or 0) < 5:
        blockers.append("multi_owner_owner_count_below_5")
    if int(metrics.get("language_count", 0) or 0) < 3:
        blockers.append("multi_owner_language_count_below_3")
    if int(metrics.get("missing_hash_rows", -1) or 0) != 0:
        blockers.append("multi_owner_missing_hash_rows_nonzero")
    if int(metrics.get("schema_missing_rows", -1) or 0) != 0:
        blockers.append("multi_owner_schema_missing_rows_nonzero")
    if float(metrics.get("control_to_positive_ratio", 0) or 0) < 4:
        blockers.append("multi_owner_control_ratio_below_4x")
    if metrics.get("margin_auc") is None:
        blockers.append("multi_owner_margin_auc_missing")
    if int(metrics.get("owner_heldout_rows", 0) or 0) == 0:
        blockers.append("multi_owner_owner_heldout_missing")
    if int(metrics.get("task_heldout_rows", 0) or 0) == 0:
        blockers.append("multi_owner_task_heldout_missing")
    if int(metrics.get("claim_bearing_rows", 0) or 0) != int(metrics.get("row_count", -1) or -1):
        blockers.append("multi_owner_claim_bearing_row_count_mismatch")
    if package.get("gate_pass") is not True or int(package.get("row_count", 0) or 0) != 6000:
        blockers.append("multi_owner_input_package_not_clean")
    if latency.get("gate_pass") is not True:
        blockers.append("latency_query_frontier_not_clean")
    if anti_leakage.get("gate_pass") is not True:
        blockers.append("anti_leakage_scan_not_clean")

    gate_pass = not blockers
    effect = v1["locked_effect_surface"]
    payload = {
        "schema_version": "probetrace_final_claim_lock_v2",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "supersedes_for_continuation_planning": f"results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v1_{DATE}.json",
        "gate_pass": gate_pass,
        "bestpaper_ready": gate_pass,
        "bestpaper_ready_reason": (
            "ProbeTrace now has APIS-300, 1200 single-owner controls, transfer-900, and fresh 6000-row "
            "DeepSeek five-owner score-vector evidence with owner-heldout/task-heldout margins. The allowed "
            "claim is still scoped to DeepSeek and source-bound active-owner attribution."
        ),
        "allowed_current_claim": "DeepSeek-only five-owner source-bound active-owner attribution with owner/task-heldout margin evidence",
        "upgrade_claim_allowed": gate_pass,
        "formal_single_active_owner_claim_allowed": gate_pass,
        "formal_source_bound_transfer_evidence_allowed": gate_pass,
        "formal_multi_owner_claim_allowed": gate_pass,
        "formal_provider_general_claim_allowed": False,
        "formal_cross_provider_claim_allowed": False,
        "formal_unbounded_student_transfer_claim_allowed": False,
        "source_artifacts": {
            "v1_claim_lock": f"results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v1_{DATE}.json",
            "apis300_live": "results/ProbeTrace/artifacts/generated/apis300_live_attribution_evidence.json",
            "transfer_integrity": "results/ProbeTrace/artifacts/generated/probetrace_transfer_validation_integrity_gate_20260506.json",
            "multi_owner_input_package": f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_package_{DATE}.json",
            "multi_owner_live_score_vectors": f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_live_score_vectors_{DATE}.jsonl",
            "multi_owner_postrun_promotion": f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_postrun_promotion_gate_v2_{DATE}.json",
            "latency_query_frontier": f"results/ProbeTrace/artifacts/generated/probetrace_latency_query_frontier_v1_{DATE}.json",
            "anti_leakage_scan": f"results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_scan_v1_{DATE}.json",
        },
        "locked_effect_surface": {
            "apis300_attribution": effect["apis300_attribution"],
            "single_owner_negative_control_false_attribution": effect["negative_control_false_attribution"],
            "transfer_validation": effect["transfer_validation"],
            "transfer_rows": effect["transfer_rows"],
            "transfer_dataset_sha256": effect["transfer_dataset_sha256"],
            "transfer_primary_independence_unit": effect["transfer_primary_independence_unit"],
            "unique_transfer_task_count": effect["unique_transfer_task_count"],
            "multi_owner_row_count": metrics.get("row_count"),
            "multi_owner_owner_count": metrics.get("owner_count"),
            "multi_owner_language_count": metrics.get("language_count"),
            "multi_owner_positive_rows": metrics.get("positive_rows"),
            "multi_owner_control_rows": metrics.get("control_rows"),
            "multi_owner_control_to_positive_ratio": metrics.get("control_to_positive_ratio"),
            "multi_owner_control_role_counts": metrics.get("control_role_counts"),
            "multi_owner_split_counts": metrics.get("split_counts"),
            "multi_owner_owner_heldout_rows": metrics.get("owner_heldout_rows"),
            "multi_owner_task_heldout_rows": metrics.get("task_heldout_rows"),
            "multi_owner_missing_hash_rows": metrics.get("missing_hash_rows"),
            "multi_owner_schema_missing_rows": metrics.get("schema_missing_rows"),
            "multi_owner_claim_bearing_rows": metrics.get("claim_bearing_rows"),
            "multi_owner_global_tpr_ci95": metrics.get("global_tpr_ci95"),
            "multi_owner_global_fpr_ci95": metrics.get("global_fpr_ci95"),
            "multi_owner_per_owner_ci95": metrics.get("per_owner_ci95"),
            "multi_owner_margin_auc": metrics.get("margin_auc"),
            "latency_query_frontier_gate_pass": latency.get("gate_pass"),
            "anti_leakage_gate_pass": anti_leakage.get("gate_pass"),
        },
        "paper_table_requirements": [
            "Report APIS-300, single-owner controls, transfer-900, and multi-owner 6000-row evidence as separate surfaces.",
            "Report multi-owner true/wrong/null/random/same-provider roles with CIs and threshold-free rank/AUC.",
            "Report owner-heldout and task-heldout splits explicitly; do not merge them into training/dev rows.",
            "Report latency/query frontier in the main evidence surface.",
            "Keep DeepSeek-only and source-bound scope in title/abstract-level claims.",
        ],
        "forbidden_claims": [
            "provider-general attribution",
            "cross-provider attribution without non-DeepSeek evidence",
            "unbounded student-transfer generalization beyond source-bound receipts",
            "claim that perfect single-owner results alone prove no shortcut",
            "multi-owner claim from input package without fresh live score vectors",
            "claim that controls prove zero false positives rather than an upper-bounded rate",
        ],
        "remaining_blockers": [] if gate_pass else blockers,
        "blockers": blockers,
    }
    write_json(OUT, payload)
    write_md(OUT_MD, payload)
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    print(f"[OK] Wrote {OUT_MD.relative_to(ROOT)}")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
