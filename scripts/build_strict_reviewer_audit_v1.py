from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT_JSON = ROOT / f"results/watermark_strict_reviewer_audit_v1_{DATE}.json"
OUT_MD = ROOT / f"results/watermark_strict_reviewer_audit_v1_{DATE}.md"


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def wilson(k: int, n: int) -> dict[str, Any]:
    if n <= 0:
        raise ValueError("n must be positive")
    z = 1.959963984540054
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return {
        "k": k,
        "n": n,
        "rate": phat,
        "ci95_low": max(0.0, center - half),
        "ci95_high": min(1.0, center + half),
        "method": "wilson_score_interval",
    }


def score(value: int, rationale: str) -> dict[str, Any]:
    return {"score_1_to_5": value, "rationale": rationale}


def mean_score(scores: dict[str, dict[str, Any]]) -> float:
    values = [int(v["score_1_to_5"]) for v in scores.values()]
    return round(sum(values) / len(values), 2)


def reviewer_verdict(mean: float, p1_count: int, p2_count: int) -> str:
    if p1_count:
        return "not_bestpaper_ready_p1_blocked"
    if mean >= 4.5 and p2_count == 0:
        return "bestpaper_ready_by_strict_artifact_gate"
    if mean >= 4.0:
        return "strong_submission_but_not_bestpaper_locked"
    return "needs_substantial_revision"


def semcodebook() -> dict[str, Any]:
    suff = load_json("results/SemCodebook/artifacts/generated/semcodebook_whitebox_model_sufficiency_gate_20260505.json")
    effect = load_json("results/SemCodebook/artifacts/generated/semcodebook_whitebox_effect_authenticity_gate_20260505.json")
    ablation = load_json("results/SemCodebook/artifacts/generated/semcodebook_generation_changing_ablation_promotion_gate_20260505.json")
    causal = load_json("results/SemCodebook/artifacts/generated/semcodebook_causal_contribution_gate_v2_20260507.json")
    manifest = load_json("results/SemCodebook/artifacts/generated/semcodebook_whitebox_main_denominator_source_manifest_20260505.json")

    family_scale = effect["whitebox_family_scale_summary"]
    positive_k = 23342
    positive_n = 24000
    negative_k = 0
    negative_n = 48000
    scores = {
        "innovation": score(4, "Structured provenance over AST/CFG/SSA with keyed schedule and ECC is a real mechanism, not just prompting."),
        "method_rigor": score(4, "Fail-closed detector, negative controls, and generation-changing ablation are strong; no-retry natural-generation is correctly excluded."),
        "evidence_workload": score(5, "72,000 white-box records, 10 admitted models, 5 families, and all scale buckets exceed normal main-paper workload."),
        "baseline_control_strength": score(4, "Controls and baseline-role boundaries exist; official-baseline claims must stay scoped to runnable/admitted cells."),
        "attack_negative_control": score(5, "0/48,000 negative hits and 8 attack conditions provide strong attack/control coverage."),
        "statistics": score(4, "Wilson intervals and denominator separation are present; row-level miss taxonomy is still not fully decisive."),
        "reproducibility": score(4, "Hash-bound manifests and scripts exist, but full reproduction depends on large local model/GPU availability."),
        "claim_boundary": score(5, "Current artifacts forbid first-sample/no-retry and provider-general overclaiming."),
    }
    p1 = []
    p2 = [
        "Finish row-level positive-miss taxonomy for all 658 headline misses before using miss-analysis as a main-paper argument.",
        "In the paper, explicitly separate supported structural provenance recovery from unsupported natural first-sample generation.",
    ]
    return {
        "project": "SemCodebook",
        "strict_verdict": reviewer_verdict(mean_score(scores), len(p1), len(p2)),
        "bestpaper_ready": False,
        "bestpaper_ready_reason": "Strongest project, but still requires careful paper claim locking and full miss taxonomy to remove residual reviewer attack surface.",
        "main_claim_allowed": "structured provenance watermark over admitted white-box model cells",
        "forbidden_claims": [
            "universal code watermark",
            "first-sample/no-retry natural-generation guarantee",
            "validator-repair evidence as main result",
            "provider-general claim outside admitted white-box cells",
        ],
        "effect_metrics": {
            "admitted_records": int(family_scale["total_admitted_records"]),
            "admitted_models": int(family_scale["admitted_model_count"]),
            "admitted_families": int(family_scale["admitted_family_count"]),
            "scale_coverage": family_scale["scale_coverage"],
            "positive_recovery": wilson(positive_k, positive_n),
            "negative_control_hits": wilson(negative_k, negative_n),
            "generation_changing_ablation_rows": int(ablation["fresh_result_summary"]["record_count"]),
            "ablation_formal_claim_allowed": bool(causal["formal_causal_claim_allowed"]),
            "source_manifest_rows": len(manifest.get("admitted_cells", manifest.get("records", []))) if isinstance(manifest, dict) else None,
            "helper_compiler_mock_negative_failures": suff["zero_failure_metrics"],
        },
        "overfit_risk": {
            "level": "medium_low",
            "reason": "Large family/scale matrix and negative controls reduce overfit risk; residual risk is mainly overclaiming no-retry or cherry-picking recovery slices.",
            "required_guard": "Keep all misses in denominator and report failure-boundary taxonomy.",
        },
        "scores": scores,
        "mean_score": mean_score(scores),
        "remaining_p1": p1,
        "remaining_p2": p2,
        "next_actions": [
            "Use semcodebook_causal_contribution_gate_v2 only with paired component deltas.",
            "Add miss taxonomy table to appendix and cite it in limitations.",
        ],
    }


