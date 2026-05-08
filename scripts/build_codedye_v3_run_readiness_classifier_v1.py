from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT = ROOT / f"results/CodeDye/artifacts/generated/codedye_v3_run_readiness_classifier_v1_{DATE}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def main() -> int:
    freeze = load_json("results/CodeDye/artifacts/generated/codedye_v3_protocol_freeze_gate_20260507.json")
    controls = load_json("results/CodeDye/artifacts/generated/codedye_v3_positive_negative_control_gate_20260507.json")
    boundary = load_json("results/CodeDye/artifacts/generated/codedye_v3_live_claim_boundary_gate_20260507.json")
    support = load_json("results/CodeDye/artifacts/generated/codedye_v3_support_exclusion_gate_20260507.json")
    neg_rows = load_json("results/CodeDye/artifacts/generated/codedye_negative_control_row_hash_manifest_v2_20260507.json")

    blockers: list[str] = []
    if freeze.get("frozen") is not True:
        blockers.append("v3_thresholds_not_frozen")
    if controls.get("gate_pass") is not True:
        blockers.append("positive_negative_control_gate_not_passed")
    if support.get("gate_pass") is not True:
        blockers.append("support_exclusion_gate_not_passed")
    if neg_rows.get("false_positive_count") != 0:
        blockers.append("negative_control_false_positive_present")
    if boundary.get("payload_transcript_hash_missing_rows") != 0:
        blockers.append("legacy_payload_hash_missing")

    run_allowed = not blockers
    payload = {
        "schema_version": "codedye_v3_run_readiness_classifier_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": run_allowed,
        "deepseek_v3_rerun_allowed": run_allowed,
        "formal_v3_live_claim_allowed": False,
        "formal_high_recall_detection_claim_allowed": False,
        "readiness_inputs": {
            "thresholds_frozen": bool(freeze.get("frozen")),
            "positive_control_denominator": controls["positive_control_denominator"],
            "positive_control_detected": controls["positive_control_detected"],
            "positive_control_missed": controls["positive_control_missed"],
            "negative_control_rows": neg_rows["row_count"],
            "negative_control_false_positive_count": neg_rows["false_positive_count"],
            "support_rows_excluded": support["support_rows_excluded_from_main_denominator"],
            "legacy_live_signal": boundary["legacy_live_final_signal"],
            "legacy_live_denominator": boundary["legacy_live_denominator"],
        },
        "required_v3_postrun_outputs": [
            "raw_provider_transcript_hashes",
            "structured_payload_hashes",
            "prompt_hashes",
            "task_hashes",
            "dual_evidence_decisions",
            "threshold_sensitivity",
            "support_exclusion_join",
            "positive_negative_control_join",
        ],
        "promotion_policy": "This classifier may allow a fresh DeepSeek v3 rerun. It cannot promote a v3 live claim until fresh postrun outputs improve or explain sensitivity without inflating false positives.",
        "blockers": blockers,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    return 0 if run_allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
