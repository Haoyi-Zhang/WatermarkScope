from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "results/CodeDye/artifacts/generated/codedye_v4_full_attack_matrix_support_22x_gate_v1_20260508.json"


def main() -> int:
    if not GATE.exists():
        raise SystemExit(f"[FAIL] missing CodeDye v4 22x support gate: {GATE.relative_to(ROOT)}")
    payload = json.loads(GATE.read_text(encoding="utf-8"))
    if payload.get("claim_bearing") is not False:
        raise SystemExit("[FAIL] CodeDye 22x gate must be non-claim-bearing.")
    if payload.get("gate_pass") is not True:
        raise SystemExit(f"[FAIL] CodeDye 22x support gate failed: {payload.get('blockers')}")
    if payload.get("formal_main_claim_allowed") is not False:
        raise SystemExit("[FAIL] CodeDye 22x support gate must not promote a main claim.")
    if payload.get("record_count", 0) < 140:
        raise SystemExit("[FAIL] CodeDye 22x support gate must bind at least 140 live rows.")
    if payload.get("support_utility_admissible_record_count", 0) < 140:
        raise SystemExit("[FAIL] CodeDye 22x support gate has too few utility-admissible support rows.")
    for attack_id, count in payload.get("support_utility_admissible_by_attack", {}).items():
        if int(count) < 20:
            raise SystemExit(f"[FAIL] attack support coverage below 20: {attack_id}={count}")
    policy = payload.get("main_denominator_policy", {})
    if policy.get("enters_any_main_claim_denominator") is not False:
        raise SystemExit("[FAIL] CodeDye 22x support rows must not enter any main denominator.")
    if policy.get("failure_rows_deleted_or_relabelled") is not False:
        raise SystemExit("[FAIL] CodeDye 22x utility failures must remain retained.")
    print(
        "[OK] CodeDye v4 full attack-matrix support gate verified: "
        f"{payload.get('record_count')} rows, {payload.get('support_utility_admissible_record_count')} utility-admissible."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
