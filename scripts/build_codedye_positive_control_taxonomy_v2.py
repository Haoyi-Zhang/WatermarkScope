from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


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
    parser = argparse.ArgumentParser(description="Build CodeDye row-level positive-control miss taxonomy.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gate-output", required=True)
    return parser.parse_args()


def load_records(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {}, [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("records", "rows", "results"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return payload, [row for row in rows if isinstance(row, dict)]
    return {}, []


def detected(row: dict[str, Any]) -> bool:
    return bool(row.get("contaminated_by_canonical_null_gate")) and bool(row.get("familywise_decision_gate_pass"))


def bucket(row: dict[str, Any]) -> str:
    if not bool(row.get("familywise_decision_gate_pass")):
        if not bool(row.get("witness_ablation_collapses_gate")):
            return "witness_ablation_did_not_collapse"
        if float(row.get("familywise_adjusted_p_value") or 1.0) > 0.05:
            return "familywise_margin_not_significant"
        return "familywise_gate_failed"
    if not bool(row.get("contaminated_by_canonical_null_gate")):
        return "canonical_null_gate_rejected"
    return "unclassified_positive_control_miss"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positives = [row for row in rows if str(row.get("variant_kind", "positive_control")) == "positive_control"]
    hits = [row for row in positives if detected(row)]
    misses = [row for row in positives if not detected(row)]
    buckets = Counter(bucket(row) for row in misses)
    by_subset = Counter(str(row.get("subset", "unknown")) for row in misses)
    by_arm = Counter(str(row.get("control_arm", "unknown")) for row in misses)
    by_hidden_diag = Counter(str(bool(row.get("hidden_test_family_diagnostic_only"))) for row in misses)
    unclassified = buckets.get("unclassified_positive_control_miss", 0)
    return {
        "positive_control_denominator": len(positives),
        "positive_control_detected": len(hits),
        "positive_control_missed": len(misses),
        "positive_control_sensitivity_ci95": wilson(len(hits), len(positives)),
        "miss_bucket_counts": dict(sorted(buckets.items())),
        "miss_by_subset": dict(sorted(by_subset.items())),
        "miss_by_control_arm": dict(sorted(by_arm.items())),
        "miss_by_hidden_family_diagnostic_only": dict(sorted(by_hidden_diag.items())),
        "unclassified_miss_count": unclassified,
    }


def main() -> int:
    args = parse_args()
    input_path = ROOT / args.input
    output_path = ROOT / args.output
    gate_path = ROOT / args.gate_output
    if not input_path.exists():
        payload = {
            "schema_version": "codedye_positive_control_taxonomy_v2",
            "generated_at_utc": utc_now(),
            "claim_bearing": False,
            "gate_pass": False,
            "blocked": True,
            "blockers": ["input_missing"],
            "input": args.input,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        gate_path.parent.mkdir(parents=True, exist_ok=True)
        gate_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("[BLOCKED] CodeDye positive-control input missing.")
        return 2

    metadata, rows = load_records(input_path)
    summary = summarize(rows)
    gate_pass = (
        summary["positive_control_denominator"] >= 300
        and summary["positive_control_detected"] > 0
        and summary["positive_control_missed"] > 0
        and summary["unclassified_miss_count"] == 0
        and bool(metadata.get("positive_control_composite_validity_pass"))
    )
    blockers = [
        name
        for name, present in [
            ("positive_control_denominator_below_300", summary["positive_control_denominator"] < 300),
            ("no_positive_control_hits_detected", summary["positive_control_detected"] == 0),
            ("no_positive_control_misses_to_explain", summary["positive_control_missed"] == 0),
            ("unclassified_positive_control_misses", summary["unclassified_miss_count"] > 0),
            ("composite_validity_not_passed", not bool(metadata.get("positive_control_composite_validity_pass"))),
        ]
        if present
    ]
    payload = {
        "schema_version": "codedye_positive_control_taxonomy_v2",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "blocked": False,
        "gate_pass": gate_pass,
        "input": args.input,
        "source_schema_version": metadata.get("schema_version"),
        "study_kind": metadata.get("study_kind"),
        "composite_validity_pass": bool(metadata.get("positive_control_composite_validity_pass")),
        "positive_control_power_pass": bool(metadata.get("positive_control_power_pass")),
        "positive_control_family_coverage_pass": bool(metadata.get("positive_control_family_coverage_pass")),
        **summary,
        "taxonomy_policy": "Misses are explanatory failure-boundary evidence only; thresholds and denominators are unchanged.",
        "blockers": blockers,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    gate = {
        "schema_version": "codedye_v3_positive_negative_control_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "formal_v3_live_claim_allowed": False,
        "gate_pass": gate_pass,
        "blocked": False,
        "positive_control_taxonomy": args.output,
        "positive_control_denominator": summary["positive_control_denominator"],
        "positive_control_detected": summary["positive_control_detected"],
        "positive_control_missed": summary["positive_control_missed"],
        "positive_control_sensitivity_ci95": summary["positive_control_sensitivity_ci95"],
        "negative_control_status": "unchanged_clean_controls_preserved_from_source_artifact",
        "blockers": blockers,
        "promotion_policy": "This gate admits the positive-control taxonomy as support for sensitivity, not a high-recall live contamination claim.",
    }
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("[OK] Wrote CodeDye positive-control taxonomy v2.")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
