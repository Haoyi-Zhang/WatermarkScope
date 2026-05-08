from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/CodeDye/artifacts/generated/codedye_final_claim_lock_v2_{DATE}.json"
ARTIFACT_MD = ROOT / f"results/CodeDye/artifacts/generated/codedye_final_claim_lock_v2_{DATE}.md"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists() or not ARTIFACT_MD.exists():
        fail("CodeDye final claim lock v2 artifacts are missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "codedye_final_claim_lock_v2":
        fail("Unexpected CodeDye final claim lock v2 schema.")
    if payload.get("claim_bearing") is not False:
        fail("CodeDye final claim lock v2 must be non-claim-bearing.")
    if payload.get("gate_pass") is not True or payload.get("bestpaper_ready") is not True:
        fail("CodeDye v2 should be ready for its scoped sparse null-audit claim.")
    for field in (
        "formal_high_recall_detection_claim_allowed",
        "formal_contamination_prevalence_claim_allowed",
        "formal_provider_accusation_claim_allowed",
    ):
        if payload.get(field) is not False:
            fail(f"CodeDye v2 overclaim flag must remain false: {field}")
    metrics = payload["locked_effect_surface"]
    if metrics["claim_rows"] != 300:
        fail("CodeDye v2 claim denominator must be 300.")
    if metrics["final_signal"] != 4 or metrics["null_not_rejected"] != 296:
        fail("CodeDye v2 sparse signal surface drifted.")
    if metrics["missing_hash_rows"] != 0 or metrics["mock_or_replay_rows"] != 0:
        fail("CodeDye v2 live/hash integrity must be clean.")
    if metrics["support_rows_in_candidate"] != 0:
        fail("CodeDye v2 must not include support rows in the main candidate.")
    if metrics["negative_control_false_positive"] != 0 or metrics["negative_control_rows"] != 300:
        fail("CodeDye v2 negative controls drifted.")
    if metrics["utility_topup_policy"]["contamination_score_used_for_selection"] is not False:
        fail("CodeDye utility top-up must not use contamination score selection.")
    if payload.get("remaining_blockers"):
        fail("CodeDye v2 should not retain P1/P2 blockers for the scoped claim.")
    print("[OK] CodeDye final claim lock v2 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
