from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_v5_postrun_promotion_gate_v2_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("SealAudit v5 postrun promotion gate v2 is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "sealaudit_v5_postrun_promotion_gate_v2":
        fail("Unexpected SealAudit v5 postrun promotion v2 schema.")
    if payload.get("claim_bearing") is not False:
        fail("Postrun promotion gate must be non-claim-bearing.")
    if payload.get("gate_pass") is not True or payload.get("materialization_gate_pass") is not True:
        fail("SealAudit v5 v2 materialization gate should pass.")
    metrics = payload.get("postrun_metrics", {})
    if metrics.get("marker_hidden_claim_rows") != 960 or metrics.get("materialized_row_count") != 960:
        fail("SealAudit v5 v2 denominator must be 960 marker-hidden rows.")
    if metrics.get("unique_case_count") != 320:
        fail("SealAudit v5 v2 unique case count must be 320.")
    if metrics.get("unsafe_pass_count") != 0:
        fail("SealAudit v5 v2 cannot contain unsafe-pass rows.")
    if metrics.get("visible_marker_claim_rows") != 0:
        fail("Visible-marker rows must not enter v5 v2 claim surface.")
    if metrics.get("threshold_sweep_count", 0) < 6:
        fail("Threshold sensitivity must include a nontrivial sweep.")
    for field in (
        "formal_security_certificate_claim_allowed",
        "formal_harmlessness_claim_allowed",
        "formal_automatic_classifier_claim_allowed",
    ):
        if payload.get(field) is not False:
            fail(f"Forbidden overclaim flag must remain false: {field}")
    if payload.get("formal_v5_claim_allowed") is True and metrics.get("decisive_count", 0) <= 81:
        fail("v5 coverage upgrade cannot be allowed without improving over 81/960.")
    print("[OK] SealAudit v5 postrun promotion gate v2 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
