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
OUT = ROOT / f"results/provider_launch_readiness_gate_v1_{DATE}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def env_key_status() -> dict[str, Any]:
    names = sorted(
        name
        for name in os.environ
        if "DEEPSEEK" in name.upper() or ("API" in name.upper() and "KEY" in name.upper())
    )
    return {
        "key_like_env_names": names,
        "deepseek_env_name_present": any("DEEPSEEK" in name.upper() for name in names),
        "secret_values_recorded": False,
        "redaction_policy": "Only environment variable names are recorded; secret values are never written.",
    }


def tcp_status(host: str, port: int, timeout: float = 5.0) -> dict[str, Any]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"host": host, "port": port, "tcp_connectable": True, "error": None}
    except OSError as exc:
        return {"host": host, "port": port, "tcp_connectable": False, "error": f"{type(exc).__name__}: {exc}"}


def ssh_batch_status(host: str, port: int, user: str = "root") -> dict[str, Any]:
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-p",
        str(port),
        f"{user}@{host}",
        "pwd",
    ]
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
            "returncode": None,
            "stdout_redacted": "",
            "stderr_summary": f"{type(exc).__name__}: {exc}",
            "secret_values_recorded": False,
        }
    return {
        "batch_ssh_attempted": True,
        "batch_ssh_success": result.returncode == 0,
        "returncode": result.returncode,
        "stdout_redacted": result.stdout.strip()[:120],
        "stderr_summary": result.stderr.strip()[:240],
        "secret_values_recorded": False,
    }


def project_statuses() -> dict[str, Any]:
    codedye = load_json("results/CodeDye/artifacts/generated/codedye_v3_run_readiness_classifier_v1_20260507.json")
    probetrace = load_json("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_evidence_classifier_v1_20260507.json")
    sealaudit = load_json("results/SealAudit/artifacts/generated/sealaudit_v5_evidence_classifier_v1_20260507.json")
    strict = load_json("results/watermark_strict_reviewer_audit_v2_20260507.json")
    sem = next(project for project in strict["projects"] if project["project"] == "SemCodebook")
    return {
        "SemCodebook": {
            "full_run_launch_allowed_now": False,
            "reason": "No new white-box full run is needed for the current blocker set; remaining items are paper/claim presentation P2.",
            "current_local_evidence": sem["effect_metrics"],
            "claim_upgrade_allowed": len(sem["remaining_p1"]) == 0,
        },
        "CodeDye": {
            "full_run_launch_allowed_now": bool(codedye.get("deepseek_v3_rerun_allowed")),
            "formal_claim_promotion_allowed_now": bool(codedye.get("formal_v3_live_claim_allowed")),
            "reason": "Fresh DeepSeek v3 rerun is allowed by frozen controls, but cannot be promoted until postrun evidence exists.",
            "blockers": codedye.get("blockers", []),
            "required_postrun_outputs": codedye.get("required_v3_postrun_outputs", []),
        },
        "ProbeTrace": {
            "full_run_launch_allowed_now": False,
            "formal_claim_promotion_allowed_now": bool(probetrace.get("formal_multi_owner_claim_allowed")),
            "reason": "Multi-owner canonical input package exists, but fresh provider score-vector outputs and postrun audits are missing.",
            "blockers": probetrace.get("blockers", []),
        },
        "SealAudit": {
            "full_run_launch_allowed_now": False,
            "formal_claim_promotion_allowed_now": bool(sealaudit.get("formal_v5_claim_allowed")),
            "reason": "Final v5 row-level evidence is missing; support-only v5 material must remain non-claim-bearing.",
            "blockers": sealaudit.get("blockers", []),
        },
    }


def main() -> int:
    env_status = env_key_status()
    remote_tcp = tcp_status("js2.blockelite.cn", 22620)
    remote_ssh = ssh_batch_status("js2.blockelite.cn", 22620)
    projects = project_statuses()
    local_api_ready = bool(env_status["deepseek_env_name_present"])
    remote_noninteractive_ready = bool(remote_tcp["tcp_connectable"] and remote_ssh["batch_ssh_success"])
    executable_now = local_api_ready or remote_noninteractive_ready
    launch_blockers: list[str] = []
    if not local_api_ready:
        launch_blockers.append("local_deepseek_env_missing")
    if remote_tcp["tcp_connectable"] and not remote_ssh["batch_ssh_success"]:
        launch_blockers.append("remote_js2_requires_interactive_password_or_key")
    elif not remote_tcp["tcp_connectable"]:
        launch_blockers.append("remote_js2_tcp_unreachable")

    codedye_launch_ready = bool(projects["CodeDye"]["full_run_launch_allowed_now"] and executable_now)
    payload = {
        "schema_version": "provider_launch_readiness_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "secret_values_recorded": False,
        "local_provider_environment": env_status,
        "remote_js2": {
            "tcp": remote_tcp,
            "batch_ssh": remote_ssh,
            "noninteractive_execution_ready": remote_noninteractive_ready,
        },
        "project_statuses": projects,
        "launch_readiness": {
            "local_api_ready": local_api_ready,
            "remote_noninteractive_ready": remote_noninteractive_ready,
            "any_provider_execution_ready_now": executable_now,
            "codedye_v3_health_or_full_run_can_start_now": codedye_launch_ready,
            "probetrace_multi_owner_can_start_now": False,
            "sealaudit_v5_can_start_now": False,
            "blockers": launch_blockers,
        },
        "safe_next_commands_if_provider_ready": {
            "CodeDye_health": (
                "python projects/CodeDye/scripts/run_attack_matrix_live_support.py "
                "--provider deepseek --claim-bearing-canonical --run-id codedye_v3_health_20260507 "
                "--max-records 10 --progress-output "
                "results/CodeDye/artifacts/generated/codedye_v3_health_progress_20260507.json"
            ),
            "CodeDye_full": (
                "python projects/CodeDye/scripts/run_attack_matrix_live_support.py "
                "--provider deepseek --claim-bearing-canonical --run-id codedye_v3_20260507"
            ),
        },
        "policy": (
            "This gate records launch readiness only. A missing key or noninteractive SSH blocker must not be "
            "converted into claim-bearing results."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    if codedye_launch_ready:
        print("[OK] CodeDye v3 provider run can start now.")
    else:
        print("[BLOCKED] Provider-backed run cannot start from this local session.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