def codedye() -> dict[str, Any]:
    low = load_json("results/CodeDye/artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json")
    pos = load_json("results/CodeDye/artifacts/generated/codedye_positive_contamination_control_300_gate_20260505.json")
    neg = load_json("results/CodeDye/artifacts/generated/codedye_negative_control_row_hash_manifest_v2_20260507.json")
    surface = low["effect_surface"]
    signal_k = int(surface["decision_counts"]["contamination_signal_detected"])
    signal_n = int(surface["claim_rows"])
    pos_k = int(pos["detected_at_frozen_0_5_count"])
    pos_n = int(pos["record_count"])
    neg_fp = int(neg["false_positive_count"])
    neg_n = int(neg["row_count"])

    scores = {
        "innovation": score(4, "Curator-side null-audit with transcript/hash retention is a useful protocol contribution."),
        "method_rigor": score(3, "Threshold discipline is good, but 130/300 positive-control misses need stronger causal diagnosis."),
        "evidence_workload": score(3, "300 live rows plus controls is acceptable for scoped DeepSeek-only audit, not yet dominant best-paper scale."),
        "baseline_control_strength": score(4, "Official/control role separation is clear and support rows are excluded from the main denominator."),
        "attack_negative_control": score(4, "0/300 false positives with row hashes is good; stronger positive-control sensitivity is still needed."),
        "statistics": score(4, "CI, FDR-sensitive language, and denominator separation are present."),
        "reproducibility": score(4, "Raw/structured hash discipline and row manifests are strong; live API rerun remains external."),
        "claim_boundary": score(5, "Artifacts correctly forbid high-recall, prevalence, or provider-accusation claims."),
    }
    p1 = [
        "Effect is weak for any detection claim: live yield is 6/300 and positive-control sensitivity is 170/300.",
        "A fresh frozen v3 control/live run is required before any claim upgrade beyond conservative null-audit.",
    ]
    p2 = [
        "Positive-control misses should be split into canary, provenance, chronology, retrieval, budget, and payload buckets.",
    ]
    return {
        "project": "CodeDye",
        "strict_verdict": reviewer_verdict(mean_score(scores), len(p1), len(p2)),
        "bestpaper_ready": False,
        "bestpaper_ready_reason": "Method is defensible as a conservative null-audit, but effect yield is too sparse for best-paper unless the protocol contribution is framed narrowly or v3 improves sensitivity.",
        "main_claim_allowed": "DeepSeek-only curator-side sparse null-audit",
        "forbidden_claims": [
            "high-recall contamination detector",
            "contamination prevalence estimate",
            "provider accusation",
            "support/public rows as part of the 300-row main denominator",
        ],
        "effect_metrics": {
            "live_signal": wilson(signal_k, signal_n),
            "positive_control_sensitivity": wilson(pos_k, pos_n),
            "negative_control_false_positive": wilson(neg_fp, neg_n),
            "support_rows_excluded": int(surface["support_rows_excluded_from_main_denominator"]),
            "missing_payload_or_transcript_hash": int(surface["claim_rows_missing_payload_or_transcript_hash"]),
            "statistics_artifact_positive_count": int(surface["statistics_artifact_boundary"]["statistics_artifact_positive_count"]),
            "final_conservative_signal_count": int(surface["statistics_artifact_boundary"]["final_conservative_signal_count"]),
        },
        "overfit_risk": {
            "level": "medium",
            "reason": "Low live yield protects against false accusation but weak positive-control sensitivity invites concerns that the method is underpowered.",
            "required_guard": "Freeze v3 before rerun; do not tune thresholds on the 300 live outcomes.",
        },
        "scores": scores,
        "mean_score": mean_score(scores),
        "remaining_p1": p1,
        "remaining_p2": p2,
        "next_actions": [
            "Run v3 positive/negative controls under frozen thresholds.",
            "Only if control sensitivity improves without FP inflation, run a fresh DeepSeek live v3 claim surface.",
        ],
    }


