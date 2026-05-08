from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
DEFAULT_INPUT = ROOT / f"results/CodeDye/artifacts/generated/codedye_v3_health_live_results_{DATE}.json"
OUT = ROOT / f"results/CodeDye/artifacts/generated/codedye_v3_health_live_gate_v1_{DATE}.json"


REQUIRED_RECORD_FIELDS = [
    "task_id",
    "attack_id",
    "run_id",
    "provider_name",
    "provider_mode_resolved",
    "prompt_hash",
    "raw_provider_transcript_hash",
    "structured_payload_hash",
    "task_hash",
    "record_hash",
    "claim_bearing",
    "decision",
    "threshold_version",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def missing_fields(row: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_RECORD_FIELDS if field not in row or row.get(field) in {None, ""}]


def main() -> int:
    blockers: list[str] = []
    exists = DEFAULT_INPUT.exists()
    payload: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    if not exists:
        blockers.append("codedye_health_live_result_missing")
    else:
        payload = json.loads(DEFAULT_INPUT.read_text(encoding="utf-8"))
        raw_records = payload.get("records", [])
        records = [row for row in raw_records if isinstance(row, dict)] if isinstance(raw_records, list) else []
        if payload.get("schema_version") != "codedye_attack_matrix_live_support_v1":
            blockers.append("health_payload_schema_not_support_live")
        if payload.get("claim_bearing") is not False:
            blockers.append("health_payload_claim_bearing")
        if payload.get("formal_claim_allowed") is not False:
            blockers.append("health_payload_formal_claim_allowed")
        if payload.get("status") not in {"support_repair_health_passed", "support_only_passed", "passed"}:
            blockers.append("health_payload_status_not_passed")
        if len(records) != 2:
            blockers.append("health_record_count_not_2")
        if any(row.get("claim_bearing") is not False for row in records):
            blockers.append("health_rows_claim_bearing")
        if any(str(row.get("provider_name", "")).lower() != "deepseek" for row in records):
            blockers.append("health_rows_not_deepseek")
        if any(str(row.get("provider_mode_resolved", "")).lower() != "live" for row in records):
            blockers.append("health_rows_not_live")
        if any(missing_fields(row) for row in records):
            blockers.append("health_rows_missing_required_schema")

    out_payload = {
        "schema_version": "codedye_v3_health_live_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": not blockers,
        "formal_v3_live_claim_allowed": False,
        "health_result": str(DEFAULT_INPUT.relative_to(ROOT)),
        "health_result_exists": exists,
        "record_count": len(records),
        "provider_modes": sorted({str(row.get("provider_mode_resolved", "")) for row in records}),
        "decisions": sorted({str(row.get("decision", "")) for row in records}),
        "required_record_fields": REQUIRED_RECORD_FIELDS,
        "blockers": blockers,
        "policy": "This gate validates provider connectivity/schema only. It is not claim-bearing and cannot promote the 300-row v3 result.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
