from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT_JSON = ROOT / f"results/watermark_strict_reviewer_audit_v2_{DATE}.json"
OUT_MD = ROOT / f"results/watermark_strict_reviewer_audit_v2_{DATE}.md"


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
    misses = load_json("results/SemCodebook/artifacts/generated/semcodebook_row_level_miss_attribution_v2_20260507.json")
    family_scale = effect["whitebox_family_scale_summary"]
    scores = {
        "innovation": score(4, "Structured AST/CFG/SSA provenance with keyed schedule and ECC is a real mechanism."),
        "method_rigor": score(5, "Fail-closed detector, clean controls, generation-changing ablation, and row-level miss attribution now close the main rigor gap."),
        "evidence_workload": score(5, "72,000 white-box records, 10 admitted models, 5 families, all scale buckets, and 43,200 ablation rows."),
        "baseline_control_strength": score(4, "Baseline/control role boundaries are explicit and no support-only cell is promoted."),
        "attack_negative_control": score(5, "0/48,000 negative hits plus 8 attack conditions provide strong coverage."),
        "statistics": score(4, "CI and denominators are present; paper must still show component deltas rather than only gates."),
        "reproducibility": score(4, "Hash-bound manifests and scripts exist; full rerun remains GPU/model dependent."),
        "claim_boundary": score(5, "No-retry and provider-general claims are explicitly forbidden."),
    }
    p1: list[str] = []
    p2 = [
        "Paper text must foreground that DeepSeek-Coder-6.7B accounts for the row-level positive misses rather than hide it.",
        "Component contribution table should be shown with paired deltas in the main paper or appendix.",
    ]
    return {
        "project": "SemCodebook",
        "strict_verdict": reviewer_verdict(mean_score(scores), len(p1), len(p2)),
        "bestpaper_ready": False,
        "bestpaper_ready_reason": "Evidence is strong enough for a best-paper-level scoped white-box claim, but final paper wording and paired-delta presentation still need lock-in.",
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
            "positive_recovery": wilson(23342, 24000),
            "negative_control_hits": wilson(0, 48000),
            "generation_changing_ablation_rows": int(ablation["fresh_result_summary"]["record_count"]),
            "ablation_formal_claim_allowed": bool(causal["formal_causal_claim_allowed"]),
            "row_level_miss_taxonomy_gate_pass": bool(misses["gate_pass"]),
            "row_level_positive_misses": int(misses["positive_miss_count"]),
            "row_level_miss_bucket_counts": misses["miss_bucket_counts"],
            "row_level_miss_by_model": misses["miss_by_model"],
            "helper_compiler_mock_negative_failures": suff["zero_failure_metrics"],
        },
        "overfit_risk": {
            "level": "low_if_claims_remain_scoped",
            "reason": "Family/scale breadth, negative controls, ablations, and miss taxonomy reduce overfit risk; residual risk is paper overclaiming.",
            "required_guard": "Keep no-retry and natural-generation boundaries explicit.",
        },
        "scores": scores,
        "mean_score": mean_score(scores),
        "remaining_p1": p1,
        "remaining_p2": p2,
    }


