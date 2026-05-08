from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/CodeDye/artifacts/generated/codedye_live_traceability_manifest_v1_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("CodeDye live traceability manifest is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "codedye_live_traceability_manifest_v1":
        fail("Unexpected CodeDye live traceability schema.")
    if payload.get("claim_bearing") is not False:
        fail("CodeDye traceability manifest must be non-claim-bearing.")
    if payload.get("gate_pass") is not True:
        fail("CodeDye legacy row traceability gate should pass for available fields.")
    if payload.get("formal_v3_live_claim_allowed") is not False:
        fail("CodeDye traceability manifest must not allow v3 live claim.")
    if payload.get("claim_row_count") != 300 or payload.get("row_manifest_count") != 300:
        fail("CodeDye traceability manifest must bind 300 legacy claim rows.")
    missing_fresh = payload.get("missing_fresh_v3_required_fields", {})
    for field in ("raw_provider_transcript_hash", "prompt_hash", "structured_payload_hash", "task_hash"):
        if int(missing_fresh.get(field, 0)) != 300:
            fail(f"CodeDye legacy source should explicitly expose missing fresh-v3 field: {field}")
    if payload.get("final_paper_signal_count_from_boundary_gate") != 6:
        fail("CodeDye boundary-gate signal count must remain visible.")
    if payload.get("source_full_eval_signal_count") != 5:
        fail("CodeDye legacy full-eval source signal count drifted.")
    print("[OK] CodeDye live traceability manifest verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
