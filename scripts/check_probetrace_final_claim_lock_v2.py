from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v2_{DATE}.json"
ARTIFACT_MD = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v2_{DATE}.md"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists() or not ARTIFACT_MD.exists():
        fail("ProbeTrace final claim-lock v2 artifacts are missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "probetrace_final_claim_lock_v2":
        fail("Unexpected ProbeTrace final claim-lock v2 schema.")
    if payload.get("claim_bearing") is not False:
        fail("ProbeTrace final claim-lock v2 must be non-claim-bearing.")
    if payload.get("gate_pass") is not True or payload.get("bestpaper_ready") is not True:
        fail("ProbeTrace v2 should be best-paper-ready for the scoped DeepSeek multi-owner claim.")
    for field in (
        "formal_provider_general_claim_allowed",
        "formal_cross_provider_claim_allowed",
        "formal_unbounded_student_transfer_claim_allowed",
    ):
        if payload.get(field) is not False:
            fail(f"ProbeTrace v2 overclaim field must remain false: {field}")
    for field in (
        "formal_single_active_owner_claim_allowed",
        "formal_source_bound_transfer_evidence_allowed",
        "formal_multi_owner_claim_allowed",
    ):
        if payload.get(field) is not True:
            fail(f"ProbeTrace v2 scoped claim flag should be true: {field}")
    surface = payload["locked_effect_surface"]
    if surface["apis300_attribution"]["k"] != 300 or surface["apis300_attribution"]["n"] != 300:
        fail("ProbeTrace APIS-300 surface drifted.")
    if surface["single_owner_negative_control_false_attribution"]["k"] != 0:
        fail("ProbeTrace single-owner negative controls drifted.")
    if surface["transfer_validation"]["k"] != 900 or surface["transfer_validation"]["n"] != 900:
        fail("ProbeTrace transfer-900 surface drifted.")
    if surface["multi_owner_row_count"] != 6000:
        fail("ProbeTrace v2 multi-owner row count must be 6000.")
    if surface["multi_owner_owner_count"] < 5 or surface["multi_owner_language_count"] < 3:
        fail("ProbeTrace v2 multi-owner breadth is insufficient.")
    if surface["multi_owner_positive_rows"] <= 0 or surface["multi_owner_control_rows"] <= 0:
        fail("ProbeTrace v2 positive/control rows missing.")
    if surface["multi_owner_control_to_positive_ratio"] < 4:
        fail("ProbeTrace v2 requires >=4x controls.")
    if surface["multi_owner_missing_hash_rows"] != 0 or surface["multi_owner_schema_missing_rows"] != 0:
        fail("ProbeTrace v2 hash/schema integrity must be clean.")
    if surface["multi_owner_claim_bearing_rows"] != surface["multi_owner_row_count"]:
        fail("ProbeTrace v2 live score-vector rows must all be claim-bearing canonical rows.")
    if surface["multi_owner_owner_heldout_rows"] <= 0 or surface["multi_owner_task_heldout_rows"] <= 0:
        fail("ProbeTrace v2 owner/task-heldout rows are required.")
    if surface["multi_owner_margin_auc"] is None:
        fail("ProbeTrace v2 margin AUC is required.")
    for role in ("true_owner", "wrong_owner", "null_owner", "random_owner", "same_provider_unwrap"):
        if role not in surface["multi_owner_control_role_counts"]:
            fail(f"ProbeTrace v2 missing control role: {role}")
    if surface["latency_query_frontier_gate_pass"] is not True:
        fail("ProbeTrace v2 latency/query frontier must remain clean.")
    if surface["anti_leakage_gate_pass"] is not True:
        fail("ProbeTrace v2 anti-leakage gate must remain clean.")
    if payload.get("remaining_blockers"):
        fail("ProbeTrace v2 should not retain P1/P2 blockers for the scoped claim.")
    print("[OK] ProbeTrace final claim-lock v2 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