def codedye() -> dict[str, Any]:
    low = load_json("results/CodeDye/artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json")
    pos_tax = load_json("results/CodeDye/artifacts/generated/codedye_positive_miss_taxonomy_v2_20260507.json")
    neg = load_json("results/CodeDye/artifacts/generated/codedye_negative_control_row_hash_manifest_v2_20260507.json")
    surface = low["effect_surface"]
    scores = {
        "innovation": score(4, "Curator-side null-audit with transcript/hash retention is useful and honestly scoped."),
        "method_rigor": score(4, "Positive-control misses now have a row-level taxonomy; effect remains underpowered for detection."),
        "evidence_workload": score(3, "300 live rows plus controls is acceptable for scoped null-audit, not yet best-paper scale/effect."),
        "baseline_control_strength": score(4, "Official/control boundaries and support-row exclusions are clean."),
        "attack_negative_control": score(4, "0/300 false positives with row hashes is strong."),
        "statistics": score(4, "CI, threshold discipline, and denominator separation are explicit."),
        "reproducibility": score(4, "Raw/structured hash discipline and row manifests are strong; API rerun remains external."),
        "claim_boundary": score(5, "High-recall, prevalence, and provider-accusation claims are forbidden."),
    }
    p1 = [
        "Effect is still too weak for any detection claim: live yield is 6/300 and positive-control sensitivity is 170/300.",
        "A fresh frozen v3 control/live run is required before any claim upgrade beyond conservative null-audit.",
    ]
    p2 = [
        "If v3 does not improve sensitivity, the paper must explicitly argue sparse-audit utility rather than detection power.",
    ]
    return {
        "project": "CodeDye",
        "strict_verdict": reviewer_verdict(mean_score(scores), len(p1), len(p2)),
        "bestpaper_ready": False,
        "bestpaper_ready_reason": "The protocol is clean, but current effect is weak; best-paper case requires v3 sensitivity improvement or an unusually compelling sparse-audit framing.",
        "main_claim_allowed": "DeepSeek-only curator-side sparse null-audit",
        "forbidden_claims": [
            "high-recall contamination detector",
            "contamination prevalence estimate",
            "provider accusation",
            "support/public rows as part of the 300-row main denominator",
        ],
        "effect_metrics": {
            "live_signal": wilson(int(surface["decision_counts"]["contamination_signal_detected"]), int(surface["claim_rows"])),
            "positive_control_sensitivity": wilson(int(pos_tax["positive_control_detected"]), int(pos_tax["positive_control_denominator"])),
            "positive_control_misses": int(pos_tax["positive_control_missed"]),
            "positive_miss_bucket_counts": pos_tax["miss_bucket_counts"],
            "negative_control_false_positive": wilson(int(neg["false_positive_count"]), int(neg["row_count"])),
            "support_rows_excluded": int(surface["support_rows_excluded_from_main_denominator"]),
            "missing_payload_or_transcript_hash": int(surface["claim_rows_missing_payload_or_transcript_hash"]),
        },
        "overfit_risk": {
            "level": "medium",
            "reason": "Frozen threshold discipline is good; the risk is optimizing v3 to the known positives rather than improving protocol invariants.",
            "required_guard": "Freeze v3 thresholds and report all positive-control misses.",
        },
        "scores": scores,
        "mean_score": mean_score(scores),
        "remaining_p1": p1,
        "remaining_p2": p2,
    }


