from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_scan_v1_{DATE}.json"
ROWS = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_row_receipts_v1_{DATE}.jsonl"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists() or not ROWS.exists():
        fail("ProbeTrace anti-leakage scan artifacts are missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "probetrace_anti_leakage_scan_v1":
        fail("Unexpected ProbeTrace anti-leakage schema.")
    if payload.get("claim_bearing") is not False:
        fail("ProbeTrace anti-leakage scan must be non-claim-bearing.")
    if payload.get("gate_pass") is not True:
        fail("ProbeTrace anti-leakage scan should pass for current single-owner claim.")
    if payload.get("formal_multi_owner_claim_allowed") is not False:
        fail("ProbeTrace anti-leakage scan must not allow multi-owner claim.")
    checks = payload["checks"]
    if checks["anti_leakage_receipt_count"] != 300 or checks["apis300_record_count"] != 300:
        fail("ProbeTrace anti-leakage scan must bind 300 APIS/control receipts.")
    if checks["control_false_attribution_count"] != 0 or checks["control_owner_id_emitted_count"] != 0:
        fail("ProbeTrace control leakage detected.")
    if checks["multi_owner_input_owner_key_material_rows"] != 0 or checks["multi_owner_input_claim_bearing_rows"] != 0:
        fail("ProbeTrace multi-owner input package leaked key material or claim-bearing rows.")
    row_count = sum(1 for line in ROWS.read_text(encoding="utf-8").splitlines() if line.strip())
    if row_count != 300:
        fail("ProbeTrace anti-leakage row receipt count drifted.")
    print("[OK] ProbeTrace anti-leakage scan verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
