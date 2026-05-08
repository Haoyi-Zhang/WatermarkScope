from __future__ import annotations

import json
import re
from pathlib import Path

from .isolated_exec import execute_io_task, execute_python_task
from .protocol import BenchmarkTask, UtilityRecord
from .probes import prompt_family_from_text
from .reranker import FAMILY_ORDER
from .response_normalization import extract_code_payload, normalize_code_response


def benchmark_matrix() -> dict[str, object]:
    return {
        "segment_run_capable_public_benchmarks": [
            "HumanEval",
            "MBPP",
            "HumanEvalPack",
            "ClassEval",
        ],
        "reference_only_public_benchmarks": [
            "LBPP",
            "LiveCodeBench",
        ],
        "private_benchmark": {
            "name": "CodeDyeBench",
            "curation_status": "user_review_confirmed_300_task_canonical_matrix",
            "utility_mode": "generated_output_only",
            "task_count_target": 300,
            "ready_task_count_target": 300,
            "pending_user_review_count_target": 0,
            "frozen_family_field": "subset",
            "frozen_family_target_counts": {
                "fresh_unseen_tasks": 60,
                "prompt_chronology": 60,
                "semantic_canaries": 60,
                "cross_language_variants": 60,
                "canary_preserving_rewrites": 60,
            },
            "subsets": [
                "fresh_unseen_tasks",
                "prompt_chronology",
                "semantic_canaries",
                "cross_language_variants",
                "canary_preserving_rewrites",
            ],
            "operator_diagnostics": [
                "query_budget",
                "latency_budget",
            ],
            "chronology_splits": [
                "same_window",
                "staggered_window",
                "post_release_holdout",
            ],
            "canary_splits": [
                "family_pack",
                "semantic_pack",
                "chronology_marker",
                "rewrite_marker",
                "hidden_test_family",
            ],
            "probe_families": list(FAMILY_ORDER),
        },
        "attacks": [
            "chronology_shuffle",
            "canary_preserving_rewrite",
            "cross_language_reexpression",
            "query_budget_drop",
        ],
        "baselines": {
            "parse_only": ["DyePack"],
            "contamination_heuristics": [
                "Lexical Overlap",
                "Embedding Retrieval",
                "AST Similarity",
                "Nearest-Neighbor Retrieval",
            ],
            "benchmark_references": ["LBPP", "LiveCodeBench"],
        },
        "metrics": [
            "final_accusation_rate",
            "strict_null_control_rate",
            "accusation_eligibility_rate",
            "average_canary_coverage",
            "cross_language_signal_rate",
            "extra_query_cost",
            "latency_overhead",
            "local_utility_score",
        ],
        "pilot_models": [
            "Qwen2.5-Coder-7B-Instruct",
            "DeepSeek-Coder-6.7B-Instruct",
            "StarCoder2-7B",
        ],
    }


def load_code_dyebench_spec(root: str | Path) -> dict[str, object]:
    return json.loads((Path(root) / "benchmarks" / "code_dyebench_spec.json").read_text(encoding="utf-8"))


