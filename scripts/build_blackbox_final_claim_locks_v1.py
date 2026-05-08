from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected object JSON: {rel}")
    return payload


def wilson(k: int, n: int) -> dict[str, Any]:
    if n <= 0:
        return {"k": k, "n": n, "rate": 0.0, "low": 0.0, "high": 1.0, "method": "wilson"}
    z = 1.959963984540054
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return {
        "k": k,
        "n": n,
        "rate": phat,
        "low": max(0.0, center - half),
        "high": min(1.0, center + half),
        "method": "wilson",
    }


def write_json(rel: str, payload: dict[str, Any]) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_md(rel: str, title: str, payload: dict[str, Any]) -> None:
    lines = [
        f"# {title}",
        "",
        "This artifact is non-claim-bearing. It locks the currently admissible paper claim and the claims that remain forbidden until fresh postrun evidence passes.",
        "",
        f"- Gate pass: `{payload['gate_pass']}`",
        f"- Best-paper ready: `{payload['bestpaper_ready']}`",
        f"- Allowed current claim: {payload['allowed_current_claim']}",
        f"- Upgrade claim allowed: `{payload['upgrade_claim_allowed']}`",
        "",
        "Effect surface:",
    ]
    for key, value in payload["locked_effect_surface"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "Forbidden claims:"])
    lines.extend(f"- {item}" for item in payload["forbidden_claims"])
    lines.extend(["", "Remaining blockers:"])
    lines.extend(f"- {item}" for item in payload["remaining_blockers"]) if payload["remaining_blockers"] else lines.append("- None.")
    lines.extend(["", "Required next evidence:"])
    lines.extend(f"- {item}" for item in payload["required_next_evidence"])
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_codedye() -> dict[str, Any]:
    boundary = load_json("results/CodeDye/artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json")
    taxonomy = load_json("results/CodeDye/artifacts/generated/codedye_positive_miss_taxonomy_v2_20260507.json")
    neg = load_json("results/CodeDye/artifacts/generated/codedye_negative_control_row_hash_manifest_v2_20260507.json")
    postrun = load_json("results/CodeDye/artifacts/generated/codedye_v3_postrun_promotion_gate_v1_20260507.json")
    support = load_json("results/CodeDye/artifacts/generated/codedye_v3_support_exclusion_gate_20260507.json")
    protocol = load_json("results/CodeDye/artifacts/generated/codedye_v3_protocol_freeze_gate_20260507.json")
    effect = boundary["effect_surface"]
    claim_rows = int(effect["claim_rows"])
    signal_count = int(effect["decision_counts"]["contamination_signal_detected"])
    pos_detected = int(taxonomy["positive_control_detected"])
    pos_denominator = int(taxonomy["positive_control_denominator"])
    false_positive = int(neg["false_positive_count"])
    negative_rows = int(neg["row_count"])
    blockers: list[str] = []
    if boundary.get("formal_curator_side_null_audit_claim_allowed") is not True:
        blockers.append("current_sparse_null_audit_not_allowed")
    if boundary.get("formal_high_recall_detection_claim_allowed") is not False:
        blockers.append("high_recall_boundary_not_fail_closed")
    if boundary.get("formal_contamination_accusation_claim_allowed") is not False:
        blockers.append("provider_accusation_boundary_not_fail_closed")
    if claim_rows != 300 or signal_count != 6:
        blockers.append("codedye_current_effect_surface_drift")
    if pos_denominator != 300 or pos_detected != 170:
        blockers.append("codedye_positive_control_drift")
    if negative_rows != 300 or false_positive != 0:
        blockers.append("codedye_negative_control_drift")
    if postrun.get("formal_v3_live_claim_allowed") is not False or postrun.get("gate_pass") is not False:
        blockers.append("codedye_v3_postrun_unexpectedly_promoted")
    if support.get("gate_pass") is not True or protocol.get("frozen") is not True:
        blockers.append("codedye_v3_prerequisite_gate_not_clean")
    payload = {
        "schema_version": "codedye_final_claim_lock_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": not blockers,
        "bestpaper_ready": False,
        "bestpaper_ready_reason": "The current DeepSeek evidence supports only a conservative sparse null-audit; positive-control sensitivity and fresh v3 postrun evidence remain insufficient for a best-paper-level detection claim.",
        "allowed_current_claim": "DeepSeek-only curator-side sparse null-audit with hash-bound transcript retention",
        "upgrade_claim_allowed": False,
        "formal_curator_side_null_audit_claim_allowed": not blockers,
        "formal_high_recall_detection_claim_allowed": False,
        "formal_contamination_prevalence_claim_allowed": False,
        "formal_provider_accusation_claim_allowed": False,
        "formal_v3_live_claim_allowed": False,
        "source_artifacts": {
            "low_signal_boundary": "results/CodeDye/artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json",
            "positive_miss_taxonomy": "results/CodeDye/artifacts/generated/codedye_positive_miss_taxonomy_v2_20260507.json",
            "negative_control_hash_manifest": "results/CodeDye/artifacts/generated/codedye_negative_control_row_hash_manifest_v2_20260507.json",
            "v3_protocol_freeze": "results/CodeDye/artifacts/generated/codedye_v3_protocol_freeze_gate_20260507.json",
            "v3_support_exclusion": "results/CodeDye/artifacts/generated/codedye_v3_support_exclusion_gate_20260507.json",
            "v3_postrun_promotion": "results/CodeDye/artifacts/generated/codedye_v3_postrun_promotion_gate_v1_20260507.json",
        },
        "locked_effect_surface": {
            "claim_rows": claim_rows,
            "final_signal": signal_count,
            "final_signal_ci95": wilson(signal_count, claim_rows),
            "statistics_artifact_positive_count": int(effect["statistics_artifact_boundary"]["statistics_artifact_positive_count"]),
            "support_rows_excluded": int(effect["support_rows_excluded_from_main_denominator"]),
            "missing_payload_or_transcript_hash": int(effect["claim_rows_missing_payload_or_transcript_hash"]),
            "positive_control_detected": pos_detected,
            "positive_control_denominator": pos_denominator,
            "positive_control_sensitivity_ci95": wilson(pos_detected, pos_denominator),
            "positive_control_missed": int(taxonomy["positive_control_missed"]),
            "positive_miss_taxonomy": taxonomy["miss_bucket_counts"],
            "negative_control_false_positive": false_positive,
            "negative_control_rows": negative_rows,
            "negative_control_fp_ci95": wilson(false_positive, negative_rows),
        },
        "paper_table_requirements": [
            "Report 6/300 final sparse audit signals with Wilson CI.",
            "Report 4/300 statistics sub-gate count separately from the 6/300 final signal.",
            "Report 170/300 positive-control sensitivity and the 130-row miss taxonomy.",
            "Report 0/300 negative-control false positives with a nonzero Wilson upper bound.",
            "State that 806 support/public rows are outside the 300-row main denominator.",
        ],
        "forbidden_claims": [
            "high-recall contamination detector",
            "contamination prevalence estimate",
            "provider accusation",
            "evidence that non-signals prove absence of contamination",
            "support/public rows as main-denominator evidence",
            "v3 live claim before the postrun promotion gate passes",
        ],
        "remaining_blockers": [
            "fresh_v3_live_result_missing",
            "positive_control_sensitivity_only_170_of_300",
            "live_signal_only_6_of_300",
        ],
        "required_next_evidence": [
            "Fresh frozen v3 DeepSeek live run with exactly 300 claim rows.",
            "Complete raw transcript, structured payload, prompt, task, and record hashes.",
            "Utility admissibility and support-row exclusion pass.",
            "Sensitivity improvement must come from preregistered protocol invariants, not threshold tuning.",
        ],
        "blockers": blockers,
    }
    return payload


