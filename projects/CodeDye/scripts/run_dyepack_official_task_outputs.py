from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from _bootstrap import ARTIFACTS, ROOT
from integrations.dyepack_official_adapter import build_bridge_payload, bridge_paths, _load_tasks


DEFAULT_OUTPUT = ARTIFACTS / "dyepack_official_task_outputs.json"
DEFAULT_MODEL_ALIAS_ROOT = Path("/data/codemark/shared/vllm_model_aliases")
DEFAULT_CACHE_ROOTS = (
    Path("/data/codemark/shared/hf_cache"),
    Path("/data/codemark/shared/hf_cache/hub"),
    Path("/root/.cache/huggingface/hub"),
)


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot_load_official_module:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snapshot_from_hf_cache(model_id: str) -> Path | None:
    slug = f"models--{model_id.replace('/', '--')}"
    for root in DEFAULT_CACHE_ROOTS:
        candidate = root / slug
        if not candidate.exists():
            continue
        refs_main = candidate / "refs" / "main"
        snapshots = candidate / "snapshots"
        if refs_main.exists():
            revision = refs_main.read_text(encoding="utf-8").strip()
            if revision and (snapshots / revision).exists():
                return (snapshots / revision).resolve()
        if snapshots.exists():
            dirs = sorted(path for path in snapshots.iterdir() if path.is_dir())
            if dirs:
                return dirs[-1].resolve()
        if (candidate / "config.json").exists():
            return candidate.resolve()
    return None


def _ensure_qwen_alias(snapshot: Path) -> Path:
    DEFAULT_MODEL_ALIAS_ROOT.mkdir(parents=True, exist_ok=True)
    alias = DEFAULT_MODEL_ALIAS_ROOT / "Qwen2_5-Coder-7B-Instruct"
    if alias.exists():
        return alias
    try:
        alias.symlink_to(snapshot, target_is_directory=True)
        return alias
    except OSError:
        return snapshot


def _resolve_model_path(explicit: str) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.exists():
            raise SystemExit(f"official_dyepack_model_missing:{path}")
        return path.resolve()
    snapshot = _snapshot_from_hf_cache("Qwen/Qwen2.5-Coder-7B-Instruct")
    if snapshot is None:
        raise SystemExit("official_dyepack_qwen25_cache_missing")
    return _ensure_qwen_alias(snapshot)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def _load_npy_dict(path: Path, *, integer_keys: bool = True) -> dict[Any, Any]:
    payload = np.load(path, allow_pickle=True).reshape(-1)[0]
    if not isinstance(payload, dict):
        raise SystemExit(f"official_dyepack_metadata_not_dict:{path}")
    if integer_keys:
        return {int(key): value for key, value in payload.items()}
    return dict(payload)


def _template_key(model_path: str) -> str:
    if "Llama-2" in model_path:
        return "Llama-2"
    if "Llama-3" in model_path:
        return "Llama-3"
    if "Qwen2_5" in model_path:
        return "Qwen2_5"
    if "mistral" in model_path:
        return "Mistral-v0.1"
    if "gemma" in model_path:
        return "Gemma-1.1"
    raise SystemExit(
        "official_dyepack_model_template_unsupported:"
        "model path must contain one of Llama-2/Llama-3/Qwen2_5/mistral/gemma"
    )