def probetrace() -> dict[str, Any]:
    apis = load_json("results/ProbeTrace/artifacts/generated/apis300_live_attribution_evidence.json")
    abstain = load_json("results/ProbeTrace/artifacts/generated/probetrace_abstain_aware_attribution_gate_20260506.json")
    transfer = load_json("results/ProbeTrace/artifacts/generated/student_transfer_live_validation_results.owner_witness_v6_clean_holdout.json")
    package = load_json("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_package_20260507.json")
    scores = {
        "innovation": score(4, "Active-owner attribution with semantic witnesses, decoys, and transfer binding is a strong mechanism."),
        "method_rigor": score(3, "300/300 is impressive but needs multi-owner score vectors to fully defeat leakage/shortcut critiques."),
        "evidence_workload": score(4, "APIS-300, 1,200 controls, HardDecoy, and 900 transfer rows are substantial but still single-owner scoped."),
        "baseline_control_strength": score(4, "Wrong/null/abstain controls exist; multi-owner controls are input-ready but not result-bearing."),
        "attack_negative_control": score(4, "0/1,200 control failures is strong; owner-heldout and task-heldout live outputs are still missing."),
        "statistics": score(4, "CI and task-cluster independence are explicit; threshold-free AUC/margin evidence should be promoted after rerun."),
        "reproducibility": score(4, "Receipts and hashes exist; provider rerun and owner secrets remain operational dependencies."),
        "claim_boundary": score(5, "Current scope is correctly single-active-owner/source-bound and DeepSeek-only."),
    }
    p1 = [
        "Broad multi-owner attribution is not claim-bearing until fresh score-vector outputs exist.",
        "Perfect 300/300 result remains vulnerable to shortcut/leakage critique without multi-owner heldout evidence.",
    ]
    p2 = [
        "Latency/query frontier should be visible in main text, not only appendix.",
    ]
    transfer_rows = int(transfer.get("record_count", transfer.get("validation_record_count", 900)))
    return {
        "project": "ProbeTrace",
        "strict_verdict": reviewer_verdict(mean_score(scores), len(p1), len(p2)),
        "bestpaper_ready": False,
        "bestpaper_ready_reason": "Single-owner claim is strong; best-paper-level generality requires fresh multi-owner live score-vector evidence.",
        "main_claim_allowed": "single-active-owner/source-bound DeepSeek attribution",
        "forbidden_claims": [
            "provider-general attribution",
            "multi-owner attribution from input package alone",
            "student-transfer claim without source-bound receipts",
        ],
        "effect_metrics": {
            "apis_attribution": wilson(300, int(apis["local_task_count"])),
            "false_owner_controls": wilson(0, int(abstain["current_effect_surface"]["negative_control_records"])),
            "transfer_validation": wilson(900, transfer_rows),
            "primary_transfer_independence_unit": "300 task clusters",
            "multi_owner_input_rows": int(package["row_count"]),
            "multi_owner_input_claim_bearing": bool(package["claim_bearing"]),
            "multi_owner_formal_claim_allowed": bool(package["formal_multi_owner_claim_allowed"]),
            "multi_owner_role_counts": package["control_role_counts"],
            "multi_owner_split_counts": package["split_counts"],
        },
        "overfit_risk": {
            "level": "medium_high_until_multi_owner_rerun",
            "reason": "Perfect single-owner results can be attacked as owner leakage or shortcut even with good current controls.",
            "required_guard": "Run the 6,000-row multi-owner package and report true/wrong/null/random owner margins separately.",
        },
        "scores": scores,
        "mean_score": mean_score(scores),
        "remaining_p1": p1,
        "remaining_p2": p2,
        "next_actions": [
            "Execute fresh DeepSeek multi-owner package only after raw/structured transcript hash retention is enabled.",
            "Promote only if per-owner TPR/FPR CI and rank/AUC separation pass.",
        ],
    }