def build_probetrace() -> dict[str, Any]:
    apis = load_json("results/ProbeTrace/artifacts/generated/apis300_live_attribution_evidence.json")
    abstain = load_json("results/ProbeTrace/artifacts/generated/probetrace_abstain_aware_attribution_gate_20260506.json")
    transfer = load_json("results/ProbeTrace/artifacts/generated/probetrace_transfer_validation_integrity_gate_20260506.json")
    binding = load_json("results/ProbeTrace/artifacts/generated/probetrace_transfer_row_binding_manifest_gate_20260505.json")
    package = load_json("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_package_20260507.json")
    postrun = load_json("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_postrun_promotion_gate_v1_20260507.json")
    blockers: list[str] = []
    if apis.get("formal_claim_allowed") is not True or int(apis.get("local_task_count", 0)) != 300:
        blockers.append("apis300_claim_surface_not_clean")
    neg_records = int(abstain["current_effect_surface"]["negative_control_records"])
    if neg_records != 1200:
        blockers.append("probetrace_negative_control_count_drift")
    if transfer.get("formal_source_bound_transfer_evidence_allowed") is not True:
        blockers.append("transfer_source_bound_evidence_not_allowed")
    if int(transfer.get("current_transfer_rows", 0)) != 900:
        blockers.append("transfer_900_drift")
    if binding.get("gate_pass") is not True or int(binding.get("unique_task_count", 0)) != 300:
        blockers.append("transfer_binding_gate_not_clean")
    if int(package.get("row_count", 0)) != 6000 or int(package.get("owner_count", 0)) < 5:
        blockers.append("multi_owner_input_package_drift")
    if postrun.get("gate_pass") is not False or postrun.get("formal_multi_owner_claim_allowed") is not False:
        blockers.append("multi_owner_postrun_unexpectedly_promoted")
    payload = {
        "schema_version": "probetrace_final_claim_lock_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": not blockers,
        "bestpaper_ready": False,
        "bestpaper_ready_reason": "Single-active-owner attribution and source-bound transfer evidence are strong, but perfect single-owner results remain shortcut/leakage-vulnerable until fresh multi-owner score-vector evidence passes.",
        "allowed_current_claim": "DeepSeek-only single-active-owner/source-bound attribution protocol",
        "upgrade_claim_allowed": False,
        "formal_single_active_owner_claim_allowed": not blockers,
        "formal_source_bound_transfer_evidence_allowed": not blockers,
        "formal_multi_owner_claim_allowed": False,
        "formal_provider_general_claim_allowed": False,
        "source_artifacts": {
            "apis300_live": "results/ProbeTrace/artifacts/generated/apis300_live_attribution_evidence.json",
            "abstain_aware_gate": "results/ProbeTrace/artifacts/generated/probetrace_abstain_aware_attribution_gate_20260506.json",
            "transfer_integrity": "results/ProbeTrace/artifacts/generated/probetrace_transfer_validation_integrity_gate_20260506.json",
            "transfer_binding": "results/ProbeTrace/artifacts/generated/probetrace_transfer_row_binding_manifest_gate_20260505.json",
            "multi_owner_input_package": "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_package_20260507.json",
            "multi_owner_postrun_promotion": "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_postrun_promotion_gate_v1_20260507.json",
        },
        "locked_effect_surface": {
            "apis300_attribution": wilson(300, 300),
            "negative_control_false_attribution": wilson(0, neg_records),
            "transfer_validation": wilson(900, 900),
            "transfer_rows": int(transfer["current_transfer_rows"]),
            "transfer_dataset_sha256": transfer["dataset_sha256"],
            "transfer_primary_independence_unit": "task_cluster",
            "unique_transfer_task_count": int(binding["unique_task_count"]),
            "multi_owner_input_rows": int(package["row_count"]),
            "multi_owner_owner_count": int(package["owner_count"]),
            "multi_owner_language_count": int(package["language_count"]),
            "multi_owner_control_role_counts": package["control_role_counts"],
            "multi_owner_split_counts": package["split_counts"],
        },
        "paper_table_requirements": [
            "Report APIS-300 as 300/300 with Wilson CI and explicit DeepSeek-only scope.",
            "Report 0/1200 false-owner/abstain controls with nonzero Wilson upper bound.",
            "Report transfer-900 only as source-bound clean-holdout evidence over 300 task clusters.",
            "Report latency/query cost in the main result surface.",
            "List the 6000-row multi-owner package as executable input only unless fresh score vectors pass postrun promotion.",
        ],
        "forbidden_claims": [
            "provider-general attribution",
            "multi-owner attribution from input package alone",
            "shortcut-free or leakage-free claim without fresh owner/task-heldout score vectors",
            "student-transfer generalization outside source-bound receipts",
            "perfect-score language without the anti-leakage caveat",
        ],
        "remaining_blockers": [
            "fresh_multi_owner_live_score_vectors_missing",
            "owner_task_heldout_margin_auc_missing",
            "perfect_single_owner_result_requires_anti_leakage_confirmation",
        ],
        "required_next_evidence": [
            "Fresh 6000-row DeepSeek score-vector output over 5 owners and 3 languages.",
            "True/wrong/null/random/same-provider owner margins and threshold-free AUC.",
            "Owner-heldout and task-heldout splits with all raw/structured/prompt/output/source hashes.",
            "Per-owner TPR/FPR CI and near-boundary rows retained.",
        ],
        "blockers": blockers,
    }
    return payload