def _bridge_alignment_report(
    root: Path,
    task_map: list[dict[str, Any]],
    *,
    target_task_count: int = 300,
) -> dict[str, Any]:
    tasks_path = root / "benchmarks" / "code_dyebench_tasks.json"
    expected = build_bridge_payload(_load_tasks(tasks_path), target_task_count=target_task_count)["task_map"]
    expected_by_index = {int(item["dyepack_index"]): item for item in expected}
    actual_by_index = {int(item.get("dyepack_index", -1)): item for item in task_map if isinstance(item, dict)}
    mismatched_indices: list[int] = []
    missing_indices: list[int] = []
    for index, expected_item in expected_by_index.items():
        actual = actual_by_index.get(index)
        if actual is None:
            missing_indices.append(index)
            continue
        for field in ("task_id", "language", "family", "subset", "prompt_sha256", "pattern", "target_answer"):
            if str(actual.get(field, "")).strip() != str(expected_item.get(field, "")).strip():
                mismatched_indices.append(index)
                break
    extra_indices = sorted(set(actual_by_index) - set(expected_by_index))
    issues: list[str] = []
    if len(task_map) != len(expected):
        issues.append(f"task_map_count_mismatch:{len(task_map)}/{len(expected)}")
    if missing_indices:
        issues.append(f"task_map_missing_current_indices:{len(missing_indices)}")
    if extra_indices:
        issues.append(f"task_map_extra_indices:{len(extra_indices)}")
    if mismatched_indices:
        issues.append(f"task_map_mismatched_current_tasks:{len(set(mismatched_indices))}")
    return {
        "tasks_path": tasks_path.relative_to(root).as_posix() if tasks_path.is_relative_to(root) else str(tasks_path),
        "target_task_count": target_task_count,
        "expected_task_count": len(expected),
        "actual_task_count": len(task_map),
        "current_bridge_aligned": not issues,
        "issues": issues,
        "first_mismatched_indices": sorted(set(mismatched_indices))[:10],
        "first_missing_indices": missing_indices[:10],
        "first_extra_indices": extra_indices[:10],
    }


