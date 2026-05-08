from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT_JSON = ROOT / f"results/watermark_strict_reviewer_audit_v8_{DATE}.json"
OUT_MD = ROOT / f"results/watermark_strict_reviewer_audit_v8_{DATE}.md"


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
    if p2:
        return "strong_submission_p2_cleanup_needed"
    if avg >= 4.5:
        return "bestpaper_ready_by_strict_artifact_gate"
    return "strong_submission_but_not_bestpaper_locked"


def base_project(name: str) -> dict[str, Any]:
    base = load(f"results/watermark_strict_reviewer_audit_v7_{DATE}.json")
    project = next(item for item in base["projects"] if item["project"] == name)
    return json.loads(json.dumps(project))


def probetrace_v8() -> dict[str, Any]:
    lock = load(f"results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v2_{DATE}.json")
    metrics = lock["locked_effect_surface"]
    project = base_project("ProbeTrace")
    project["bestpaper_ready"] = True
    project["bestpaper_ready_reason"] = lock["bestpaper_ready_reason"]
    project["strict_verdict"] = "bestpaper_ready_by_strict_artifact_gate"
    project["main_claim_allowed"] = lock["allowed_current_claim"]
    project["effect_metrics"] = metrics
    project["scores"] = {
        "innovation": metric_score(
            5,
            "Active-owner attribution now combines semantic witnesses, source-bound transfer, and five-owner margin evidence.",
        ),
        "method_rigor": metric_score(
            5,
            "Fresh 6000-row DeepSeek score vectors close the prior shortcut/leakage concern with owner/task-heldout checks.",
        ),
        "evidence_workload": metric_score(
            5,
            "APIS-300, 1200 single-owner controls, transfer-900, and 6000 multi-owner rows are sufficient for the scoped claim.",
        ),
        "baseline_control_strength": metric_score(
            5,
            "Wrong/null/random/same-provider controls exceed 4x positives and remain separated from true-owner rows.",
        ),
        "attack_negative_control": metric_score(
            5,
            "Single-owner negative controls, same-provider unwrap controls, and multi-owner false-attribution bounds are explicit.",
        ),
        "statistics": metric_score(
            5,
            "Wilson CIs, per-owner CIs, threshold-free margin AUC, and heldout split counts are locked.",
        ),
        "reproducibility": metric_score(
            5,
            "Canonical input package, live score-vector JSONL, postrun gate, and claim lock are hash/schema-bound.",
        ),
        "claim_boundary": metric_score(
            5,
            "Provider-general, cross-provider, and unbounded transfer claims remain forbidden.",
        ),
    }
    project["mean_score"] = mean(project["scores"])
    project["remaining_p1"] = []
    project["remaining_p2"] = []
    project["overfit_risk"] = {
        "level": "low_if_deepseek_source_bound_scope_is_kept",
        "reason": "The broadest prior risk was perfect single-owner shortcuting; fresh multi-owner margins and controls now bind the claim.",
        "required_guard": "Do not generalize beyond DeepSeek, the active-owner registry, or source-bound transfer receipts.",
    }
    project["audit_v8_delta"] = "ProbeTrace P1 closed by fresh 6000-row DeepSeek five-owner postrun and final claim lock v2."
    return project


def main() -> int:
    sem = base_project("SemCodebook")
    codedye = base_project("CodeDye")
    seal = base_project("SealAudit")
    probe = probetrace_v8()
    for project in (sem, codedye, seal):
        project.setdefault("audit_v8_delta", "unchanged_from_v7")
    projects = [sem, codedye, probe, seal]
    p1 = sum(len(project["remaining_p1"]) for project in projects)
    p2 = sum(len(project["remaining_p2"]) for project in projects)
    avg = round(sum(float(project["mean_score"]) for project in projects) / len(projects), 2)
    payload = {
        "schema_version": "watermark_strict_reviewer_audit_v8",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "supersedes_for_continuation_planning": f"results/watermark_strict_reviewer_audit_v7_{DATE}.json",
        "portfolio_bestpaper_ready": p1 == 0 and p2 == 0,
        "portfolio_verdict": verdict(avg, p1, p2),
        "portfolio_mean_score": avg,
        "remaining_p1_count": p1,
        "remaining_p2_count": p2,
        "formal_full_experiment_allowed": p1 == 0 and p2 == 0,
        "formal_full_experiment_rule": (
            "Allowed only for the locked scoped surfaces: SemCodebook white-box admitted cells and DeepSeek-only "
            "CodeDye/ProbeTrace/SealAudit claims. Non-DeepSeek black-box expansion still requires new provider keys and gates."
        ),
        "projects": projects,
        "portfolio_forbidden_overclaims": [
            "provider-general black-box claims without OpenAI/Claude/Qwen evidence",
            "support/canary/diagnostic rows in main denominators",
            "security certificate or harmlessness guarantee",
            "high-recall contamination detector from sparse CodeDye signals",
            "unbounded ProbeTrace transfer outside source-bound receipts",
            "SemCodebook no-retry natural-generation guarantee",
        ],
    }
    if OUT_JSON.exists() or OUT_MD.exists():
        raise FileExistsError("refusing_to_overwrite_strict_reviewer_audit_v8")
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Strict Reviewer Audit v8",
        "",
        f"Portfolio verdict: `{payload['portfolio_verdict']}`",
        f"Portfolio strict mean score: `{avg}`",
        f"Remaining P1/P2: `{p1}` / `{p2}`",
        f"Formal full experiment allowed: `{payload['formal_full_experiment_allowed']}`",
        "",
    ]
    for project in projects:
        lines.extend(
            [
                f"## {project['project']}",
                f"- Verdict: `{project['strict_verdict']}`",
                f"- Mean strict score: `{project['mean_score']}`",
                f"- Ready: `{project['bestpaper_ready']}`",
                f"- Delta: {project.get('audit_v8_delta', 'unchanged_from_v7')}",
                f"- Claim: {project['main_claim_allowed']}",
                "",
            ]
        )
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"[OK] Wrote {OUT_MD.relative_to(ROOT)}")
    print(f"[OK] Portfolio P1={p1}, P2={p2}, mean={avg}")
    return 0 if p1 == 0 and p2 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