def build_sealaudit() -> dict[str, Any]:
    surface = load_json("results/SealAudit/artifacts/generated/canonical_claim_surface_results.json")
    frontier = load_json("results/SealAudit/artifacts/generated/sealaudit_coverage_risk_frontier_gate_20260505.json")
    expert = load_json("results/SealAudit/artifacts/generated/sealaudit_expert_review_role_support_gate_v1_20260507.json")
    v5 = load_json("results/SealAudit/artifacts/generated/sealaudit_v5_final_evidence_readiness_gate_20260507.json")
    postrun = load_json("results/SealAudit/artifacts/generated/sealaudit_v5_postrun_promotion_gate_v1_20260507.json")
    hidden_rows = int(surface["claim_bearing_record_count"])
    visible_rows = int(surface["diagnostic_visible_record_count"])
    dist = frontier["decision_distribution"]
    decisive = int(dist["benign"]) + int(dist["latent_trojan"])
    needs_review = int(dist["needs_review"])
    unsafe_pass = int(frontier["unsafe_pass_count"])
    blockers: list[str] = []
    if surface.get("gate_pass") is not True or hidden_rows != 960:
        blockers.append("sealaudit_canonical_hidden_claim_surface_drift")
    if visible_rows != 320:
        blockers.append("sealaudit_visible_diagnostic_count_drift")
    if frontier.get("gate_pass") is not True or decisive != 81:
        blockers.append("sealaudit_frontier_drift")
    if unsafe_pass != 0:
        blockers.append("sealaudit_unsafe_pass_nonzero")
    if expert.get("role_based_support_only") is not True:
        blockers.append("sealaudit_expert_support_boundary_not_role_based")
    if v5.get("gate_pass") is not False:
        blockers.append("sealaudit_v5_readiness_unexpectedly_passed")
    if postrun.get("gate_pass") is not False or postrun.get("formal_v5_claim_allowed") is not False:
        blockers.append("sealaudit_v5_postrun_unexpectedly_promoted")
    payload = {
        "schema_version": "sealaudit_final_claim_lock_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": not blockers,
        "bestpaper_ready": False,
        "bestpaper_ready_reason": "Current v3 DeepSeek evidence supports selective marker-hidden triage; decisive coverage is only 81/960, so v5 must improve coverage-risk frontier before any stronger audit-classifier claim.",
        "allowed_current_claim": "DeepSeek-only marker-hidden selective audit/triage protocol",
        "upgrade_claim_allowed": False,
        "formal_marker_hidden_selective_triage_claim_allowed": not blockers,
        "formal_v5_claim_allowed": False,
        "formal_security_certificate_claim_allowed": False,
        "formal_harmlessness_claim_allowed": False,
        "formal_automatic_classifier_claim_allowed": False,
        "source_artifacts": {
            "canonical_claim_surface": "results/SealAudit/artifacts/generated/canonical_claim_surface_results.json",
            "coverage_risk_frontier": "results/SealAudit/artifacts/generated/sealaudit_coverage_risk_frontier_gate_20260505.json",
            "expert_role_support": "results/SealAudit/artifacts/generated/sealaudit_expert_review_role_support_gate_v1_20260507.json",
            "v5_readiness": "results/SealAudit/artifacts/generated/sealaudit_v5_final_evidence_readiness_gate_20260507.json",
            "v5_postrun_promotion": "results/SealAudit/artifacts/generated/sealaudit_v5_postrun_promotion_gate_v1_20260507.json",
        },
        "locked_effect_surface": {
            "case_count": int(surface["main_table_unique_case_count"]),
            "marker_hidden_claim_rows": hidden_rows,
            "marker_visible_diagnostic_rows": visible_rows,
            "decisive_count": decisive,
            "decisive_coverage_ci95": wilson(decisive, hidden_rows),
            "needs_review_count": needs_review,
            "needs_review_ci95": wilson(needs_review, hidden_rows),
            "unsafe_pass_count": unsafe_pass,
            "unsafe_pass_ci95": wilson(unsafe_pass, hidden_rows),
            "decision_distribution": dist,
            "expert_review_role_support_only": bool(expert["role_based_support_only"]),
            "v5_final_evidence_ready": bool(v5["gate_pass"]),
            "v5_postrun_gate_pass": bool(postrun["gate_pass"]),
        },
        "paper_table_requirements": [
            "Report 81/960 decisive marker-hidden rows as selective coverage, not accuracy.",
            "Report 879/960 needs-review rows as review load, not hidden success.",
            "Report 0/960 unsafe-pass rows with nonzero Wilson upper bound.",
            "Keep 320 visible-marker rows diagnostic-only.",
            "Describe expert review only as anonymous role-based support and packet confirmation.",
        ],
        "forbidden_claims": [
            "security certificate",
            "harmlessness guarantee",
            "automatic latent-trojan classifier",
            "visible-marker rows as main evidence",
            "expert-signed gold labels or named/institutional expert certification",
            "v5 coverage upgrade before final v5 postrun promotion passes",
        ],
        "remaining_blockers": [
            "decisive_coverage_only_81_of_960",
            "v5_final_evidence_not_claim_bearing",
            "v5_coverage_risk_frontier_missing",
            "v5_threshold_sensitivity_missing",
            "v5_visible_marker_boundary_missing",
        ],
        "required_next_evidence": [
            "Fresh v5 second-stage DeepSeek evidence with 960 hidden claim rows.",
            "Coverage-risk frontier showing improved decisive coverage without unsafe-pass inflation.",
            "Threshold sensitivity and visible-marker diagnostic boundary artifacts.",
            "Hard ambiguity retained rather than forced labels.",
        ],
        "blockers": blockers,
    }
    return payload


def main() -> int:
    artifacts = {
        "CodeDye": (
            "results/CodeDye/artifacts/generated/codedye_final_claim_lock_v1_20260507.json",
            "results/CodeDye/artifacts/generated/codedye_final_claim_lock_v1_20260507.md",
            "CodeDye Final Claim Lock v1",
            build_codedye(),
        ),
        "ProbeTrace": (
            "results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v1_20260507.json",
            "results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v1_20260507.md",
            "ProbeTrace Final Claim Lock v1",
            build_probetrace(),
        ),
        "SealAudit": (
            "results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v1_20260507.json",
            "results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v1_20260507.md",
            "SealAudit Final Claim Lock v1",
            build_sealaudit(),
        ),
    }
    any_blocked = False
    for project, (json_rel, md_rel, title, payload) in artifacts.items():
        write_json(json_rel, payload)
        write_md(md_rel, title, payload)
        any_blocked = any_blocked or not payload["gate_pass"]
        print(f"[OK] Wrote {json_rel}")
        print(f"[OK] Wrote {md_rel}")
        print(f"[OK] {project}: current claim lock gate_pass={payload['gate_pass']}, bestpaper_ready={payload['bestpaper_ready']}")
    return 0 if not any_blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
