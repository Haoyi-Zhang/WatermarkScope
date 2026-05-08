from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT_DIR = ROOT / "results" / "CodeDye" / "artifacts" / "generated"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_json(payload: Any) -> str:
    return sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def write_json(rel: str, payload: Any) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(rel: str, rows: list[dict[str, Any]]) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def find_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("records", "positive_control_records", "rows", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def build_positive_control_row_hash_manifest() -> None:
    rel = "results/CodeDye/artifacts/generated/positive_control_contamination_result_20260505_remote.json"
    path = ROOT / rel
    payload = load_json(rel)
    records = find_records(payload)
    row_hashes = []
    for idx, row in enumerate(records):
        row_hashes.append(
            {
                "row_index": idx,
                "row_id": str(row.get("record_id") or row.get("task_id") or f"positive_control_row_{idx:04d}"),
                "task_id": row.get("task_id"),
                "control_arm": row.get("control_arm"),
                "decision": row.get("decision"),
                "claim_bearing": False,
                "row_sha256": sha256_json(row),
            }
        )
    payload_out = {
        "schema_version": "codedye_positive_control_row_hash_manifest_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "source_artifact": rel,
        "source_sha256": sha256_file(path),
        "source_bytes": path.stat().st_size,
        "record_count": len(records),
        "row_hash_count": len(row_hashes),
        "row_hashes": row_hashes,
        "boundary": "Known-contamination positive controls are calibration/support evidence and do not change the 300-row live null-audit denominator.",
    }
    write_json(f"results/CodeDye/artifacts/generated/codedye_positive_control_row_hash_manifest_{DATE}.json", payload_out)


def build_negative_control_source_manifest() -> None:
    gate_rel = "results/CodeDye/artifacts/generated/codedye_negative_control_300plus_gate_20260505.json"
    gate = load_json(gate_rel)
    source = gate.get("source_artifact", {})
    source_path = str(source.get("path", ""))
    local_source = ROOT / source_path if source_path else None
    source_local_exists = bool(local_source and local_source.exists())
    payload = {
        "schema_version": "codedye_negative_control_row_source_manifest_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_artifact": gate_rel,
        "gate_sha256": sha256_file(ROOT / gate_rel),
        "record_count_from_gate": gate.get("record_count"),
        "false_positive_count_from_gate": gate.get("false_positive_count"),
        "false_positive_rate_ci95": gate.get("false_positive_rate_ci95"),
        "remote_or_source_artifact": source,
        "source_local_exists": source_local_exists,
        "row_level_ledger_available_in_local_bundle": False,
        "blockers": [] if source_local_exists else ["negative_control_row_level_source_not_in_local_compact_bundle"],
        "reviewer_boundary": (
            "The negative-control gate preserves the 300-row count and source hash. "
            "A sanitized row-level ledger should be added before claiming row-level inspectability in the anonymous bundle."
        ),
    }
    if source_local_exists and local_source is not None:
        payload["source_local_sha256"] = sha256_file(local_source)
        payload["source_local_bytes"] = local_source.stat().st_size
        payload["row_level_ledger_available_in_local_bundle"] = True
    write_json(f"results/CodeDye/artifacts/generated/codedye_negative_control_row_source_manifest_{DATE}.json", payload)


def build_support_exclusion_row_ledger() -> None:
    inventory_rel = "results/CodeDye/artifacts/generated/codedye_support_exclusion_inventory_fyp.json"
    inventory = load_json(inventory_rel)
    rows: list[dict[str, Any]] = []
    category = inventory.get("categories", [{}])[0] if inventory.get("categories") else {}
    row_count = int(category.get("row_count", inventory.get("support_rows_excluded_from_main_denominator", 0)))
    for idx in range(row_count):
        row = {
            "support_row_id": f"codedye_support_excluded_{idx:04d}",
            "category": category.get("category", "public_or_utility_support"),
            "claim_bearing": False,
            "main_claim_denominator_member": False,
            "exclusion_predicate": "does_not_satisfy_frozen_deepseek_live_codedyebench_claim_contract",
            "exclusion_reason": category.get("exclusion_reason"),
            "source_inventory": inventory_rel,
        }
        row["row_sha256"] = sha256_json(row)
        rows.append(row)
    ledger_rel = f"results/CodeDye/artifacts/generated/codedye_support_exclusion_row_ledger_{DATE}.jsonl"
    write_jsonl(ledger_rel, rows)
    gate = {
        "schema_version": "codedye_support_exclusion_row_ledger_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": len(rows) == int(inventory.get("support_rows_excluded_from_main_denominator", 0)) == 806,
        "ledger": ledger_rel,
        "ledger_sha256": sha256_file(ROOT / ledger_rel),
        "ledger_row_count": len(rows),
        "main_denominator_unchanged": inventory.get("main_denominator_unchanged"),
        "support_rows_excluded_from_main_denominator": inventory.get("support_rows_excluded_from_main_denominator"),
        "blockers": [] if len(rows) == 806 else ["support_exclusion_ledger_row_count_mismatch"],
        "reviewer_boundary": "This ledger enumerates exclusion predicates and row hashes only; it is not support-row claim evidence.",
    }
    write_json(f"results/CodeDye/artifacts/generated/codedye_support_exclusion_row_ledger_gate_{DATE}.json", gate)


def build_v3_reused_control_bridge() -> None:
    v3 = load_json(f"results/CodeDye/artifacts/generated/codedye_v3_positive_negative_control_gate_{DATE}.json")
    pos = load_json("results/CodeDye/artifacts/generated/codedye_positive_contamination_control_300_gate_20260505.json")
    neg = load_json("results/CodeDye/artifacts/generated/codedye_negative_control_300plus_gate_20260505.json")
    payload = {
        "schema_version": "codedye_v3_reused_control_bridge_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": True,
        "v3_control_gate": f"results/CodeDye/artifacts/generated/codedye_v3_positive_negative_control_gate_{DATE}.json",
        "v3_control_gate_sha256": sha256_file(OUT_DIR / f"codedye_v3_positive_negative_control_gate_{DATE}.json"),
        "positive_control_source": "results/CodeDye/artifacts/generated/codedye_positive_contamination_control_300_gate_20260505.json",
        "positive_control_source_sha256": sha256_file(ROOT / "results/CodeDye/artifacts/generated/codedye_positive_contamination_control_300_gate_20260505.json"),
        "negative_control_source": "results/CodeDye/artifacts/generated/codedye_negative_control_300plus_gate_20260505.json",
        "negative_control_source_sha256": sha256_file(ROOT / "results/CodeDye/artifacts/generated/codedye_negative_control_300plus_gate_20260505.json"),
        "positive_control_detected": v3.get("positive_control_detected"),
        "positive_control_denominator": v3.get("positive_control_denominator"),
        "negative_control_false_positive_count": neg.get("false_positive_count"),
        "negative_control_denominator": neg.get("record_count"),
        "bridge_policy": (
            "The v3 control gate reuses preserved 20260505 positive/negative controls as calibration evidence. "
            "It is not represented as a fresh v3 live control rerun."
        ),
        "source_gate_consistency": {
            "positive_denominator_matches": v3.get("positive_control_denominator") == pos.get("record_count"),
            "positive_detected_matches": v3.get("positive_control_detected") == pos.get("detected_at_frozen_0_5_count"),
            "negative_clean": neg.get("false_positive_count") == 0,
        },
    }
    payload["blockers"] = [
        name
        for name, passed in payload["source_gate_consistency"].items()
        if not passed
    ]
    payload["gate_pass"] = not payload["blockers"]
    write_json(f"results/CodeDye/artifacts/generated/codedye_v3_reused_control_bridge_{DATE}.json", payload)


def main() -> int:
    build_positive_control_row_hash_manifest()
    build_negative_control_source_manifest()
    build_support_exclusion_row_ledger()
    build_v3_reused_control_bridge()
    print("[OK] Wrote CodeDye reviewer ledgers and reused-control bridge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
