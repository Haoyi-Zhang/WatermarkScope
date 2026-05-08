from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT


SCHEMA_VERSION = "probetrace_student_transfer_training_queue_v1"
DEFAULT_MANIFEST = ARTIFACTS / "student_transfer_training_launch_manifest.json"
DEFAULT_OUTPUT = ARTIFACTS / "student_transfer_training_queue_receipt.json"
DEFAULT_LOG_DIR = ARTIFACTS / "student_transfer_runs" / "_queue_logs"
DEFAULT_POST_MANIFEST_GATE = ARTIFACTS / "real_student_transfer_manifest_gate.json"
DEFAULT_LIVE_VALIDATION = ARTIFACTS / "student_transfer_live_validation_results.json"


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_secret_env_file(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _gpu_memory_used_mib(gpu_index: int) -> int | None:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                f"--id={gpu_index}",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    first = completed.stdout.strip().splitlines()[0].strip() if completed.stdout.strip() else ""
    try:
        return int(first)
    except ValueError:
        return None


def _probe_command(command: list[str], *, timeout: int = 20) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return {
            "command": " ".join(command),
            "ok": False,
            "returncode": None,
            "status": "missing_executable",
            "detail": str(exc.filename or ""),
        }
    except subprocess.TimeoutExpired:
        return {
            "command": " ".join(command),
            "ok": False,
            "returncode": None,
            "status": "timeout",
            "detail": f"timeout_after_seconds:{timeout}",
        }
    detail = (completed.stdout.strip() or completed.stderr.strip()).splitlines()
    return {
        "command": " ".join(command),
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "detail": "; ".join(line[:180] for line in detail[:4]),
    }


def _training_resource_preflight(*, python_executable: str, gpu_index: int) -> dict[str, Any]:
    gpu = _probe_command(
        [
            "nvidia-smi",
            f"--id={gpu_index}",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader",
        ]
    )
    torch_probe = _probe_command(
        [
            python_executable,
            "-c",
            (
                "import torch; "
                "print('torch=' + torch.__version__); "
                "print('cuda_available=' + str(torch.cuda.is_available()))"
            ),
        ]
    )
    transformers_probe = _probe_command([python_executable, "-c", "import transformers; print(transformers.__version__)"])
    peft_probe = _probe_command([python_executable, "-c", "import peft; print(getattr(peft, '__version__', 'unknown'))"])
    blockers: list[str] = []
    if not gpu["ok"]:
        blockers.append("gpu_driver_unavailable")
    if not torch_probe["ok"] or "cuda_available=True" not in str(torch_probe.get("detail", "")):
        blockers.append("torch_cuda_unavailable")
    if not transformers_probe["ok"]:
        blockers.append("transformers_import_failed")
    if not peft_probe["ok"]:
        blockers.append("peft_import_failed")
    return {
        "schema_version": "probetrace_student_transfer_training_resource_preflight_v1",
        "claim_role": "training_resource_preflight_not_evidence",
        "policy": "real SFT/LoRA/quantized transfer must fail closed unless a CUDA GPU and required training libraries are available",
        "gpu": gpu,
        "torch": torch_probe,
        "transformers": transformers_probe,
        "peft": peft_probe,
        "blockers": blockers,
        "ready_for_real_training": not blockers,
    }


def _resolve_command(command: list[Any], python_executable: str) -> list[str]:
    resolved = [str(item) for item in command]
    if resolved and Path(resolved[0]).name.lower() in {"python", "python3", "python.exe"}:
        resolved[0] = python_executable
    return resolved


def _jobs_from_manifest(manifest: dict[str, Any], *, python_executable: str, selected_families: set[str]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for item in manifest.get("jobs", []):
        if not isinstance(item, dict):
            continue
        family = str(item.get("family", "")).strip()
        if selected_families and family not in selected_families:
            continue
        command = item.get("command", [])
        if not isinstance(command, list) or not command:
            jobs.append({"family": family or "<missing>", "status": "blocked", "blocker": "command_missing_or_invalid"})
            continue
        jobs.append(
            {
                "family": family,
                "status": "queued",
                "command": _resolve_command(command, python_executable),
                "output_dir": str(item.get("output_dir", "")),
                "receipt_output": str(item.get("receipt_output", "")),
                "training_kind": str(item.get("training_kind", "")),
            }
        )
    return jobs


def build_queue_plan(
    root: Path,
    *,
    manifest_path: Path,
    python_executable: str,
    selected_families: set[str],
    wait_pid: int,
    gpu_index: int,
    max_gpu_used_mib: int,
) -> dict[str, Any]:
    manifest = _load(manifest_path)
    blockers: list[str] = []
    if manifest.get("schema_version") != "probetrace_real_student_transfer_launch_manifest_v1":
        blockers.append("training_launch_manifest_schema_missing_or_wrong")
    if manifest.get("launch_ready") is not True:
        blockers.append("training_launch_manifest_not_ready")
    jobs = _jobs_from_manifest(manifest, python_executable=python_executable, selected_families=selected_families)
    resource_preflight = _training_resource_preflight(python_executable=python_executable, gpu_index=gpu_index)
    if not jobs:
        blockers.append("no_training_jobs_selected")
    blockers.extend(str(job["blocker"]) for job in jobs if job.get("status") == "blocked")
    blockers.extend(f"resource_preflight:{item}" for item in resource_preflight["blockers"])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "claim_role": "training_queue_not_result_not_claim_bearing",
        "status": "ready" if not blockers else "blocked",
        "blockers": blockers,
        "root": str(root),
        "manifest": str(manifest_path),
        "wait_policy": {
            "wait_pid": wait_pid,
            "gpu_index": gpu_index,
            "max_gpu_used_mib": max_gpu_used_mib,
            "does_not_interrupt_existing_gpu_runs": True,
        },
        "training_resource_preflight": resource_preflight,
        "jobs": jobs,
    }


def _wait_for_gpu(plan: dict[str, Any], *, poll_seconds: int, output: Path) -> None:
    policy = plan["wait_policy"]
    wait_pid = int(policy["wait_pid"])
    gpu_index = int(policy["gpu_index"])
    max_gpu_used_mib = int(policy["max_gpu_used_mib"])
    plan["gpu_wait_started_at_utc"] = _utc_now()
    while True:
        pid_busy = _pid_alive(wait_pid)
        used = _gpu_memory_used_mib(gpu_index)
        gpu_busy = used is None or used > max_gpu_used_mib
        plan["last_wait_probe_utc"] = _utc_now()
        plan["last_wait_probe"] = {"pid_alive": pid_busy, "gpu_memory_used_mib": used, "gpu_busy": gpu_busy}
        plan["status"] = "waiting_for_gpu" if pid_busy or gpu_busy else "ready"
        _write(output, plan)
        if not pid_busy and not gpu_busy:
            plan["gpu_wait_finished_at_utc"] = _utc_now()
            _write(output, plan)
            return
        time.sleep(max(1, poll_seconds))


def _post_build_real_manifest(root: Path, python_executable: str) -> dict[str, Any]:
    script = root / "scripts" / "build_real_student_transfer_manifest_from_receipts.py"
    if not script.exists():
        return {"status": "skipped", "reason": "builder_script_missing"}
    completed = subprocess.run(
        [python_executable, str(script.relative_to(root))],
        cwd=root,
        capture_output=True,
        text=True,
    )
    gate = DEFAULT_POST_MANIFEST_GATE
    payload = _load(gate)
    return {
        "status": "completed" if completed.returncode == 0 else "blocked_or_failed",
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout.splitlines()[-5:],
        "stderr_tail": completed.stderr.splitlines()[-5:],
        "gate": str(gate.relative_to(root) if gate.is_relative_to(root) else gate),
        "gate_status": payload.get("status"),
        "gate_blockers": payload.get("blockers", []),
    }


def _post_live_validation(root: Path, python_executable: str, env: dict[str, str]) -> dict[str, Any]:
    script = root / "scripts" / "run_real_student_transfer_live_validation.py"
    if not script.exists():
        return {"status": "skipped", "reason": "validation_script_missing"}
    completed = subprocess.run(
        [python_executable, str(script.relative_to(root))],
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = _load(DEFAULT_LIVE_VALIDATION)
    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout.splitlines()[-5:],
        "stderr_tail": completed.stderr.splitlines()[-5:],
        "validation": str(DEFAULT_LIVE_VALIDATION.relative_to(root) if DEFAULT_LIVE_VALIDATION.is_relative_to(root) else DEFAULT_LIVE_VALIDATION),
        "result_count": len(payload.get("results", [])) if isinstance(payload.get("results"), list) else 0,
        "statuses": [
            item.get("validation_status")
            for item in payload.get("results", [])
            if isinstance(item, dict)
        ][:10],
    }


def run_queue(
    root: Path,
    plan: dict[str, Any],
    *,
    output: Path,
    log_dir: Path,
    dry_run: bool,
    post_build_manifest: bool,
    post_live_validation: bool,
    owner_secret_env_file: Path | None,
    python_executable: str,
) -> dict[str, Any]:
    plan["started_at_utc"] = _utc_now()
    if plan["status"] != "ready":
        _write(output, plan)
        return plan
    if dry_run:
        plan["status"] = "dry_run_ready"
        plan["dry_run"] = True
        _write(output, plan)
        return plan
    log_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(_load_secret_env_file(owner_secret_env_file))
    env["PYTHONUNBUFFERED"] = "1"
    for job in plan["jobs"]:
        if job.get("status") != "queued":
            continue
        family = str(job.get("family") or "unknown")
        log_path = log_dir / f"{family}.train.log"
        job["log_path"] = str(log_path)
        job["started_at_utc"] = _utc_now()
        job["status"] = "running"
        _write(output, plan)
        with log_path.open("ab") as log_file:
            proc = subprocess.Popen(job["command"], cwd=root, stdout=log_file, stderr=subprocess.STDOUT, env=env)
            job["pid"] = proc.pid
            rc = proc.wait()
        job["returncode"] = rc
        job["finished_at_utc"] = _utc_now()
        job["status"] = "completed" if rc == 0 else "failed"
        _write(output, plan)
        if rc != 0:
            plan["status"] = "failed"
            plan["blockers"] = [f"training_job_failed:{family}"]
            _write(output, plan)
            return plan
    plan["finished_at_utc"] = _utc_now()
    plan["status"] = "completed"
    if post_live_validation:
        plan["post_training_live_validation"] = _post_live_validation(root, python_executable, env)
        if plan["post_training_live_validation"].get("status") != "completed":
            plan["status"] = "failed"
            plan["blockers"] = ["post_training_live_validation_failed"]
            _write(output, plan)
            return plan
    if post_build_manifest:
        plan["post_training_real_manifest_gate"] = _post_build_real_manifest(root, python_executable)
    _write(output, plan)
    return plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--wait-pid", type=int, default=0)
    parser.add_argument("--gpu-index", type=int, default=0)
    parser.add_argument("--max-gpu-used-mib", type=int, default=8192)
    parser.add_argument("--poll-seconds", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--post-live-validation", action="store_true")
    parser.add_argument("--owner-secret-env-file", type=Path, default=None)
    parser.add_argument("--no-post-build-manifest", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
    output = args.output if args.output.is_absolute() else root / args.output
    log_dir = args.log_dir if args.log_dir.is_absolute() else root / args.log_dir
    plan = build_queue_plan(
        root,
        manifest_path=manifest,
        python_executable=args.python_executable,
        selected_families=set(args.family),
        wait_pid=args.wait_pid,
        gpu_index=args.gpu_index,
        max_gpu_used_mib=args.max_gpu_used_mib,
    )
    _write(output, plan)
    if plan["status"] == "ready" and not args.dry_run:
        _wait_for_gpu(plan, poll_seconds=args.poll_seconds, output=output)
    result = run_queue(
        root,
        plan,
        output=output,
        log_dir=log_dir,
        dry_run=args.dry_run,
        post_build_manifest=not args.no_post_build_manifest,
        post_live_validation=args.post_live_validation,
        owner_secret_env_file=args.owner_secret_env_file,
        python_executable=args.python_executable,
    )
    print(json.dumps({"status": result["status"], "job_count": len(result["jobs"]), "output": str(output)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
