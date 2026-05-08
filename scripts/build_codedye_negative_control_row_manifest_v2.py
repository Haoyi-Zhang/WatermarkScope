from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
SOURCE = ROOT / "results/CodeDye/artifacts/generated/null_calibration_negative_controls_300_20260505_remote.json"
OUT = ROOT / f"results/CodeDye/artifacts/generated/codedye_negative_control_row_hash_manifest_v2_{DATE}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def row_hash(row: Any) -> str:
    return sha256_bytes(json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("records", "rows", "results", "negative_controls", "controls"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def main() -> int:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = rows_from_payload(payload)
    row_entries: list[dict[str, Any]] = []
    fp_count = 0
    for idx, row in enumerate(rows):
        decision = str(row.get("decision", row.get("decision_status", row.get("final_decision", "")))).lower()
        detected = bool(row.get("detected")) or decision in {
            "contamination_signal_detected",
            "detected",
            "positive",
            "reject_null",
        }
        fp_count += 1 if detected else 0
        row_entries.append(
            {
                "row_index": idx,
                "row_id": str(row.get("record_id") or row.get("task_id") or row.get("case_id") or f"negative_control_row_{idx:04d}"),
                "task_id": row.get("task_id"),
                "family": row.get("family") or row.get("task_family"),
                "language": row.get("language"),
                "decision": row.get("decision", row.get("decision_status", row.get("final_decision"))),
                "claim_bearing": False,
                "negative_control": True,
                "row_sha256": row_hash(row),
            }
        )
    blockers = []
    if len(rows) != 300:
        blockers.append("negative_control_row_count_not_300")
    if fp_count != 0:
        blockers.append("negative_control_false_positive_present")
    out = {
        "schema_version": "codedye_negative_control_row_hash_manifest_v2",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": not blockers,
        "source_artifact": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": sha256_file(SOURCE),
        "source_bytes": SOURCE.stat().st_size,
        "row_count": len(rows),
        "false_positive_count": fp_count,
        "row_hash_count": len(row_entries),
        "row_hashes": row_entries,
        "blockers": blockers,
        "reviewer_boundary": "Row hashes provide inspectability for preserved negative controls; these rows remain false-positive controls and do not affect the 300 live-audit numerator.",
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("[OK] Wrote CodeDye negative-control row hash manifest v2.")
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
