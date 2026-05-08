from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/CodeDye/artifacts/generated/codedye_v3_postrun_promotion_gate_v1_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("CodeDye v3 postrun promotion gate is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "codedye_v3_postrun_promotion_gate_v1":
        fail("Unexpected CodeDye v3 postrun promotion schema.")
    if payload.get("claim_bearing") is not False:
        fail("Postrun promotion gate itself must be non-claim-bearing.")
    if payload.get("formal_high_recall_detection_claim_allowed") is not False:
        fail("High-recall detection claim must remain forbidden.")
    if payload.get("formal_contamination_prevalence_claim_allowed") is not False:
        fail("Prevalence claim must remain forbidden.")
    prereq = payload.get("prerequisite_gates", {})
    for field in ("protocol_freeze_gate_pass", "positive_negative_control_gate_pass", "support_exclusion_gate_pass"):
        if prereq.get(field) is not True:
            fail(f"Prerequisite gate is not passing: {field}")
    if payload.get("gate_pass") is False:
        blockers = set(payload.get("blockers", []))
        if "fresh_v3_live_result_missing" not in blockers and "candidate_schema_not_v3_canonical_live" not in blockers:
            fail("Blocked CodeDye postrun gate lacks an expected fail-closed blocker.")
        if payload.get("formal_v3_live_claim_allowed") is not False:
            fail("Blocked postrun gate must not allow v3 live claim.")
    else:
        metrics = payload.get("postrun_metrics", {})
        if payload.get("formal_v3_live_claim_allowed") is not True:
            fail("Passing postrun gate should explicitly allow only scoped v3 live claim.")
        if metrics.get("record_count") != 300 or metrics.get("claim_denominator") != 300:
            fail("Passing CodeDye v3 postrun gate must bind exactly 300 claim rows.")
        if metrics.get("missing_hash_rows") != 0 or metrics.get("mock_or_replay_rows") != 0:
            fail("Passing CodeDye v3 postrun gate cannot have missing hashes or replay/mock rows.")
    print("[OK] CodeDye v3 postrun promotion gate verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
