from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v2_{DATE}.json"
ARTIFACT_MD = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v2_{DATE}.md"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists() or not ARTIFACT_MD.exists():
        fail("SealAudit final claim-lock v2 artifacts are missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "sealaudit_final_claim_lock_v2":
        fail("Unexpected SealAudit final claim-lock v2 schema.")
    if payload.get("claim_bearing") is not False:
        fail("SealAudit final claim-lock v2 must be non-claim-bearing.")
    if payload.get("gate_pass") is not True or payload.get("bestpaper_ready") is not True:
        fail("SealAudit v2 should be best-paper-ready for the scoped selective audit claim.")
    if payload.get("formal_v5_claim_allowed") is not True:
        fail("SealAudit v2 should allow the scoped v5 selective audit claim.")
    for field in (
        "formal_security_certificate_claim_allowed",
        "formal_harmlessness_claim_allowed",
        "formal_automatic_classifier_claim_allowed",
    ):
        if payload.get(field) is not False:
            fail(f"SealAudit v2 overclaim field must remain false: {field}")
    surface = payload["locked_effect_surface"]
    if surface["marker_hidden_claim_rows"] != 960 or surface["case_count"] != 320:
        fail("SealAudit v2 denominator drifted.")
    if surface["marker_visible_diagnostic_rows"] != 320 or surface["visible_marker_claim_rows"] != 0:
        fail("Visible-marker boundary drifted.")
    if surface["decisive_count"] != 320:
        fail("SealAudit v2 decisive count drifted from locked 320/960.")
    if surface["confirmed_benign_count"] != 80 or surface["confirmed_latent_risk_count"] != 240:
        fail("SealAudit v2 benign/risk decomposition drifted.")
    if surface["unsafe_pass_count"] != 0:
        fail("SealAudit v2 unsafe-pass count must remain zero.")
    if surface["expert_review_role_support_only"] is not True:
        fail("Expert review must remain role-based support only.")
    if payload.get("remaining_blockers"):
        fail("SealAudit v2 should not retain P1/P2 blockers for the scoped claim.")
    print("[OK] SealAudit final claim-lock v2 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
