from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
SOURCE = ROOT.parent / "CodeDye" / "artifacts" / "generated" / "full_eval_results.json"
OUT = ROOT / f"results/CodeDye/artifacts/generated/codedye_live_traceability_manifest_v1_{DATE}.json"


REQUIRED_MAIN_CLAIM_FIELDS = (
    "task_id",
    "provider_mode_resolved",
    "provider_name",
    "contamination_scoring_status",
    "task_source",
    "candidate_payload_capture_complete",
    "candidate_payload_schema_version",
    "candidate_sample_count",
    "run_checkpoint_key",
    "evidence_trace",
)

REQUIRED_FRESH_V3_FIELDS = (
    "prompt_hash",
    "raw_provider_transcript_hash",
    "structured_payload_hash",
    "task_hash",
    "record_hash",
    "threshold_version",
    "claim_bearing",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(row: dict[str, Any]) -> str:
    return sha256_bytes(json.dumps(row, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))


def wilson(k: int, n: int) -> dict[str, Any]:
    if n <= 0:
        return {"k": k, "n": n, "rate": 0.0, "low": 0.0, "high": 1.0, "method": "wilson"}
    z = 1.959963984540054
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return {"k": k, "n": n, "rate": phat, "low": max(0.0, center - half), "high": min(1.0, center + half), "method": "wilson"}


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"[FAIL] Source full_eval_results missing: {SOURCE}")
    source_bytes = SOURCE.read_bytes()
    payload = json.loads(source_bytes.decode("utf-8"))
    records = payload.get("records", [])
    if not isinstance(records, list):
        raise SystemExit("[FAIL] Source records must be a list.")
    claim_rows = [
        row
        for row in records
        if isinstance(row, dict)
        and str(row.get("provider_mode_resolved", "")) == "live"
        and str(row.get("contamination_scoring_status", row.get("scoring_status", ""))) == "scored"
        and str(row.get("task_source", row.get("source", ""))) != "external_checkout"
    ]
    row_manifests: list[dict[str, Any]] = []
    missing_main_fields = {field: 0 for field in REQUIRED_MAIN_CLAIM_FIELDS}
    missing_fresh_fields = {field: 0 for field in REQUIRED_FRESH_V3_FIELDS}
    signal_count = 0
    for index, row in enumerate(claim_rows):
        for field in REQUIRED_MAIN_CLAIM_FIELDS:
            if row.get(field) in (None, "", [], {}):
                missing_main_fields[field] += 1
        for field in REQUIRED_FRESH_V3_FIELDS:
            if row.get(field) in (None, "", [], {}):
                missing_fresh_fields[field] += 1
        contaminated = bool(row.get("contaminated", False))
        signal_count += 1 if contaminated else 0
        row_manifests.append(
            {
                "row_index": index,
                "task_id": str(row.get("task_id", "")),
                "provider_mode_resolved": str(row.get("provider_mode_resolved", "")),
                "provider_name": str(row.get("provider_name", "")),
                "task_source": str(row.get("task_source", "")),
                "contamination_scoring_status": str(row.get("contamination_scoring_status", "")),
                "decision": "contamination_signal_detected" if contaminated else "null_not_rejected",
                "row_sha256": canonical_hash(row),
                "candidate_payload_capture_complete": bool(row.get("candidate_payload_capture_complete", False)),
                "candidate_sample_count": int(row.get("candidate_sample_count", 0) or 0),
                "candidate_sample_hashes": [
                    str(sample.get("normalized_code_sha256", ""))
                    for sample in row.get("candidate_samples", [])
                    if isinstance(sample, dict)
                ],
                "run_checkpoint_key_sha256": sha256_bytes(str(row.get("run_checkpoint_key", "")).encode("utf-8")),
                "fresh_v3_hash_fields_present": {
                    field: row.get(field) not in (None, "", [], {})
                    for field in REQUIRED_FRESH_V3_FIELDS
                },
            }
        )
    blockers: list[str] = []
    if len(claim_rows) != 300:
        blockers.append(f"claim_row_count_not_300:{len(claim_rows)}")
    if signal_count != 5:
        blockers.append(f"source_full_eval_signal_count_not_5:{signal_count}")
    if any(missing_main_fields.values()):
        blockers.append("legacy_main_claim_traceability_fields_missing")
    if any(missing_fresh_fields.values()):
        blockers.append("fresh_v3_required_hash_fields_missing_in_legacy_source")
    out = {
        "schema_version": "codedye_live_traceability_manifest_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": len(claim_rows) == 300 and not any(missing_main_fields.values()),
        "formal_v3_live_claim_allowed": False,
        "legacy_source_only": True,
        "source_full_eval_path": "CodeDye/artifacts/generated/full_eval_results.json",
        "source_full_eval_location_note": "legacy sibling project source; no local absolute path is required for reviewer-facing use",
        "source_full_eval_sha256": sha256_bytes(source_bytes),
        "source_run_id": payload.get("run_id"),
        "claim_row_count": len(claim_rows),
        "source_full_eval_signal_count": signal_count,
        "source_full_eval_signal_ci95": wilson(signal_count, len(claim_rows)),
        "final_paper_signal_count_from_boundary_gate": 6,
        "signal_count_discrepancy_policy": "The preserved boundary gate remains the paper-level effect surface; this manifest exposes row-level traceability for the available legacy full-eval source and flags the mismatch as a required fresh-v3 rerun issue.",
        "missing_main_claim_traceability_fields": missing_main_fields,
        "missing_fresh_v3_required_fields": missing_fresh_fields,
        "fresh_v3_blockers": [
            field for field, count in missing_fresh_fields.items() if count
        ],
        "row_manifest_count": len(row_manifests),
        "row_manifests": row_manifests,
        "reviewer_boundary": "This artifact improves row-level inspection of the available legacy source. It does not repair missing raw transcript hashes and cannot promote the v3 live claim.",
        "blockers": blockers,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    return 0 if out["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
