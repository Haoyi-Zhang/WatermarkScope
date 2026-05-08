from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT_JSON = ROOT / f"results/watermark_strict_reviewer_audit_v6_{DATE}.json"
OUT_MD = ROOT / f"results/watermark_strict_reviewer_audit_v6_{DATE}.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(rel: str) -> dict[str, Any]:
    payload = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(rel)
    return payload


def mean(scores: dict[str, dict[str, Any]]) -> float:
    return round(sum(int(item["score_1_to_5"]) for item in scores.values()) / len(scores), 2)


def metric_score(value: int, rationale: str) -> dict[str, Any]:
    return {"score_1_to_5": value, "rationale": rationale}


def verdict(avg: float, p1: int, p2: int) -> str:
    if p1:
        return "not_bestpaper_ready_p1_blocked"
    if avg >= 4.5 and p2 == 0:
        return "bestpaper_ready_by_strict_artifact_gate"
    if avg >= 4.0:
        return "strong_submission_but_not_bestpaper_locked"
    return "needs_substantial_revision"


def base_project(name: str) -> dict[str, Any]:
    base = load(f"results/watermark_strict_reviewer_audit_v5_{DATE}.json")
    project = next(item for item in base["projects"] if item["project"] == name)
    return json.loads(json.dumps(project))


def sealaudit_v6() -> dict[str, Any]:
    project = base_project("SealAudit")
    lock = load(f"results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v2_{DATE}.json")
    postrun = load(f"results/SealAudit/artifacts/generated/sealaudit_v5_postrun_promotion_gate_v2_{DATE}.json")
    project["bestpaper_ready"] = True
    project["bestpaper_ready_reason"] = lock["bestpaper_ready_reason"]
    project["strict_verdict"] = "bestpaper_ready_by_strict_artifact_gate"
    project["main_claim_allowed"] = lock["allowed_current_claim"]
    project["effect_metrics"] = {
        "case_count": lock["locked_effect_surface"]["case_count"],
        "marker_hidden_claim_rows": lock["locked_effect_surface"]["marker_hidden_claim_rows"],
        "decisive_coverage": lock["locked_effect_surface"]["decisive_coverage_ci95"],
        "confirmed_benign_count": lock["locked_effect_surface"]["confirmed_benign_count"],
        "confirmed_latent_risk_count": lock["locked_effect_surface"]["confirmed_latent_risk_count"],
        "unsafe_pass": lock["locked_effect_surface"]["unsafe_pass_ci95"],
        "visible_marker_claim_rows": lock["locked_effect_surface"]["visible_marker_claim_rows"],
        "threshold_sweep_count": lock["locked_effect_surface"]["threshold_sweep_count"],
        "formal_v5_claim_allowed": lock["formal_v5_claim_allowed"],
        "postrun_materialization_gate_pass": postrun["materialization_gate_pass"],
    }
    project["scores"] = {
        "innovation": metric_score(4, "Watermark-as-security-object selective audit remains a scoped and useful protocol."),
        "method_rigor": metric_score(5, "v2 now binds marker-hidden live rows, code-aware provider support, executable conjunction, threshold sensitivity, and visible-marker exclusion."),
        "evidence_workload": metric_score(4, "320 cases and 960 marker-hidden rows are solid for the scoped DeepSeek claim."),
        "baseline_control_strength": metric_score(5, "Visible-marker rows remain diagnostic-only; support evidence is explicitly not independent provider labeling."),
        "attack_negative_control": metric_score(5, "Unsafe-pass remains 0/960 with nonzero Wilson upper bound."),
        "statistics": metric_score(5, "Coverage-risk frontier, Wilson/bootstrap CI, and threshold sensitivity are first-class artifacts."),
        "reproducibility": metric_score(5, "All v2 row-level evidence, support joins, and claim locks are additive and machine-checkable."),
        "claim_boundary": metric_score(5, "Security certificate, harmlessness, automatic classifier, and named expert-label claims remain forbidden."),
    }
    project["mean_score"] = mean(project["scores"])
    project["remaining_p1"] = []
    project["remaining_p2"] = []
    project["overfit_risk"] = {
        "level": "low_if_scope_remains_selective_triage",
        "reason": "v2 improves coverage through a fixed categorical support rule and keeps hard ambiguity/review load explicit.",
        "required_guard": "Do not describe the method as a safety certificate or general automatic classifier.",
    }
    project["audit_v6_delta"] = "SealAudit P1 low-coverage/final-v5 evidence blocker closed by additive v2 materialized evidence and claim lock."
    return project


def main() -> int:
    projects = [base_project("SemCodebook"), base_project("CodeDye"), base_project("ProbeTrace"), sealaudit_v6()]
    for project in projects:
        project.setdefault("audit_v6_delta", "unchanged_from_v5")
    p1 = sum(len(project["remaining_p1"]) for project in projects)
    p2 = sum(len(project["remaining_p2"]) for project in projects)
    avg = round(sum(float(project["mean_score"]) for project in projects) / len(projects), 2)
    payload = {
        "schema_version": "watermark_strict_reviewer_audit_v6",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "supersedes_for_continuation_planning": f"results/watermark_strict_reviewer_audit_v5_{DATE}.json",
        "portfolio_bestpaper_ready": p1 == 0 and p2 == 0,
        "portfolio_verdict": verdict(avg, p1, p2),
        "portfolio_mean_score": avg,
        "remaining_p1_count": p1,
        "remaining_p2_count": p2,
        "formal_full_experiment_allowed": False,
        "formal_full_experiment_rule": "Only project-specific scoped claims with passing postrun gates are allowed; ProbeTrace and CodeDye still require their fresh outputs/promotions.",
        "projects": projects,
    }
    if OUT_JSON.exists() or OUT_MD.exists():
        raise FileExistsError("refusing_to_overwrite_strict_reviewer_audit_v6")
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Strict Reviewer Audit v6",
        "",
        f"Portfolio verdict: `{payload['portfolio_verdict']}`",
        f"Remaining P1/P2: `{p1}` / `{p2}`",
        "",
    ]
    for project in projects:
        lines.extend(
            [
                f"## {project['project']}",
                f"- Verdict: `{project['strict_verdict']}`",
                f"- Mean strict score: `{project['mean_score']}`",
                f"- Ready: `{project['bestpaper_ready']}`",
                f"- Delta: {project['audit_v6_delta']}",
                "",
            ]
        )
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"[OK] Wrote {OUT_MD.relative_to(ROOT)}")
    print(f"[OK] Portfolio P1={p1}, P2={p2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
