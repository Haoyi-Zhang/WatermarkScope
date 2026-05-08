from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/CodeDye/artifacts/generated/codedye_v3_launch_denominator_consistency_gate_v1_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("CodeDye v3 launch denominator consistency gate is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "codedye_v3_launch_denominator_consistency_gate_v1":
        fail("Unexpected CodeDye denominator consistency schema.")
    if payload.get("claim_bearing") is not False:
        fail("Denominator consistency gate must be non-claim-bearing.")
    if payload.get("formal_v3_live_claim_allowed") is not False:
        fail("Denominator consistency gate must not promote v3 live claim.")
    if payload.get("gate_pass") is not True:
        fail("CodeDye denominator consistency gate failed: " + ", ".join(payload.get("blockers", [])))
    probe = payload.get("runner_probe", {})
    if probe.get("post_target_row_count") != 300:
        fail("Runner probe did not bind a 300-row launch.")
    if "query_budget_drop" in probe.get("post_target_by_attack", {}):
        fail("Support-only query-budget rows entered the main denominator.")
    print("[OK] CodeDye v3 launch denominator consistency gate verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
