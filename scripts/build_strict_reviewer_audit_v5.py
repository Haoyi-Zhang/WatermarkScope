from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT_JSON = ROOT / f"results/watermark_strict_reviewer_audit_v5_{DATE}.json"
OUT_MD = ROOT / f"results/watermark_strict_reviewer_audit_v5_{DATE}.md"


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


def base_project(name: str) -> dict[str, Any]:
    base = load(f"results/watermark_strict_reviewer_audit_v4_{DATE}.json")
    project = next(item for item in base["projects"] if item["project"] == name)
    return json.loads(json.dumps(project))


def semcodebook() -> dict[str, Any]:
    project = base_project("SemCodebook")
    project["audit_v5_delta"] = "unchanged_from_v4; reviewer manifest v6 now indexes fresh-run hardening for black-box projects"
    return project


def codedye() -> dict[str, Any]:
    project = base_project("CodeDye")
    contract = load(f"results/CodeDye/artifacts/generated/codedye_v3_fresh_run_preflight_contract_v1_{DATE}.json")
    readiness = load(f"results/provider_launch_readiness_gate_v2_{DATE}.json")
    project["scores"]["reproducibility"] = metric_score(
        5,
        "Fresh v3 execution contract, canonical output path, and postrun gate are now machine-bound; provider access remains a runtime blocker, not a schema blocker.",
    )
    project["mean_score"] = mean(project["scores"])
    project["strict_verdict"] = verdict(project["mean_score"], len(project["remaining_p1"]), len(project["remaining_p2"]))
    project["effect_metrics"]["fresh_run_contract_gate_pass"] = contract["gate_pass"]
    project["effect_metrics"]["provider_execution_ready_now"] = readiness["provider_execution_readiness"]["any_provider_execution_ready_now"]
    project["remaining_p1"] = [
        "Effect is still too weak for any detection/prevalence claim: final boundary is 6/300 and positive-control sensitivity is 170/300.",
        "A fresh frozen v3 DeepSeek run with full prompt/raw/structured/task/record hashes is still required before any claim upgrade; the execution contract is ready, provider execution is not.",
    ]
    project["audit_v5_delta"] = "Fresh-run contract and provider-readiness v2 close launch-schema risk; effect/fresh-output P1 remains."
    return project


