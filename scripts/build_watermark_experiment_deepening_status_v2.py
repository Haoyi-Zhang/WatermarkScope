from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260508"
OUT_JSON = ROOT / f"results/watermark_experiment_deepening_status_v2_{DATE}.json"
OUT_MD = ROOT / f"results/watermark_experiment_deepening_status_v2_{DATE}.md"


def load(rel: str) -> dict[str, Any]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def project_status() -> dict[str, Any]:
    sem_queue = load("results/SemCodebook/artifacts/generated/semcodebook_whitebox_next_gpu_queue_v1_20260508.json")
    code_v4 = load("results/CodeDye/artifacts/generated/codedye_v4_query_budget_support_postrun_gate_v1_20260508.json")
    probe_challenge = load("results/ProbeTrace/artifacts/generated/probetrace_commitment_shortcut_challenge_postrun_gate_v1_20260508.json")
    seal_v6 = load("results/SealAudit/artifacts/generated/sealaudit_v6_failure_taxonomy_audit_v1_20260508.json")
    strict = load("results/watermark_strict_reviewer_audit_v8_20260507.json")

    blockers: list[str] = []
    if code_v4.get("gate_pass") is not True:
        blockers.append("codedye_v4_query_budget_support_not_admitted")
    if probe_challenge.get("gate_pass") is not True:
        blockers.append("probetrace_commitment_shortcut_challenge_not_admitted")
    if seal_v6.get("gate_pass") is not True:
        blockers.append("sealaudit_v6_failure_taxonomy_not_admitted")
    if not sem_queue.get("next_gpu_queue"):
        blockers.append("semcodebook_next_gpu_queue_missing")
    if sem_queue.get("gpu_run_allowed_now") is True:
        blockers.append("semcodebook_gpu_queue_unexpectedly_runnable_on_current_js4_without_explicit_launch")

    return {
        "schema_version": "watermark_experiment_deepening_status_v2",
        "date": DATE,
        "claim_bearing": False,
        "gate_pass": not blockers,
        "portfolio_prior_strict_audit": {
            "path": "results/watermark_strict_reviewer_audit_v8_20260507.json",
            "claim_bearing": strict.get("claim_bearing"),
            "verdict": strict.get("verdict", strict.get("portfolio_verdict")),
        },
        "projects": {
            "SemCodebook": {
                "new_artifact": "results/SemCodebook/artifacts/generated/semcodebook_whitebox_next_gpu_queue_v1_20260508.json",
                "status": "current 72k admitted claim preserved; future white-box expansion is queued but blocked on current machine resources",
                "gpu_run_allowed_now": sem_queue.get("gpu_run_allowed_now"),
                "resource_blockers": sem_queue.get("blockers"),
                "current_admitted_model_count": sem_queue.get("current_admitted_model_count"),
                "current_total_admitted_records": sem_queue.get("current_total_admitted_records"),
                "next_gpu_queue_count": len(sem_queue.get("next_gpu_queue", [])),
                "next_action": "Move to a server with NVIDIA device access and PEFT installed, then run queued CodeLlama/Stable-Code/CodeGen expansions as full 7200-row cells.",
            },
            "CodeDye": {
                "new_artifacts": [
                    "results/CodeDye/artifacts/generated/codedye_v4_query_budget_support_protocol_v1_20260508.json",
                    "results/CodeDye/artifacts/generated/codedye_v4_query_budget_support_results_20260508.json",
                    "results/CodeDye/artifacts/generated/codedye_v4_query_budget_support_postrun_gate_v1_20260508.json",
                ],
                "status": "DeepSeek query-budget support axis executed with live rows and admitted as support-only",
                "support_gate_pass": code_v4.get("gate_pass"),
                "record_count": code_v4.get("record_count"),
                "decision_counts": code_v4.get("decision_counts"),
                "main_claim_boundary": code_v4.get("main_claim_boundary"),
                "next_action": "Do not upgrade to high-recall detection; use v4 as robustness support for the sparse null-audit narrative.",
            },
            "ProbeTrace": {
                "new_artifacts": [
                    "results/ProbeTrace/artifacts/generated/probetrace_commitment_shortcut_challenge_protocol_v1_20260508.json",
                    "results/ProbeTrace/artifacts/generated/probetrace_commitment_shortcut_challenge_live_results_v1_20260508.jsonl",
                    "results/ProbeTrace/artifacts/generated/probetrace_commitment_shortcut_challenge_postrun_gate_v1_20260508.json",
                ],
                "status": "DeepSeek corrupted-commitment challenge executed; perfect main score-vector result now has an explicit fail-closed shortcut control",
                "support_gate_pass": probe_challenge.get("gate_pass"),
                "record_count": probe_challenge.get("record_count"),
                "candidate_owner_emit_rows": probe_challenge.get("candidate_owner_emit_rows"),
                "high_score_rows": probe_challenge.get("high_score_rows"),
                "abstain_or_noncandidate_ci95": probe_challenge.get("abstain_or_noncandidate_ci95"),
                "next_action": "Keep provider-general claim blocked until non-DeepSeek keys are available; report shortcut challenge in robustness section.",
            },
            "SealAudit": {
                "new_artifact": "results/SealAudit/artifacts/generated/sealaudit_v6_failure_taxonomy_audit_v1_20260508.json",
                "status": "v5 selective triage result decomposed into coverage-risk and nondecisive failure taxonomy",
                "support_gate_pass": seal_v6.get("gate_pass"),
                "hidden_claim_rows": seal_v6.get("hidden_claim_rows"),
                "decisive_count": seal_v6.get("decisive_count"),
                "unsafe_pass_count": seal_v6.get("unsafe_pass_count"),
                "decision_counts": seal_v6.get("decision_counts"),
                "next_action": "Use taxonomy to justify selective triage; do not claim full classifier or security certificate.",
            },
        },
        "remaining_experiment_constraints": [
            "SemCodebook white-box expansion cannot run on current js4 because NVIDIA device access is unavailable and PEFT is missing.",
            "Black-box scope remains DeepSeek-only until additional provider keys are supplied.",
            "New CodeDye and ProbeTrace rows are support-only and must not enter the locked main denominators.",
            "No existing result file was overwritten; new files are additive and versioned.",
        ],
        "blockers": blockers,
    }


