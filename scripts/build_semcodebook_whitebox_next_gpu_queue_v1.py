from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260508"
OUT = ROOT / f"results/SemCodebook/artifacts/generated/semcodebook_whitebox_next_gpu_queue_v1_{DATE}.json"


NEXT_MODELS = [
    {
        "model": "codellama/CodeLlama-7b-Instruct-hf",
        "family": "codellama",
        "scale_group": "mid",
        "reason": "Adds a major Llama-derived code family absent from admitted rows.",
    },
    {
        "model": "codellama/CodeLlama-13b-Instruct-hf",
        "family": "codellama",
        "scale_group": "large",
        "reason": "Tests scale-up behavior in the Llama-derived family.",
    },
    {
        "model": "Salesforce/codegen-2B-mono",
        "family": "codegen",
        "scale_group": "small",
        "reason": "Fills CodeGen scale continuity between 350M and larger public code LMs.",
    },
    {
        "model": "Salesforce/codegen-6B-mono",
        "family": "codegen",
        "scale_group": "mid",
        "reason": "Tests whether the CodeGen family holds beyond the tiny admitted cell.",
    },
    {
        "model": "stabilityai/stable-code-3b",
        "family": "stable-code",
        "scale_group": "small",
        "reason": "Adds an independent public code family if licensing/cache availability permits.",
    },
]


def run_capture(args: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=30)
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except Exception as exc:  # pragma: no cover - defensive diagnostics
        return 127, f"{type(exc).__name__}:{exc}"


def python_module_state(name: str) -> str:
    code = f"import {name}; print('ok')"
    rc, out = run_capture(["python", "-c", code])
    return "ok" if rc == 0 and "ok" in out else out.splitlines()[-1] if out else "missing"


def gpu_state() -> dict[str, Any]:
    binary = shutil.which("nvidia-smi")
    if not binary:
        return {"nvidia_smi": "missing", "available": False, "raw": ""}
    rc, out = run_capture([binary, "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader"])
    return {"nvidia_smi": binary, "available": rc == 0 and bool(out.strip()), "raw": out}


def main() -> int:
    gpu = gpu_state()
    modules = {name: python_module_state(name) for name in ["torch", "transformers", "accelerate", "peft", "datasets"]}
    manifest_path = ROOT / "results/SemCodebook/artifacts/generated/semcodebook_whitebox_main_denominator_source_manifest_20260505.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    current_models = [row.get("model") for row in manifest.get("rows", []) if isinstance(row, dict)]
    blockers: list[str] = []
    if not gpu["available"]:
        blockers.append("nvidia_gpu_unavailable")
    if modules.get("torch") != "ok":
        blockers.append("torch_missing")
    if modules.get("transformers") != "ok":
        blockers.append("transformers_missing")
    if modules.get("peft") != "ok":
        blockers.append("peft_missing")
    payload = {
        "schema_version": "semcodebook_whitebox_next_gpu_queue_v1",
        "date": DATE,
        "project": "SemCodebook",
        "claim_bearing": False,
        "gate_pass": not blockers,
        "gpu_run_allowed_now": not blockers,
        "current_admitted_source": manifest_path.relative_to(ROOT).as_posix(),
        "current_admitted_model_count": len(current_models),
        "current_admitted_models": current_models,
        "current_total_admitted_records": manifest.get("summary", {}).get("total_admitted_records"),
        "resource_state": {
            "gpu": gpu,
            "python_modules": modules,
        },
        "next_gpu_queue": [
            {
                **item,
                "target_records": 7200,
                "task_count": 600,
                "attack_conditions": 8,
                "admission_required": [
                    "postrun_audit_gate_pass",
                    "record_count == 7200",
                    "positive_count == 2400",
                    "negative_count == 4800",
                    "helper_failure_count == 0",
                    "compiler_failure_count == 0",
                    "mock_or_fallback_count == 0",
                    "negative_detected == 0",
                    "no threshold changes after launch",
                ],
                "claim_policy": "support/stretch only until full 7200-row postrun audit passes; failed or partial cells remain nonpromotion.",
            }
            for item in NEXT_MODELS
        ],
        "recommended_launch_order": [
            "codellama/CodeLlama-7b-Instruct-hf",
            "stabilityai/stable-code-3b",
            "codellama/CodeLlama-13b-Instruct-hf",
            "Salesforce/codegen-2B-mono",
            "Salesforce/codegen-6B-mono",
        ],
        "blocked_policy": (
            "The existing 72,000-row SemCodebook claim remains unchanged. This queue only controls future "
            "white-box expansion. A machine without NVIDIA device access must not be reported as having run "
            "new white-box model experiments."
        ),
        "blockers": blockers,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"gate_pass": payload["gate_pass"], "gpu_run_allowed_now": payload["gpu_run_allowed_now"], "blockers": blockers}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
