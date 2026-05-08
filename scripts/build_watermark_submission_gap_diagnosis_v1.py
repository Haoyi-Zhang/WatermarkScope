from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "results/watermark_submission_gap_diagnosis_v1_20260508.json"
OUT_MD = ROOT / "results/watermark_submission_gap_diagnosis_v1_20260508.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(rel: str) -> dict[str, Any]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def project_from_audit(name: str) -> dict[str, Any]:
    audit = load("results/watermark_strict_reviewer_audit_v8_20260507.json")
    return next(project for project in audit["projects"] if project["project"] == name)


def main() -> int:
    if OUT_JSON.exists() or OUT_MD.exists():
        raise FileExistsError("refusing_to_overwrite_submission_gap_diagnosis_v1")

    sem = load("results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v1_20260507.json")
    codedye = load("results/CodeDye/artifacts/generated/codedye_final_claim_lock_v2_20260507.json")
    probe = load("results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v2_20260507.json")
    seal = load("results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v2_20260507.json")
    audit = load("results/watermark_strict_reviewer_audit_v8_20260507.json")

    projects = [
        {
            "project": "SemCodebook",
            "strict_score": project_from_audit("SemCodebook")["mean_score"],
            "current_status": "strong_submission_ready_for_scoped_whitebox_claim",
            "locked_claim": project_from_audit("SemCodebook")["main_claim_allowed"],
            "effect_snapshot": sem["locked_effect_surface"],
            "best_paper_gap": [
                {
                    "axis": "method_theory",
                    "severity": "medium",
                    "issue": "The mechanism is strong, but the paper must make AST/CFG/SSA/ECC/keyed schedule read as a compact theory of structured provenance rather than an artifact-heavy system.",
                    "fix": "Add formal definitions, recovery sufficient conditions, and component necessity lemmas tied directly to the generation-changing ablation.",
                    "requires_new_experiment": False,
                },
                {
                    "axis": "baseline_positioning",
                    "severity": "medium",
                    "issue": "Reviewers may question whether official watermark baselines are fully comparable to structured provenance under semantic rewrite.",
                    "fix": "Add a baseline-role table and a fairness paragraph that separates runnable official baselines, citation-only baselines, and non-equivalent comparators.",
                    "requires_new_experiment": False,
                },
                {
                    "axis": "external_validity",
                    "severity": "low_medium",
                    "issue": "72k records cover model/family/scale breadth, but real-repo workflow examples would make the claim more memorable.",
                    "fix": "Add one non-main-table real-repo walkthrough with compile/test witness and failure-boundary discussion.",
                    "requires_new_experiment": "optional_support_only",
                },
            ],
            "next_execution": "Do not rerun whitebox until paper/theory tables are aligned; if adding evidence, run support-only real-repo witness, not another broad sweep.",
        },
        {
            "project": "CodeDye",
            "strict_score": project_from_audit("CodeDye")["mean_score"],
            "current_status": "strong_submission_ready_only_for_sparse_null_audit",
            "locked_claim": codedye["allowed_current_claim"],
            "effect_snapshot": codedye["locked_effect_surface"],
            "best_paper_gap": [
                {
                    "axis": "effect_size",
                    "severity": "high_for_award_low_for_scoped_acceptance",
                    "issue": "Main DeepSeek signal is sparse: 4/300. This is acceptable for a conservative null-audit paper but weak for a best-paper-style detection narrative.",
                    "fix": "Frame sparse yield as the point of a low-false-positive audit protocol; add utility and query-budget curves instead of inflating recall.",
                    "requires_new_experiment": "optional_deepseek_support",
                },
                {
                    "axis": "positive_control_sensitivity",
                    "severity": "medium",
                    "issue": "Positive-control sensitivity is 170/300, with 130 witness-ablation misses. Reviewers will ask whether the protocol misses known contamination too often.",
                    "fix": "Add miss taxonomy examples and a frozen v4 evidence-enrichment design; rerun only if thresholds are preregistered before execution.",
                    "requires_new_experiment": "only_if_v4_protocol_frozen_first",
                },
                {
                    "axis": "claim_boundary",
                    "severity": "medium",
                    "issue": "The paper can be rejected if it sounds like a provider contamination accusation or high-recall detector.",
                    "fix": "Keep the title/abstract as curator-side null-audit; report non-signals as non-accusatory outcomes, not absence proof.",
                    "requires_new_experiment": False,
                },
            ],
            "next_execution": "No immediate rerun. First write the sparse-audit narrative and tables; then decide whether a preregistered v4 support run is worth the API cost.",
        },
        {
            "project": "ProbeTrace",
            "strict_score": project_from_audit("ProbeTrace")["mean_score"],
            "current_status": "closest_to_best_paper_ready_for_scoped_deepseek_claim",
            "locked_claim": probe["allowed_current_claim"],
            "effect_snapshot": probe["locked_effect_surface"],
            "best_paper_gap": [
                {
                    "axis": "too_perfect_result_risk",
                    "severity": "medium_high",
                    "issue": "AUC=1.0, APIS=300/300, transfer=900/900 are strong but invite leakage/shortcut skepticism.",
                    "fix": "Make anti-leakage evidence prominent: hidden owner IDs, wrong/null/random/same-provider controls, owner/task-heldout splits, and near-boundary examples.",
                    "requires_new_experiment": False,
                },
                {
                    "axis": "provider_scope",
                    "severity": "medium_for_best_paper",
                    "issue": "The locked claim is DeepSeek-only. This is acceptable for a scoped paper but weaker than a provider-general award narrative.",
                    "fix": "Do not claim provider-general. If future keys are available, prioritize GPT/Claude replication for this project first.",
                    "requires_new_experiment": "future_non_deepseek_key",
                },
                {
                    "axis": "cost_usability",
                    "severity": "low_medium",
                    "issue": "Latency/query overhead can become a practical objection even when attribution is accurate.",
                    "fix": "Move latency/query frontier into main results instead of appendix.",
                    "requires_new_experiment": False,
                },
            ],
            "next_execution": "No new DeepSeek run needed. Next work is writing: anti-leakage section, near-boundary rows, and cost frontier in the main text.",
        },
        {
            "project": "SealAudit",
            "strict_score": project_from_audit("SealAudit")["mean_score"],
            "current_status": "strong_submission_ready_only_for_selective_triage",
            "locked_claim": seal["allowed_current_claim"],
            "effect_snapshot": seal["locked_effect_surface"],
            "best_paper_gap": [
                {
                    "axis": "coverage",
                    "severity": "medium_high",
                    "issue": "Decisive coverage is 320/960. This is a selective triage result, not a full classifier.",
                    "fix": "Make coverage-risk frontier the core contribution; explicitly treat retained ambiguity as safety-preserving abstention.",
                    "requires_new_experiment": False,
                },
                {
                    "axis": "human_support_boundary",
                    "severity": "medium",
                    "issue": "Expert review can help credibility but becomes a liability if described as signed/named gold labels.",
                    "fix": "Use only anonymous role-based support and row-level packet confirmation wording.",
                    "requires_new_experiment": False,
                },
                {
                    "axis": "security_overclaim",
                    "severity": "high_if_written_wrong",
                    "issue": "Reviewers will reject any harmlessness guarantee or security certificate claim.",
                    "fix": "Write watermark-as-security-object audit/triage, not automatic safety classification.",
                    "requires_new_experiment": False,
                },
            ],
            "next_execution": "No new DeepSeek run needed. Next work is paper framing: coverage-risk frontier, unsafe-pass bound, and failure taxonomy.",
        },
    ]

    payload = {
        "schema_version": "watermark_submission_gap_diagnosis_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "source_audit": "results/watermark_strict_reviewer_audit_v8_20260507.json",
        "portfolio_current_state": {
            "verdict": audit["portfolio_verdict"],
            "mean_score": audit["portfolio_mean_score"],
            "remaining_p1": audit["remaining_p1_count"],
            "remaining_p2": audit["remaining_p2_count"],
            "formal_full_experiment_allowed_for_locked_scopes": audit["formal_full_experiment_allowed"],
        },
        "execution_policy": {
            "do_not_rerun_blindly": True,
            "whitebox_minimal_rerun_note": "SemCodebook already exceeds one-model minimal run; any new run should be support-only real-repo witness unless a new formal claim is introduced.",
            "blackbox_minimal_rerun_note": "CodeDye/ProbeTrace/SealAudit already have DeepSeek-only locked claims; do not spend API on duplicate DeepSeek runs without a frozen new protocol.",
            "optimization_priority": [
                "paper_claim_alignment",
                "main_table_and_failure_analysis",
                "anonymous_repro_package",
                "optional support-only real-repo SemCodebook witness",
                "future non-DeepSeek provider replication if keys are available",
            ],
        },
        "projects": projects,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Watermark Submission Gap Diagnosis v1",
        "",
        f"Portfolio: `{audit['portfolio_verdict']}`; score `{audit['portfolio_mean_score']}/5`; P1/P2 `{audit['remaining_p1_count']}/{audit['remaining_p2_count']}`.",
        "",
        "This is a non-claim-bearing planning artifact. It distinguishes scoped gate readiness from best-paper-award competitiveness.",
        "",
    ]
    for project in projects:
        lines.extend(
            [
                f"## {project['project']}",
                f"- Strict score: `{project['strict_score']}/5`",
                f"- Current status: `{project['current_status']}`",
                f"- Locked claim: {project['locked_claim']}",
                f"- Next execution: {project['next_execution']}",
                "",
                "Best-paper gaps:",
            ]
        )
        for gap in project["best_paper_gap"]:
            lines.append(f"- `{gap['axis']}` ({gap['severity']}): {gap['issue']} Fix: {gap['fix']}")
        lines.append("")
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"[OK] Wrote {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
