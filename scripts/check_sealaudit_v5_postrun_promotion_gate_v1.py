from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_v5_postrun_promotion_gate_v1_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("SealAudit v5 postrun promotion gate is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "sealaudit_v5_postrun_promotion_gate_v1":
        fail("Unexpected SealAudit v5 postrun promotion schema.")
    if payload.get("claim_bearing") is not False:
        fail("SealAudit v5 postrun gate itself must be non-claim-bearing.")
    if payload.get("formal_security_certificate_claim_allowed") is not False:
        fail("Security-certificate claim must remain forbidden.")
    if payload.get("formal_harmlessness_claim_allowed") is not False:
        fail("Harmlessness claim must remain forbidden.")
    if payload.get("gate_pass") is False:
        blockers = set(payload.get("blockers", []))
        expected = {
            "v5_runner_receipt_not_passed",
            "v5_coverage_risk_frontier_missing",
            "v5_visible_marker_boundary_missing",
            "v5_threshold_sensitivity_missing",
            "v5_evidence_missing",
        }
        if not blockers.intersection(expected):
            fail("Blocked SealAudit v5 postrun gate lacks expected fail-closed blockers.")
        if payload.get("formal_v5_claim_allowed") is not False:
            fail("Blocked SealAudit v5 postrun gate must not allow v5 claim.")
    else:
        metrics = payload.get("postrun_metrics", {})
        if payload.get("formal_v5_claim_allowed") is not True:
            fail("Passing SealAudit v5 postrun gate should allow scoped v5 claim.")
        if metrics.get("marker_hidden_claim_rows") != 960:
            fail("Passing SealAudit v5 postrun gate must bind 960 hidden claim rows.")
        if metrics.get("unsafe_pass_count") != 0:
            fail("Passing SealAudit v5 postrun gate cannot include unsafe-pass rows.")
        if metrics.get("visible_marker_claim_or_non_diagnostic_rows") != 0:
            fail("Visible-marker rows must remain diagnostic-only.")
    print("[OK] SealAudit v5 postrun promotion gate verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
