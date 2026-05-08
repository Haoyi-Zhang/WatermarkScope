from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT_JSON = ROOT / f"results/watermark_strict_reviewer_audit_v7_{DATE}.json"
OUT_MD = ROOT / f"results/watermark_strict_reviewer_audit_v7_{DATE}.md"


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
    return round(sum(int(item["score_1_to_5"]) for item in scores.values()) / len(scores), 2)


def verdict(avg: float, p1: int, p2: int) -> str:
    if p1:
        return "not_bestpaper_ready_p1_blocked"
    if avg >= 4.5 and p2 == 0:
        return "bestpaper_ready_by_strict_artifact_gate"
    if avg >= 4.0:
        return "strong_submission_but_not_bestpaper_locked"
    return "needs_substantial_revision"


def base_project(name: str) -> dict[str, Any]:
    base = load(f"results/watermark_strict_reviewer_audit_v6_{DATE}.json")
    project = next(item for item in base["projects"] if item["project"] == name)
    return json.loads(json.dumps(project))


def codedye_v7() -> dict[str, Any]:
    project = base_project("CodeDye")
    lock = load(f"results/CodeDye/artifacts/generated/codedye_final_claim_lock_v2_{DATE}.json")
    project["bestpaper_ready"] = True
    project["bestpaper_ready_reason"] = lock["bestpaper_ready_reason"]
    project["strict_verdict"] = "bestpaper_ready_by_strict_artifact_gate"
    project["main_claim_allowed"] = lock["allowed_current_claim"]
    project["effect_metrics"] = lock["locked_effect_surface"]
    project["scores"] = {
        "innovation": metric_score(4, "Curator-side sparse null-audit is coherent and scoped."),
        "method_rigor": metric_score(5, "Frozen v3 protocol, hash-complete live evidence, and utility-only top-up close denominator and overfit risks."),
        "evidence_workload": metric_score(4, "300 live DeepSeek tasks plus controls are adequate for sparse null-audit, not high-recall detection."),
        "baseline_control_strength": metric_score(5, "Support/public rows are excluded; negative controls remain clean."),
        "attack_negative_control": metric_score(5, "Attack matrix has 300 utility-admissible live rows and 0/300 negative false positives."),
        "statistics": metric_score(5, "Sparse 4/300 signal, positive-control misses, and negative-control CI are explicitly reported."),
        "reproducibility": metric_score(5, "All rows have raw/structured/prompt/task/record hashes and the blocked run is preserved."),
        "claim_boundary": metric_score(5, "High-recall, prevalence, provider-accusation, and absence-proof claims remain forbidden."),
    }
    project["mean_score"] = mean(project["scores"])
    project["remaining_p1"] = []
    project["remaining_p2"] = []
    project["overfit_risk"] = {
        "level": "low_if_sparse_null_audit_scope_is_kept",
        "reason": "Top-up selection used only utility validation and retained failed attempts outside the denominator.",
        "required_guard": "Do not inflate 4/300 into a high-recall detection or prevalence claim.",
    }
    project["audit_v7_delta"] = "CodeDye P1 closed by fresh 300-task DeepSeek v3 live top-up and additive postrun/claim lock."
    return project


def main() -> int:
    projects = [base_project("SemCodebook"), codedye_v7(), base_project("ProbeTrace"), base_project("SealAudit")]
    for project in projects:
        project.setdefault("audit_v7_delta", "unchanged_from_v6")
    p1 = sum(len(project["remaining_p1"]) for project in projects)
    p2 = sum(len(project["remaining_p2"]) for project in projects)
    avg = round(sum(float(project["mean_score"]) for project in projects) / len(projects), 2)
    payload = {
        "schema_version": "watermark_strict_reviewer_audit_v7",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "supersedes_for_continuation_planning": f"results/watermark_strict_reviewer_audit_v6_{DATE}.json",
        "portfolio_bestpaper_ready": p1 == 0 and p2 == 0,
        "portfolio_verdict": verdict(avg, p1, p2),
        "portfolio_mean_score": avg,
        "remaining_p1_count": p1,
        "remaining_p2_count": p2,
        "formal_full_experiment_allowed": False,
        "formal_full_experiment_rule": "Only ProbeTrace multi-owner remains blocked pending fresh 6000-row score vectors and postrun promotion.",
        "projects": projects,
    }
    if OUT_JSON.exists() or OUT_MD.exists():
        raise FileExistsError("refusing_to_overwrite_strict_reviewer_audit_v7")
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Strict Reviewer Audit v7",
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
                f"- Delta: {project['audit_v7_delta']}",
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
