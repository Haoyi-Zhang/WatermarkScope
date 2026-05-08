from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHECKOUT = ROOT / "external_checkout" / "kgw-lm-watermarking"
TASKS = ROOT / "benchmarks" / "carrier_stressbench_tasks.json"
OUTPUT = ROOT / "artifacts" / "generated" / "baselines" / "kgw_official_carrierstressbench_task_records.json"
PROGRESS = ROOT / "artifacts" / "generated" / "baselines" / "kgw_official_carrierstressbench_task_records.jsonl"
SCHEMA_VERSION = "semcodebook_kgw_official_carrierstressbench_task_records_v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_tasks(limit: int) -> list[dict[str, Any]]:
    payload = json.loads(TASKS.read_text(encoding="utf-8"))
    tasks = [dict(item) for item in payload.get("tasks", []) if isinstance(item, dict)]
    return tasks[:limit] if limit else tasks


def _extract_code(text: str) -> str:
    match = re.search(r"```(?:python|go|java|javascript|cpp|c\+\+)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip() + "\n"
    return text.strip() + "\n"


def _python_tests_pass(code: str, tests: list[str]) -> tuple[bool, str]:
    script = code + "\n" + "\n".join(tests) + "\n"
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", script],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout"
    if completed.returncode == 0:
        return True, ""
    return False, (completed.stderr.strip() or completed.stdout.strip() or f"exit:{completed.returncode}")[-240:]


def _existing_records() -> list[dict[str, Any]]:
    if not PROGRESS.exists():
        return []
    records = []
    for line in PROGRESS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    return records


def _configure_cache() -> None:
    cache_root = Path("/data/codemark/shared/hf_cache")
    os.environ.setdefault("HF_HOME", str(cache_root))
    os.environ.setdefault("HF_HUB_CACHE", str(cache_root))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(cache_root))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")


def _load_stack(model_name: str):
    _configure_cache()
    sys.path.insert(0, str(CHECKOUT))
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, LogitsProcessorList
    from watermark_processor import WatermarkDetector, WatermarkLogitsProcessor

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
    ).to("cuda")
    model.eval()
    device = next(model.parameters()).device
    vocab = list(range(len(tokenizer)))
    processor = WatermarkLogitsProcessor(vocab=vocab, gamma=0.25, delta=2.0, seeding_scheme="simple_1")
    detector = WatermarkDetector(
        vocab=vocab,
        gamma=0.25,
        delta=2.0,
        seeding_scheme="simple_1",
        device=device,
        tokenizer=tokenizer,
        z_threshold=4.0,
        normalizers=[],
        ignore_repeated_bigrams=False,
    )
    return torch, tokenizer, model, LogitsProcessorList([processor]), detector, device


def _generate_record(task: dict[str, Any], stack: tuple[Any, ...], *, max_new_tokens: int) -> dict[str, Any]:
    torch, tokenizer, model, processors, detector, device = stack
    prompt = str(task.get("prompt", ""))
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024).to(device)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.95,
            logits_processor=processors,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated_ids = output_ids[0][inputs["input_ids"].shape[-1] :]
    generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
    generated_code = _extract_code(generated_text)
    token_ids = tokenizer(generated_text, add_special_tokens=False)["input_ids"]
    token_tensor = torch.tensor(token_ids, dtype=torch.long, device=device)
    detection = detector.detect(tokenized_text=token_tensor, return_prediction=True, return_scores=True)
    language = str(task.get("language", ""))
    task_passed = False
    task_error = "not_python_or_not_executed"
    if language == "python":
        task_passed, task_error = _python_tests_pass(generated_code, [str(item) for item in task.get("tests", [])])
    return {
        "schema_version": "semcodebook_kgw_official_task_record_v1",
        "baseline": "KGW",
        "official_baseline": True,
        "official_task_level_output": True,
        "task_id": str(task.get("task_id", "")),
        "family": str(task.get("family", "")),
        "language": language,
        "negative_control": bool(task.get("metadata", {}).get("negative_control", False)),
        "prompt_sha256": _sha256_text(prompt),
        "generated_text_sha256": _sha256_text(generated_text),
        "generated_code_sha256": _sha256_text(generated_code),
        "generated_text": generated_text,
        "task_tests_passed": task_passed,
        "task_error": task_error,
        "official_checkout_slug": "kgw-lm-watermarking",
        "official_module": "watermark_processor.WatermarkLogitsProcessor+WatermarkDetector",
        "official_core_logic_modified": False,
        "official_pipeline_end_to_end": True,
        "official_language_supported": True,
        "unsupported_language": False,
        "task_level_end_to_end": True,
        "pipeline_scope": "official_generation_detection_pipeline",
        "uses_model_generation": True,
        "uses_provider": False,
        "decision": bool(detection.get("prediction", False)),
        "decision_status": "detected" if bool(detection.get("prediction", False)) else "not_detected",
        "score": float(detection.get("z_score", 0.0)),
        "threshold": 4.0,
        "num_tokens_scored": int(detection.get("num_tokens_scored", 0)),
        "main_table_denominator_included": True,
        "fail_closed": False,
        "abstain_reason": "",
        "failure_boundary": "",
        "claim_bearing": True,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tasks = _load_tasks(args.limit)
    done = {str(item.get("task_id", "")): item for item in _existing_records()} if args.resume else {}
    stack = _load_stack(args.model)
    records: list[dict[str, Any]] = []
    with PROGRESS.open("a", encoding="utf-8") as handle:
        for task in tasks:
            task_id = str(task.get("task_id", ""))
            if task_id in done:
                records.append(done[task_id])
                continue
            record = _generate_record(task, stack, max_new_tokens=args.max_new_tokens)
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
            handle.flush()
            records.append(record)
    # Preserve progress-file order and de-duplicate on resume.
    merged = {str(item.get("task_id", "")): item for item in _existing_records()}
    for item in records:
        merged[str(item.get("task_id", ""))] = item
    final_records = [merged[str(task.get("task_id", ""))] for task in tasks if str(task.get("task_id", "")) in merged]
    detection_count = sum(1 for item in final_records if bool(item.get("decision", False)))
    task_pass_count = sum(1 for item in final_records if bool(item.get("task_tests_passed", False)))
    target_count = len(tasks)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "baseline": "KGW",
        "official_baseline": True,
        "official_task_level_output": True,
        "official_generation_detection_pipeline": True,
        "official_repo_url": "https://github.com/jwkirchenbauer/lm-watermarking.git",
        "official_checkout": "external_checkout/kgw-lm-watermarking",
        "official_entrypoint": "watermark_processor.WatermarkLogitsProcessor+WatermarkDetector",
        "upstream_core_logic_modified": False,
        "generation_model": args.model,
        "claim_role": "official_kgw_task_level_baseline_output",
        "summary": {
            "record_count": len(final_records),
            "target_record_count": target_count,
            "detection_count": detection_count,
            "detection_rate": round(detection_count / max(len(final_records), 1), 4),
            "task_pass_count": task_pass_count,
            "task_pass_rate": round(task_pass_count / max(len(final_records), 1), 4),
            "language_count": len({str(item.get("language", "")) for item in final_records}),
            "family_count": len({str(item.get("family", "")) for item in final_records}),
        },
        "records": final_records,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="deepseek-ai/deepseek-coder-6.7b-instruct")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    payload = run(args)
    print(json.dumps({"record_count": payload["summary"]["record_count"], "target_record_count": payload["summary"]["target_record_count"], "output": str(OUTPUT)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