def _build_prompts(
    *,
    checkout: Path,
    task_map: list[dict[str, Any]],
    dataset,
    poisoned_answers: dict[int, Any],
    poisoned_patterns: dict[int, Any],
    model_path: str,
) -> tuple[list[int], list[str]]:
    templates = json.loads((checkout / "model-prompt-templates.json").read_text(encoding="utf-8"))
    template = templates[_template_key(model_path)]
    indices = sorted(poisoned_answers)
    prompts: list[str] = []
    task_map_by_index = {int(item["dyepack_index"]): item for item in task_map}
    for index in indices:
        if index not in task_map_by_index:
            raise SystemExit(f"official_dyepack_task_map_missing_index:{index}")
        pattern = poisoned_patterns[index]
        prompt = (
            template["user_start"]
            + dataset["input"][index]
            + f" ({pattern})"
            + template["user_end"]
            + template["assistant_start"]
        )
        prompts.append(prompt)
    return indices, prompts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="")
    parser.add_argument("--gpu-util", default="0.82")
    parser.add_argument("--selected-subjects", default="codedye_bridge")
    parser.add_argument("--pat", default="rand")
    parser.add_argument("--num-pattern", type=int, default=4)
    parser.add_argument("--poison-rate", default="0.1")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    paths = bridge_paths(
        ROOT,
        selected_subjects=args.selected_subjects,
        pat=args.pat,
        num_pattern=args.num_pattern,
        poison_rate=args.poison_rate,
    )
    checkout = paths.checkout
    if not checkout.exists():
        raise SystemExit(f"official_dyepack_checkout_missing:{checkout}")
    for required in (paths.bbh_dataset, paths.task_id_map, paths.metadata_dir / "poisoned_ans_dict.npy", paths.metadata_dir / "poisoned_pat_dict.npy", paths.metadata_dir / "pattern2ans.npy"):
        if not required.exists():
            raise SystemExit(f"official_dyepack_bridge_file_missing:{required}")

    model_path = _resolve_model_path(args.model).as_posix()
    task_map = json.loads(paths.task_id_map.read_text(encoding="utf-8"))
    if not isinstance(task_map, list):
        raise SystemExit(f"official_dyepack_task_map_malformed:{paths.task_id_map}")
    bridge_alignment = _bridge_alignment_report(ROOT, task_map, target_task_count=300)
    if bridge_alignment["issues"]:
        raise SystemExit(
            "official_dyepack_current_bridge_alignment_failed:"
            + ",".join(str(item) for item in bridge_alignment["issues"])
        )
    poisoned_answers = _load_npy_dict(paths.metadata_dir / "poisoned_ans_dict.npy")
    poisoned_patterns = _load_npy_dict(paths.metadata_dir / "poisoned_pat_dict.npy")
    pattern2ans = _load_npy_dict(paths.metadata_dir / "pattern2ans.npy", integer_keys=False)

    official = _load_module(checkout / "BIG-Bench-Hard" / "cheatcheck_from_local.py", "dyepack_official_cheatcheck")
    official.args = SimpleNamespace(
        ntrain=5,
        selected_subjects=args.selected_subjects,
        gpu_util=args.gpu_util,
        model=model_path,
        pr=float(args.poison_rate),
        pat=args.pat,
        num_pattern=args.num_pattern,
        num_answer_option=args.num_pattern,
    )

    previous_cwd = Path.cwd()
    os.chdir(checkout)
    try:
        model, tokenizer = official.load_model()
        dataset = official.load_BBH_dataset(f"BIG-Bench-Hard/bbh/{args.selected_subjects}.json")
        indices, prompts = _build_prompts(
            checkout=checkout,
            task_map=task_map,
            dataset=dataset,
            poisoned_answers=poisoned_answers,
            poisoned_patterns=poisoned_patterns,
            model_path=model_path,
        )
        if args.limit > 0:
            indices = indices[: args.limit]
            prompts = prompts[: args.limit]
        pred_batch, response_batch = official.batch_inference(model[0], model[1], prompts)
    finally:
        os.chdir(previous_cwd)

    task_map_by_index = {int(item["dyepack_index"]): item for item in task_map}
    records: list[dict[str, Any]] = []
    for index, pred, response, prompt in zip(indices, pred_batch, response_batch, prompts, strict=True):
        task = task_map_by_index[index]
        pattern = str(poisoned_patterns[index])
        target_answer = str(poisoned_answers[index])
        expected_from_pattern = str(pattern2ans.get(pattern, ""))
        records.append(
            {
                "baseline_name": "DyePack",
                "official_repo": "https://github.com/chengez/DyePack.git",
                "official_entrypoint": "BIG-Bench-Hard/cheatcheck_from_local.py",
                "official_function_path": "load_model/load_BBH_dataset/batch_inference/extract_answer",
                "official_main_table_baseline": True,
                "claim_bearing": args.limit == 0,
                "dyepack_index": index,
                "task_id": str(task.get("task_id", "")),
                "language": str(task.get("language", "")),
                "family": str(task.get("family", "")),
                "subset": str(task.get("subset", "")),
                "pattern": pattern,
                "target_answer": target_answer,
                "pattern_target_answer": expected_from_pattern,
                "pred": None if pred is None else str(pred).strip("()"),
                "activation_match": str(pred).strip("()") == target_answer if pred is not None else False,
                "prompt_sha256": _sha256_text(prompt),
                "raw_response_sha256": _sha256_text(str(response or "")),
                "raw_response": str(response or ""),
                "model_path": model_path,
                "provider_required": False,
                "upstream_core_logic_modified": False,
                "bridge_dataset_sha256": _sha256_text(paths.bbh_dataset.read_text(encoding="utf-8")),
                "bridge_task_map_sha256": _sha256_file(paths.task_id_map),
                "bridge_manifest_sha256": _sha256_file(ARTIFACTS / "dyepack_official_bridge_manifest.json"),
                "stale_for_current_canonical_task_bridge": False,
            }
        )
    activation_rate = round(
        sum(1 for item in records if item["activation_match"]) / max(1, len(records)),
        6,
    )
    payload = {
        "schema_version": "codedye_dyepack_official_task_outputs_v1",
        "official_repo": "https://github.com/chengez/DyePack.git",
        "official_entrypoint": "BIG-Bench-Hard/cheatcheck_from_local.py",
        "official_functions_used": ["load_model", "load_BBH_dataset", "batch_inference", "extract_answer"],
        "upstream_core_logic_modified": False,
        "claim_bearing": args.limit == 0,
        "selected_subjects": args.selected_subjects,
        "pat": args.pat,
        "num_pattern": args.num_pattern,
        "poison_rate": args.poison_rate,
        "model_path": model_path,
        "record_count": len(records),
        "target_record_count": len(poisoned_answers),
        "activation_rate": activation_rate,
        "bridge_alignment": bridge_alignment,
        "bridge_task_map_sha256": _sha256_file(paths.task_id_map),
        "bridge_manifest_sha256": _sha256_file(ARTIFACTS / "dyepack_official_bridge_manifest.json"),
        "current_canonical_task_bridge_aligned": bool(bridge_alignment["current_bridge_aligned"]),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    tmp.replace(args.output)
    print(json.dumps({k: payload[k] for k in ("schema_version", "claim_bearing", "record_count", "target_record_count", "activation_rate", "model_path")}, indent=2))


if __name__ == "__main__":
    main()
