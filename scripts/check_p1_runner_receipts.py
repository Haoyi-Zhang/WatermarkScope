from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RECEIPTS = [
    "results/SemCodebook/artifacts/generated/semcodebook_row_level_miss_attribution_v1_20260507.json",
    "results/SemCodebook/artifacts/generated/semcodebook_row_level_miss_attribution_v2_20260507.json",
    "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_promotion_gate_probetrace_multi_owner_20260507.json",
    "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_promotion_gate_20260507.json",
    "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_promotion_gate_probetrace_multi_owner_strict_smoke_20260507.json",
    "results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_sealaudit_v5_20260507.json",
    "results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_remote_support_guard_20260507.json",
    "results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_strict_smoke_20260507.json",
]

REAL_INPUT_RECEIPTS_ALLOWED_TO_PASS = {
    "results/SemCodebook/artifacts/generated/semcodebook_row_level_miss_attribution_v2_20260507.json",
}


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    existing = [path for path in RECEIPTS if (ROOT / path).exists()]
    if not existing:
        fail("No P1 runner receipts found; run fail-closed runner smoke first.")
    passed_real_input = 0
    blocked_or_guarded = 0
    for rel in existing:
        payload = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        if payload.get("claim_bearing") is not False:
            fail(f"P1 receipt must be non-claim-bearing: {rel}")
        if rel in REAL_INPUT_RECEIPTS_ALLOWED_TO_PASS:
            if payload.get("gate_pass") is not True or payload.get("blocked") is not False:
                fail(f"Real-input P1 receipt should pass without being blocked: {rel}")
            passed_real_input += 1
            continue
        if payload.get("gate_pass") is not False:
            fail(f"P1 smoke receipt must not pass without real inputs: {rel}")
        if payload.get("blocked") is not True:
            if rel.endswith("probetrace_multi_owner_promotion_gate_20260507.json") and payload.get("blockers") == [
                "multi_owner_support_contract_not_satisfied"
            ]:
                blocked_or_guarded += 1
                continue
            fail(f"P1 smoke/guard receipt should be blocked without promotable inputs: {rel}")
        blocked_or_guarded += 1
    print(
        f"[OK] P1 runner receipts verified: {passed_real_input} real-input pass, "
        f"{blocked_or_guarded} blocked/guarded non-claim-bearing receipts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
