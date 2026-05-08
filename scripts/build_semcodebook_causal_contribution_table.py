from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FULL_ARM = "full_ast_cfg_ssa_ecc_keyed"
COMPARISONS = {
    "full_vs_ast_only": "ast_only_carriers",
    "full_vs_cfg_only": "cfg_only_carriers",
    "full_vs_ssa_only": "ssa_only_carriers",
    "full_vs_drop_ast": "drop_ast_carriers",
    "full_vs_drop_cfg": "drop_cfg_carriers",
    "full_vs_drop_ssa": "drop_ssa_carriers",
    "full_vs_ecc_off": "ecc_raw_payload4_no_correction",
    "full_vs_unkeyed_schedule": "unkeyed_static_family_order",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def wilson(k: int, n: int) -> dict[str, float | int | str]:
    if n <= 0:
        return {"k": k, "n": n, "rate": 0.0, "low": 0.0, "high": 0.0, "method": "wilson"}
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SemCodebook causal contribution table from full ablation rows.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gate-output", required=True)
    return parser.parse_args()


def load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        rows = payload.get("records", [])
    else:
        rows = payload
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def is_positive(row: dict[str, Any]) -> bool:
    return row.get("negative_control") is False or "positive" in str(row.get("ablation_kind", "")).lower()


def detected(row: dict[str, Any]) -> bool:
    if "detected" in row:
        return bool(row.get("detected"))
    return str(row.get("decision_status", "")).lower() in {"watermarked", "detected", "recovered"}


def row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("task_id", "")),
        str(row.get("attack_condition", "")),
        "positive" if is_positive(row) else "negative",
    )


def summarize_arm(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positives = [row for row in rows if is_positive(row)]
    negatives = [row for row in rows if not is_positive(row)]
    pos_hits = sum(1 for row in positives if detected(row))
    neg_hits = sum(1 for row in negatives if detected(row))
    return {
        "row_count": len(rows),
        "positive_n": len(positives),
        "positive_detected": pos_hits,
        "positive_recovery_ci95": wilson(pos_hits, len(positives)),
        "negative_n": len(negatives),
        "negative_false_positive": neg_hits,
        "negative_fp_ci95": wilson(neg_hits, len(negatives)),
        "language_counts": dict(sorted(Counter(str(row.get("language", "unknown")) for row in rows).items())),
        "attack_counts": dict(sorted(Counter(str(row.get("attack_condition", "unknown")) for row in rows).items())),
        "family_counts": dict(sorted(Counter(str(row.get("family", "unknown")) for row in rows).items())),
    }


def paired_delta(full_rows: list[dict[str, Any]], other_rows: list[dict[str, Any]]) -> dict[str, Any]:
    full_map = {row_key(row): row for row in full_rows if is_positive(row)}
    other_map = {row_key(row): row for row in other_rows if is_positive(row)}
    common = sorted(set(full_map) & set(other_map))
    full_hits = [1 if detected(full_map[key]) else 0 for key in common]
    other_hits = [1 if detected(other_map[key]) else 0 for key in common]
    deltas = [a - b for a, b in zip(full_hits, other_hits)]
    mean_delta = sum(deltas) / len(deltas) if deltas else 0.0
    wins = sum(1 for value in deltas if value > 0)
    losses = sum(1 for value in deltas if value < 0)
    ties = sum(1 for value in deltas if value == 0)
    if len(deltas) > 1:
        variance = sum((value - mean_delta) ** 2 for value in deltas) / (len(deltas) - 1)
        se = math.sqrt(variance / len(deltas))
    else:
        se = 0.0
    return {
        "paired_n": len(common),
        "paired_delta_full_minus_arm": mean_delta,
        "normal_ci95": {
            "low": mean_delta - 1.959963984540054 * se,
            "high": mean_delta + 1.959963984540054 * se,
            "method": "paired_normal_approximation",
        },
        "full_better_rows": wins,
        "arm_better_rows": losses,
        "tied_rows": ties,
    }


def slice_summary(rows_by_arm: dict[str, list[dict[str, Any]]], slice_key: str) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for arm, rows in sorted(rows_by_arm.items()):
        positives = [row for row in rows if is_positive(row)]
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in positives:
            grouped[str(row.get(slice_key, "unknown"))].append(row)
        output[arm] = {
            group: {
                "positive_n": len(items),
                "positive_detected": sum(1 for item in items if detected(item)),
                "rate": (sum(1 for item in items if detected(item)) / len(items)) if items else 0.0,
            }
            for group, items in sorted(grouped.items())
        }
    return output


def main() -> int:
    args = parse_args()
    input_path = ROOT / args.input
    output_path = ROOT / args.output
    gate_path = ROOT / args.gate_output
    rows = load_records(input_path)
    rows_by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_arm[str(row.get("ablation_arm", "unknown"))].append(row)
    arm_summaries = {arm: summarize_arm(arm_rows) for arm, arm_rows in sorted(rows_by_arm.items())}
    comparisons = {
        name: paired_delta(rows_by_arm.get(FULL_ARM, []), rows_by_arm.get(arm, []))
        for name, arm in COMPARISONS.items()
    }
    missing_arms = sorted(set([FULL_ARM, *COMPARISONS.values()]) - set(rows_by_arm))
    negative_fp_total = sum(summary["negative_false_positive"] for summary in arm_summaries.values())
    comparison_pass = all(item["paired_n"] == 2400 for item in comparisons.values())
    gate_pass = (
        not missing_arms
        and len(rows) == 43200
        and all(summary["positive_n"] == 2400 and summary["negative_n"] == 2400 for summary in arm_summaries.values())
        and negative_fp_total == 0
        and comparison_pass
    )
    blockers = [
        name
        for name, present in [
            ("ablation_rows_not_43200", len(rows) != 43200),
            ("required_arms_missing", bool(missing_arms)),
            ("arm_denominator_mismatch", any(summary["positive_n"] != 2400 or summary["negative_n"] != 2400 for summary in arm_summaries.values())),
            ("negative_false_positive_present", negative_fp_total > 0),
            ("paired_comparison_incomplete", not comparison_pass),
        ]
        if present
    ]
    payload = {
        "schema_version": "semcodebook_causal_contribution_table_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": gate_pass,
        "input": args.input,
        "record_count": len(rows),
        "arm_summaries": arm_summaries,
        "paired_comparisons": comparisons,
        "slice_summaries": {
            "language": slice_summary(rows_by_arm, "language"),
            "attack_condition": slice_summary(rows_by_arm, "attack_condition"),
            "family": slice_summary(rows_by_arm, "family"),
        },
        "claim_boundary": "This table supports component contribution analysis for the fresh generation-changing ablation only; it does not promote first-sample/no-retry natural generation.",
        "blockers": blockers,
    }
    gate = {
        "schema_version": "semcodebook_causal_contribution_gate_v2",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "formal_causal_claim_allowed": gate_pass,
        "gate_pass": gate_pass,
        "causal_contribution_table": args.output,
        "required_comparisons": list(COMPARISONS),
        "required_slices": ["language", "attack_condition", "family"],
        "negative_false_positive_total": negative_fp_total,
        "blockers": blockers,
        "promotion_policy": "Component-causality language is allowed only for this fixed ablation table and must report paired deltas plus negative-control bounds.",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("[OK] Wrote SemCodebook causal contribution table.")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
