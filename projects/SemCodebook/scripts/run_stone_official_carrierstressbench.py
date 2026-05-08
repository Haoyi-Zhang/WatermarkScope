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
CHECKOUT = ROOT / "external_checkout" / "stone-watermarking" / "stone_implementation"
TASKS = ROOT / "benchmarks" / "carrier_stressbench_tasks.json"
OUTPUT = ROOT / "artifacts" / "generated" / "baselines" / "stone_official_carrierstressbench_task_records.json"
PROGRESS = ROOT / "artifacts" / "generated" / "baselines" / "stone_official_carrierstressbench_task_records.jsonl"
SCHEMA_VERSION = "semcodebook_stone_official_carrierstressbench_task_records_v1"
SUPPORTED_LANGUAGES = {"python": "python", "cpp": "cpp", "c++": "cpp", "java": "java"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_tasks(limit: int) -> list[dict[str, Any]]:
    payload = json.loads(TASKS.read_text(encoding="utf-8"))
    tasks = [dict(item) for item in payload.get("tasks", []) if isinstance(item, dict)]
    return tasks[:limit] if limit else tasks


def _existing_records() -> list[dict[str, Any]]:
    if not PROGRESS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in PROGRESS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


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


def _configure_cache() -> None:
    cache_root = Path("/data/codemark/shared/hf_cache")
    os.environ.setdefault("HF_HOME", str(cache_root))
    os.environ.setdefault("HF_HUB_CACHE", str(cache_root))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(cache_root))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")


def _load_stack(model_name: str, *, max_new_tokens: int) -> tuple[Any, ...]:
    _configure_cache()
    sys.path.insert(0, str(CHECKOUT))
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from utils.transformers_config import TransformersConfig
    from watermark.auto_watermark import STONEAutoWatermark

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

    def factory(language: str) -> Any:
        config = TransformersConfig(
            model=model,
            tokenizer=tokenizer,
            vocab_size=len(tokenizer),
            device=device,
            max_new_tokens=max_new_tokens,
            min_length=16,
            do_sample=True,
            temperature=0.7,
            top_p=0.95,
            no_repeat_ngram_size=4,
            pad_token_id=tokenizer.eos_token_id,
        )
        return STONEAutoWatermark.load(
            "STONE",
            transformers_config=config,
            skipping_rule="all_pl",
            watermark_on_pl="False",
            gamma=0.5,
            delta=2.0,
            hash_key=15485863,
            prefix_length=1,
            z_threshold=4.0,
            language=language,
        )

    return tokenizer, model, factory


def _fail_closed_record(
    task: dict[str, Any],
    *,
    reason: str,
    official_language_supported: bool,
) -> dict[str, Any]:
    prompt = str(task.get("prompt", ""))
    language = str(task.get("language", "")).lower()
    unsupported_language = not official_language_supported
    pipeline_scope = (
        "official_pipeline_fail_closed_unsupported_language"
        if unsupported_language
        else "official_pipeline_fail_closed_runtime_failure"
    )
    decision_status = "fail_closed_unsupported_language" if unsupported_language else "fail_closed_runtime_failure"
    return {
        "schema_version": "semcodebook_stone_official_task_record_v1",
        "baseline": "STONE",
        "task_id": str(task.get("task_id", "")),
        "family": str(task.get("family", "")),
        "language": language,
        "negative_control": bool(task.get("metadata", {}).get("negative_control", False)),
        "prompt_sha256": _sha256_text(prompt),
        "generated_text_sha256": "",
        "generated_code_sha256": "",
        "generated_text": "",
        "task_tests_passed": False,
        "task_error": reason,
        "official_language_supported": official_language_supported,
        "official_checkout_slug": "stone-watermarking",
        "official_module": "watermark.auto_watermark.STONEAutoWatermark",
        "official_core_logic_modified": False,
        "official_pipeline_end_to_end": False,
        "task_level_end_to_end": True,
        "pipeline_scope": pipeline_scope,
        "uses_model_generation": False,
        "uses_provider": False,
        "decision": False,
        "decision_status": decision_status,
        "score": 0.0,
        "threshold": 4.0,
        "claim_bearing": True,
        "main_table_denominator_included": True,
        "fail_closed": True,
        "unsupported_language": unsupported_language,
        "abstain_reason": reason,
        "failure_boundary": "official_stone_language_support" if unsupported_language else "official_stone_runtime",
    }


