from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v1_{DATE}.json"
ARTIFACT_MD = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v1_{DATE}.md"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists() or not ARTIFACT_MD.exists():
        fail("ProbeTrace final claim-lock artifacts are missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "probetrace_final_claim_lock_v1":
        fail("Unexpected ProbeTrace final claim-lock schema.")
    if payload.get("claim_bearing") is not False:
        fail("ProbeTrace final claim-lock must be non-claim-bearing.")
    if payload.get("gate_pass") is not True:
        fail("ProbeTrace current claim lock should pass for single-active-owner framing.")
    if payload.get("bestpaper_ready") is not False:
        fail("ProbeTrace must not be marked best-paper-ready before multi-owner postrun evidence.")
    if payload.get("formal_single_active_owner_claim_allowed") is not True:
        fail("ProbeTrace single-active-owner claim should be allowed.")
    if payload.get("formal_source_bound_transfer_evidence_allowed") is not True:
        fail("ProbeTrace source-bound transfer evidence should be allowed.")
    for field in ("formal_multi_owner_claim_allowed", "formal_provider_general_claim_allowed", "upgrade_claim_allowed"):
        if payload.get(field) is not False:
            fail(f"ProbeTrace overclaim field must remain false: {field}")
    surface = payload["locked_effect_surface"]
    if surface["apis300_attribution"]["k"] != 300 or surface["apis300_attribution"]["n"] != 300:
        fail("ProbeTrace APIS-300 surface drifted.")
    if surface["negative_control_false_attribution"]["k"] != 0 or surface["negative_control_false_attribution"]["n"] != 1200:
        fail("ProbeTrace negative control surface drifted.")
    if surface["transfer_validation"]["k"] != 900 or surface["transfer_validation"]["n"] != 900:
        fail("ProbeTrace transfer surface drifted.")
    if surface["multi_owner_input_rows"] != 6000 or surface["multi_owner_owner_count"] < 5:
        fail("ProbeTrace multi-owner input package drifted.")
    required = {
        "fresh_multi_owner_live_score_vectors_missing",
        "owner_task_heldout_margin_auc_missing",
        "perfect_single_owner_result_requires_anti_leakage_confirmation",
    }
    if not required.issubset(set(payload.get("remaining_blockers", []))):
        fail("ProbeTrace remaining blockers do not preserve anti-leakage limitations.")
    print("[OK] ProbeTrace final claim-lock verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
