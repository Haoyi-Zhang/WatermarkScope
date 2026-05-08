from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
TAXONOMY_ROWS = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_needs_review_row_taxonomy_v2_{DATE}.jsonl"
ABSTENTION = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_abstention_burden_frontier_v1_{DATE}.json"
WORDING = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_claim_wording_lock_v1_{DATE}.json"
JOIN = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_claim_surface_frontier_join_audit_v1_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def load(path: Path) -> dict:
    if not path.exists():
        fail(f"Missing artifact: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    abstention = load(ABSTENTION)
    wording = load(WORDING)
    join = load(JOIN)
    if abstention.get("schema_version") != "sealaudit_abstention_burden_frontier_v1":
        fail("Unexpected SealAudit abstention schema.")
    if wording.get("schema_version") != "sealaudit_claim_wording_lock_v1":
        fail("Unexpected SealAudit wording schema.")
    if join.get("schema_version") != "sealaudit_claim_surface_frontier_join_audit_v1":
        fail("Unexpected SealAudit join schema.")
    for name, payload in (("abstention", abstention), ("wording", wording), ("join", join)):
        if payload.get("claim_bearing") is not False:
            fail(f"{name} artifact must be non-claim-bearing.")
        if payload.get("gate_pass") is not True:
            fail(f"{name} artifact gate must pass.")
    if abstention.get("hidden_claim_rows") != 960 or abstention.get("needs_review_count") != 879:
        fail("SealAudit abstention burden drifted.")
    if abstention.get("decisive_count") != 81 or abstention.get("unsafe_pass_count") != 0:
        fail("SealAudit coverage-risk counts drifted.")
    if abstention.get("formal_classifier_claim_allowed") is not False:
        fail("SealAudit classifier claim must remain forbidden.")
    if "AI-prefilled expert labels" not in wording.get("forbidden_wording", []):
        fail("SealAudit wording lock must forbid AI-prefilled expert label wording.")
    if join.get("needs_review_taxonomy_row_count") != 879:
        fail("SealAudit needs-review row taxonomy must bind all 879 rows.")
    row_count = sum(1 for line in TAXONOMY_ROWS.read_text(encoding="utf-8").splitlines() if line.strip())
    if row_count != 879:
        fail("SealAudit needs-review taxonomy JSONL row count drifted.")
    print("[OK] SealAudit abstention and wording artifacts verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
