from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v1_{DATE}.json"
ARTIFACT_MD = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v1_{DATE}.md"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists() or not ARTIFACT_MD.exists():
        fail("SealAudit final claim-lock artifacts are missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "sealaudit_final_claim_lock_v1":
        fail("Unexpected SealAudit final claim-lock schema.")
    if payload.get("claim_bearing") is not False:
        fail("SealAudit final claim-lock must be non-claim-bearing.")
    if payload.get("gate_pass") is not True:
        fail("SealAudit current claim lock should pass for selective marker-hidden triage.")
    if payload.get("bestpaper_ready") is not False:
        fail("SealAudit must not be marked best-paper-ready before final v5 evidence.")
    if payload.get("formal_marker_hidden_selective_triage_claim_allowed") is not True:
        fail("SealAudit marker-hidden selective triage claim should be allowed.")
    for field in (
        "formal_v5_claim_allowed",
        "formal_security_certificate_claim_allowed",
        "formal_harmlessness_claim_allowed",
        "formal_automatic_classifier_claim_allowed",
        "upgrade_claim_allowed",
    ):
        if payload.get(field) is not False:
            fail(f"SealAudit overclaim field must remain false: {field}")
    surface = payload["locked_effect_surface"]
    if surface["marker_hidden_claim_rows"] != 960 or surface["marker_visible_diagnostic_rows"] != 320:
        fail("SealAudit marker-hidden/visible denominator drifted.")
    if surface["decisive_count"] != 81 or surface["needs_review_count"] != 879:
        fail("SealAudit selective-triage distribution drifted.")
    if surface["unsafe_pass_count"] != 0:
        fail("SealAudit unsafe-pass count must remain zero.")
    if surface["expert_review_role_support_only"] is not True:
        fail("SealAudit expert review must remain role-based support only.")
    required = {
        "decisive_coverage_only_81_of_960",
        "v5_final_evidence_not_claim_bearing",
        "v5_coverage_risk_frontier_missing",
    }
    if not required.issubset(set(payload.get("remaining_blockers", []))):
        fail("SealAudit remaining blockers do not preserve coverage/v5 limitations.")
    print("[OK] SealAudit final claim-lock verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
