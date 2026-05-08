from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT_JSON = ROOT / f"results/watermark_strict_reviewer_audit_v4_{DATE}.json"
OUT_MD = ROOT / f"results/watermark_strict_reviewer_audit_v4_{DATE}.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(rel: str) -> dict[str, Any]:
    payload = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(rel)
    return payload


def metric_score(value: int, rationale: str) -> dict[str, Any]:
    return {"score_1_to_5": value, "rationale": rationale}


def mean(scores: dict[str, dict[str, Any]]) -> float:
    values = [int(item["score_1_to_5"]) for item in scores.values()]
    return round(sum(values) / len(values), 2)


def verdict(avg: float, p1: int, p2: int) -> str:
    if p1:
        return "not_bestpaper_ready_p1_blocked"
    if avg >= 4.5 and p2 == 0:
        return "bestpaper_ready_by_strict_artifact_gate"
    if avg >= 4.0:
        return "strong_submission_but_not_bestpaper_locked"
    return "needs_substantial_revision"


def semcodebook() -> dict[str, Any]:
    base = load("results/watermark_strict_reviewer_audit_v3_20260507.json")
    project = next(item for item in base["projects"] if item["project"] == "SemCodebook")
    project = json.loads(json.dumps(project))
    project["strict_verdict"] = "bestpaper_ready_by_strict_artifact_gate"
    project["audit_v4_delta"] = "unchanged_from_v3"
    return project


def codedye() -> dict[str, Any]:
    lock = load("results/CodeDye/artifacts/generated/codedye_final_claim_lock_v1_20260507.json")
    trace = load("results/CodeDye/artifacts/generated/codedye_live_traceability_manifest_v1_20260507.json")
    scores = {
        "innovation": metric_score(4, "Curator-side sparse null-audit remains a coherent, scoped protocol."),
        "method_rigor": metric_score(4, "Final claim lock, positive-miss taxonomy, support exclusion, and legacy row traceability now make the low-effect boundary explicit."),
        "evidence_workload": metric_score(3, "300 live rows plus controls are adequate for sparse null-audit, not for a best-paper-level detection claim."),
        "baseline_control_strength": metric_score(4, "Controls and official/control boundaries are clean; support rows remain excluded."),
        "attack_negative_control": metric_score(4, "0/300 negative controls and row hashes are strong, but fresh v3 controls remain needed for an upgrade."),
        "statistics": metric_score(4, "CI, 4/300 vs 6/300 boundary, and signal/source discrepancy disclosure are locked."),
        "reproducibility": metric_score(4, "Legacy 300-row traceability is now present; raw transcript hashes are still absent in the legacy source."),
        "claim_boundary": metric_score(5, "High-recall, prevalence, provider-accusation, and v3-live claims remain forbidden."),
    }
    p1 = [
        "Effect is still too weak for any detection/prevalence claim: final boundary is 6/300 and positive-control sensitivity is 170/300.",
        "A fresh frozen v3 DeepSeek run with full prompt/raw/structured/task/record hashes is still required before any claim upgrade.",
    ]
    return {
        "project": "CodeDye",
        "strict_verdict": verdict(mean(scores), len(p1), 0),
        "bestpaper_ready": False,
        "bestpaper_ready_reason": lock["bestpaper_ready_reason"],
        "main_claim_allowed": lock["allowed_current_claim"],
        "forbidden_claims": lock["forbidden_claims"],
        "effect_metrics": {
            "final_signal": lock["locked_effect_surface"]["final_signal_ci95"],
            "positive_control_sensitivity": lock["locked_effect_surface"]["positive_control_sensitivity_ci95"],
            "negative_control_false_positive": lock["locked_effect_surface"]["negative_control_fp_ci95"],
            "legacy_traceability_gate_pass": trace["gate_pass"],
            "legacy_source_signal_count": trace["source_full_eval_signal_count"],
            "paper_boundary_signal_count": trace["final_paper_signal_count_from_boundary_gate"],
            "fresh_v3_missing_hash_fields": trace["missing_fresh_v3_required_fields"],
        },
        "overfit_risk": {
            "level": "medium",
            "reason": "Effect is weak and must not be optimized through threshold tuning; v3 must be preregistered and hash-complete.",
            "required_guard": "Keep sparse-audit claim and report positive-control misses.",
        },
        "scores": scores,
        "mean_score": mean(scores),
        "remaining_p1": p1,
        "remaining_p2": [],
        "audit_v4_delta": "Closed the reviewer-facing row-traceability P2; effect and fresh-v3 evidence remain P1.",
    }