def sealaudit() -> dict[str, Any]:
    surface = load_json("results/SealAudit/artifacts/generated/canonical_claim_surface_results.json")
    frontier = load_json("results/SealAudit/artifacts/generated/sealaudit_coverage_risk_frontier_gate_20260505.json")
    v5 = load_json("results/SealAudit/artifacts/generated/sealaudit_v5_final_evidence_readiness_gate_20260507.json")
    hidden_n = int(surface["claim_bearing_record_count"])
    decisive_k = int(frontier["decision_distribution"]["benign"]) + int(frontier["decision_distribution"]["latent_trojan"])
    needs_review = int(frontier["decision_distribution"]["needs_review"])
    unsafe_pass = int(frontier["unsafe_pass_count"])
    scores = {
        "innovation": score(4, "Watermark-as-security-object audit framing is valuable and well scoped."),
        "method_rigor": score(3, "Explicit abstention is honest, but decisive coverage is too low for a strong utility claim."),
        "evidence_workload": score(4, "320 cases and 960 marker-hidden rows are solid for a scoped DeepSeek audit."),
        "baseline_control_strength": score(4, "Marker-hidden/visible boundaries and controls are explicit."),
        "attack_negative_control": score(4, "Unsafe-pass tracking and marker-hidden stress are strong, but v5 must be final-row claim-bearing."),
        "statistics": score(4, "Coverage-risk CI and unsafe-pass upper bound are explicit."),
        "reproducibility": score(4, "Artifacts and role-based review support exist; final v5 rows remain blocked."),
        "claim_boundary": score(5, "Artifacts forbid safety certificate or automatic classifier claims."),
    }
    p1 = [
        "Decisive coverage is only 81/960; the current result is a selective triage surface, not a strong audit classifier.",
        "v5 final evidence is not claim-bearing yet, so coverage cannot be upgraded.",
    ]
    p2 = [
        "Expert review support should stay role-based and row-confirmation based without implying signatures or identity disclosure.",
    ]
    return {
        "project": "SealAudit",
        "strict_verdict": reviewer_verdict(mean_score(scores), len(p1), len(p2)),
        "bestpaper_ready": False,
        "bestpaper_ready_reason": "The protocol is honest and useful, but coverage is too low until v5 increases decisive routing without unsafe-pass inflation.",
        "main_claim_allowed": "marker-hidden DeepSeek selective audit/triage",
        "forbidden_claims": [
            "security certificate",
            "harmlessness guarantee",
            "automatic latent-trojan classifier",
            "visible-marker diagnostic rows as main evidence",
        ],
        "effect_metrics": {
            "marker_hidden_decisive_coverage": wilson(decisive_k, hidden_n),
            "needs_review_rate": wilson(needs_review, hidden_n),
            "unsafe_pass": wilson(unsafe_pass, hidden_n),
            "case_count": int(surface["main_table_unique_case_count"]),
            "hidden_claim_rows": hidden_n,
            "visible_marker_diagnostic_rows": int(surface["diagnostic_visible_record_count"]),
            "v5_final_evidence_ready": bool(v5["gate_pass"]),
            "v5_blockers": v5.get("blockers", []),
        },
        "overfit_risk": {
            "level": "medium",
            "reason": "High abstention avoids unsafe overclaiming but weakens utility; trying to force labels would create overfit/unsafe-pass risk.",
            "required_guard": "Improve coverage through preregistered v5 conjunction only; preserve hard ambiguity as a valid outcome.",
        },
        "scores": scores,
        "mean_score": mean_score(scores),
        "remaining_p1": p1,
        "remaining_p2": p2,
        "next_actions": [
            "Produce final v5 row-level evidence with the 960 marker-hidden denominator intact.",
            "Report coverage-risk frontier and unsafe-pass upper bound in the main paper.",
        ],
    }


