from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "results/watermark_experiment_deepening_status_v2_20260508.json"


def main() -> int:
    if not STATUS.exists():
        raise SystemExit(f"[FAIL] missing status: {STATUS.relative_to(ROOT)}")
    payload = json.loads(STATUS.read_text(encoding="utf-8"))
    if payload.get("claim_bearing") is not False:
        raise SystemExit("[FAIL] deepening status must be non-claim-bearing.")
    if payload.get("gate_pass") is not True:
        raise SystemExit(f"[FAIL] deepening status failed: {payload.get('blockers')}")
    projects = payload.get("projects", {})
    for name in ["SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"]:
        if name not in projects:
            raise SystemExit(f"[FAIL] missing project status: {name}")
    if projects["CodeDye"].get("record_count") != 20:
        raise SystemExit("[FAIL] CodeDye v4 support run must bind 20 rows.")
    if projects["ProbeTrace"].get("candidate_owner_emit_rows") != 0:
        raise SystemExit("[FAIL] ProbeTrace corrupted-commitment challenge must emit zero candidate owners.")
    if projects["SealAudit"].get("unsafe_pass_count") != 0:
        raise SystemExit("[FAIL] SealAudit v6 audit must retain zero unsafe-pass.")
    if not projects["SemCodebook"].get("resource_blockers"):
        raise SystemExit("[FAIL] SemCodebook queue must document current resource blockers.")
    print("[OK] Watermark experiment deepening status v2 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
