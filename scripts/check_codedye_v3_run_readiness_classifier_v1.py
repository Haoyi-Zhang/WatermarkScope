from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/CodeDye/artifacts/generated/codedye_v3_run_readiness_classifier_v1_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("CodeDye v3 run-readiness classifier is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("claim_bearing") is not False:
        fail("CodeDye v3 run-readiness classifier must be non-claim-bearing.")
    if payload.get("formal_v3_live_claim_allowed") is not False:
        fail("Classifier must not promote v3 live claim.")
    if payload.get("formal_high_recall_detection_claim_allowed") is not False:
        fail("Classifier must not allow high-recall detection claim.")
    if payload.get("gate_pass") is not True or payload.get("deepseek_v3_rerun_allowed") is not True:
        fail("CodeDye v3 rerun should be allowed after frozen controls pass.")
    inputs = payload["readiness_inputs"]
    if inputs["positive_control_detected"] != 170 or inputs["positive_control_missed"] != 130:
        fail("CodeDye positive-control boundary drifted.")
    if inputs["negative_control_false_positive_count"] != 0:
        fail("CodeDye negative controls are no longer clean.")
    if inputs["support_rows_excluded"] != 806:
        fail("CodeDye support-exclusion boundary drifted.")
    print("[OK] CodeDye v3 run-readiness classifier verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