def probetrace() -> dict[str, Any]:
    lock = load("results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v1_20260507.json")
    anti = load("results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_scan_v1_20260507.json")
    latency = load("results/ProbeTrace/artifacts/generated/probetrace_latency_query_frontier_v1_20260507.json")
    scores = {
        "innovation": metric_score(4, "Active-owner attribution with semantic witnesses, controls, and transfer binding is strong."),
        "method_rigor": metric_score(4, "Single-owner leakage/control-emission checks now pass; multi-owner score vectors remain missing."),
        "evidence_workload": metric_score(4, "APIS-300, 1,200 controls, transfer-900, and 6,000-row multi-owner input are substantial."),
        "baseline_control_strength": metric_score(4, "Wrong/null/random/utility/same-provider controls are visible and fail closed for multi-owner."),
        "attack_negative_control": metric_score(4, "0 control false attributions and 0 owner-id emissions support the scoped single-owner claim."),
        "statistics": metric_score(4, "Task-cluster transfer CI and control bounds are explicit; rank/AUC still awaits multi-owner outputs."),
        "reproducibility": metric_score(4, "Anti-leakage receipts and latency/query frontier are now indexed."),
        "claim_boundary": metric_score(5, "Multi-owner and provider-general claims remain forbidden."),
    }
    p1 = [
        "Broad multi-owner attribution remains non-claim-bearing until fresh 6,000-row DeepSeek score vectors, margin AUC, and owner/task-heldout postrun gates pass.",
    ]
    return {
        "project": "ProbeTrace",
        "strict_verdict": verdict(mean(scores), len(p1), 0),
        "bestpaper_ready": False,
        "bestpaper_ready_reason": lock["bestpaper_ready_reason"],
        "main_claim_allowed": lock["allowed_current_claim"],
        "forbidden_claims": lock["forbidden_claims"],
        "effect_metrics": {
            "apis300_attribution": lock["locked_effect_surface"]["apis300_attribution"],
            "false_owner_controls": lock["locked_effect_surface"]["negative_control_false_attribution"],
            "transfer_validation": lock["locked_effect_surface"]["transfer_validation"],
            "anti_leakage_gate_pass": anti["gate_pass"],
            "control_false_attribution_count": anti["checks"]["control_false_attribution_count"],
            "control_owner_id_emitted_count": anti["checks"]["control_owner_id_emitted_count"],
            "near_boundary_positive_count": anti["checks"]["near_boundary_positive_count"],
            "latency_query_gate_pass": latency["gate_pass"],
            "missing_latency_count": latency["missing_latency_count"],
        },
        "overfit_risk": {
            "level": "medium_until_multi_owner_rerun",
            "reason": "Single-owner leakage checks reduce shortcut concerns, but broad attribution still needs multi-owner score vectors.",
            "required_guard": "Keep single-active-owner scope until multi-owner postrun passes.",
        },
        "scores": scores,
        "mean_score": mean(scores),
        "remaining_p1": p1,
        "remaining_p2": [],
        "audit_v4_delta": "Closed leakage-scan and latency/query P2s for scoped single-owner claim.",
    }


