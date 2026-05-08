from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_commitment_shortcut_challenge_postrun_gate_v1_20260508.json"


def main() -> int:
    if not GATE.exists():
        raise SystemExit(f"[FAIL] missing gate: {GATE.relative_to(ROOT)}")
    payload = json.loads(GATE.read_text(encoding="utf-8"))
    if payload.get("claim_bearing") is not False:
        raise SystemExit("[FAIL] challenge gate must be non-claim-bearing")
    if payload.get("formal_multi_owner_claim_allowed") is not False:
        raise SystemExit("[FAIL] challenge gate must not promote a multi-owner claim")
    if payload.get("gate_pass") is not True:
        raise SystemExit(f"[FAIL] challenge gate failed: {payload.get('blockers')}")
    print(
        "[OK] ProbeTrace commitment-shortcut challenge passed: "
        f"{payload.get('record_count')} live corrupted-commitment rows failed closed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
