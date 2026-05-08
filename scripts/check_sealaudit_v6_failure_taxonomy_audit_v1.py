from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "results/SealAudit/artifacts/generated/sealaudit_v6_failure_taxonomy_audit_v1_20260508.json"


def main() -> int:
    if not GATE.exists():
        raise SystemExit(f"[FAIL] missing SealAudit v6 audit: {GATE.relative_to(ROOT)}")
    payload = json.loads(GATE.read_text(encoding="utf-8"))
    if payload.get("claim_bearing") is not False:
        raise SystemExit("[FAIL] SealAudit v6 taxonomy audit must be non-claim-bearing.")
    if payload.get("gate_pass") is not True:
        raise SystemExit(f"[FAIL] SealAudit v6 taxonomy audit failed: {payload.get('blockers')}")
    if payload.get("hidden_claim_rows") != 960:
        raise SystemExit("[FAIL] SealAudit v6 taxonomy audit must bind 960 hidden claim rows.")
    if payload.get("unsafe_pass_count") != 0:
        raise SystemExit("[FAIL] SealAudit v6 taxonomy audit must retain zero unsafe-pass.")
    if payload.get("formal_security_certificate_claim_allowed") is not False:
        raise SystemExit("[FAIL] SealAudit v6 taxonomy audit must not allow security-certificate claims.")
    print(
        "[OK] SealAudit v6 failure taxonomy audit passed: "
        f"{payload.get('decisive_count')}/960 decisive, unsafe-pass={payload.get('unsafe_pass_count')}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