def _normalize_metadata_value(value: object) -> str:
    if isinstance(value, list):
        return "|".join(str(entry) for entry in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def load_code_dyebench_tasks(root: str | Path) -> tuple[BenchmarkTask, ...]:
    spec = load_code_dyebench_spec(root)
    payload = json.loads((Path(root) / "benchmarks" / "code_dyebench_tasks.json").read_text(encoding="utf-8"))
    items = payload["tasks"] if isinstance(payload, dict) else payload
    tasks: list[BenchmarkTask] = []
    standard_keys = {
        "task_id",
        "prompt",
        "language",
        "reference_code",
        "tests",
        "hidden_tests",
        "subset",
        "metadata",
        "source",
        "benchmark",
        "test_protocol",
    }
    for item in items:
        metadata = dict(item.get("metadata", {}))
        hidden_tests = tuple(str(test) for test in item.get("hidden_tests", []))
        if "test_protocol" in item:
            metadata["test_protocol"] = str(item["test_protocol"])
        if hidden_tests:
            metadata["visible_test_count"] = str(len(item.get("tests", [])))
            metadata["hidden_test_count"] = str(len(hidden_tests))
        for key, value in item.items():
            if key not in standard_keys:
                metadata[key] = _normalize_metadata_value(value)
        metadata.setdefault("target_family", prompt_family_from_text(str(item["prompt"])))
        metadata.setdefault("review_status", "ready")
        metadata.setdefault("review_reason", "")
        metadata.setdefault("chronology_split", "same_window")
        metadata.setdefault("release_window", metadata.get("chronology_tag", ""))
        metadata.setdefault("canary_split", "semantic_pack")
        metadata.setdefault("canary_pack_id", metadata.get("target_family", "canary_pack"))
        metadata.setdefault("hidden_test_family", "unspecified_hidden_test_family")
        tasks.append(
            BenchmarkTask(
                benchmark=str(item.get("benchmark", "CodeDyeBench")),
                task_id=str(item["task_id"]),
                prompt=str(item["prompt"]),
                language=str(item["language"]),
                reference_code=str(item["reference_code"]),
                tests=tuple(str(test) for test in item.get("tests", [])) + hidden_tests,
                subset=str(item.get("subset", "smoke")),
                source=str(item.get("source", "project_local")),
                metadata=tuple((str(key), str(value)) for key, value in metadata.items()),
            )
        )
    materialized = tuple(tasks)
    _validate_code_dyebench_manifest(materialized, spec)
    return materialized


def _validate_code_dyebench_manifest(tasks: tuple[BenchmarkTask, ...], spec: dict[str, object]) -> None:
    target_count = int(spec.get("local_task_count_target", 0) or 0)
    if target_count and len(tasks) != target_count:
        raise ValueError(f"CodeDyeBench task count mismatch: expected {target_count}, found {len(tasks)}")
    task_ids = [task.task_id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("CodeDyeBench task ids must be unique")
    ready_target = int(spec.get("ready_task_count_target", 0) or 0)
    pending_target = int(spec.get("pending_user_review_count_target", 0) or 0)
    ready_count = sum(1 for task in tasks if task_review_status(task) == "ready")
    pending_count = sum(1 for task in tasks if task_review_status(task) == "pending_user_review")
    if ready_target and ready_count != ready_target:
        raise ValueError(f"CodeDyeBench ready task count mismatch: expected {ready_target}, found {ready_count}")
    if pending_target and pending_count != pending_target:
        raise ValueError(
            f"CodeDyeBench pending_user_review task count mismatch: expected {pending_target}, found {pending_count}"
        )
    frozen_field = str(spec.get("frozen_family_field", "subset"))
    if frozen_field != "subset":
        raise ValueError(f"unsupported CodeDyeBench frozen family field: {frozen_field}")
    frozen_targets = {str(key): int(value) for key, value in dict(spec.get("frozen_family_target_counts", {})).items()}
    if frozen_targets:
        subset_counts: dict[str, int] = {}
        for task in tasks:
            subset_counts[task.subset] = subset_counts.get(task.subset, 0) + 1
        if set(subset_counts) != set(frozen_targets):
            raise ValueError(
                "CodeDyeBench subset mismatch: "
                f"expected {sorted(frozen_targets)}, found {sorted(subset_counts)}"
            )
        for subset_name, expected_count in frozen_targets.items():
            found = subset_counts.get(subset_name, 0)
            if found != expected_count:
                raise ValueError(
                    f"CodeDyeBench subset count mismatch for {subset_name}: expected {expected_count}, found {found}"
                )


def load_code_dyebench(root: str | Path) -> tuple[BenchmarkTask, ...]:
    return load_code_dyebench_tasks(root)


def task_metadata(task: BenchmarkTask) -> dict[str, str]:
    return {str(key): str(value) for key, value in task.metadata}


def task_target_family(task: BenchmarkTask) -> str:
    return task_metadata(task).get("target_family", prompt_family_from_text(task.prompt))


def task_review_status(task: BenchmarkTask) -> str:
    return task_metadata(task).get("review_status", "ready")


def task_review_reason(task: BenchmarkTask) -> str:
    return task_metadata(task).get("review_reason", "")


def task_chronology_split(task: BenchmarkTask) -> str:
    return task_metadata(task).get("chronology_split", "same_window")


def task_release_window(task: BenchmarkTask) -> str:
    metadata = task_metadata(task)
    return metadata.get("release_window", metadata.get("chronology_tag", "unknown"))


def task_canary_split(task: BenchmarkTask) -> str:
    return task_metadata(task).get("canary_split", "semantic_pack")


def task_canary_pack_id(task: BenchmarkTask) -> str:
    return task_metadata(task).get("canary_pack_id", f"{task_target_family(task)}_pack")


def task_hidden_test_family(task: BenchmarkTask) -> str:
    return task_metadata(task).get("hidden_test_family", "unspecified_hidden_test_family")


def task_operator_slice(task: BenchmarkTask) -> str:
    return task_metadata(task).get("operator_slice", "")


def ready_code_dyebench_tasks(tasks: tuple[BenchmarkTask, ...] | list[BenchmarkTask]) -> tuple[BenchmarkTask, ...]:
    return tuple(task for task in tasks if task_review_status(task) == "ready")


def pending_code_dyebench_tasks(tasks: tuple[BenchmarkTask, ...] | list[BenchmarkTask]) -> tuple[BenchmarkTask, ...]:
    return tuple(task for task in tasks if task_review_status(task) != "ready")


def _expected_entrypoints(task: BenchmarkTask) -> tuple[str, ...]:
    names: list[str] = []
    for test in task.tests:
        names.extend(re.findall(r"assert\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", test))
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name not in seen:
            ordered.append(name)
            seen.add(name)
    return tuple(ordered)


def evaluate_task(task: BenchmarkTask, code: str) -> UtilityRecord:
    metadata = task_metadata(task)
    test_protocol = metadata.get("test_protocol", "")
    if test_protocol == "io_cases_v1":
        normalized_code = (
            normalize_code_response(code)
            if task.language.lower() == "python"
            else extract_code_payload(code)
        )
        run = execute_io_task(
            normalized_code,
            task.language,
            task.tests,
            timeout_seconds=20,
        )
        return UtilityRecord(
            benchmark=task.benchmark,
            task_id=task.task_id,
            language=task.language,
            compile_supported=True,
            compile_ok=run.compile_ok,
            pass_supported=bool(task.tests),
            pass_ok=run.pass_ok,
            source=task.source,
            notes=(run.error,) if run.error else (),
        )
    normalized_code = normalize_code_response(code)
    compile_supported = task.language.lower() == "python"
    pass_supported = compile_supported and bool(task.tests)
    compile_ok: bool | None = None
    pass_ok: bool | None = None
    notes: tuple[str, ...] = ()
    if compile_supported:
        run = execute_python_task(
            normalized_code,
            task.tests,
            entrypoints=_expected_entrypoints(task),
            timeout_seconds=20,
        )
        compile_ok = run.compile_ok
        pass_ok = run.pass_ok if pass_supported else None
        if run.error:
            notes = (run.error,)
    return UtilityRecord(
        benchmark=task.benchmark,
        task_id=task.task_id,
        language=task.language,
        compile_supported=compile_supported,
        compile_ok=compile_ok,
        pass_supported=pass_supported,
        pass_ok=pass_ok,
        source=task.source,
        notes=notes,
    )


def summarize_utility(records: list[UtilityRecord]) -> dict[str, object]:
    compile_supported = [item for item in records if item.compile_supported]
    pass_supported = [item for item in records if item.pass_supported]
    compile_rate = (
        sum(1 for item in compile_supported if item.compile_ok is True) / len(compile_supported) if compile_supported else 0.0
    )
    pass_rate = sum(1 for item in pass_supported if item.pass_ok is True) / len(pass_supported) if pass_supported else 0.0
    return {
        "utility_task_count": len(records),
        "utility_supported_task_count": len(compile_supported),
        "utility_score": round(pass_rate if pass_supported else compile_rate, 4),
        "compile_rate": round(compile_rate, 4),
        "pass_rate": round(pass_rate, 4),
    }
