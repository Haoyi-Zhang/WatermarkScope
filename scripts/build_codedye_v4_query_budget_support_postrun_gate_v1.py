from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260508"
GENERATED = "artifacts/generated"
PROTOCOL = ROOT / f"results/CodeDye/{GENERATED}/codedye_v4_query_budget_support_protocol_v1_{DATE}.json"
DEFAULT_INPUT = ROOT / f"results/CodeDye/{GENERATED}/codedye_v4_query_budget_support_results_{DATE}.json"
OUT = ROOT / f"results/CodeDye/{GENERATED}/codedye_v4_query_budget_support_postrun_gate_v1_{DATE}.json"


REQUIRED_RECORD_FIELDS = [
    "task_id",
    "attack_id",
    "run_id",
    "provider_name",
    "provider_mode_resolved",
    "provider_or_backbone",
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
    "selected_utility_score",
    "decision",
    "threshold_version",
]


def wilson(k: int, n: int) -> dict[str, float | int | str]:
    if n <= 0:
        return {"k": k, "n": n, "rate": 0.0, "low": 0.0, "high": 1.0, "method": "wilson"}
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


def missing_fields(row: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_RECORD_FIELDS if field not in row or row.get(field) in {None, ""}]


def write(payload: dict[str, Any]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def blocked(blockers: list[str], records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = records or []
    return {
        "schema_version": "codedye_v4_query_budget_support_postrun_gate_v1",
        "date": DATE,
        "project": "CodeDye",
        "claim_bearing": False,
        "gate_pass": False,
        "support_experiment_admitted": False,
        "formal_v4_main_claim_allowed": False,
        "formal_high_recall_detection_claim_allowed": False,
        "result_path": str(DEFAULT_INPUT.relative_to(ROOT)),
        "record_count": len(rows),
        "required_record_fields": REQUIRED_RECORD_FIELDS,
        "blockers": blockers,
        "policy": "Fail closed. This gate can only admit support-only query-budget evidence; it cannot promote a main claim.",
    }


def main() -> int:
    blockers: list[str] = []
    if not PROTOCOL.exists():
        payload = blocked(["protocol_missing"])
        write(payload)
        print(json.dumps({"gate_pass": False, "blockers": payload["blockers"]}, ensure_ascii=True))
        return 1
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if protocol.get("gate_pass") is not True or protocol.get("frozen") is not True:
        blockers.append("protocol_not_frozen_or_not_passed")
    if not DEFAULT_INPUT.exists():
        payload = blocked(blockers + ["result_missing"])
        write(payload)
        print(json.dumps({"gate_pass": False, "blockers": payload["blockers"]}, ensure_ascii=True))
        return 1

    result = json.loads(DEFAULT_INPUT.read_text(encoding="utf-8"))
    raw_records = result.get("records", []) if isinstance(result, dict) else []
    records = [row for row in raw_records if isinstance(row, dict)]
    summary = result.get("summary", {}) if isinstance(result, dict) else {}
    targeted = result.get("targeted_repair_health", {}) if isinstance(result, dict) else {}

    if result.get("schema_version") != "codedye_attack_matrix_live_support_v1":
        blockers.append("payload_schema_not_support_live")
    if result.get("claim_bearing") is not False:
        blockers.append("payload_claim_bearing_not_false")
    if result.get("formal_claim_allowed") is not False:
        blockers.append("payload_formal_claim_allowed_not_false")
    if result.get("status") not in {"support_repair_health_passed", "support_only_passed", "passed"}:
        blockers.append("payload_status_not_support_passed")
    if len(records) < int(protocol.get("minimum_live_records", 20) or 20):
        blockers.append("record_count_below_protocol_minimum")
    if any(str(row.get("attack_id", "")) != "query_budget_drop" for row in records):
        blockers.append("non_query_budget_drop_rows_present")
    if any(row.get("claim_bearing") is not False for row in records):
        blockers.append("claim_bearing_rows_present")
    if any(row.get("claim_bearing_attack_evidence") is not False for row in records):
        blockers.append("claim_attack_rows_present")
    if any(row.get("support_only_not_claim_bearing") is not True for row in records):
        blockers.append("non_support_only_rows_present")
    if any(str(row.get("provider_name", "")).lower() != "deepseek" for row in records):
        blockers.append("non_deepseek_rows_present")
    if any(str(row.get("provider_mode_resolved", "")).lower() != "live" for row in records):
        blockers.append("non_live_rows_present")
    schema_missing_rows = sum(1 for row in records if missing_fields(row))
    if schema_missing_rows:
        blockers.append("required_record_schema_missing")
    missing_hash_rows = sum(
        1
        for row in records
        if not row.get("raw_provider_transcript_hash")
        or not row.get("structured_payload_hash")
        or not row.get("prompt_hash")
        or not row.get("task_hash")
        or not row.get("record_hash")
    )
    if missing_hash_rows:
        blockers.append("row_hash_or_payload_hash_missing")
    utility_failures = sum(1 for row in records if row.get("utility_admissible_for_attack_claim") is not True)
    if utility_failures:
        blockers.append("utility_inadmissible_support_rows_present")
    if targeted.get("repair_health_pass") is not True:
        blockers.append("targeted_support_health_not_passed")

    decisions = Counter(str(row.get("decision", "missing")) for row in records)
    signal_count = int(decisions.get("contamination_signal_detected", 0))
    payload = {
        "schema_version": "codedye_v4_query_budget_support_postrun_gate_v1",
        "date": DATE,
        "project": "CodeDye",
        "claim_bearing": False,
        "gate_pass": not blockers,
        "support_experiment_admitted": not blockers,
        "formal_v4_main_claim_allowed": False,
        "formal_high_recall_detection_claim_allowed": False,
        "formal_contamination_prevalence_claim_allowed": False,
        "protocol": str(PROTOCOL.relative_to(ROOT)),
        "result_path": str(DEFAULT_INPUT.relative_to(ROOT)),
        "record_count": len(records),
        "provider_modes": sorted({str(row.get("provider_mode_resolved", "")) for row in records}),
        "attack_ids": sorted({str(row.get("attack_id", "")) for row in records}),
        "schema_missing_rows": schema_missing_rows,
        "missing_hash_rows": missing_hash_rows,
        "utility_inadmissible_rows": utility_failures,
        "decision_counts": dict(sorted(decisions.items())),
        "query_budget_signal_ci95": wilson(signal_count, len(records)),
        "source_summary": summary,
        "targeted_repair_health": targeted,
        "main_claim_boundary": {
            "v3_main_denominator_unchanged": True,
            "v4_rows_support_only": True,
            "threshold_adjusted_after_result": False,
            "support_rows_enter_main_table": False,
        },
        "required_record_fields": REQUIRED_RECORD_FIELDS,
        "blockers": blockers,
    }
    write(payload)
    print(json.dumps({"gate_pass": payload["gate_pass"], "record_count": len(records), "blockers": blockers}, ensure_ascii=True))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
