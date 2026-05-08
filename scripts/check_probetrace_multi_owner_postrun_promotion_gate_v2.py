from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_postrun_promotion_gate_v2_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("ProbeTrace multi-owner postrun promotion gate v2 is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "probetrace_multi_owner_postrun_promotion_gate_v2":
        fail("Unexpected ProbeTrace postrun v2 payload schema.")
    if payload.get("claim_bearing") is not False:
        fail("ProbeTrace postrun gate must be non-claim-bearing.")
    metrics = payload.get("postrun_metrics", {})
    if payload.get("gate_pass") is True:
        if payload.get("formal_multi_owner_claim_allowed") is not True:
            fail("Passing ProbeTrace v2 postrun should allow scoped multi-owner claim.")
        if metrics.get("row_count") != 6000:
            fail("Passing ProbeTrace v2 postrun must bind 6000 rows.")
        if metrics.get("owner_count", 0) < 5 or metrics.get("language_count", 0) < 3:
            fail("ProbeTrace v2 postrun requires 5 owners and 3 languages.")
        if metrics.get("missing_hash_rows") != 0 or metrics.get("schema_missing_rows") != 0:
            fail("ProbeTrace v2 postrun cannot have schema/hash gaps.")
        if metrics.get("control_to_positive_ratio", 0) < 4:
            fail("ProbeTrace v2 postrun requires >=4x controls.")
        if metrics.get("margin_auc") is None:
            fail("ProbeTrace v2 postrun requires rank/AUC.")
        if metrics.get("owner_heldout_rows", 0) <= 0 or metrics.get("task_heldout_rows", 0) <= 0:
            fail("ProbeTrace v2 postrun requires owner-heldout and task-heldout rows.")
        for role in ("true_owner", "wrong_owner", "null_owner", "random_owner", "same_provider_unwrap"):
            if role not in metrics.get("control_role_counts", {}):
                fail(f"ProbeTrace v2 postrun missing role: {role}")
    else:
        blockers = set(payload.get("blockers", []))
        expected = {"fresh_multi_owner_live_score_vectors_missing", "row_count_not_6000"}
        if not blockers.intersection(expected):
            fail("Blocked ProbeTrace v2 postrun lacks expected fail-closed blockers.")
        if payload.get("formal_multi_owner_claim_allowed") is not False:
            fail("Blocked ProbeTrace v2 postrun must not allow multi-owner claim.")
    print("[OK] ProbeTrace multi-owner postrun promotion gate v2 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
