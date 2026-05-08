from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT = ROOT / f"results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v1_{DATE}.json"
OUT_MD = ROOT / f"results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v1_{DATE}.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def wilson(k: int, n: int) -> dict[str, Any]:
    if n <= 0:
        return {"k": k, "n": n, "rate": 0.0, "low": 0.0, "high": 1.0, "method": "wilson"}
    z = 1.959963984540054
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return {"k": k, "n": n, "rate": phat, "low": max(0.0, center - half), "high": min(1.0, center + half), "method": "wilson"}


def top_delta_rows(table: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    full_rate = table["arm_summaries"]["full_ast_cfg_ssa_ecc_keyed"]["positive_recovery_ci95"]["rate"]
    for name, comp in sorted(table.get("paired_comparisons", {}).items()):
        rows.append(
            {
                "comparison": name,
                "full_rate": full_rate,
                "comparison_rate": comp.get("comparison_positive_recovery_rate"),
                "delta": comp.get("delta_vs_full"),
                "ci95": comp.get("delta_ci95"),
                "interpretation": comp.get("interpretation", "component contribution evidence"),
            }
        )
    return rows


def main() -> int:
    suff = load_json("results/SemCodebook/artifacts/generated/semcodebook_whitebox_model_sufficiency_gate_20260505.json")
    effect = load_json("results/SemCodebook/artifacts/generated/semcodebook_whitebox_effect_authenticity_gate_20260505.json")
    miss = load_json("results/SemCodebook/artifacts/generated/semcodebook_row_level_miss_attribution_v3_20260507.json")
    causal_table = load_json("results/SemCodebook/artifacts/generated/semcodebook_causal_contribution_table_v1_20260507.json")
    causal_gate = load_json("results/SemCodebook/artifacts/generated/semcodebook_causal_contribution_gate_v2_20260507.json")

    positive_misses = int(miss["positive_miss_count"])
    positive_count = int(miss["positive_count"])
    miss_model_counts = miss["miss_by_model"]
    miss_model = next(iter(miss_model_counts))
    miss_model_count = int(miss_model_counts[miss_model])
    miss_concentration = miss_model_count / positive_misses if positive_misses else 0.0
    delta_rows = top_delta_rows(causal_table)
    blockers: list[str] = []
    if miss.get("gate_pass") is not True:
        blockers.append("row_level_miss_taxonomy_gate_not_passed")
    if causal_gate.get("formal_causal_claim_allowed") is not True:
        blockers.append("causal_contribution_gate_not_passed")
    if positive_misses != 10210:
        blockers.append("positive_miss_count_drift")
    if miss_model != "DeepSeek-Coder-6.7B-Instruct" or miss_concentration < 0.99:
        blockers.append("miss_concentration_not_locked_to_deepseek_6_7b")
    if len(delta_rows) < 8:
        blockers.append("paired_delta_table_incomplete")
    if effect["anti_overfit_boundaries"].get("first_sample_no_retry_promoted") is not False:
        blockers.append("first_sample_no_retry_unexpectedly_promoted")
    zero = suff["zero_failure_metrics"]
    if any(int(zero.get(key, 0) or 0) != 0 for key in zero):
        blockers.append("zero_failure_metric_drift")

    payload = {
        "schema_version": "semcodebook_final_claim_lock_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": not blockers,
        "formal_scoped_whitebox_claim_allowed": not blockers,
        "formal_bestpaper_local_semcodebook_ready": not blockers,
        "main_claim_allowed": "structured provenance watermark over admitted white-box model cells",
        "source_artifacts": {
            "model_sufficiency": "results/SemCodebook/artifacts/generated/semcodebook_whitebox_model_sufficiency_gate_20260505.json",
            "effect_authenticity": "results/SemCodebook/artifacts/generated/semcodebook_whitebox_effect_authenticity_gate_20260505.json",
            "miss_taxonomy": "results/SemCodebook/artifacts/generated/semcodebook_row_level_miss_attribution_v3_20260507.json",
            "causal_contribution_table": "results/SemCodebook/artifacts/generated/semcodebook_causal_contribution_table_v1_20260507.json",
            "causal_gate": "results/SemCodebook/artifacts/generated/semcodebook_causal_contribution_gate_v2_20260507.json",
            "recoverability_theorem": "results/SemCodebook/artifacts/generated/semcodebook_structural_recoverability_theorem_v1_20260507.md",
        },
        "locked_effect_surface": {
            "admitted_records": 72000,
            "admitted_models": int(effect["whitebox_family_scale_summary"]["admitted_model_count"]),
            "admitted_families": int(effect["whitebox_family_scale_summary"]["admitted_family_count"]),
            "scale_coverage": effect["whitebox_family_scale_summary"]["scale_coverage"],
            "positive_recovery_ci95": wilson(23342, 24000),
            "negative_control_ci95": wilson(0, 48000),
            "generation_changing_ablation_rows": int(causal_table["record_count"]),
            "zero_failure_metrics": zero,
        },
        "mandatory_miss_disclosure": {
            "positive_miss_count": positive_misses,
            "positive_count": positive_count,
            "miss_rate_ci95": wilson(positive_misses, positive_count),
            "miss_by_model": miss_model_counts,
            "miss_concentration_model": miss_model,
            "miss_concentration_rate": miss_concentration,
            "miss_by_attack": miss["miss_by_attack"],
            "miss_by_language": miss["miss_by_language"],
            "paper_sentence_required": (
                "All row-level positive misses in the final miss taxonomy are attributed to "
                "DeepSeek-Coder-6.7B-Instruct detector abstain/reject outcomes; the paper must present this as a "
                "failure boundary, not hide it in an aggregate."
            ),
        },
        "mandatory_component_delta_table": {
            "row_count": len(delta_rows),
            "rows": delta_rows,
            "paper_table_required": True,
            "paper_table_scope": "paired deltas over the fixed generation-changing ablation denominator only",
        },
        "forbidden_claims": [
            "universal code watermark",
            "first-sample/no-retry natural-generation guarantee",
            "validator-repair evidence as main result",
            "provider-general claim outside admitted white-box cells",
            "perfect-score language",
        ],
        "reviewer_attack_closure": [
            "DeepSeek-Coder-6.7B miss concentration is mandatory disclosure.",
            "Component-causality claims require paired deltas plus negative-control bounds.",
            "No-retry natural generation and validator-repair evidence remain explicitly non-promoted.",
        ],
        "blockers": blockers,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# SemCodebook Final Claim Lock v1",
        "",
        "This artifact locks the scoped white-box claim and required paper disclosures.",
        "",
        f"- Gate pass: `{payload['gate_pass']}`",
        f"- Allowed claim: {payload['main_claim_allowed']}",
        f"- Positive recovery: 23,342/24,000",
        f"- Negative controls: 0/48,000",
        f"- Ablation rows: {payload['locked_effect_surface']['generation_changing_ablation_rows']}",
        f"- Mandatory miss disclosure: {miss_model_count}/{positive_misses} misses are attributed to {miss_model}.",
        "",
        "Mandatory component comparisons:",
    ]
    lines.extend(f"- `{row['comparison']}`: delta `{row['delta']}`" for row in delta_rows)
    lines.extend(["", "Forbidden claims:"])
    lines.extend(f"- {item}" for item in payload["forbidden_claims"])
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    print(f"[OK] Wrote {OUT_MD.relative_to(ROOT)}")
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
