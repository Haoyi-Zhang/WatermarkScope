from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def load_jsonl(rel: str) -> list[dict[str, Any]]:
    rows = []
    for line in (ROOT / rel).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_json(rel: str, payload: Any) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def quantiles(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "q05": None, "q25": None, "median": None, "q75": None, "q95": None, "max": None}
    ordered = sorted(values)

    def q(p: float) -> float:
        return ordered[int(p * (len(ordered) - 1))]

    return {
        "count": len(ordered),
        "min": ordered[0],
        "q05": q(0.05),
        "q25": q(0.25),
        "median": median(ordered),
        "q75": q(0.75),
        "q95": q(0.95),
        "max": ordered[-1],
    }


def semcodebook_family_scale_sufficiency() -> dict[str, Any]:
    manifest = load_json("results/SemCodebook/artifacts/generated/semcodebook_whitebox_main_denominator_source_manifest_20260505.json")
    rows = manifest["rows"]
    by_family: dict[str, dict[str, int]] = defaultdict(lambda: {"models": 0, "records": 0, "positive": 0, "positive_detected": 0, "negative": 0, "negative_detected": 0})
    by_scale: dict[str, dict[str, int]] = defaultdict(lambda: {"models": 0, "records": 0, "positive": 0, "positive_detected": 0, "negative": 0, "negative_detected": 0})
    model_rows = []
    for row in rows:
        family = row["family"]
        scale = row["scale_group"]
        for bucket in (by_family[family], by_scale[scale]):
            bucket["models"] += 1
            bucket["records"] += int(row["record_count"])
            bucket["positive"] += int(row["positive_count"])
            bucket["positive_detected"] += int(row["positive_detected"])
            bucket["negative"] += int(row["negative_count"])
            bucket["negative_detected"] += int(row["negative_detected"])
        model_rows.append(
            {
                "model": row["model"],
                "family": family,
                "scale_group": scale,
                "positive_rate": row["positive_detected"] / row["positive_count"],
                "negative_fp_rate": row["negative_detected"] / row["negative_count"],
                "compiler_failure_count": row["compiler_failure_count"],
                "helper_failure_count": row["helper_failure_count"],
                "mock_or_fallback_count": row["mock_or_fallback_count"],
                "validator_repair_dependency_count": row["validator_repair_dependency_count"],
            }
        )

    def finalize(groups: dict[str, dict[str, int]]) -> dict[str, Any]:
        out = {}
        for name, value in sorted(groups.items()):
            out[name] = {
                **value,
                "positive_rate": value["positive_detected"] / value["positive"] if value["positive"] else None,
                "negative_fp_rate": value["negative_detected"] / value["negative"] if value["negative"] else None,
            }
        return out

    payload = {
        "schema_version": "semcodebook_family_scale_sufficiency_table_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "source_artifact": "semcodebook_whitebox_main_denominator_source_manifest_20260505.json",
        "family_table": finalize(by_family),
        "scale_table": finalize(by_scale),
        "model_rows": model_rows,
        "bestpaper_relevance": "This closes the reviewer question about whether the 72k result is concentrated in one family or one scale bucket.",
        "remaining_gap": "Row-level positive-miss attribution still requires the raw full-eval result rows referenced by the manifest.",
    }
    write_json(f"results/SemCodebook/artifacts/generated/semcodebook_family_scale_sufficiency_table_v1_{DATE}.json", payload)
    return payload


def codedye_control_utility() -> dict[str, Any]:
    low = load_json("results/CodeDye/artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json")
    stats = load_json("results/CodeDye/artifacts/generated/statistics_repro_gate.json")
    surface = low["effect_surface"]
    payload = {
        "schema_version": "codedye_audit_utility_second_pass_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "source_artifacts": [
            "codedye_low_signal_claim_boundary_gate_20260505.json",
            "statistics_repro_gate.json",
        ],
        "utility_surface": {
            "live_audit_rows": surface["claim_rows"],
            "final_signal_count": surface["decision_counts"]["contamination_signal_detected"],
            "final_signal_ci95": surface["final_signal_wilson95"],
            "statistics_artifact_signal_count": surface["statistics_artifact_boundary"]["statistics_artifact_positive_count"],
            "positive_control_detected": surface["positive_control_detected_at_frozen_threshold"],
            "positive_control_ci95": surface["positive_control_sensitivity_wilson95"],
            "negative_control_false_positive_ci95": surface["negative_control_false_positive_wilson95"],
            "support_rows_excluded": surface["support_rows_excluded_from_main_denominator"],
            "payload_hash_missing": surface["claim_rows_missing_payload_or_transcript_hash"],
            "full_eval_record_count": stats["full_eval_contract"]["record_count"],
        },
        "reviewer_attack_closure": {
            "low_effect": "Low live yield is preserved as sparse null-audit evidence, not inflated into detection accuracy.",
            "moderate_sensitivity": "Positive-control misses remain a P1 method-improvement target.",
            "statistics_boundary": "4/300 statistics-artifact positives are not substituted for the final 6/300 signal count.",
        },
    }
    write_json(f"results/CodeDye/artifacts/generated/codedye_audit_utility_second_pass_v1_{DATE}.json", payload)
    return payload


