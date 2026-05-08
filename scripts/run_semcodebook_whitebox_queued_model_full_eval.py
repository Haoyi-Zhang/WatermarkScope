from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260508"
QUEUE = ROOT / f"results/SemCodebook/artifacts/generated/semcodebook_whitebox_next_gpu_queue_v1_{DATE}.json"
DEFAULT_OUTPUT = ROOT / f"results/SemCodebook/artifacts/generated/semcodebook_whitebox_queued_model_runner_receipt_v1_{DATE}.json"

REQUIRED_MODULES = ["torch", "transformers", "accelerate", "peft", "datasets"]
ADMISSION_CONTRACT = {
    "target_records": 7200,
    "task_count": 600,
    "positive_count": 2400,
    "negative_count": 4800,
    "attack_conditions": 8,
    "required_zero_failures": [
        "helper_failure_count",
        "compiler_failure_count",
        "mock_or_fallback_count",
        "negative_detected",
        "validator_repair_dependency_count",
    ],
    "threshold_policy": "no threshold changes after launch",
    "promotion_policy": "A queued model enters the main white-box table only after a complete 7200-row postrun audit passes.",
}

SMOKE_TASKS = [
    {
        "task_id": "semcodebook_smoke_python_sum_nonnegative",
        "language": "python",
        "prompt": "Write only a Python function solve(values) that returns the sum of non-negative integers in values.",
    },
    {
        "task_id": "semcodebook_smoke_python_unique_order",
        "language": "python",
        "prompt": "Write only a Python function solve(items) that removes duplicates while preserving first occurrence order.",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_capture(args: list[str], *, timeout: int = 30) -> tuple[int, str]:
    try:
        completed = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return completed.returncode, (completed.stdout + completed.stderr).strip()
    except Exception as exc:
        return 127, f"{type(exc).__name__}:{exc}"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected object JSON: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def nvidia_smi_state() -> dict[str, Any]:
    binary = shutil.which("nvidia-smi")
    if not binary:
        return {"available": False, "binary": "", "raw": ""}
    rc, out = run_capture([binary, "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader"])
    return {"available": rc == 0 and bool(out), "binary": binary, "raw": out, "returncode": rc}


def module_state() -> dict[str, Any]:
    code = (
        "import importlib, json\n"
        "out={}\n"
        f"for name in {REQUIRED_MODULES!r}:\n"
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
    rc, out = run_capture([os.sys.executable, "-c", code], timeout=60)
    try:
        payload = json.loads(out.splitlines()[-1]) if out else {}
    except json.JSONDecodeError:
        payload = {"parse_error": out}
    payload["returncode"] = rc
    payload["python"] = os.sys.executable
    return payload


def queue_entry(model: str) -> dict[str, Any]:
    queue = load_json(QUEUE) if QUEUE.exists() else {}
    entries = queue.get("next_gpu_queue", [])
    if not isinstance(entries, list):
        return {}
    if not model and entries:
        first = entries[0]
        return first if isinstance(first, dict) else {}
    for entry in entries:
        if isinstance(entry, dict) and str(entry.get("model", "")) == model:
            return entry
    return {}


def model_access_probe(model: str, *, local_files_only: bool) -> dict[str, Any]:
    code = (
        "import json\n"
        "from huggingface_hub import model_info\n"
        f"model={model!r}\n"
        "try:\n"
        "    info=model_info(model, timeout=20)\n"
        "    print(json.dumps({'ok': True, 'model': model, 'private': getattr(info, 'private', None), 'gated': getattr(info, 'gated', None), 'sha': getattr(info, 'sha', '')}, sort_keys=True))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'ok': False, 'model': model, 'error': type(exc).__name__ + ':' + str(exc)[:240]}, sort_keys=True))\n"
    )
    if local_files_only:
        return {"ok": None, "skipped": True, "reason": "local_files_only_requested"}
    rc, out = run_capture([os.sys.executable, "-c", code], timeout=60)
    try:
        payload = json.loads(out.splitlines()[-1]) if out else {}
    except json.JSONDecodeError:
        payload = {"ok": False, "parse_error": out}
    payload["returncode"] = rc
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed SemCodebook queued white-box model runner.")
    parser.add_argument("--model", default="", help="Queued Hugging Face model id. Defaults to first queue entry.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--full-7200", action="store_true")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--max-new-tokens", type=int, default=96)
    parser.add_argument("--temperature", type=float, default=0.0)
    return parser.parse_args()


def build_blocked_payload(args: argparse.Namespace, blockers: list[str], *, entry: dict[str, Any], modules: dict[str, Any], gpu: dict[str, Any], access: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "semcodebook_whitebox_queued_model_runner_receipt_v1",
        "generated_at_utc": utc_now(),
        "project": "SemCodebook",
        "claim_bearing": False,
        "gate_pass": False,
        "blocked": True,
        "model": args.model or entry.get("model", ""),
        "queue_entry": entry,
        "run_mode": "full_7200" if args.full_7200 else "smoke" if args.smoke else "preflight_only",
        "admission_contract": ADMISSION_CONTRACT,
        "resource_state": {
            "gpu": gpu,
            "python_modules": modules,
            "model_access": access,
        },
        "claim_policy": {
            "receipt_enters_main_claim": False,
            "partial_rows_enter_main_claim": False,
            "smoke_rows_replace_7200_cell": False,
            "cpu_only_run_can_promote": False,
        },
        "blockers": blockers,
    }


def smoke_generate(args: argparse.Namespace, model: str) -> tuple[list[dict[str, Any]], list[str]]:
    blockers: list[str] = []
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as exc:
        return [], [f"import_failed:{type(exc).__name__}:{str(exc)[:120]}"]
    if not torch.cuda.is_available():
        return [], ["torch_cuda_unavailable"]
    started = time.time()
    try:
        tokenizer = AutoTokenizer.from_pretrained(model, local_files_only=args.local_files_only, trust_remote_code=False)
        model_obj = AutoModelForCausalLM.from_pretrained(
            model,
            local_files_only=args.local_files_only,
            trust_remote_code=False,
            torch_dtype=torch.float16,
            device_map="auto",
        )
    except Exception as exc:
        return [], [f"model_load_failed:{type(exc).__name__}:{str(exc)[:160]}"]
    rows: list[dict[str, Any]] = []
    for task in SMOKE_TASKS:
        prompt = (
            "### SemCodebook queued-model smoke generation\n"
            f"Language: {task['language']}\n"
            "Return code only. Do not include Markdown.\n"
            f"Task: {task['prompt']}\n"
        )
        try:
            encoded = tokenizer(prompt, return_tensors="pt").to(model_obj.device)
            with torch.no_grad():
                output = model_obj.generate(
                    **encoded,
                    max_new_tokens=args.max_new_tokens,
                    do_sample=args.temperature > 0.0,
                    temperature=args.temperature if args.temperature > 0.0 else None,
                    pad_token_id=tokenizer.eos_token_id,
                )
            text = tokenizer.decode(output[0], skip_special_tokens=True)
        except Exception as exc:
            blockers.append(f"generation_failed:{task['task_id']}:{type(exc).__name__}:{str(exc)[:120]}")
            continue
        rows.append(
            {
                "task_id": task["task_id"],
                "language": task["language"],
                "model": model,
                "prompt_hash": sha256_text(prompt),
                "raw_generation_hash": sha256_text(text),
                "raw_generation_preview": text[-800:],
                "claim_bearing": False,
                "formal_claim_allowed": False,
                "support_only_not_claim_bearing": True,
                "record_hash": sha256_text(json.dumps({"task": task, "model": model, "text": text}, sort_keys=True)),
            }
        )
    elapsed = round(time.time() - started, 3)
    for row in rows:
        row["elapsed_seconds_total"] = elapsed
    return rows, blockers


def main() -> int:
    args = parse_args()
    entry = queue_entry(args.model)
    if not args.model and entry:
        args.model = str(entry.get("model", ""))
    gpu = nvidia_smi_state()
    modules = module_state()
    access = model_access_probe(args.model, local_files_only=args.local_files_only) if args.model else {"ok": False, "error": "model_missing"}
    blockers: list[str] = []
    if not entry:
        blockers.append("model_not_in_queue")
    if not gpu.get("available"):
        blockers.append("nvidia_smi_unavailable")
    if not modules.get("torch_cuda", {}).get("cuda_available"):
        blockers.append("torch_cuda_unavailable")
    for name in REQUIRED_MODULES:
        if modules.get(name, {}).get("ok") is not True:
            blockers.append(f"python_module_unavailable:{name}")
    if access.get("ok") is False:
        blockers.append("model_access_probe_failed")
    if args.full_7200:
        blockers.append("full_detector_postrun_pipeline_not_attached")
    if not (args.preflight_only or args.smoke or args.full_7200):
        blockers.append("run_mode_not_selected")
    output = ROOT / args.output
    if blockers or args.preflight_only:
        payload = build_blocked_payload(args, blockers, entry=entry, modules=modules, gpu=gpu, access=access)
        if args.preflight_only and not blockers:
            payload["blocked"] = False
            payload["gate_pass"] = True
        write_json(output, payload)
        print(json.dumps({"gate_pass": payload["gate_pass"], "blocked": payload["blocked"], "blockers": blockers}, ensure_ascii=True))
        return 0 if args.preflight_only else 1
    rows, smoke_blockers = smoke_generate(args, args.model)
    payload = {
        "schema_version": "semcodebook_whitebox_queued_model_runner_receipt_v1",
        "generated_at_utc": utc_now(),
        "project": "SemCodebook",
        "claim_bearing": False,
        "gate_pass": not smoke_blockers and bool(rows),
        "blocked": bool(smoke_blockers) or not rows,
        "model": args.model,
        "queue_entry": entry,
        "run_mode": "smoke",
        "admission_contract": ADMISSION_CONTRACT,
        "resource_state": {
            "gpu": gpu,
            "python_modules": modules,
            "model_access": access,
        },
        "records": rows,
        "record_count": len(rows),
        "claim_policy": {
            "receipt_enters_main_claim": False,
            "partial_rows_enter_main_claim": False,
            "smoke_rows_replace_7200_cell": False,
            "cpu_only_run_can_promote": False,
        },
        "blockers": smoke_blockers,
    }
    write_json(output, payload)
    print(json.dumps({"gate_pass": payload["gate_pass"], "record_count": len(rows), "blockers": smoke_blockers}, ensure_ascii=True))
    return 0 if payload["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
