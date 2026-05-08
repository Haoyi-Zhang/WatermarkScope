from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "results/SemCodebook/artifacts/generated/semcodebook_whitebox_runtime_preflight_v1_20260508.json"


def main() -> int:
    if not PREFLIGHT.exists():
        raise SystemExit(f"[FAIL] missing SemCodebook runtime preflight: {PREFLIGHT.relative_to(ROOT)}")
    payload = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    if payload.get("claim_bearing") is not False:
        raise SystemExit("[FAIL] SemCodebook runtime preflight must be non-claim-bearing.")
    policy = payload.get("resource_policy", {})
    for key in [
        "failed_or_partial_model_cells_enter_main_claim",
        "cpu_only_generation_may_promote_whitebox_claim",
        "support_only_smoke_may_replace_7200_row_cell",
    ]:
        if policy.get(key) is not False:
            raise SystemExit(f"[FAIL] unsafe SemCodebook runtime policy: {key}")
    if payload.get("full_whitebox_launch_allowed") is True and payload.get("gate_pass") is not True:
        raise SystemExit("[FAIL] SemCodebook full launch cannot be allowed while gate fails.")
    blockers = set(payload.get("blockers", []))
    if payload.get("gate_pass") is False and not blockers:
        raise SystemExit("[FAIL] failed SemCodebook preflight lacks blockers.")
    if payload.get("gate_pass") is False and not (
        "torch_cuda_unavailable" in blockers
        or "local_nvidia_smi_unavailable" in blockers
        or "js4_nvidia_device_unavailable" in blockers
        or "whitebox_queued_model_full_runner_missing" in blockers
    ):
        raise SystemExit(f"[FAIL] failed SemCodebook preflight lacks a launch blocker: {sorted(blockers)}")
    print(
        "[OK] SemCodebook white-box runtime preflight verified: "
        f"gate_pass={payload.get('gate_pass')}; full_launch={payload.get('full_whitebox_launch_allowed')}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
