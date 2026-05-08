from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/CodeDye/artifacts/generated/codedye_final_claim_lock_v1_{DATE}.json"
ARTIFACT_MD = ROOT / f"results/CodeDye/artifacts/generated/codedye_final_claim_lock_v1_{DATE}.md"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists() or not ARTIFACT_MD.exists():
        fail("CodeDye final claim-lock artifacts are missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "codedye_final_claim_lock_v1":
        fail("Unexpected CodeDye final claim-lock schema.")
    if payload.get("claim_bearing") is not False:
        fail("CodeDye final claim-lock must be non-claim-bearing.")
    if payload.get("gate_pass") is not True:
        fail("CodeDye current claim lock should pass for sparse null-audit framing.")
    if payload.get("bestpaper_ready") is not False:
        fail("CodeDye must not be marked best-paper-ready before fresh v3 postrun evidence.")
    if payload.get("formal_curator_side_null_audit_claim_allowed") is not True:
        fail("CodeDye sparse null-audit claim should be allowed.")
    for field in (
        "formal_high_recall_detection_claim_allowed",
        "formal_contamination_prevalence_claim_allowed",
        "formal_provider_accusation_claim_allowed",
        "formal_v3_live_claim_allowed",
        "upgrade_claim_allowed",
    ):
        if payload.get(field) is not False:
            fail(f"CodeDye overclaim field must remain false: {field}")
    surface = payload["locked_effect_surface"]
    if surface["claim_rows"] != 300 or surface["final_signal"] != 6:
        fail("CodeDye locked live signal drifted.")
    if surface["positive_control_detected"] != 170 or surface["positive_control_denominator"] != 300:
        fail("CodeDye positive-control sensitivity drifted.")
    if surface["negative_control_false_positive"] != 0 or surface["negative_control_rows"] != 300:
        fail("CodeDye negative-control surface drifted.")
    if surface["support_rows_excluded"] != 806:
        fail("CodeDye support exclusion count drifted.")
    required = {
        "fresh_v3_live_result_missing",
        "positive_control_sensitivity_only_170_of_300",
        "live_signal_only_6_of_300",
    }
    if not required.issubset(set(payload.get("remaining_blockers", []))):
        fail("CodeDye remaining blockers do not preserve effect limitations.")
    print("[OK] CodeDye final claim-lock verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
