from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SemCodebook row-level positive miss attribution.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def load_records(path: Path) -> tuple[list[dict[str, Any]], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        for key in ("records", "rows", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)], key
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], "list_root"
    return [], "unsupported"


def is_positive(row: dict[str, Any]) -> bool:
    if row.get("negative_control") is False or row.get("is_negative_control") is False:
        return True
    ablation_kind = str(row.get("ablation_kind", "")).lower()
    if "positive" in ablation_kind:
        return True
    for key in ("negative_control", "is_negative_control", "claim_negative_control"):
        if row.get(key) is True:
            return False
    role = str(row.get("claim_role", row.get("record_role", ""))).lower()
    if "negative" in role or "control" in role and "positive" not in role:
        return False
    if row.get("positive") is True or row.get("claim_positive") is True:
        return True
    if "positive" in role or "carrier" in role:
        return True
    return False


def detected(row: dict[str, Any]) -> bool:
    for key in ("detected", "watermark_detected", "positive_detected", "recovered", "recovery_success"):
        if key in row:
            return bool(row.get(key))
    decision = str(row.get("decision", row.get("decision_status", ""))).lower()
    return decision in {"detected", "recovered", "accept", "accepted", "watermark_present"}


def bucket(row: dict[str, Any]) -> str:
    if row.get("mock_or_fallback_generation"):
        return "mock_or_fallback_generation"
    if row.get("generation_failure"):
        return "generation_failure"
    if row.get("semantic_or_compile_failure") or row.get("compile_ok") is False:
        return "semantic_or_compile_failure"
    if row.get("schedule_commitment_mismatch"):
        return "schedule_commitment_mismatch"
    if row.get("abstain_reason") or str(row.get("decision_status", "")).lower() in {"abstain", "reject"}:
        return "detector_abstain_or_reject_on_positive"
    if row.get("attack_not_applicable_or_unchanged"):
        return "attack_not_applicable_or_unchanged"
    return "unclassified_positive_miss"


def main() -> int:
    args = parse_args()
    input_path = ROOT / args.input
    output_path = ROOT / args.output
    if not input_path.exists():
        output = {
            "schema_version": "semcodebook_row_level_miss_attribution_v1",
            "generated_at_utc": utc_now(),
            "claim_bearing": False,
            "gate_pass": False,
            "blocked": True,
            "blockers": ["input_missing"],
            "input": args.input,
            "required_action": "Fetch the large raw full-eval artifact referenced in LARGE_ARTIFACTS_MANIFEST.json before running this attribution.",
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("[BLOCKED] SemCodebook miss attribution input missing.")
        return 2

    records, source_shape = load_records(input_path)
    positives = [row for row in records if is_positive(row)]
    misses = [row for row in positives if not detected(row)]
    by_bucket = Counter(bucket(row) for row in misses)
    by_attack = Counter(str(row.get("attack_condition", row.get("attack", "unknown"))) for row in misses)
    by_language = Counter(str(row.get("language", "unknown")) for row in misses)
    by_model = Counter(
        str(row.get("model_name", row.get("model", row.get("backbone", row.get("model_id", "unknown")))))
        for row in misses
    )
    unclassified = by_bucket.get("unclassified_positive_miss", 0)
    gate_pass = bool(records) and len(positives) > 0 and len(misses) > 0 and unclassified == 0
    blockers = [
        blocker
        for blocker, present in [
            ("no_positive_rows_detected", len(positives) == 0),
            ("no_positive_miss_rows_detected_for_attribution", len(misses) == 0),
            ("unclassified_positive_miss_rows_present", unclassified > 0),
        ]
        if present
    ]
    output = {
        "schema_version": "semcodebook_row_level_miss_attribution_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": gate_pass,
        "blocked": False,
        "input": args.input,
        "source_shape": source_shape,
        "record_count": len(records),
        "positive_count": len(positives),
        "positive_miss_count": len(misses),
        "miss_bucket_counts": dict(sorted(by_bucket.items())),
        "miss_by_attack": dict(sorted(by_attack.items())),
        "miss_by_language": dict(sorted(by_language.items())),
        "miss_by_model": dict(by_model.most_common(30)),
        "promotion_condition": "Every positive miss must map to exactly one primary failure bucket; no threshold or denominator changes.",
        "blockers": blockers,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("[OK] Wrote SemCodebook miss attribution.")
    return 0 if output["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
