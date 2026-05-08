from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "results/SemCodebook/artifacts/generated/semcodebook_whitebox_next_gpu_queue_v1_20260508.json"


def main() -> int:
    if not GATE.exists():
        raise SystemExit(f"[FAIL] missing SemCodebook GPU queue: {GATE.relative_to(ROOT)}")
    payload = json.loads(GATE.read_text(encoding="utf-8"))
    if payload.get("claim_bearing") is not False:
        raise SystemExit("[FAIL] SemCodebook GPU queue must be non-claim-bearing.")
    queue = payload.get("next_gpu_queue", [])
    if len(queue) < 3:
        raise SystemExit("[FAIL] SemCodebook GPU queue must list multiple expansion candidates.")
    for row in queue:
        if row.get("target_records") != 7200:
            raise SystemExit("[FAIL] each queued SemCodebook model must require 7200 records.")
        if "postrun_audit_gate_pass" not in row.get("admission_required", []):
            raise SystemExit("[FAIL] each queued SemCodebook model must require postrun audit.")
    if payload.get("gpu_run_allowed_now") is False:
        blockers = set(payload.get("blockers", []))
        expected_resource_blockers = {
            "nvidia_gpu_unavailable",
            "torch_missing",
            "transformers_missing",
            "peft_missing",
        }
        if not blockers.intersection(expected_resource_blockers):
            raise SystemExit(f"[FAIL] blocked GPU queue lacks explicit resource blocker: {blockers}")
    print(
        "[OK] SemCodebook white-box GPU queue verified: "
        f"{len(queue)} expansion candidates; gpu_run_allowed_now={payload.get('gpu_run_allowed_now')}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