def probetrace() -> dict[str, Any]:
    abstain = load_json("results/ProbeTrace/artifacts/generated/probetrace_abstain_aware_attribution_gate_20260506.json")
    package = load_json("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_package_20260507.json")
    scores = {
        "innovation": score(4, "Active-owner attribution with semantic witnesses, decoys, and transfer binding is strong."),
        "method_rigor": score(3, "Perfect single-owner results still need multi-owner score vectors to remove leakage/shortcut concerns."),
        "evidence_workload": score(4, "300 APIS, 1,200 controls, 900 transfer rows, and a 6,000-row multi-owner input package."),
        "baseline_control_strength": score(4, "Wrong/null/abstain controls exist; multi-owner controls are input-ready but not result-bearing."),
        "attack_negative_control": score(4, "0/1,200 control failures is strong, but owner/task-heldout live outputs are missing."),
        "statistics": score(4, "CI and task-cluster independence are explicit; rank/AUC awaits multi-owner outputs."),
        "reproducibility": score(4, "Receipts and hashes exist; provider rerun and owner secrets remain operational dependencies."),
        "claim_boundary": score(5, "Scope is correctly single-active-owner/source-bound and DeepSeek-only."),
    }
    p1 = [
        "Broad multi-owner attribution is not claim-bearing until fresh score-vector outputs exist.",
        "Perfect 300/300 result remains vulnerable to shortcut/leakage critique without multi-owner heldout evidence.",
    ]
    p2 = [
        "Latency/query frontier should be visible in main text.",
    ]
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
            "apis_attribution": wilson(300, 300),
            "false_owner_controls": wilson(0, int(abstain["current_effect_surface"]["negative_control_records"])),
            "transfer_validation": wilson(900, 900),
            "primary_transfer_independence_unit": "300 task clusters",
            "multi_owner_input_rows": int(package["row_count"]),
            "multi_owner_input_claim_bearing": bool(package["claim_bearing"]),
            "multi_owner_formal_claim_allowed": bool(package["formal_multi_owner_claim_allowed"]),
            "multi_owner_role_counts": package["control_role_counts"],
            "multi_owner_split_counts": package["split_counts"],
        },
        "overfit_risk": {
            "level": "medium_high_until_multi_owner_rerun",
            "reason": "Perfect single-owner result can be attacked as owner leakage or shortcut.",
            "required_guard": "Run the 6,000-row multi-owner package and report true/wrong/null/random owner margins separately.",
        },
        "scores": scores,
        "mean_score": mean_score(scores),
        "remaining_p1": p1,
        "remaining_p2": p2,
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
        "innovation": score(4, "Watermark-as-security-object audit framing is valuable and scoped."),
        "method_rigor": score(3, "Explicit abstention is honest, but decisive coverage is low."),
        "evidence_workload": score(4, "320 cases and 960 marker-hidden rows are solid."),
        "baseline_control_strength": score(4, "Marker-hidden/visible boundaries and controls are explicit."),
        "attack_negative_control": score(4, "Unsafe-pass tracking and marker-hidden stress are strong; v5 must be final-row claim-bearing."),
        "statistics": score(4, "Coverage-risk CI and unsafe-pass upper bound are explicit."),
        "reproducibility": score(4, "Artifacts and role-based review support exist; final v5 rows remain blocked."),
        "claim_boundary": score(5, "Safety-certificate and automatic-classifier claims are forbidden."),
    }
    p1 = [
        "Decisive coverage is only 81/960; current result is selective triage, not a strong audit classifier.",
        "v5 final evidence is not claim-bearing yet, so coverage cannot be upgraded.",
    ]
    p2 = [
        "Expert review support must remain role-based and row-confirmation based.",
    ]
    return {
        "project": "SealAudit",
        "strict_verdict": reviewer_verdict(mean_score(scores), len(p1), len(p2)),
        "bestpaper_ready": False,
        "bestpaper_ready_reason": "Protocol is honest and useful, but coverage is too low until v5 increases decisive routing without unsafe-pass inflation.",
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
            "reason": "Forcing labels would overfit and inflate unsafe-pass risk; abstention must remain legitimate.",
            "required_guard": "Improve coverage only through preregistered v5 conjunction.",
        },
        "scores": scores,
        "mean_score": mean_score(scores),
        "remaining_p1": p1,
        "remaining_p2": p2,
    }


def write_markdown(payload: dict[str, Any]) -> None:
    lines = [
        "# Strict Reviewer Audit v2",
        "",
        "This audit is non-claim-bearing and supersedes v1 for planning. It does not overwrite any result artifact.",
        "",
        f"Portfolio verdict: `{payload['portfolio_verdict']}`",
        f"Best-paper ready: `{payload['portfolio_bestpaper_ready']}`",
        f"Remaining P1/P2: `{payload['remaining_p1_count']}` / `{payload['remaining_p2_count']}`",
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
                f"- Reason: {project['bestpaper_ready_reason']}",
                "",
                "P1:",
            ]
        )
        lines.extend(f"- {item}" for item in project["remaining_p1"]) if project["remaining_p1"] else lines.append("- None.")
        lines.append("")
        lines.append("P2:")
        lines.extend(f"- {item}" for item in project["remaining_p2"]) if project["remaining_p2"] else lines.append("- None.")
        lines.append("")
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    projects = [semcodebook(), codedye(), probetrace(), sealaudit()]
    p1_total = sum(len(project["remaining_p1"]) for project in projects)
    p2_total = sum(len(project["remaining_p2"]) for project in projects)
    mean = round(sum(project["mean_score"] for project in projects) / len(projects), 2)
    payload = {
        "schema_version": "watermark_strict_reviewer_audit_v2",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "supersedes": "results/watermark_strict_reviewer_audit_v1_20260507.json",
        "portfolio_bestpaper_ready": False,
        "portfolio_verdict": reviewer_verdict(mean, p1_total, p2_total),
        "portfolio_mean_score": mean,
        "remaining_p1_count": p1_total,
        "remaining_p2_count": p2_total,
        "formal_full_experiment_allowed": False,
        "formal_full_experiment_rule": "Full claim experiments require zero P1/P2 and project-specific pre-run gates.",
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