def probetrace_margin_second_pass() -> dict[str, Any]:
    rows = load_jsonl("results/ProbeTrace/artifacts/generated/probetrace_owner_margin_control_audit_rows_20260505.jsonl")
    controls: dict[str, list[float]] = defaultdict(list)
    owner_emit_by_control: Counter[str] = Counter()
    false_attr_by_control: Counter[str] = Counter()
    for row in rows:
        for name, control in (row.get("controls") or {}).items():
            score = control.get("observed_control_score")
            if isinstance(score, (int, float)):
                controls[name].append(float(score))
            if control.get("owner_id_hat_emitted"):
                owner_emit_by_control[name] += 1
            if control.get("false_attribution"):
                false_attr_by_control[name] += 1

    payload = {
        "schema_version": "probetrace_margin_second_pass_audit_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "source_artifact": "probetrace_owner_margin_control_audit_rows_20260505.jsonl",
        "row_count": len(rows),
        "family_counts": dict(Counter(row.get("family") for row in rows)),
        "language_counts": dict(Counter(row.get("language") for row in rows)),
        "true_owner_verified_count": sum(1 for row in rows if row.get("true_owner_verified")),
        "near_boundary_confidence_count": sum(1 for row in rows if row.get("near_boundary_confidence")),
        "high_control_score_without_owner_emission_count": sum(1 for row in rows if row.get("high_control_score_without_owner_emission")),
        "control_score_summaries": {
            name: {
                "score_quantiles": quantiles(values),
                "owner_id_emitted": owner_emit_by_control[name],
                "false_attribution": false_attr_by_control[name],
            }
            for name, values in sorted(controls.items())
        },
        "claim_boundary": "This supports anti-leakage review for the current single-owner artifact. It still does not promote comparable owner-margin separability or multi-owner attribution.",
        "remaining_gap": "Comparable true-owner vs wrong-owner score vectors require a fresh multi-owner support run.",
    }
    write_json(f"results/ProbeTrace/artifacts/generated/probetrace_margin_second_pass_audit_v1_{DATE}.json", payload)
    return payload


def sealaudit_needs_review_second_pass() -> dict[str, Any]:
    data = load_json("results/SealAudit/artifacts/generated/canonical_claim_surface_results.json")
    records = data["records"]
    needs = [row for row in records if row.get("decision") == "needs_review"]
    score_values = [float(row["score"]) for row in records if isinstance(row.get("score"), (int, float))]
    needs_scores = [float(row["score"]) for row in needs if isinstance(row.get("score"), (int, float))]
    by_family = Counter(row.get("case_family") for row in needs)
    by_language = Counter(row.get("language") for row in needs)
    by_variant = Counter(row.get("prompt_variant_id") for row in needs)
    provisional = Counter()
    for row in needs:
        score = row.get("score")
        variant = row.get("prompt_variant_id")
        if score == 0.5:
            provisional["hard_ambiguity_retained"] += 1
        elif variant == "marker_hidden_schema_only":
            provisional["insufficient_context_schema_only"] += 1
        elif isinstance(score, (int, float)) and score >= 0.7:
            provisional["latent_risk_evidence_below_confirmation"] += 1
        else:
            provisional["expert_review_required"] += 1

    payload = {
        "schema_version": "sealaudit_needs_review_second_pass_taxonomy_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "source_artifact": "canonical_claim_surface_results.json",
        "record_count": len(records),
        "needs_review_count": len(needs),
        "needs_review_by_family": dict(sorted(by_family.items())),
        "needs_review_by_language": dict(sorted(by_language.items())),
        "needs_review_by_prompt_variant": dict(sorted(by_variant.items())),
        "score_quantiles_all_rows": quantiles(score_values),
        "score_quantiles_needs_review": quantiles(needs_scores),
        "provisional_taxonomy": dict(provisional),
        "taxonomy_policy": "This is a second-pass routing taxonomy derived from existing row fields. It does not relabel old v3/v4 results and does not certify safety.",
        "remaining_gap": "A claim-bearing coverage increase requires a fresh v5 run with the preregistered conjunction gate.",
    }
    write_json(f"results/SealAudit/artifacts/generated/sealaudit_needs_review_second_pass_taxonomy_v1_{DATE}.json", payload)
    return payload


def main() -> int:
    sem = semcodebook_family_scale_sufficiency()
    code = codedye_control_utility()
    probe = probetrace_margin_second_pass()
    seal = sealaudit_needs_review_second_pass()
    summary = {
        "schema_version": "bestpaper_second_pass_summary_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "artifacts": {
            "SemCodebook": "semcodebook_family_scale_sufficiency_table_v1_20260507.json",
            "CodeDye": "codedye_audit_utility_second_pass_v1_20260507.json",
            "ProbeTrace": "probetrace_margin_second_pass_audit_v1_20260507.json",
            "SealAudit": "sealaudit_needs_review_second_pass_taxonomy_v1_20260507.json",
        },
        "closure_effect": {
            "SemCodebook": "Family/scale concentration risk is now auditable from manifest rows.",
            "CodeDye": "Sparse-yield utility and positive-control weakness are explicitly separated.",
            "ProbeTrace": "Current anti-leakage evidence is summarized from row-level controls.",
            "SealAudit": "Needs-review load is split by family/language/variant and provisional routing.",
        },
        "remaining_p1": [
            "SemCodebook row-level positive-miss attribution from raw full-eval rows.",
            "CodeDye v3 control rerun to improve or explain positive-control sensitivity.",
            "ProbeTrace fresh multi-owner score-vector run.",
            "SealAudit fresh v5 claim-bearing second-stage run.",
        ],
        "counts": {
            "sem_families": len(sem["family_table"]),
            "codedye_live_rows": code["utility_surface"]["live_audit_rows"],
            "probe_rows": probe["row_count"],
            "seal_needs_review": seal["needs_review_count"],
        },
    }
    write_json(f"results/bestpaper_second_pass_summary_v1_{DATE}.json", summary)
    print("[OK] Wrote second-pass best-paper closure artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
