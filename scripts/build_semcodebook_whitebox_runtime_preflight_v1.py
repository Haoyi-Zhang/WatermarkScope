from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260508"
OUT = ROOT / f"results/SemCodebook/artifacts/generated/semcodebook_whitebox_runtime_preflight_v1_{DATE}.json"
DEFAULT_PYTHON = ROOT / ".venv-semcodebook-gpu" / "Scripts" / "python.exe"

RUNTIME_MODULES = ["torch", "transformers", "accelerate", "peft", "datasets"]
LOCAL_REQUIRED_FILES = [
    "projects/SemCodebook/src/semcodebook/protocol.py",
    "projects/SemCodebook/src/semcodebook/detector.py",
    "projects/SemCodebook/src/semcodebook/evaluation.py",
    "projects/SemCodebook/src/semcodebook/variant_pool.py",
]
HISTORICAL_FULL_RUNNER_CANDIDATES = [
    ".codex_remote_semcodebook_full_ablation/materialize_generation_changing_ablation_full_eval.py",
    "projects/SemCodebook/scripts/run_whitebox_queued_model_full_eval.py",
    "scripts/run_semcodebook_whitebox_queued_model_full_eval.py",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_capture(args: list[str], *, timeout: int = 30, cwd: Path | None = None) -> tuple[int, str]:
    try:
        completed = subprocess.run(args, cwd=cwd or ROOT, text=True, capture_output=True, timeout=timeout)
        return completed.returncode, (completed.stdout + completed.stderr).strip()
    except Exception as exc:
        return 127, f"{type(exc).__name__}:{exc}"


def python_probe(python: Path) -> dict[str, Any]:
    if not python.exists():
        return {"python": str(python), "exists": False, "blocker": "python_not_found"}
    code = (
        "import importlib, json\n"
        "out={}\n"
        "for name in " + repr(RUNTIME_MODULES) + ":\n"
        "    try:\n"
        "        mod=importlib.import_module(name)\n"
        "        out[name]={'ok': True, 'version': getattr(mod, '__version__', 'unknown')}\n"
        "    except Exception as exc:\n"
        "        out[name]={'ok': False, 'error': type(exc).__name__ + ':' + str(exc)[:240]}\n"
        "try:\n"
        "    import torch\n"
        "    out['torch_cuda']={'cuda_available': bool(torch.cuda.is_available()), 'cuda_version': torch.version.cuda, 'device_count': torch.cuda.device_count(), 'device0': torch.cuda.get_device_name(0) if torch.cuda.is_available() else ''}\n"
        "except Exception as exc:\n"
        "    out['torch_cuda']={'cuda_available': False, 'error': type(exc).__name__ + ':' + str(exc)[:240]}\n"
        "print(json.dumps(out, sort_keys=True))\n"
    )
    rc, out = run_capture([str(python), "-c", code], timeout=60)
    try:
        parsed = json.loads(out.splitlines()[-1]) if out else {}
    except json.JSONDecodeError:
        parsed = {"parse_error": out}
    parsed.update({"python": str(python), "exists": True, "returncode": rc})
    return parsed


def nvidia_smi_state() -> dict[str, Any]:
    binary = shutil.which("nvidia-smi")
    if not binary:
        return {"available": False, "binary": "", "raw": ""}
    rc, out = run_capture([binary, "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader"], timeout=30)
    return {"available": rc == 0 and bool(out), "binary": binary, "raw": out, "returncode": rc}


def remote_js4_state() -> dict[str, Any]:
    key = Path(os.environ.get("USERPROFILE", "")) / ".ssh" / "codemark_js2_ed25519"
    if not key.exists():
        return {"checked": False, "blocker": "ssh_key_missing"}
    command = (
        "set -o pipefail; "
        "gpu=$(lspci | egrep -i 'nvidia|3d|vga' || true); "
        "dev=$(ls /dev/nvidia* 2>/dev/null || true); "
        "smi=$(nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv,noheader 2>&1 || true); "
        "printf '%s\\n---DEV---\\n%s\\n---SMI---\\n%s\\n' \"$gpu\" \"$dev\" \"$smi\""
    )
    rc, out = run_capture(
        [
            "ssh",
            "-i",
            str(key),
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "StrictHostKeyChecking=no",
            "-p",
            "15012",
            "root@js4.blockelite.cn",
            command,
        ],
        timeout=60,
    )
    return {"checked": True, "returncode": rc, "raw": out, "nvidia_device_visible": "/dev/nvidia" in out and "failed" not in out.lower()}


def main() -> int:
    python = Path(os.environ.get("SEMCODEBOOK_GPU_PYTHON", str(DEFAULT_PYTHON)))
    local_gpu = nvidia_smi_state()
    modules = python_probe(python)
    remote = remote_js4_state()
    missing_files = [rel for rel in LOCAL_REQUIRED_FILES if not (ROOT / rel).exists()]
    runner_candidates = [
        {"path": rel, "exists": (ROOT / rel).exists()}
        for rel in HISTORICAL_FULL_RUNNER_CANDIDATES
    ]
    blockers: list[str] = []
    if not local_gpu.get("available"):
        blockers.append("local_nvidia_smi_unavailable")
    torch_cuda = modules.get("torch_cuda", {}) if isinstance(modules, dict) else {}
    if not torch_cuda.get("cuda_available"):
        blockers.append("torch_cuda_unavailable")
    for name in RUNTIME_MODULES:
        item = modules.get(name, {}) if isinstance(modules, dict) else {}
        if item.get("ok") is not True:
            blockers.append(f"python_module_unavailable:{name}")
    if missing_files:
        blockers.append("semcodebook_runtime_files_missing")
    if not any(item["exists"] for item in runner_candidates):
        blockers.append("whitebox_queued_model_full_runner_missing")
    if remote.get("checked") and remote.get("nvidia_device_visible") is not True:
        blockers.append("js4_nvidia_device_unavailable")
    payload = {
        "schema_version": "semcodebook_whitebox_runtime_preflight_v1",
        "generated_at_utc": utc_now(),
        "project": "SemCodebook",
        "claim_bearing": False,
        "gate_pass": not blockers,
        "full_whitebox_launch_allowed": not blockers,
        "smoke_launch_allowed": not blockers,
        "local_gpu": local_gpu,
        "python_runtime": modules,
        "remote_js4": remote,
        "required_local_files": [{"path": rel, "exists": (ROOT / rel).exists()} for rel in LOCAL_REQUIRED_FILES],
        "missing_required_local_files": missing_files,
        "full_runner_candidates": runner_candidates,
        "resource_policy": {
            "failed_or_partial_model_cells_enter_main_claim": False,
            "cpu_only_generation_may_promote_whitebox_claim": False,
            "support_only_smoke_may_replace_7200_row_cell": False,
        },
        "next_allowed_action": (
            "Install a CUDA-enabled torch wheel or move to a host with visible NVIDIA devices, then run a queued-model "
            "smoke before any 7200-row cell launch."
        ),
        "blockers": blockers,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"gate_pass": payload["gate_pass"], "full_whitebox_launch_allowed": payload["full_whitebox_launch_allowed"], "blockers": blockers}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
