from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v1_{DATE}.json"
ARTIFACT_MD = ROOT / f"results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v1_{DATE}.md"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists() or not ARTIFACT_MD.exists():
        fail("SemCodebook final claim-lock artifacts are missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "semcodebook_final_claim_lock_v1":
        fail("Unexpected SemCodebook final claim-lock schema.")
    if payload.get("claim_bearing") is not False:
        fail("Claim-lock artifact must be non-claim-bearing.")
    if payload.get("gate_pass") is not True:
        fail("SemCodebook final claim-lock gate must pass.")
    if payload.get("formal_scoped_whitebox_claim_allowed") is not True:
        fail("Scoped white-box SemCodebook claim should be allowed.")
    miss = payload["mandatory_miss_disclosure"]
    if miss["positive_miss_count"] != 10210:
        fail("SemCodebook positive miss count drifted.")
    if miss["miss_concentration_model"] != "DeepSeek-Coder-6.7B-Instruct":
        fail("SemCodebook miss concentration model is not locked.")
    if miss["miss_concentration_rate"] < 0.99:
        fail("SemCodebook miss concentration disclosure is incomplete.")
    deltas = payload["mandatory_component_delta_table"]
    if deltas["row_count"] < 8 or deltas.get("paper_table_required") is not True:
        fail("SemCodebook paired component delta table is not locked.")
    forbidden = set(payload["forbidden_claims"])
    for item in ("first-sample/no-retry natural-generation guarantee", "perfect-score language"):
        if item not in forbidden:
            fail(f"Missing forbidden claim: {item}")
    print("[OK] SemCodebook final claim-lock verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
