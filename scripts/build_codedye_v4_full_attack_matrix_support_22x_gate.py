from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260508"
RESULT = ROOT / f"results/CodeDye/artifacts/generated/codedye_v4_full_attack_matrix_support_22x_results_{DATE}.json"
OUT = ROOT / f"results/CodeDye/artifacts/generated/codedye_v4_full_attack_matrix_support_22x_gate_v1_{DATE}.json"

REQUIRED_ATTACKS = {
    "ast_canonicalization",
    "canary_preserving_rewrite",
    "chronology_shuffle",
    "comment_whitespace_normalize",
    "cross_language_reexpression",
    "query_budget_drop",
    "rename_identifiers",
}

REQUIRED_ROW_FIELDS = {
    "task_id",
    "attack_id",
    "run_id",
    "provider_name",
    "provider_mode_resolved",
    "prompt_hash",
    "attack_prompt_hash",
    "raw_payload_hash",
    "raw_provider_transcript_hash",
    "structured_payload_hash",
    "task_hash",
    "record_hash",
    "claim_bearing",
    "claim_bearing_attack_evidence",
    "support_only_not_claim_bearing",
    "utility_admissible_for_attack_claim",
    "decision",
    "threshold_version",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def wilson(k: int, n: int) -> dict[str, float | int | str]:
    if n <= 0:
        return {"k": k, "n": n, "rate": 0.0, "low": 0.0, "high": 1.0, "method": "wilson"}
    z = 1.959963984540054
    phat = k / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(phat * (1.0 - phat) / n + z * z / (4.0 * n * n)) / denom
    return {
        "k": k,
        "n": n,
        "rate": phat,
        "low": max(0.0, center - half),
        "high": min(1.0, center + half),
        "method": "wilson",
    }


def load_rows() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(RESULT.read_text(encoding="utf-8"))
    rows = payload.get("records", []) if isinstance(payload, dict) else []
    return payload, [row for row in rows if isinstance(row, dict)]


def missing_fields(row: dict[str, Any]) -> list[str]:
    return [field for field in sorted(REQUIRED_ROW_FIELDS) if field not in row or row.get(field) in {"", None}]


def main() -> int:
    blockers: list[str] = []
    if not RESULT.exists():
        payload = {
            "schema_version": "codedye_v4_full_attack_matrix_support_22x_gate_v1",
            "generated_at_utc": utc_now(),
            "claim_bearing": False,
            "gate_pass": False,
            "support_experiment_admitted": False,
            "formal_main_claim_allowed": False,
            "blockers": ["result_missing"],
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"gate_pass": False, "blockers": payload["blockers"]}))
        return 1

    source, rows = load_rows()
    summary = source.get("summary", {}) if isinstance(source, dict) else {}
    if source.get("schema_version") != "codedye_attack_matrix_live_support_v1":
        blockers.append("unexpected_schema")
    if source.get("claim_bearing") is not False or source.get("formal_claim_allowed") is not False:
        blockers.append("source_not_support_only")
    if str(source.get("status", "")) != "support_only_passed":
        blockers.append("source_status_not_support_only_passed")
    if summary.get("support_gate_pass") is not True:
        blockers.append("source_support_gate_not_passed")
    if summary.get("gate_pass") is True:
        blockers.append("source_unexpectedly_promotes_canonical_claim")

    schema_missing_rows = sum(1 for row in rows if missing_fields(row))
    if schema_missing_rows:
        blockers.append(f"schema_missing_rows:{schema_missing_rows}")

    non_deepseek = sum(1 for row in rows if str(row.get("provider_name", "")).lower() != "deepseek")
    non_live = sum(1 for row in rows if str(row.get("provider_mode_resolved", "")).lower() != "live")
    claim_rows = sum(1 for row in rows if row.get("claim_bearing") is not False or row.get("claim_bearing_attack_evidence") is not False)
    non_support_rows = sum(1 for row in rows if row.get("support_only_not_claim_bearing") is not True)
    missing_hash_rows = sum(
        1
        for row in rows
        if not row.get("raw_provider_transcript_hash")
        or not row.get("structured_payload_hash")
        or not row.get("prompt_hash")
        or not row.get("task_hash")
        or not row.get("record_hash")
    )
    if non_deepseek:
        blockers.append(f"non_deepseek_rows:{non_deepseek}")
    if non_live:
        blockers.append(f"non_live_rows:{non_live}")
    if claim_rows:
        blockers.append(f"claim_rows_present:{claim_rows}")
    if non_support_rows:
        blockers.append(f"non_support_rows:{non_support_rows}")
    if missing_hash_rows:
        blockers.append(f"missing_hash_rows:{missing_hash_rows}")

    support_rows = [row for row in rows if row.get("support_only_not_claim_bearing") is True]
    utility_rows = [row for row in support_rows if row.get("utility_admissible_for_attack_claim") is True]
    by_attack = Counter(str(row.get("attack_id", "")) for row in rows)
    utility_by_attack = Counter(str(row.get("attack_id", "")) for row in utility_rows)
    missing_attacks = sorted(REQUIRED_ATTACKS - set(by_attack))
    if missing_attacks:
        blockers.append(f"missing_attacks:{','.join(missing_attacks)}")
    for attack_id in sorted(REQUIRED_ATTACKS):
        if utility_by_attack.get(attack_id, 0) < 20:
            blockers.append(f"support_utility_rows_below_20:{attack_id}:{utility_by_attack.get(attack_id, 0)}")

    utility_failure_rows = [row for row in support_rows if row.get("utility_admissible_for_attack_claim") is not True]
    decisions = Counter(str(row.get("decision", "missing")) for row in rows)
    signal_count = int(decisions.get("contamination_signal_detected", 0))
    payload = {
        "schema_version": "codedye_v4_full_attack_matrix_support_22x_gate_v1",
        "generated_at_utc": utc_now(),
        "project": "CodeDye",
        "claim_bearing": False,
        "gate_pass": not blockers,
        "support_experiment_admitted": not blockers,
        "formal_main_claim_allowed": False,
        "formal_high_recall_detection_claim_allowed": False,
        "formal_contamination_prevalence_claim_allowed": False,
        "source_result": RESULT.relative_to(ROOT).as_posix(),
        "source_status": source.get("status"),
        "record_count": len(rows),
        "support_utility_admissible_record_count": len(utility_rows),
        "utility_failure_boundary_record_count": len(utility_failure_rows),
        "attack_record_counts": dict(sorted(by_attack.items())),
        "support_utility_admissible_by_attack": dict(sorted(utility_by_attack.items())),
        "decision_counts": dict(sorted(decisions.items())),
        "signal_ci95": wilson(signal_count, len(rows)),
        "schema_missing_rows": schema_missing_rows,
        "missing_hash_rows": missing_hash_rows,
        "non_deepseek_rows": non_deepseek,
        "non_live_rows": non_live,
        "claim_rows_present": claim_rows,
        "non_support_rows": non_support_rows,
        "main_denominator_policy": {
            "enters_v3_300_main_denominator": False,
            "enters_any_main_claim_denominator": False,
            "failure_rows_deleted_or_relabelled": False,
            "threshold_adjusted_after_result": False,
        },
        "utility_failure_ledger": [
            {
                "attack_id": row.get("attack_id"),
                "task_id": row.get("task_id"),
                "language": row.get("language"),
                "record_hash": row.get("record_hash"),
                "selected_utility_score": row.get("selected_utility_score"),
            }
            for row in utility_failure_rows
        ],
        "blockers": blockers,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"gate_pass": payload["gate_pass"], "record_count": len(rows), "blockers": blockers}, ensure_ascii=True))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