def _generate_record(task: dict[str, Any], stack: tuple[Any, ...]) -> dict[str, Any]:
    _, _, factory = stack
    raw_language = str(task.get("language", "")).lower()
    stone_language = SUPPORTED_LANGUAGES.get(raw_language)
    if stone_language is None:
        return _fail_closed_record(
            task,
            reason=f"official_stone_language_unsupported:{raw_language}",
            official_language_supported=False,
        )
    prompt = str(task.get("prompt", ""))
    try:
        watermark = factory(stone_language)
        generated_text = str(watermark.generate_watermarked_text(prompt))
        generated_code = _extract_code(generated_text)
        detection = watermark.detect_watermark(generated_text, return_dict=True)
        task_passed = False
        task_error = "not_python_or_not_executed"
        if raw_language == "python":
            task_passed, task_error = _python_tests_pass(generated_code, [str(item) for item in task.get("tests", [])])
        return {
            "schema_version": "semcodebook_stone_official_task_record_v1",
            "baseline": "STONE",
            "task_id": str(task.get("task_id", "")),
            "family": str(task.get("family", "")),
            "language": raw_language,
            "stone_language": stone_language,
            "negative_control": bool(task.get("metadata", {}).get("negative_control", False)),
            "prompt_sha256": _sha256_text(prompt),
            "generated_text_sha256": _sha256_text(generated_text),
            "generated_code_sha256": _sha256_text(generated_code),
            "generated_text": generated_text,
            "task_tests_passed": task_passed,
            "task_error": task_error,
            "official_language_supported": True,
            "official_checkout_slug": "stone-watermarking",
            "official_module": "watermark.auto_watermark.STONEAutoWatermark",
            "official_core_logic_modified": False,
            "official_pipeline_end_to_end": True,
            "task_level_end_to_end": True,
            "pipeline_scope": "official_generation_detection_pipeline",
            "uses_model_generation": True,
            "uses_provider": False,
            "decision": bool(detection.get("is_watermarked", False)),
            "decision_status": "detected" if bool(detection.get("is_watermarked", False)) else "not_detected",
            "score": float(detection.get("score", 0.0)),
            "threshold": 4.0,
            "claim_bearing": True,
            "main_table_denominator_included": True,
            "fail_closed": False,
            "unsupported_language": False,
            "abstain_reason": "",
            "failure_boundary": "",
        }
    except Exception as exc:
        return _fail_closed_record(
            task,
            reason=f"official_stone_runtime_failure:{type(exc).__name__}:{str(exc)[:160]}",
            official_language_supported=True,
        )


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    language_supported = bool(normalized.get("official_language_supported", False))
    pipeline_scope = str(normalized.get("pipeline_scope", ""))
    task_error = str(normalized.get("task_error", ""))
    unsupported = (not language_supported) or pipeline_scope == "official_pipeline_fail_closed_unsupported_language"
    fail_closed = unsupported or pipeline_scope == "official_pipeline_fail_closed_runtime_failure" or task_error.startswith(
        "official_stone_runtime_failure:"
    )
    normalized["main_table_denominator_included"] = True
    normalized["unsupported_language"] = bool(unsupported)
    normalized["fail_closed"] = bool(fail_closed)
    if fail_closed:
        normalized["decision"] = False
        normalized["score"] = float(normalized.get("score", 0.0) or 0.0)
        normalized["uses_model_generation"] = bool(normalized.get("uses_model_generation", False)) and not unsupported
        normalized["official_pipeline_end_to_end"] = False
        normalized["abstain_reason"] = task_error or (
            f"official_stone_language_unsupported:{normalized.get('language', '')}" if unsupported else "official_stone_runtime_failure"
        )
        normalized["decision_status"] = (
            "fail_closed_unsupported_language" if unsupported else "fail_closed_runtime_failure"
        )
        normalized["failure_boundary"] = (
            "official_stone_language_support" if unsupported else "official_stone_runtime"
        )
        if unsupported:
            normalized["official_language_supported"] = False
            normalized["pipeline_scope"] = "official_pipeline_fail_closed_unsupported_language"
            normalized["uses_model_generation"] = False
    else:
        decision = bool(normalized.get("decision", False))
        normalized["decision_status"] = "detected" if decision else "not_detected"
        normalized["abstain_reason"] = ""
        normalized["failure_boundary"] = ""
        normalized["official_language_supported"] = True
        normalized["official_pipeline_end_to_end"] = True
        normalized["pipeline_scope"] = "official_generation_detection_pipeline"
    normalized.setdefault("claim_bearing", True)
    normalized.setdefault("uses_provider", False)
    return normalized