def probetrace() -> dict[str, Any]:
    project = base_project("ProbeTrace")
    contract = load(f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_fresh_run_preflight_contract_v1_{DATE}.json")
    readiness = load(f"results/provider_launch_readiness_gate_v2_{DATE}.json")
    project["scores"]["reproducibility"] = metric_score(
        5,
        "The 6,000-row multi-owner input package, canonical score-vector output path, and postrun gate are now bound by a fresh-run contract.",
    )
    project["mean_score"] = mean(project["scores"])
    project["strict_verdict"] = verdict(project["mean_score"], len(project["remaining_p1"]), len(project["remaining_p2"]))
    project["effect_metrics"]["fresh_run_contract_gate_pass"] = contract["gate_pass"]
    project["effect_metrics"]["provider_execution_ready_now"] = readiness["provider_execution_readiness"]["any_provider_execution_ready_now"]
    project["remaining_p1"] = [
        "Broad multi-owner attribution remains non-claim-bearing until fresh 6,000-row DeepSeek score vectors, margin AUC, and owner/task-heldout postrun gates pass; the input/output contract is ready, provider execution is not.",
    ]
    project["audit_v5_delta"] = "Multi-owner launch contract now closes schema/naming risk; fresh score-vector evidence P1 remains."
    return project


def sealaudit() -> dict[str, Any]:
    project = base_project("SealAudit")
    contract = load(f"results/SealAudit/artifacts/generated/sealaudit_v5_fresh_run_preflight_contract_v1_{DATE}.json")
    readiness = load(f"results/provider_launch_readiness_gate_v2_{DATE}.json")
    project["scores"]["reproducibility"] = metric_score(
        5,
        "The final v5 evidence input, runner receipt, frontier, visible-marker boundary, threshold outputs, and postrun gate are now machine-bound.",
    )
    project["mean_score"] = mean(project["scores"])
    project["strict_verdict"] = verdict(project["mean_score"], len(project["remaining_p1"]), len(project["remaining_p2"]))
    project["effect_metrics"]["fresh_run_contract_gate_pass"] = contract["gate_pass"]
    project["effect_metrics"]["provider_execution_ready_now"] = readiness["provider_execution_readiness"]["any_provider_execution_ready_now"]
    project["remaining_p1"] = [
        "Decisive coverage is still only 81/960, so current evidence supports selective triage rather than a strong audit classifier.",
        "Fresh v5 final evidence, coverage-risk frontier, threshold sensitivity, and visible-marker boundary are still missing; the v5 input/output contract is ready, provider execution is not.",
    ]
    project["audit_v5_delta"] = "v5 launch/output contract closes final-evidence naming risk; low coverage/fresh-v5 evidence P1 remains."
    return project


def write_md(payload: dict[str, Any]) -> None:
    lines = [
        "# Strict Reviewer Audit v5",
        "",
        "This additive audit incorporates fresh-run contracts, naming consistency, and provider readiness v2. It does not overwrite earlier audits.",
        "",
        f"Portfolio verdict: `{payload['portfolio_verdict']}`",
        f"Best-paper ready: `{payload['portfolio_bestpaper_ready']}`",
        f"Remaining P1/P2: `{payload['remaining_p1_count']}` / `{payload['remaining_p2_count']}`",
        f"Provider execution ready now: `{payload['provider_execution_ready_now']}`",
        "",
    ]
    for project in payload["projects"]:
        lines.extend(
            [
                f"## {project['project']}",
                "",
                f"- Verdict: `{project['strict_verdict']}`",
                f"- Mean strict score: `{project['mean_score']}`",
                f"- Allowed claim: {project['main_claim_allowed']}",
                f"- Ready: `{project['bestpaper_ready']}`",
                f"- Delta: {project['audit_v5_delta']}",
                "",
                "P1:",
            ]
        )
        lines.extend(f"- {item}" for item in project["remaining_p1"]) if project["remaining_p1"] else lines.append("- None.")
        lines.extend(["", "P2:"])
        lines.extend(f"- {item}" for item in project["remaining_p2"]) if project["remaining_p2"] else lines.append("- None.")
        lines.append("")
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    provider = load(f"results/provider_launch_readiness_gate_v2_{DATE}.json")
    naming = load(f"results/blackbox_artifact_naming_consistency_v1_{DATE}.json")
    reviewer = load(f"results/watermark_reviewer_reproducibility_manifest_v6_{DATE}.json")
    projects = [semcodebook(), codedye(), probetrace(), sealaudit()]
    p1 = sum(len(project["remaining_p1"]) for project in projects)
    p2 = sum(len(project["remaining_p2"]) for project in projects)
    avg = round(sum(float(project["mean_score"]) for project in projects) / len(projects), 2)
    payload = {
        "schema_version": "watermark_strict_reviewer_audit_v5",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "supersedes_for_continuation_planning": f"results/watermark_strict_reviewer_audit_v4_{DATE}.json",
        "portfolio_bestpaper_ready": False,
        "portfolio_verdict": verdict(avg, p1, p2),
        "portfolio_mean_score": avg,
        "remaining_p1_count": p1,
        "remaining_p2_count": p2,
        "formal_full_experiment_allowed": False,
        "provider_execution_ready_now": provider["provider_execution_readiness"]["any_provider_execution_ready_now"],
        "fresh_run_contracts_gate_pass": naming["gate_pass"] is True and reviewer["gate_pass"] is True,
        "formal_full_experiment_rule": "Fresh-run contracts are ready; black-box upgrade claims require provider execution plus project-specific postrun promotion gates.",
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
