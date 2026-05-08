from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_postrun_promotion_gate_v1_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("ProbeTrace multi-owner postrun promotion gate is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "probetrace_multi_owner_postrun_promotion_gate_v1":
        fail("Unexpected ProbeTrace postrun schema.")
    if payload.get("claim_bearing") is not False:
        fail("ProbeTrace postrun gate itself must be non-claim-bearing.")
    if payload.get("gate_pass") is False:
        blockers = set(payload.get("blockers", []))
        if "fresh_multi_owner_live_score_vectors_missing" not in blockers and "row_count_not_6000" not in blockers:
            fail("Blocked ProbeTrace postrun gate lacks an expected fail-closed blocker.")
        if payload.get("formal_multi_owner_claim_allowed") is not False:
            fail("Blocked ProbeTrace postrun gate must not allow multi-owner claim.")
    else:
        metrics = payload.get("postrun_metrics", {})
        if payload.get("formal_multi_owner_claim_allowed") is not True:
            fail("Passing ProbeTrace postrun gate should allow scoped multi-owner claim.")
        if metrics.get("row_count") != 6000:
            fail("Passing ProbeTrace postrun gate must bind 6000 rows.")
        if metrics.get("owner_count", 0) < 5 or metrics.get("language_count", 0) < 3:
            fail("Passing ProbeTrace postrun gate requires 5 owners and 3 languages.")
        if metrics.get("missing_hash_rows") != 0 or metrics.get("schema_missing_rows") != 0:
            fail("Passing ProbeTrace postrun gate cannot have schema/hash gaps.")
    print("[OK] ProbeTrace multi-owner postrun promotion gate verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