def sealaudit() -> dict[str, Any]:
    lock = load("results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v1_20260507.json")
    abstention = load("results/SealAudit/artifacts/generated/sealaudit_abstention_burden_frontier_v1_20260507.json")
    wording = load("results/SealAudit/artifacts/generated/sealaudit_claim_wording_lock_v1_20260507.json")
    scores = {
        "innovation": metric_score(4, "Watermark-as-security-object selective audit remains useful and honestly scoped."),
        "method_rigor": metric_score(3, "Abstention is now row-taxonomized, but decisive coverage is still low."),
        "evidence_workload": metric_score(4, "320 cases and 960 marker-hidden rows are solid."),
        "baseline_control_strength": metric_score(4, "Marker-hidden/visible boundary and role-based support wording are explicit."),
        "attack_negative_control": metric_score(4, "Unsafe-pass bound remains 0/960; v5 final rows are still absent."),
        "statistics": metric_score(4, "Coverage-risk and abstention burden are now first-class, with row-level taxonomy."),
        "reproducibility": metric_score(4, "SealAudit tests now pass and wording/abstention artifacts are indexed."),
        "claim_boundary": metric_score(5, "Certificate, harmlessness, automatic-classifier, and signed-expert-label claims remain forbidden."),
    }
    p1 = [
        "Decisive coverage is still only 81/960, so current evidence supports selective triage rather than a strong audit classifier.",
        "Fresh v5 final evidence, coverage-risk frontier, threshold sensitivity, and visible-marker boundary are still missing.",
    ]
    return {
        "project": "SealAudit",
        "strict_verdict": verdict(mean(scores), len(p1), 0),
        "bestpaper_ready": False,
        "bestpaper_ready_reason": lock["bestpaper_ready_reason"],
        "main_claim_allowed": lock["allowed_current_claim"],
        "forbidden_claims": lock["forbidden_claims"],
        "effect_metrics": {
            "decisive_coverage": abstention["decisive_coverage_ci95"],
            "needs_review": abstention["needs_review_ci95"],
            "unsafe_pass": abstention["unsafe_pass_ci95"],
            "needs_review_bucket_counts": abstention["needs_review_bucket_counts"],
            "wording_lock_gate_pass": wording["gate_pass"],
        },
        "overfit_risk": {
            "level": "medium",
            "reason": "Forcing needs-review rows would inflate performance; the row taxonomy preserves abstention honestly.",
            "required_guard": "Improve coverage only through preregistered v5 conjunction, not relabeling.",
        },
        "scores": scores,
        "mean_score": mean(scores),
        "remaining_p1": p1,
        "remaining_p2": [],
        "audit_v4_delta": "Closed abstention taxonomy and expert-wording P2s; low coverage/v5 evidence remain P1.",
    }


def write_md(payload: dict[str, Any]) -> None:
    lines = [
        "# Strict Reviewer Audit v4",
        "",
        "This additive audit incorporates the v5 reviewer manifest and the new black-box claim-lock/traceability artifacts. It does not overwrite v3.",
        "",
        f"Portfolio verdict: `{payload['portfolio_verdict']}`",
        f"Best-paper ready: `{payload['portfolio_bestpaper_ready']}`",
        f"Remaining P1/P2: `{payload['remaining_p1_count']}` / `{payload['remaining_p2_count']}`",
        "",
    ]
    for project in payload["projects"]:
        lines.extend([
            f"## {project['project']}",
            "",
            f"- Verdict: `{project['strict_verdict']}`",
            f"- Mean strict score: `{project['mean_score']}`",
            f"- Allowed claim: {project['main_claim_allowed']}",
            f"- Ready: `{project['bestpaper_ready']}`",
            f"- Delta: {project['audit_v4_delta']}",
            "",
            "P1:",
        ])
        lines.extend(f"- {item}" for item in project["remaining_p1"]) if project["remaining_p1"] else lines.append("- None.")
        lines.extend(["", "P2:"])
        lines.extend(f"- {item}" for item in project["remaining_p2"]) if project["remaining_p2"] else lines.append("- None.")
        lines.append("")
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    projects = [semcodebook(), codedye(), probetrace(), sealaudit()]
    p1 = sum(len(project["remaining_p1"]) for project in projects)
    p2 = sum(len(project["remaining_p2"]) for project in projects)
    avg = round(sum(float(project["mean_score"]) for project in projects) / len(projects), 2)
    payload = {
        "schema_version": "watermark_strict_reviewer_audit_v4",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "supersedes_for_continuation_planning": "results/watermark_strict_reviewer_audit_v3_20260507.json",
        "portfolio_bestpaper_ready": False,
        "portfolio_verdict": verdict(avg, p1, p2),
        "portfolio_mean_score": avg,
        "remaining_p1_count": p1,
        "remaining_p2_count": p2,
        "formal_full_experiment_allowed": False,
        "formal_full_experiment_rule": "Full black-box upgrade claims require zero P1/P2 plus project-specific postrun gates and provider readiness.",
        "projects": projects,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_md(payload)
    print(f"[OK] Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"[OK] Wrote {OUT_MD.relative_to(ROOT)}")
    print(f"[OK] Portfolio verdict: {payload['portfolio_verdict']} with P1={p1}, P2={p2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
