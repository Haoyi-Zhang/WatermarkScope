from __future__ import annotations

import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT = ROOT / f"results/provider_launch_readiness_gate_v2_{DATE}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(rel: str) -> dict[str, Any]:
    payload = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(rel)
    return payload


def env_key_status() -> dict[str, Any]:
    names = sorted(
        name
        for name in os.environ
        if "DEEPSEEK" in name.upper() or ("API" in name.upper() and "KEY" in name.upper())
    )
    deepseek_names = [name for name in names if "DEEPSEEK" in name.upper()]
    return {
        "key_like_env_names": names,
        "deepseek_env_name_present": bool(deepseek_names),
        "deepseek_env_names": deepseek_names,
        "secret_values_recorded": False,
        "redaction_policy": "Only environment variable names are recorded; secret values are never written.",
    }


def tcp_status(host: str, port: int, timeout: float = 5.0) -> dict[str, Any]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"host": host, "port": port, "tcp_connectable": True, "error": None}
    except OSError as exc:
        return {"host": host, "port": port, "tcp_connectable": False, "error": f"{type(exc).__name__}: {exc}"}


def local_js2_key_path() -> Path:
    return Path.home() / ".ssh" / "codemark_js2_ed25519"


def ssh_batch_status(host: str, port: int, user: str = "root") -> dict[str, Any]:
    key_path = local_js2_key_path()
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    if key_path.exists():
        command.extend(["-i", str(key_path)])
    command.extend([
        "-p",
        str(port),
        f"{user}@{host}",
        "pwd",
    ])
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "batch_ssh_attempted": True,
            "batch_ssh_success": False,
            "identity_file_present": key_path.exists(),
            "identity_file_path_recorded": False,
            "returncode": None,
            "stdout_redacted": "",
            "stderr_summary": f"{type(exc).__name__}: {exc}",
            "secret_values_recorded": False,
        }
    return {
        "batch_ssh_attempted": True,
        "batch_ssh_success": result.returncode == 0,
        "identity_file_present": key_path.exists(),
        "identity_file_path_recorded": False,
        "returncode": result.returncode,
        "stdout_redacted": result.stdout.strip()[:120],
        "stderr_summary": result.stderr.strip()[:240],
        "secret_values_recorded": False,
    }


def project_contracts() -> dict[str, dict[str, Any]]:
    portfolio = load_json(f"results/blackbox_fresh_run_preflight_contracts_v1_{DATE}.json")
    projects: dict[str, dict[str, Any]] = {}
    for project, meta in portfolio.get("project_contracts", {}).items():
        if not isinstance(meta, dict):
            continue
        contract = load_json(str(meta["path"]))
        projects[str(project)] = {
            "contract_path": meta["path"],
            "contract_gate_pass": contract.get("gate_pass") is True,
            "execution_contract_ready": contract.get("execution_contract_ready") is True,
            "run_id": contract.get("run_id"),
            "canonical_output": contract.get("canonical_output", contract.get("canonical_v5_evidence_input")),
            "launch_command_redacted": contract.get("launch_command_redacted"),
            "postrun_promotion_gate": contract.get("postrun_promotion_gate"),
            "claim_bearing": contract.get("claim_bearing"),
            "contract_blockers": contract.get("blockers", []),
        }
    return projects


def main() -> int:
    env_status = env_key_status()
    remote_tcp = tcp_status("js2.blockelite.cn", 22620)
    remote_ssh = ssh_batch_status("js2.blockelite.cn", 22620)
    projects = project_contracts()
    local_api_ready = bool(env_status["deepseek_env_name_present"])
    remote_noninteractive_ready = bool(remote_tcp["tcp_connectable"] and remote_ssh["batch_ssh_success"])
    provider_execution_ready = local_api_ready or remote_noninteractive_ready

    provider_blockers: list[str] = []
    if not local_api_ready:
        provider_blockers.append("local_deepseek_env_missing")
    if remote_tcp["tcp_connectable"] and not remote_ssh["batch_ssh_success"]:
        provider_blockers.append("remote_js2_requires_noninteractive_ssh_key_or_agent")
    elif not remote_tcp["tcp_connectable"]:
        provider_blockers.append("remote_js2_tcp_unreachable")

    project_launch: dict[str, Any] = {}
    for project, contract in projects.items():
        contract_ready = bool(contract["execution_contract_ready"] and not contract["contract_blockers"])
        startable = contract_ready and provider_execution_ready
        project_launch[project] = {
            "execution_contract_ready": contract_ready,
            "provider_execution_ready": provider_execution_ready,
            "can_start_provider_run_now": startable,
            "formal_claim_promotion_allowed_now": False,
            "canonical_output": contract["canonical_output"],
            "postrun_promotion_gate": contract["postrun_promotion_gate"],
            "launch_command_redacted": contract["launch_command_redacted"],
            "blockers": [] if startable else [*contract["contract_blockers"], *provider_blockers],
        }

    payload = {
        "schema_version": "provider_launch_readiness_gate_v2",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "secret_values_recorded": False,
        "supersedes_for_launch_planning": f"results/provider_launch_readiness_gate_v1_{DATE}.json",
        "fresh_run_contracts_gate": f"results/blackbox_fresh_run_preflight_contracts_v1_{DATE}.json",
        "local_provider_environment": env_status,
        "remote_js2": {
            "tcp": remote_tcp,
            "batch_ssh": remote_ssh,
            "noninteractive_execution_ready": remote_noninteractive_ready,
        },
        "provider_execution_readiness": {
            "local_api_ready": local_api_ready,
            "remote_noninteractive_ready": remote_noninteractive_ready,
            "any_provider_execution_ready_now": provider_execution_ready,
            "blockers": provider_blockers,
        },
        "project_launch_readiness": project_launch,
        "launch_order_if_ready": ["CodeDye", "ProbeTrace", "SealAudit"],
        "formal_claim_policy": (
            "This gate can allow provider execution only. It never promotes a paper claim; project-specific "
            "postrun promotion gates must pass after fresh outputs exist."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    if provider_execution_ready:
        print("[OK] Provider execution path is ready; use project launch commands from the gate.")
    else:
        print("[BLOCKED] Provider execution is blocked locally/remotely, but fresh-run contracts are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