def _load_final_records(tasks: list[dict[str, Any]], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {str(item.get("task_id", "")): _normalize_record(item) for item in records}
    return [merged[str(task.get("task_id", ""))] for task in tasks if str(task.get("task_id", "")) in merged]


def _payload_from_records(args: argparse.Namespace, tasks: list[dict[str, Any]], final_records: list[dict[str, Any]]) -> dict[str, Any]:
    detection_count = sum(1 for item in final_records if bool(item.get("decision", False)))
    task_pass_count = sum(1 for item in final_records if bool(item.get("task_tests_passed", False)))
    unsupported_count = sum(1 for item in final_records if bool(item.get("unsupported_language", False)))
    fail_closed_count = sum(1 for item in final_records if bool(item.get("fail_closed", False)))
    official_supported_count = sum(1 for item in final_records if bool(item.get("official_language_supported", False)))
    official_pipeline_count = sum(1 for item in final_records if bool(item.get("official_pipeline_end_to_end", False)))
    target_count = len(tasks)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "baseline": "STONE",
        "official_baseline": True,
        "official_task_level_output": True,
        "official_generation_detection_pipeline": True,
        "official_repo_url": "https://github.com/inistory/STONE-watermarking.git",
        "official_checkout": "external_checkout/stone-watermarking",
        "official_entrypoint": "watermark.auto_watermark.STONEAutoWatermark",
        "upstream_core_logic_modified": False,
        "generation_model": args.model,
        "claim_role": "official_stone_task_level_baseline_output",
        "fail_closed_policy": "Unsupported official STONE languages remain in the 600-task record set as explicit fail-closed denominator records; no task is deleted.",
        "summary": {
            "record_count": len(final_records),
            "target_record_count": target_count,
            "detection_count": detection_count,
            "detection_rate": round(detection_count / max(len(final_records), 1), 4),
            "task_pass_count": task_pass_count,
            "task_pass_rate": round(task_pass_count / max(len(final_records), 1), 4),
            "unsupported_language_count": unsupported_count,
            "fail_closed_record_count": fail_closed_count,
            "official_supported_record_count": official_supported_count,
            "official_pipeline_record_count": official_pipeline_count,
            "language_count": len({str(item.get("language", "")) for item in final_records}),
            "family_count": len({str(item.get("family", "")) for item in final_records}),
        },
        "records": final_records,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tasks = _load_tasks(args.limit)
    done = {str(item.get("task_id", "")): item for item in _existing_records()} if args.resume else {}
    stack = _load_stack(args.model, max_new_tokens=args.max_new_tokens)
    records: list[dict[str, Any]] = []
    with PROGRESS.open("a", encoding="utf-8") as handle:
        for task in tasks:
            task_id = str(task.get("task_id", ""))
            if task_id in done:
                records.append(done[task_id])
                continue
            record = _generate_record(task, stack)
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
            handle.flush()
            records.append(record)
    merged = {str(item.get("task_id", "")): _normalize_record(item) for item in _existing_records()}
    for item in records:
        merged[str(item.get("task_id", ""))] = _normalize_record(item)
    final_records = [merged[str(task.get("task_id", ""))] for task in tasks if str(task.get("task_id", "")) in merged]
    payload = _payload_from_records(args, tasks, final_records)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return payload


def normalize_existing(args: argparse.Namespace) -> dict[str, Any]:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tasks = _load_tasks(args.limit)
    records = _existing_records()
    if not records and OUTPUT.exists():
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
        loaded = payload.get("records", [])
        if isinstance(loaded, list):
            records = [item for item in loaded if isinstance(item, dict)]
    final_records = _load_final_records(tasks, records)
    payload = _payload_from_records(args, tasks, final_records)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    PROGRESS.write_text(
        "".join(json.dumps(item, ensure_ascii=True, sort_keys=True) + "\n" for item in final_records),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="deepseek-ai/deepseek-coder-6.7b-instruct")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--normalize-existing-only",
        action="store_true",
        help="Rewrite existing STONE records with the current audit schema without loading the model.",
    )
    args = parser.parse_args()
    payload = normalize_existing(args) if args.normalize_existing_only else run(args)
    print(
        json.dumps(
            {
                "record_count": payload["summary"]["record_count"],
                "target_record_count": payload["summary"]["target_record_count"],
                "unsupported_language_count": payload["summary"]["unsupported_language_count"],
                "output": str(OUTPUT),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
