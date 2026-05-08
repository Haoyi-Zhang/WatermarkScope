from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/CodeDye/artifacts/generated/codedye_v3_health_live_gate_v1_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("CodeDye v3 health live gate is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "codedye_v3_health_live_gate_v1":
        fail("Unexpected CodeDye health live gate schema.")
    if payload.get("claim_bearing") is not False:
        fail("Health live gate must be non-claim-bearing.")
    if payload.get("formal_v3_live_claim_allowed") is not False:
        fail("Health live gate must not promote v3 live claim.")
    if payload.get("gate_pass") is not True:
        fail("CodeDye health live gate failed: " + ", ".join(payload.get("blockers", [])))
    if payload.get("record_count") != 2:
        fail("Health live gate must bind exactly two rows.")
    if payload.get("provider_modes") != ["live"]:
        fail("Health live gate must prove live provider mode.")
    print("[OK] CodeDye v3 health live gate verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