def write_md(payload: dict[str, Any]) -> None:
    lines = [
        "# Watermark Experiment Deepening Status v2",
        "",
        f"- Gate pass: `{payload['gate_pass']}`",
        f"- Blockers: `{payload['blockers']}`",
        "",
    ]
    for name, item in payload["projects"].items():
        lines.extend(
            [
                f"## {name}",
                "",
                f"- Status: {item['status']}",
                f"- Next action: {item['next_action']}",
                "",
            ]
        )
    lines.extend(["## Constraints", ""])
    lines.extend(f"- {item}" for item in payload["remaining_experiment_constraints"])
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    required = [
        "results/SemCodebook/artifacts/generated/semcodebook_whitebox_next_gpu_queue_v1_20260508.json",
        "results/CodeDye/artifacts/generated/codedye_v4_query_budget_support_postrun_gate_v1_20260508.json",
        "results/ProbeTrace/artifacts/generated/probetrace_commitment_shortcut_challenge_postrun_gate_v1_20260508.json",
        "results/SealAudit/artifacts/generated/sealaudit_v6_failure_taxonomy_audit_v1_20260508.json",
    ]
    missing = [rel for rel in required if not exists(rel)]
    if missing:
        payload = {"schema_version": "watermark_experiment_deepening_status_v2", "date": DATE, "claim_bearing": False, "gate_pass": False, "blockers": [f"missing:{rel}" for rel in missing]}
    else:
        payload = project_status()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_md(payload)
    print(json.dumps({"gate_pass": payload.get("gate_pass"), "blockers": payload.get("blockers")}, ensure_ascii=True))
    return 0 if payload.get("gate_pass") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
