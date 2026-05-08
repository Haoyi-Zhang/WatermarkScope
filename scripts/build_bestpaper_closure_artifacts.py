from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def write_json(rel: str, payload: Any) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_md(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def wilson(k: int, n: int) -> dict[str, float | int | str]:
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
        "low": max(0.0, center - half),
        "high": min(1.0, center + half),
        "method": "wilson",
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def gap(priority: str, area: str, issue: str, closure: str, artifact: str, status: str = "planned") -> dict[str, str]:
    return {
        "priority": priority,
        "area": area,
        "issue": issue,
        "closure_action": closure,
        "closure_artifact": artifact,
        "status": status,
    }


def score(value: int, rationale: str) -> dict[str, Any]:
    return {"score_1_to_5": value, "rationale": rationale}


def semcodebook() -> dict[str, Any]:
    effect = load_json("results/SemCodebook/artifacts/generated/semcodebook_whitebox_effect_authenticity_gate_20260505.json")
    summary = effect["effect_summary"]
    positives = int(summary["positive_carrier_records"])
    detected = int(summary["clean_positive_detected"])
    missed = positives - detected
    total_pos = 24000
    total_detected = 23342
    total_missed = total_pos - total_detected
    family = effect["whitebox_family_scale_summary"]
    failure = summary["failure_boundary_counts"]

    failure_taxonomy = {
        "schema_version": "semcodebook_failure_taxonomy_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "source_artifact": "semcodebook_whitebox_effect_authenticity_gate_20260505.json",
        "headline_positive_denominator": total_pos,
        "headline_positive_recovered": total_detected,
        "headline_positive_missed": total_missed,
        "clean_slice_positive_denominator": positives,
        "clean_slice_positive_recovered": detected,
        "clean_slice_positive_missed": missed,
        "taxonomy_policy": "Failures are preserved as boundary evidence and must not be deleted, relabeled, or excluded from the denominator.",
        "known_failure_sources": {
            "detector_abstain_or_reject_on_positive": failure.get("detector_abstain_or_reject_on_positive", 0),
            "attack_not_applicable_or_unchanged": failure.get("attack_not_applicable_or_unchanged", 0),
            "schedule_commitment_mismatch": failure.get("schedule_commitment_mismatch", 0),
            "semantic_or_compile_failure": failure.get("semantic_or_compile_failure", 0),
            "generation_failure": failure.get("generation_failure", 0),
            "mock_or_fallback_generation": failure.get("mock_or_fallback_generation", 0),
            "unattributed_headline_positive_misses_requiring_row_level_join": total_missed,
        },
        "next_required_closure": [
            "Join row-level detector outcomes by model, language, family, attack, and carrier family.",
            "Map every missed positive into exactly one primary failure bucket.",
            "Report miss rates with Wilson intervals; do not tune thresholds after seeing the taxonomy.",
        ],
    }
    write_json(f"results/SemCodebook/artifacts/generated/semcodebook_failure_taxonomy_v1_{DATE}.json", failure_taxonomy)

    theorem = r"""# SemCodebook Structural Recoverability Theorem v1

This artifact formalizes the claim that SemCodebook supports structured provenance recovery inside admitted white-box cells, not universal natural-generation watermarking.

Let a generated program be \(x\), and let the structural carrier set be
\[
C(x)=C_{AST}(x)\cup C_{CFG}(x)\cup C_{SSA}(x).
\]
For task identifier \(t\), secret key \(K\), and carrier index \(i\), slots are scheduled by
\[
s_i=\mathrm{HMAC}_K(t\Vert i)\bmod |C(x)|.
\]
Let \(\gamma(x)\) be carrier coverage, \(\rho(x,a)\) be the retained carrier fraction after attack \(a\), and \(d_{ECC}\) be the maximum correctable erasure distance. A sufficient condition for recovery is
\[
\gamma(x)\rho(x,a) \ge 1-d_{ECC}.
\]
The detector must abstain when the commitment check fails, when the retained carriers fall below the ECC boundary, or when the parser/compiler witness is unavailable. Therefore, false positive control is enforced by keyed schedule agreement and commitment consistency rather than by lowering thresholds.

Current evidence:

- 72,000 admitted white-box records.
- 23,342/24,000 positive recoveries.
- 0/48,000 negative-control hits.
- 43,200 generation-changing ablation rows.

This theorem is a claim-boundary artifact. It does not promote first-sample/no-retry generation, validator repair, or cells outside the admitted model/source matrix.
"""
    write_md(f"results/SemCodebook/artifacts/generated/semcodebook_structural_recoverability_theorem_v1_{DATE}.md", theorem)

    causal_gate = {
        "schema_version": "semcodebook_causal_contribution_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "formal_causal_claim_allowed": False,
        "source_artifact": "semcodebook_generation_changing_ablation_promotion_gate_20260505.json",
        "required_comparisons": [
            "full_vs_ast_only",
            "full_vs_cfg_only",
            "full_vs_ssa_only",
            "full_vs_ecc_off",
            "full_vs_unkeyed_schedule",
            "full_vs_drop_ast",
            "full_vs_drop_cfg",
            "full_vs_drop_ssa",
        ],
        "required_slices": ["model_family", "model_scale", "language", "attack_condition"],
        "required_statistics": ["paired_delta", "bootstrap_ci95", "negative_control_fp_bound"],
        "promotion_policy": "A component may be claimed causal only after paired CI is computed without changing denominators or thresholds.",
        "current_status": "prerun_analysis_contract_created",
    }
    write_json(f"results/SemCodebook/artifacts/generated/semcodebook_causal_contribution_gate_v1_{DATE}.json", causal_gate)

    return {
        "project": "SemCodebook",
        "current_state": {
            "whitebox_records": family["total_admitted_records"],
            "admitted_models": family["admitted_model_count"],
            "admitted_families": family["admitted_family_count"],
            "scale_coverage": family["scale_coverage"],
            "positive_recovery": f"{total_detected}/{total_pos}",
            "negative_hits": "0/48000",
            "ablation_rows": 43200,
        },
        "scores": {
            "innovation": score(4, "Structured AST/CFG/SSA provenance with keyed scheduling and ECC is strong, but the theorem must be linked more directly to per-carrier row outcomes."),
            "method_rigor": score(4, "Negative controls and ablations are strong; row-level failure attribution remains the main rigor gap."),
            "evidence_scale": score(5, "72,000 rows, 10 admitted models, 5 families, and full scale buckets are best-paper scale."),
            "baseline_control_strength": score(4, "Official baseline bridge exists; reviewer-facing role table should remain explicit."),
            "attack_negative_control_coverage": score(5, "48,000 negative controls with zero hits and multiple attack conditions."),
            "statistical_trust": score(4, "CI and denominators exist; missed-positive taxonomy needs row-level CI."),
            "reproducibility": score(4, "Artifacts and scripts are present; full rerun remains GPU/model dependent."),
            "claim_discipline": score(5, "No universal or no-retry claim is made."),
        },
        "gaps": [
            gap("P1", "causal_method", "Ablation evidence exists but is not yet distilled into a decisive per-component causal table.", "Build component contribution table with paired CI and family/language splits.", f"semcodebook_causal_contribution_gate_v1_{DATE}.json"),
            gap("P1", "failure_boundary", "658 headline positive misses need row-level attribution.", "Join row outcomes and assign every miss to one primary failure bucket.", f"semcodebook_failure_taxonomy_v1_{DATE}.json", "partial_artifact_created"),
            gap("P2", "theory", "Recoverability condition is implicit in current docs.", "Publish structural recoverability theorem and connect variables to measured artifacts.", f"semcodebook_structural_recoverability_theorem_v1_{DATE}.md", "artifact_created"),
        ],
        "claim_upgrade_allowed": False,
        "next_experiment_allowed": "Only after row-level miss taxonomy and causal contribution gate pass.",
    }


def codedye() -> dict[str, Any]:
    low = load_json("results/CodeDye/artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json")
    surface = low["effect_surface"]
    misses = 300 - int(surface["positive_control_detected_at_frozen_threshold"])
    miss_taxonomy = {
        "schema_version": "codedye_positive_miss_taxonomy_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "source_artifact": "codedye_low_signal_claim_boundary_gate_20260505.json",
        "positive_control_denominator": 300,
        "positive_control_detected": int(surface["positive_control_detected_at_frozen_threshold"]),
        "positive_control_missed": misses,
        "miss_taxonomy_status": "requires_row_level_join",
        "provisional_failure_buckets": [
            "canary_absent_or_destroyed",
            "provenance_margin_below_frozen_threshold",
            "chronology_not_retained",
            "retrieval_confound_discounted",
            "query_budget_insufficient",
            "structured_payload_incomplete",
        ],
        "closure_policy": "Do not lower thresholds after seeing misses; v3 must be frozen before any new claim-bearing rerun.",
    }
    write_json(f"results/CodeDye/artifacts/generated/codedye_positive_miss_taxonomy_v1_{DATE}.json", miss_taxonomy)

    v3 = {
        "schema_version": "codedye_v3_protocol_freeze_gate",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "frozen": True,
        "formal_live_claim_allowed": False,
        "purpose": "Preregister the next CodeDye protocol before any new DeepSeek claim-bearing rerun.",
        "evidence_conjunction": [
            "raw_provider_transcript_hash_present",
            "structured_payload_hash_present",
            "prompt_hash_present",
            "task_hash_present",
            "canary_margin_above_frozen_threshold",
            "provenance_margin_above_frozen_threshold",
            "chronology_consistency_pass",
            "retrieval_confound_discount_below_rejection_limit",
            "query_budget_recorded",
        ],
        "threshold_policy": "Thresholds are frozen before rerun and cannot be adjusted using live 300-row outcomes.",
        "claim_policy": "If sensitivity remains moderate, claim remains curator-side null-audit rather than high-recall detection.",
        "required_postrun_gates": [
            f"codedye_v3_positive_negative_control_gate_{DATE}.json",
            f"codedye_v3_live_claim_boundary_gate_{DATE}.json",
            f"codedye_v3_support_exclusion_gate_{DATE}.json",
        ],
    }
    write_json(f"results/CodeDye/artifacts/generated/codedye_v3_protocol_freeze_gate_{DATE}.json", v3)

    utility = {
        "schema_version": "codedye_null_audit_utility_framework_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "source_artifact": "codedye_low_signal_claim_boundary_gate_20260505.json",
        "metrics": {
            "live_audit_yield": wilson(int(surface["decision_counts"]["contamination_signal_detected"]), int(surface["claim_rows"])),
            "known_control_sensitivity": surface["positive_control_sensitivity_wilson95"],
            "negative_control_fp_upper_bound": surface["negative_control_false_positive_wilson95"],
            "support_exclusion_count": int(surface["support_rows_excluded_from_main_denominator"]),
            "payload_hash_completeness": {
                "missing_payload_or_transcript_hash": int(surface["claim_rows_missing_payload_or_transcript_hash"]),
                "denominator": int(surface["claim_rows"]),
            },
        },
        "interpretation": "Utility is measured as evidence-preserving null-audit value, not as contamination detection accuracy.",
        "bestpaper_gap": "Sparse yield is acceptable only if the paper emphasizes audit protocol value and improves or explains known-control misses.",
    }
    write_json(f"results/CodeDye/artifacts/generated/codedye_null_audit_utility_framework_v1_{DATE}.json", utility)

    return {
        "project": "CodeDye",
        "current_state": {
            "deepseek_live_rows": surface["claim_rows"],
            "signals": surface["decision_counts"]["contamination_signal_detected"],
            "signal_rate": surface["final_signal_wilson95"]["rate"],
            "positive_controls": f"{surface['positive_control_detected_at_frozen_threshold']}/300",
            "negative_controls": "0/300",
            "support_rows_excluded": surface["support_rows_excluded_from_main_denominator"],
        },
        "scores": {
            "innovation": score(4, "Evidence-preserving null-audit framing is defensible and useful."),
            "method_rigor": score(3, "Protocol discipline is good, but positive-control misses need row-level diagnosis."),
            "evidence_scale": score(3, "300 live rows plus controls is acceptable but not dominant for best-paper unless protocol contribution is emphasized."),
            "baseline_control_strength": score(4, "Controls and official baseline direction are documented."),
            "attack_negative_control_coverage": score(4, "Negative controls are clean; attack matrix must remain joined to claim records."),
            "statistical_trust": score(4, "CI and support exclusion are explicit."),
            "reproducibility": score(4, "Hash retention and manifests are strong; provider rerun remains API-dependent."),
            "claim_discipline": score(5, "The package correctly avoids contamination/prevalence/high-recall claims."),
        },
        "gaps": [
            gap("P1", "effect", "6/300 live signals and 170/300 positive controls are too weak for detection claims.", "Improve known-control sensitivity through preregistered v3 dual-evidence protocol, not threshold tuning.", f"codedye_v3_protocol_freeze_gate_{DATE}.json", "artifact_created"),
            gap("P1", "failure_analysis", f"{misses} positive-control misses lack row-level taxonomy.", "Assign misses to canary/provenance/chronology/retrieval/budget/payload buckets.", f"codedye_positive_miss_taxonomy_v1_{DATE}.json", "partial_artifact_created"),
            gap("P2", "paper_framing", "Reviewer may ask why sparse evidence matters.", "Add null-audit utility table: FP bound, sensitivity, evidence completeness, cost per signal.", f"codedye_null_audit_utility_framework_v1_{DATE}.json"),
        ],
        "claim_upgrade_allowed": False,
        "next_experiment_allowed": "v3 controls first; live DeepSeek rerun only after freeze gate and control gate pass.",
    }


def probetrace() -> dict[str, Any]:
    anti = {
        "schema_version": "probetrace_anti_leakage_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "formal_multi_owner_claim_allowed": False,
        "current_claim_preserved": "single-active-owner/source-bound attribution",
        "required_checks": [
            {"check": "owner_token_exposure_scan", "status": "planned"},
            {"check": "prompt_shortcut_scan", "status": "planned"},
            {"check": "registry_leakage_scan", "status": "planned"},
            {"check": "same_provider_unwrap_control", "status": "planned"},
            {"check": "owner_heldout_split_integrity", "status": "planned"},
            {"check": "task_heldout_split_integrity", "status": "planned"},
        ],
        "promotion_policy": "A 300/300 result can remain claim-bearing only with leakage controls and margin evidence; it must not be expanded to provider-general attribution.",
    }
    write_json(f"results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_gate_v1_{DATE}.json", anti)

    margin = {
        "schema_version": "probetrace_owner_margin_distribution_plan_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "source_artifacts": [
            "apis300_live_attribution_evidence.json",
            "probetrace_owner_margin_control_audit_gate_20260505.json",
            "probetrace_abstain_aware_attribution_gate_20260506.json",
        ],
        "required_distributions": [
            "true_owner_score_cdf",
            "wrong_owner_score_cdf",
            "null_owner_score_cdf",
            "random_owner_score_cdf",
            "near_boundary_rows",
            "rank_auc_threshold_free_summary",
        ],
        "claim_policy": "Margin evidence is required to defend against shortcut and threshold-tuning attacks.",
    }
    write_json(f"results/ProbeTrace/artifacts/generated/probetrace_owner_margin_distribution_v1_{DATE}.json", margin)

    multi_owner = {
        "schema_version": "probetrace_multi_owner_support_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "formal_multi_owner_claim_allowed": False,
        "planned_support_matrix": {
            "active_owners": 5,
            "split_requirements": ["owner_heldout", "task_heldout"],
            "control_ratio": "wrong/null/random owners >= 4x positives",
            "required_outputs": [
                "owner_margin_distribution",
                "per_owner_tpr_fpr_ci",
                "near_boundary_examples",
                "latency_query_frontier",
            ],
        },
        "promotion_policy": "The existing main claim remains single-active-owner. Multi-owner evidence is support-only unless all per-owner controls and heldout gates pass.",
    }
    write_json(f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_support_gate_v1_{DATE}.json", multi_owner)

    return {
        "project": "ProbeTrace",
        "current_state": {
            "apis_success": "300/300",
            "false_owner_controls": "0/1200",
            "transfer_support_rows": "900/900",
            "primary_independence_unit": "300 task clusters",
            "scope": "single active owner/source-bound split",
        },
        "scores": {
            "innovation": score(4, "Active-owner attribution with semantic witness and transfer receipts is strong."),
            "method_rigor": score(3, "Perfect APIS result requires stronger anti-leakage and margin evidence."),
            "evidence_scale": score(4, "300 APIS, 1,200 controls, and 900 transfer rows are substantial but single-owner scoped."),
            "baseline_control_strength": score(4, "Wrong/null controls exist; multi-owner support is still missing."),
            "attack_negative_control_coverage": score(4, "False-owner controls are clean; leakage controls need formal gate."),
            "statistical_trust": score(4, "Wilson intervals and independence boundaries are explicit."),
            "reproducibility": score(4, "Receipts and hashes exist; live provider rerun remains external."),
            "claim_discipline": score(5, "Single-owner and task-cluster boundaries are correctly preserved."),
        },
        "gaps": [
            gap("P1", "anti_leakage", "300/300 can be attacked as shortcut or owner leakage.", "Add leakage scan, same-provider unwrap, owner/task heldout checks.", f"probetrace_anti_leakage_gate_v1_{DATE}.json", "artifact_created"),
            gap("P1", "margin_evidence", "Threshold-free separation evidence is not yet main-surface.", "Generate owner margin CDF and rank/AUC summary.", f"probetrace_owner_margin_distribution_v1_{DATE}.json", "artifact_created"),
            gap("P2", "scope", "Single-owner scope is narrow for best-paper.", "Run 5-owner support experiment; keep support-only unless full promotion passes.", f"probetrace_multi_owner_support_gate_v1_{DATE}.json"),
        ],
        "claim_upgrade_allowed": False,
        "next_experiment_allowed": "Anti-leakage and margin gates first; multi-owner only as support until promotion.",
    }


def sealaudit() -> dict[str, Any]:
    frontier = load_json("results/SealAudit/artifacts/generated/sealaudit_coverage_risk_frontier_gate_20260505.json")
    taxonomy = {
        "schema_version": "sealaudit_needs_review_taxonomy_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "source_artifact": "sealaudit_coverage_risk_frontier_gate_20260505.json",
        "needs_review_count": frontier["decision_distribution"]["needs_review"],
        "taxonomy_status": "requires_row_level_join",
        "required_buckets": [
            "hard_ambiguity_retained",
            "insufficient_execution_evidence",
            "semantic_drift_conflict",
            "laundering_sensitive",
            "spoofability_sensitive",
            "expert_review_required",
        ],
        "policy": "Needs-review rows are explicit abstentions, not hidden successes; v5 may split them but must not relabel old v3/v4 artifacts.",
    }
    write_json(f"results/SealAudit/artifacts/generated/sealaudit_needs_review_taxonomy_v1_{DATE}.json", taxonomy)

    v5 = {
        "schema_version": "sealaudit_second_stage_v5_conjunction_prerun_gate",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "formal_v5_claim_allowed": False,
        "does_not_overwrite": ["v3", "v4", "canonical_claim_surface_results.json"],
        "conjunction": [
            "static_safety",
            "semantic_drift",
            "laundering_resistance",
            "spoofability_resistance",
            "marker_hidden_stress",
            "provider_judge_perturbation",
            "ambiguity_retention",
        ],
        "promotion_policy": "Increase decisive coverage only if unsafe-pass count and upper bound remain conservative.",
        "required_postrun_artifacts": [
            f"sealaudit_second_stage_v5_results_{DATE}.json",
            f"sealaudit_v5_coverage_risk_frontier_{DATE}.json",
            f"sealaudit_v5_visible_marker_diagnostic_boundary_{DATE}.json",
        ],
    }
    write_json(f"results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_conjunction_gate_{DATE}.json", v5)

    expert = {
        "schema_version": "sealaudit_expert_review_role_support_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "role_based_support_only": True,
        "allowed_wording": "Role-based experts reviewed the packet and reported no blocking concerns through the project coordinator.",
        "forbidden_wording": [
            "signed gold labels",
            "named expert identities",
            "institutional certification",
            "timestamped legal attestation",
            "expert-created row labels without completed row-level packet",
        ],
        "roles": ["curator_01", "curator_02", "adjudicator_01", "seal_expert_01_to_07"],
    }
    write_json(f"results/SealAudit/artifacts/generated/sealaudit_expert_review_role_support_gate_v1_{DATE}.json", expert)

    return {
        "project": "SealAudit",
        "current_state": {
            "cases": 320,
            "marker_hidden_rows": frontier["hidden_claim_rows"],
            "decisive": frontier["decision_distribution"]["benign"] + frontier["decision_distribution"]["latent_trojan"],
            "needs_review": frontier["decision_distribution"]["needs_review"],
            "unsafe_pass": frontier["unsafe_pass_count"],
            "decisive_coverage": frontier["decisive_coverage"],
        },
        "scores": {
            "innovation": score(4, "Watermark-as-security-object audit framing is strong."),
            "method_rigor": score(3, "Explicit abstention is rigorous, but needs-review rows require finer taxonomy."),
            "evidence_scale": score(4, "320 cases and 960 hidden rows are solid."),
            "baseline_control_strength": score(4, "Controls and citation-only boundaries are present."),
            "attack_negative_control_coverage": score(4, "Marker-hidden boundary and unsafe-pass tracking are strong; v5 attack conjunction should be main-surface."),
            "statistical_trust": score(4, "Coverage-risk CI exists; coverage remains low."),
            "reproducibility": score(4, "Artifacts and tests are present; human review is role-based support."),
            "claim_discipline": score(5, "No safety certificate or automatic classifier claim is made."),
        },
        "gaps": [
            gap("P1", "coverage", "8.44% decisive coverage is too low for a strong utility claim.", "Run v5 second-stage conjunction to improve coverage without increasing unsafe-pass risk.", f"sealaudit_second_stage_v5_conjunction_gate_{DATE}.json", "artifact_created"),
            gap("P1", "abstention_taxonomy", "879 needs-review rows are not yet split into reviewer-useful categories.", "Create row-level needs-review taxonomy.", f"sealaudit_needs_review_taxonomy_v1_{DATE}.json", "partial_artifact_created"),
            gap("P2", "human_review", "Expert support wording can be attacked if overstated.", "Lock role-based support wording and forbidden claims.", f"sealaudit_expert_review_role_support_gate_v1_{DATE}.json", "artifact_created"),
        ],
        "claim_upgrade_allowed": False,
        "next_experiment_allowed": "v5 prerun gate exists; claim-bearing v5 run only after row schema and unsafe-pass policy are locked.",
    }


def main() -> int:
    projects = [semcodebook(), codedye(), probetrace(), sealaudit()]
    scorecard = {
        "schema_version": "bestpaper_review_scorecard_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "preservation_policy": "Existing result artifacts are immutable; this scorecard adds reviewer-facing closure artifacts only.",
        "bestpaper_ready": False,
        "projects": projects,
        "portfolio_blockers": [
            "SemCodebook: row-level positive-miss taxonomy and causal contribution table.",
            "CodeDye: positive-control sensitivity and v3 control rerun before any claim upgrade.",
            "ProbeTrace: anti-leakage and threshold-free margin evidence.",
            "SealAudit: low decisive coverage and needs-review taxonomy.",
        ],
        "entry_conditions_for_full_experiments": [
            "No preserved result file changed.",
            "Project-specific preregistered protocol gate exists.",
            "Support-only rows cannot enter main denominator.",
            "Thresholds and claim boundaries are frozen before rerun.",
        ],
    }
    write_json(f"results/bestpaper_review_scorecard_v1_{DATE}.json", scorecard)

    md_lines = [
        "# Best-Paper Gap Closure Status v1",
        "",
        "This document is generated from current preserved artifacts. It is additive and does not replace prior results.",
        "",
        "Second-pass computable closure artifacts are generated by `scripts/build_bestpaper_second_pass_artifacts.py`. They close reviewer-facing auditability gaps where row-level evidence is already packaged, while keeping fresh-rerun items open.",
        "",
    ]
    for project in projects:
        md_lines.append(f"## {project['project']}")
        md_lines.append("")
        md_lines.append("Current gaps:")
        for item in project["gaps"]:
            md_lines.append(f"- {item['priority']} / {item['area']}: {item['issue']} Closure: {item['closure_action']}")
        md_lines.append("")
        md_lines.append("Strict reviewer scores:")
        for name, value in project["scores"].items():
            md_lines.append(f"- {name}: {value['score_1_to_5']}/5. {value['rationale']}")
        md_lines.append("")
    md_lines.extend(
        [
            "## Second-Pass Computed Closure",
            "",
            "- SemCodebook: `semcodebook_family_scale_sufficiency_table_v1_20260507.json` makes family/scale concentration risk auditable from the 72,000-row manifest.",
            "- CodeDye: `codedye_audit_utility_second_pass_v1_20260507.json` separates sparse live yield, positive-control sensitivity, negative-control bound, and payload-hash completeness.",
            "- ProbeTrace: `probetrace_margin_second_pass_audit_v1_20260507.json` summarizes row-level controls, high-control-score/no-owner-emission rows, and near-boundary positives.",
            "- SealAudit: `sealaudit_needs_review_second_pass_taxonomy_v1_20260507.json` splits needs-review load by family, language, prompt variant, score, and provisional routing.",
            "",
            "Remaining P1 items require new or remote full artifacts: SemCodebook raw-row miss attribution, CodeDye v3 controls/rerun, ProbeTrace multi-owner score-vector run, and SealAudit v5 claim-bearing second-stage run.",
            "",
        ]
    )
    write_md(f"docs/BESTPAPER_GAP_CLOSURE_STATUS_v1_{DATE}.md", "\n".join(md_lines))

    print(f"[OK] Wrote best-paper closure artifacts for {len(projects)} projects.")
    print(f"[OK] results/bestpaper_review_scorecard_v1_{DATE}.json")
    print(f"[OK] docs/BESTPAPER_GAP_CLOSURE_STATUS_v1_{DATE}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
