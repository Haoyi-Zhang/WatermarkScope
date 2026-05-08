from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/blackbox_artifact_naming_consistency_v1_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("Black-box artifact naming consistency gate is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "blackbox_artifact_naming_consistency_v1":
        fail("Unexpected naming consistency schema.")
    if payload.get("claim_bearing") is not False:
        fail("Naming consistency gate must be non-claim-bearing.")
    if payload.get("gate_pass") is not True:
        fail("Naming consistency gate has blockers: " + ", ".join(payload.get("blockers", [])))
    rows = payload.get("project_rows", [])
    if {row.get("project") for row in rows} != {"CodeDye", "ProbeTrace", "SealAudit"}:
        fail("Naming consistency project set is incomplete.")
    for row in rows:
        project = row["project"]
        if row.get("contract_gate_pass") is not True:
            fail(f"{project} fresh-run contract should pass.")
        if row.get("contract_claim_bearing") is not False:
            fail(f"{project} fresh-run contract must be non-claim-bearing.")
        if row.get("postrun_claim_bearing") is not False:
            fail(f"{project} postrun gate must be non-claim-bearing.")
        if row.get("canonical_output_bound_to_postrun") is not True:
            fail(f"{project} canonical output is not bound to postrun gate.")
        if "fresh_run_preflight_contract" not in str(row.get("contract_schema_version", "")):
            fail(f"{project} contract schema does not describe a fresh-run preflight.")
        if "postrun_promotion_gate" not in str(row.get("postrun_schema_version", "")):
            fail(f"{project} postrun schema does not describe a promotion gate.")
    print("[OK] Black-box artifact naming consistency verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
