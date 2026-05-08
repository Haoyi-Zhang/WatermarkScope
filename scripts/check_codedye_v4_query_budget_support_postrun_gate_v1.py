from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "results/CodeDye/artifacts/generated/codedye_v4_query_budget_support_postrun_gate_v1_20260508.json"


def main() -> int:
    if not GATE.exists():
        raise SystemExit(f"[FAIL] missing gate: {GATE.relative_to(ROOT)}")
    payload = json.loads(GATE.read_text(encoding="utf-8"))
    blockers = payload.get("blockers", [])
    if payload.get("gate_pass") is not True:
        raise SystemExit(f"[FAIL] CodeDye v4 query-budget support gate failed: {blockers}")
    if payload.get("claim_bearing") is not False:
        raise SystemExit("[FAIL] CodeDye v4 support gate must remain non-claim-bearing.")
    if payload.get("formal_v4_main_claim_allowed") is not False:
        raise SystemExit("[FAIL] CodeDye v4 support gate must not promote a main claim.")
    print(
        "[OK] CodeDye v4 query-budget support gate passed: "
        f"{payload.get('record_count')} DeepSeek live support rows admitted."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
