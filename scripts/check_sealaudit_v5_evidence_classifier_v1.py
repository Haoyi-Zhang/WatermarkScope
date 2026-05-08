from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_v5_evidence_classifier_v1_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("SealAudit v5 evidence classifier artifact is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("claim_bearing") is not False:
        fail("SealAudit v5 classifier must be non-claim-bearing.")
    if payload.get("formal_v5_claim_allowed") is not False:
        fail("SealAudit v5 classifier must keep v5 claim blocked.")
    if payload.get("gate_pass") is not False:
        fail("SealAudit v5 classifier must fail closed without final row-level evidence.")
    if payload["current_claim_surface"]["decisive_coverage_locked"] != "81/960":
        fail("SealAudit locked decisive coverage drifted.")
    if payload["claim_eligible_candidate_count"] != 0:
        fail("A v5 candidate was classified as claim-eligible; inspect manually before promotion.")
    required = {
        "final_v5_claim_bearing_rows_missing",
        "v5_coverage_risk_frontier_missing",
        "v5_threshold_sensitivity_missing",
        "visible_marker_diagnostic_boundary_missing",
    }
    blockers = set(payload.get("blockers", []))
    missing = required - blockers
    if missing:
        fail("Missing expected v5 blockers: " + ", ".join(sorted(missing)))
    print("[OK] SealAudit v5 evidence classifier verified fail-closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
