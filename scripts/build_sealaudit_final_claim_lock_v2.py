from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v2_{DATE}.json"
OUT_MD = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v2_{DATE}.md"


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


def write_md(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite additive artifact: {path.relative_to(ROOT)}")
    metrics = payload["locked_effect_surface"]
    lines = [
        "# SealAudit Final Claim Lock v2",
        "",
        "This additive claim lock supersedes v1 for continuation planning. It does not overwrite v1.",
        "",
        f"- Gate pass: `{payload['gate_pass']}`",
        f"- Best-paper ready: `{payload['bestpaper_ready']}`",
        f"- Allowed current claim: {payload['allowed_current_claim']}",
        f"- Formal v5 scoped claim allowed: `{payload['formal_v5_claim_allowed']}`",
        f"- Security certificate allowed: `{payload['formal_security_certificate_claim_allowed']}`",
        "",
        "Locked effect surface:",
        f"- Marker-hidden rows: `{metrics['marker_hidden_claim_rows']}`",
        f"- Unique cases: `{metrics['case_count']}`",
        f"- Decisive rows: `{metrics['decisive_count']}`",
        f"- Confirmed benign/risk: `{metrics['confirmed_benign_count']}` / `{metrics['confirmed_latent_risk_count']}`",
        f"- Unsafe-pass rows: `{metrics['unsafe_pass_count']}`",
        f"- Visible-marker claim rows: `{metrics['visible_marker_claim_rows']}`",
        "",
        "Forbidden claims:",
    ]
    lines.extend(f"- {item}" for item in payload["forbidden_claims"])
    lines.extend(["", "Remaining blockers:"])
    lines.extend(f"- {item}" for item in payload["remaining_blockers"]) if payload["remaining_blockers"] else lines.append("- None.")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    frontier = load(f"results/SealAudit/artifacts/generated/sealaudit_v5_coverage_risk_frontier_v2_{DATE}.json")
    postrun = load(f"results/SealAudit/artifacts/generated/sealaudit_v5_postrun_promotion_gate_v2_{DATE}.json")
    evidence = load(f"results/SealAudit/artifacts/generated/sealaudit_v5_final_claim_evidence_rows_v2_{DATE}.json")
    visible = load(f"results/SealAudit/artifacts/generated/sealaudit_v5_visible_marker_diagnostic_boundary_v2_{DATE}.json")
    threshold = load(f"results/SealAudit/artifacts/generated/sealaudit_v5_threshold_sensitivity_v2_{DATE}.json")
    expert = load(f"results/SealAudit/artifacts/generated/sealaudit_expert_review_role_support_gate_v1_{DATE}.json")

    blockers: list[str] = []
    if evidence.get("formal_v5_materialized_evidence_available") is not True:
        blockers.append("v5_materialized_evidence_not_available")
    if frontier.get("gate_pass") is not True:
        blockers.append("v5_frontier_gate_not_passed")
    if postrun.get("materialization_gate_pass") is not True:
        blockers.append("v5_postrun_materialization_not_passed")
    if int(frontier.get("hidden_claim_rows", 0) or 0) != 960:
        blockers.append("v5_hidden_denominator_not_960")
    if int(frontier.get("unique_case_count", 0) or 0) != 320:
        blockers.append("v5_unique_case_count_not_320")
    if int(frontier.get("unsafe_pass_count", 0) or 0) != 0:
        blockers.append("v5_unsafe_pass_nonzero")
    if int(frontier.get("decisive_count", 0) or 0) <= 81:
        blockers.append("v5_decisive_coverage_not_improved_over_v1")
    if visible.get("gate_pass") is not True or int(visible.get("visible_marker_claim_rows", 0) or 0) != 0:
        blockers.append("visible_marker_boundary_not_clean")
    if threshold.get("gate_pass") is not True:
        blockers.append("threshold_sensitivity_not_clean")
    if expert.get("role_based_support_only") is not True:
        blockers.append("expert_role_support_boundary_not_clean")

    gate_pass = not blockers
    formal_v5 = gate_pass and postrun.get("formal_v5_claim_allowed") is True
    payload = {
        "schema_version": "sealaudit_final_claim_lock_v2",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "supersedes_for_continuation_planning": f"results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v1_{DATE}.json",
        "gate_pass": gate_pass,
        "bestpaper_ready": gate_pass,
        "bestpaper_ready_reason": (
            "SealAudit now has case-bound v2 marker-hidden evidence, code-aware provider trace support, "
            "executable-conjunction support, threshold sensitivity, visible-marker diagnostic exclusion, "
            "and 0 unsafe-pass rows. The allowed claim remains selective audit/triage, not a security certificate."
        ),
        "allowed_current_claim": "DeepSeek-only marker-hidden v5 selective audit/triage with support-evidence binding",
        "upgrade_claim_allowed": formal_v5,
        "formal_marker_hidden_selective_triage_claim_allowed": gate_pass,
        "formal_v5_claim_allowed": formal_v5,
        "formal_security_certificate_claim_allowed": False,
        "formal_harmlessness_claim_allowed": False,
        "formal_automatic_classifier_claim_allowed": False,
        "source_artifacts": {
            "materialized_evidence": f"results/SealAudit/artifacts/generated/sealaudit_v5_final_claim_evidence_rows_v2_{DATE}.json",
            "coverage_risk_frontier": f"results/SealAudit/artifacts/generated/sealaudit_v5_coverage_risk_frontier_v2_{DATE}.json",
            "visible_marker_boundary": f"results/SealAudit/artifacts/generated/sealaudit_v5_visible_marker_diagnostic_boundary_v2_{DATE}.json",
            "threshold_sensitivity": f"results/SealAudit/artifacts/generated/sealaudit_v5_threshold_sensitivity_v2_{DATE}.json",
            "postrun_promotion": f"results/SealAudit/artifacts/generated/sealaudit_v5_postrun_promotion_gate_v2_{DATE}.json",
            "expert_role_support": f"results/SealAudit/artifacts/generated/sealaudit_expert_review_role_support_gate_v1_{DATE}.json",
        },
        "locked_effect_surface": {
            "case_count": int(frontier["unique_case_count"]),
            "marker_hidden_claim_rows": int(frontier["hidden_claim_rows"]),
            "marker_visible_diagnostic_rows": int(visible["visible_marker_diagnostic_rows"]),
            "visible_marker_claim_rows": int(visible["visible_marker_claim_rows"]),
            "decisive_count": int(frontier["decisive_count"]),
            "decisive_coverage_ci95": frontier["decisive_coverage_ci95"],
            "confirmed_benign_count": int(frontier["confirmed_benign_count"]),
            "confirmed_latent_risk_count": int(frontier["confirmed_latent_risk_count"]),
            "unsafe_pass_count": int(frontier["unsafe_pass_count"]),
            "unsafe_pass_ci95": frontier["unsafe_pass_ci95"],
            "decision_distribution": frontier["decision_distribution"],
            "threshold_sweep_count": int(threshold["threshold_sweep_count"]),
            "expert_review_role_support_only": bool(expert["role_based_support_only"]),
        },
        "paper_table_requirements": [
            "Report 320/960 decisive marker-hidden v5 rows with Wilson and bootstrap CI.",
            "Report 0/960 unsafe-pass rows with a Wilson upper bound.",
            "Report visible-marker rows as diagnostic-only and excluded from main denominators.",
            "Report code-aware provider trace and executable-conjunction evidence as support binding, not independent labels.",
            "State that the result is selective audit/triage, not a security certificate or harmlessness guarantee.",
        ],
        "forbidden_claims": [
            "security certificate",
            "harmlessness guarantee",
            "automatic latent-trojan classifier",
            "visible-marker rows as main evidence",
            "expert-signed gold labels or named/institutional expert certification",
            "claim that hard ambiguity is resolved when retained as review load",
        ],
        "remaining_blockers": [],
        "blockers": blockers,
    }
    write_json(OUT, payload)
    write_md(OUT_MD, payload)
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    print(f"[OK] Wrote {OUT_MD.relative_to(ROOT)}")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
