from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/provider_launch_readiness_gate_v1_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("Provider launch readiness gate artifact is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "provider_launch_readiness_gate_v1":
        fail("Unexpected provider launch readiness schema.")
    if payload.get("claim_bearing") is not False:
        fail("Provider launch readiness gate must be non-claim-bearing.")
    if payload.get("secret_values_recorded") is not False:
        fail("Provider launch gate must never record secret values.")
    env_status = payload["local_provider_environment"]
    if env_status.get("secret_values_recorded") is not False:
        fail("Local env status must be redacted.")
    remote = payload["remote_js2"]
    if remote["batch_ssh"].get("secret_values_recorded") is not False:
        fail("Remote SSH status must be redacted.")
    projects = payload["project_statuses"]
    if set(projects) != {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}:
        fail("Project status set is incomplete.")
    if projects["CodeDye"].get("formal_claim_promotion_allowed_now") is not False:
        fail("CodeDye v3 must not be promotable before fresh postrun evidence.")
    if projects["ProbeTrace"].get("formal_claim_promotion_allowed_now") is not False:
        fail("ProbeTrace multi-owner claim must remain blocked.")
    if projects["SealAudit"].get("formal_claim_promotion_allowed_now") is not False:
        fail("SealAudit v5 claim must remain blocked.")
    readiness = payload["launch_readiness"]
    if readiness.get("probetrace_multi_owner_can_start_now") is not False:
        fail("ProbeTrace multi-owner should not be marked startable by this local readiness gate.")
    if readiness.get("sealaudit_v5_can_start_now") is not False:
        fail("SealAudit v5 should not be marked startable by this local readiness gate.")
    if readiness.get("codedye_v3_health_or_full_run_can_start_now") and not readiness.get("any_provider_execution_ready_now"):
        fail("CodeDye cannot be startable without provider execution readiness.")
    print("[OK] Provider launch readiness gate verified.")
    print("[OK] Secret values are redacted; missing provider access remains a blocker, not a result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
