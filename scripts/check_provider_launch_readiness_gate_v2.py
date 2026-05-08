from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/provider_launch_readiness_gate_v2_{DATE}.json"

SECRET_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"ghp_[A-Za-z0-9_]{20,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"bearer\s+[A-Za-z0-9_.-]{12,}",
        r"authorization:",
    ]
]


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("Provider launch readiness gate v2 artifact is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "provider_launch_readiness_gate_v2":
        fail("Unexpected provider launch readiness v2 schema.")
    if payload.get("claim_bearing") is not False:
        fail("Provider readiness v2 must be non-claim-bearing.")
    if payload.get("secret_values_recorded") is not False:
        fail("Provider readiness v2 must not record secret values.")
    if payload.get("fresh_run_contracts_gate") != f"results/blackbox_fresh_run_preflight_contracts_v1_{DATE}.json":
        fail("Provider readiness v2 is not bound to the fresh-run contracts gate.")

    local = payload.get("local_provider_environment", {})
    if local.get("secret_values_recorded") is not False:
        fail("Local provider environment must be redacted.")
    remote = payload.get("remote_js2", {})
    if remote.get("batch_ssh", {}).get("secret_values_recorded") is not False:
        fail("Remote SSH status must be redacted.")
    if remote.get("batch_ssh", {}).get("identity_file_path_recorded") is not False:
        fail("Remote SSH identity file path must not be recorded in readiness artifacts.")

    projects = payload.get("project_launch_readiness", {})
    if set(projects) != {"CodeDye", "ProbeTrace", "SealAudit"}:
        fail("Provider readiness v2 project set is incomplete.")
    provider_ready = payload.get("provider_execution_readiness", {}).get("any_provider_execution_ready_now")
    for project, status in projects.items():
        if status.get("execution_contract_ready") is not True:
            fail(f"{project} execution contract should be ready before provider readiness is evaluated.")
        if status.get("formal_claim_promotion_allowed_now") is not False:
            fail(f"{project} must not be claim-promoted by provider readiness v2.")
        if status.get("can_start_provider_run_now") and not provider_ready:
            fail(f"{project} is marked startable without provider execution readiness.")
        command = str(status.get("launch_command_redacted", ""))
        for pattern in SECRET_PATTERNS:
            if pattern.search(command):
                fail(f"Secret-like token found in {project} launch command.")
        if "deepseek" not in command.lower():
            fail(f"{project} launch command is not DeepSeek-scoped.")
        if not status.get("canonical_output") or not status.get("postrun_promotion_gate"):
            fail(f"{project} launch readiness lacks canonical output or postrun gate.")

    if provider_ready is False:
        blockers = set(payload.get("provider_execution_readiness", {}).get("blockers", []))
        expected = {
            "local_deepseek_env_missing",
            "remote_js2_requires_noninteractive_ssh_key_or_agent",
            "remote_js2_tcp_unreachable",
        }
        if not blockers.intersection(expected):
            fail("Blocked provider readiness lacks an expected execution blocker.")
    print("[OK] Provider launch readiness gate v2 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