def write_markdown(payload: dict[str, Any]) -> None:
    lines = [
        "# Strict Reviewer Audit v1",
        "",
        "This audit is non-claim-bearing. It evaluates current evidence, claim discipline, and remaining reviewer attack surface.",
        "",
        f"Portfolio verdict: `{payload['portfolio_verdict']}`",
        f"Best-paper ready: `{payload['portfolio_bestpaper_ready']}`",
        "",
    ]
    for project in payload["projects"]:
        lines.extend(
            [
                f"## {project['project']}",
                "",
                f"- Verdict: `{project['strict_verdict']}`",
                f"- Mean strict score: `{project['mean_score']}`",
                f"- Main claim allowed: {project['main_claim_allowed']}",
                f"- Best-paper ready: `{project['bestpaper_ready']}`",
                f"- Reason: {project['bestpaper_ready_reason']}",
                "",
                "Remaining P1:",
            ]
        )
        if project["remaining_p1"]:
            lines.extend(f"- {item}" for item in project["remaining_p1"])
        else:
            lines.append("- None.")
        lines.append("")
        lines.append("Remaining P2:")
        if project["remaining_p2"]:
            lines.extend(f"- {item}" for item in project["remaining_p2"])
        else:
            lines.append("- None.")
        lines.append("")
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    projects = [semcodebook(), codedye(), probetrace(), sealaudit()]
    p1_total = sum(len(project["remaining_p1"]) for project in projects)
    p2_total = sum(len(project["remaining_p2"]) for project in projects)
    payload = {
        "schema_version": "watermark_strict_reviewer_audit_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "portfolio_bestpaper_ready": False,
        "portfolio_verdict": reviewer_verdict(
            round(sum(project["mean_score"] for project in projects) / len(projects), 2),
            p1_total,
            p2_total,
        ),
        "portfolio_mean_score": round(sum(project["mean_score"] for project in projects) / len(projects), 2),
        "remaining_p1_count": p1_total,
        "remaining_p2_count": p2_total,
        "formal_full_experiment_allowed": False,
        "formal_full_experiment_rule": "Do not run or promote full canonical claim experiments until each project has zero P1/P2 under this audit and project-specific pre-run gates pass.",
        "projects": projects,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(payload)
    print(f"[OK] Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"[OK] Wrote {OUT_MD.relative_to(ROOT)}")
    print(f"[OK] Portfolio verdict: {payload['portfolio_verdict']} with P1={p1_total}, P2={p2_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
