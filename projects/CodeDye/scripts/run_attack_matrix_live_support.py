from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter
from dataclasses import asdict
from math import ceil
from pathlib import Path

from _bootstrap import ROOT
from codedye.benchmarks import evaluate_task, load_code_dyebench_tasks, task_metadata
from codedye.provider_prompts import build_code_only_provider_prompt
from codedye.providers import generate_provider_trace, provider_summary, resolve_provider_config_path
from codedye.response_normalization import normalize_code_response
from codedye.statistics import build_contamination_decision
from run_attack_matrix_ci_scaffold import (
    PLACEHOLDER_TRANSFORM_KINDS,
    REQUIRED_ATTACK_IDS,
    SUPPORT_REQUIRED_ATTACK_IDS,
    _build_attack_rows,
    _metadata_hash,
    _read_json,
    _sha256_text as _attack_sha256_text,
    _transform_code,
    _utility_preservation,
)


DEFAULT_ATTACK_MATRIX = ROOT / "configs" / "attack_matrix.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "generated" / "attack_matrix_live_support.json"
DEFAULT_ENV_FILE = Path("/root/.codemark_secrets/deepseek.env")
MIN_ADMISSIBLE_RECORDS_PER_ATTACK = 20
MIN_ADMISSIBLE_RATE = 0.90


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a DeepSeek live attack-matrix pass. By default this records "
            "non-claim-bearing provider behavior; --claim-bearing-canonical "
            "must be set before launch to produce a canonical attack-evidence artifact."
        )
    )
    parser.add_argument("--attack-matrix", default=str(DEFAULT_ATTACK_MATRIX))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--rows-per-attack", type=int, default=8)
    parser.add_argument(
        "--target-records",
        type=int,
        default=0,
        help=(
            "Optional fixed live row target. For claim-bearing canonical launches this builds "
            "a claim-denominator-only matrix and excludes support-only budget-stress attacks."
        ),
    )
    parser.add_argument("--max-records", type=int, default=0, help="Optional total record cap; 0 means no cap.")
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--sample-count", type=int, default=2)
    parser.add_argument("--require-live", action="store_true", default=True)
    parser.add_argument("--progress-output", default="")
    parser.add_argument("--claim-bearing-canonical", action="store_true")
    parser.add_argument("--run-id", default="")
    parser.add_argument(
        "--task-id",
        action="append",
        default=[],
        help=(
            "Restrict a support/canonical launch to one or more task ids. "
            "Repeatable; intended for non-claim-bearing repair health runs."
        ),
    )
    parser.add_argument(
        "--task-id-file",
        default="",
        help="Optional newline-delimited task-id allowlist for targeted repair health runs.",
    )
    parser.add_argument(
        "--attack-id",
        action="append",
        default=[],
        help="Restrict a launch to one or more attack ids. Repeatable.",
    )
    return parser.parse_args()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_json(payload: object) -> str:
    return _sha256_text(json.dumps(payload, sort_keys=True, ensure_ascii=True))


def _load_env_file(path: Path) -> dict[str, object]:
    loaded: list[str] = []
    if not path.exists():
        return {"env_file": str(path), "env_file_state": "missing", "loaded_env_keys": []}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith("export "):
            text = text[len("export ") :].strip()
        if "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key.startswith("DEEPSEEK_") and value:
            os.environ[key] = value
            loaded.append(key)
    return {
        "env_file": str(path),
        "env_file_state": "loaded",
        "loaded_env_keys": sorted(set(loaded)),
        "secret_values_serialized": False,
    }


def _utility_score(utility) -> float:
    if utility.pass_supported:
        return 1.0 if utility.pass_ok is True else 0.0
    if utility.compile_supported:
        return 1.0 if utility.compile_ok is not False else 0.0
    return 1.0


def _candidate_samples(raw_samples: list[str], normalized_samples: list[str], utilities: list[object], selected_index: int) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for index, raw in enumerate(raw_samples):
        normalized = normalized_samples[index] if index < len(normalized_samples) else ""
        utility = utilities[index] if index < len(utilities) else None
        output.append(
            {
                "sample_index": index,
                "selected": index == selected_index,
                "raw_response_text": raw,
                "raw_response_sha256": _sha256_text(raw),
                "normalized_code": normalized,
                "normalized_code_sha256": _sha256_text(normalized),
                "utility": asdict(utility) if utility is not None else {},
                "utility_score": _utility_score(utility) if utility is not None else 0.0,
            }
        )
    return output


def _task_hash(task) -> str:
    return _sha256_json(
        {
            "benchmark": task.benchmark,
            "task_id": task.task_id,
            "language": task.language,
            "subset": task.subset,
            "prompt_hash": _sha256_text(task.prompt),
            "reference_code_hash": _sha256_text(task.reference_code),
            "tests_hash": _sha256_json({"tests": list(task.tests)}),
        }
    )


def _record_hash(record: dict[str, object]) -> str:
    stable = {key: value for key, value in record.items() if key != "record_hash"}
    return _sha256_json(stable)


def _select_sample(utilities: list[object]) -> int:
    best_index = 0
    best_key: tuple[float, int] = (-1.0, 0)
    for index, utility in enumerate(utilities):
        key = (_utility_score(utility), -index)
        if key > best_key:
            best_key = key
            best_index = index
    return best_index


def _utility_admissible_score(record: dict[str, object]) -> float:
    try:
        return float(record.get("selected_utility_score", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _record_utility_admissible(record: dict[str, object]) -> bool:
    if "utility_admissible_for_attack_claim" in record:
        return bool(record.get("utility_admissible_for_attack_claim"))
    return _utility_admissible_score(record) >= 1.0


def _row_claim_eligible(row: dict[str, object]) -> bool:
    metadata = row.get("transform_metadata", {})
    metadata = metadata if isinstance(metadata, dict) else {}
    return (
        bool(row.get("claim_bearing_attack_evidence", True))
        and not bool(row.get("support_only_not_claim_bearing", False))
        and not bool(metadata.get("support_only_not_claim_bearing", False))
    )


def _record_claim_admissible(record: dict[str, object]) -> bool:
    return (
        _record_utility_admissible(record)
        and bool(record.get("claim_bearing_attack_evidence", False))
        and not bool(record.get("support_only_not_claim_bearing", False))
    )


def _template_contract(metadata: dict[str, object]) -> str:
    generator_template = str(metadata.get("generator_template", "")).strip()
    contracts = {
        "reverse_words": (
            "Tokenize with arbitrary whitespace semantics, ignore empty chunks, reverse the words, "
            "and join with one ASCII space."
        ),
        "dedupe_words": (
            "Tokenize with arbitrary whitespace semantics, lowercase before duplicate checking, preserve first "
            "occurrence order, and join kept words with '|'."
        ),
        "normalize_csv": "Split on commas, trim each field, drop empty fields, and join remaining fields with '|'.",
        "mask_digits": "Replace every decimal digit character with '#', preserving all non-digits exactly.",
        "sorted_words": (
            "Tokenize with arbitrary whitespace semantics, lowercase all words, lexicographically sort them, "
            "and join with '|'."
        ),
        "path_tokens": (
            "Split on '/', discard empty fragments from repeated or leading/trailing slashes, and join with '|'."
        ),
        "segment_lengths": (
            "Split on '|', keep empty segments, compute each segment length as a decimal string, "
            "and join lengths with ','."
        ),
    }
    text = contracts.get(generator_template, "")
    return f" Template contract: {text}" if text else ""


def _legacy_signature_contract(task) -> str:
    task_id = str(getattr(task, "task_id", ""))
    if task_id == "cross_language_segment_lengths":
        return (
            " Interface contract: define exactly a Python function segment_lengths(text). "
            "It must return a list of integer lengths for non-empty '-' separated segments; "
            "for an empty input or all-empty segments return []. Do not print or wrap in solve."
        )
    if task_id == "cross_language_reverse_words":
        return (
            " Interface contract: define exactly a Python function reverse_words(text). "
            "It must return a string with words reversed under arbitrary whitespace splitting. Do not print or wrap in solve."
        )
    return ""


def build_attack_prompt(task, attack_row: dict[str, object]) -> str:
    base = build_code_only_provider_prompt(task)
    attack_id = str(attack_row.get("attack_id", ""))
    metadata = task_metadata(task)
    legacy_contract = _legacy_signature_contract(task)
    if attack_id == "query_budget_drop":
        return (
            base
            + "\nAudit condition: answer in one independent attempt. Do not request clarification or alternative samples.\n"
        )
    if attack_id == "canary_preserving_rewrite":
        return (
            base
            + "\nAudit condition: solve the same semantics under a structurally different but natural implementation. "
            "Keep the public interface and validation behavior unchanged."
            f"{_template_contract(metadata)}{legacy_contract}\n"
        )
    if attack_id == "cross_language_reexpression":
        language = str(task.language).strip().lower()
        metadata = task_metadata(task)
        python_surface = language == "python"
        forbid_python = (
            ""
            if python_surface
            else (
                "Do not return Python. A response starting with 'def solve', using Python indentation syntax, "
                "or containing Python type hints will fail this attack condition."
            )
        )
        language_hint = {
            "python": "Use Python with a top-level solve function and preserve the exact input/output contract.",
            "typescript": "Use a JavaScript/TypeScript function declaration such as function solve(input) { ... }.",
            "javascript": "Use a JavaScript function declaration such as function solve(input) { ... }.",
            "java": "Use class Solution { public static String solve(String input) { ... } } or the matching primitive signature.",
            "cpp": "Use C++17 with a top-level solve function and required headers.",
            "c++": "Use C++17 with a top-level solve function and required headers.",
            "cxx": "Use C++17 with a top-level solve function and required headers.",
            "go": "Use package main with func solve(input string) string or the matching primitive signature.",
        }.get(language, f"Use the requested {task.language} syntax exactly.")
        template_constraints = _template_contract(metadata) + legacy_contract
        attack_surface = "same-language semantic reexpression" if python_surface else "matched non-Python reference slot"
        return (
            base
            + f"\nAudit condition: the task has a {attack_surface} ({task.language}). "
            "Return code for the requested reference surface language and preserve the same behavior without copying superficial marker text. "
            f"{language_hint} {forbid_python}{template_constraints}\n"
        )
    if attack_id == "chronology_shuffle":
        release_window = metadata.get("release_window", "unknown")
        return (
            base
            + f"\nAudit condition: chronology metadata is intentionally shuffled for this null-control run "
            f"(held-out release window: {release_window}). Solve only from task semantics and public examples."
            f"{legacy_contract}\n"
        )
    if attack_id == "rename_identifiers":
        return (
            base
            + "\nAudit condition: use fresh local variable/helper names; do not copy identifier surfaces from any remembered implementation."
            f"{legacy_contract}\n"
        )
    if attack_id == "comment_whitespace_normalize":
        return (
            base
            + "\nAudit condition: return compact executable code without explanatory comments or formatting flourishes."
            f"{legacy_contract}\n"
        )
    if attack_id == "ast_canonicalization":
        return (
            base
            + "\nAudit condition: prefer a canonical direct AST shape with simple control flow and no decorative helper layout."
            f"{legacy_contract}\n"
        )
    return base + "\nAudit condition: robustness support run; solve the task semantics only.\n"


def _decision_payload(decision) -> dict[str, object]:
    return {
        "contaminated": decision.contaminated,
        "decision": "contamination_signal_detected" if decision.contaminated else "null_not_rejected",
        "accused_asset_ids": list(decision.accused_asset_ids),
        "contamination_score": decision.contamination_score,
        "score": decision.contamination_score,
        "p_value_or_score": decision.p_value_or_score,
        "false_positive_bound": decision.false_positive_bound,
        "familywise_adjusted_p_value": decision.familywise_adjusted_p_value,
        "familywise_decision_gate_pass": decision.familywise_decision_gate_pass,
        "null_sample_size": decision.null_sample_size,
        "matched_null_sample_size": decision.matched_null_sample_size,
        "null_pool_strategy": decision.null_pool_strategy,
        "null_pool_tier": decision.null_pool_tier,
        "null_pool_fallback_used": decision.null_pool_fallback_used,
        "null_calibration_method": decision.null_calibration_method,
        "canary_coverage": decision.canary_coverage,
        "witness_density": decision.witness_density,
        "query_count": decision.query_count,
        "query_budget_used": decision.query_budget_used,
        "extra_query_cost": decision.extra_query_cost,
        "latency_overhead": decision.latency_ms,
        "evidence_trace": list(decision.evidence_trace),
    }


def _write_progress(path: Path | None, payload: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _read_filter_file(path_text: str) -> set[str]:
    path_text = str(path_text or "").strip()
    if not path_text:
        return set()
    path = Path(path_text)
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise SystemExit(f"filter_file_unreadable:{path}:{exc}") from exc
    values: set[str] = set()
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        values.add(text)
    return values


def _filter_rows(
    rows: list[dict[str, object]],
    *,
    task_ids: set[str],
    attack_ids: set[str],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    filtered = [
        row
        for row in rows
        if (not task_ids or str(row.get("task_id", "")).strip() in task_ids)
        and (not attack_ids or str(row.get("attack_id", "")).strip() in attack_ids)
    ]
    observed_task_ids = {str(row.get("task_id", "")).strip() for row in rows}
    observed_attack_ids = {str(row.get("attack_id", "")).strip() for row in rows}
    missing_task_ids = sorted(task_ids - observed_task_ids)
    missing_attack_ids = sorted(attack_ids - observed_attack_ids)
    if task_ids and not filtered:
        raise SystemExit(f"task_filter_matched_no_rows:{sorted(task_ids)}")
    if attack_ids and not filtered:
        raise SystemExit(f"attack_filter_matched_no_rows:{sorted(attack_ids)}")
    if missing_task_ids:
        raise SystemExit(f"task_filter_unknown_ids:{missing_task_ids}")
    if missing_attack_ids:
        raise SystemExit(f"attack_filter_unknown_ids:{missing_attack_ids}")
    return filtered, {
        "task_filter_enabled": bool(task_ids),
        "attack_filter_enabled": bool(attack_ids),
        "task_ids": sorted(task_ids),
        "attack_ids": sorted(attack_ids),
        "input_row_count": len(rows),
        "filtered_row_count": len(filtered),
        "missing_task_ids": missing_task_ids,
        "missing_attack_ids": missing_attack_ids,
        "claim_policy_note": (
            "Filters are permitted for repair-health/support-only launches. "
            "A filtered canonical run is never sufficient for a full main-table claim."
        ),
    }


def _claim_denominator_rows(
    rows: list[dict[str, object]],
    *,
    target_records: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if target_records <= 0:
        return rows, {
            "target_records_enabled": False,
            "target_records": 0,
            "support_attack_excluded_for_main_denominator": [],
        }
    claim_rows = [
        row
        for row in rows
        if str(row.get("attack_id", "")).strip() not in SUPPORT_REQUIRED_ATTACK_IDS
    ]
    if len(claim_rows) < target_records:
        raise SystemExit(f"target_records_unavailable:{len(claim_rows)}_available:{target_records}_requested")
    selected = claim_rows[:target_records]
    return selected, {
        "target_records_enabled": True,
        "target_records": target_records,
        "support_attack_excluded_for_main_denominator": sorted(SUPPORT_REQUIRED_ATTACK_IDS),
        "pre_target_row_count": len(rows),
        "pre_target_claim_denominator_row_count": len(claim_rows),
        "post_target_row_count": len(selected),
        "post_target_by_attack": dict(sorted(Counter(str(row.get("attack_id", "")) for row in selected).items())),
        "target_policy": (
            "Claim-bearing v3 main-denominator launches exclude support-only budget-stress attacks. "
            "Support-only query-budget evidence must be run and reported separately."
        ),
    }


def _build_target_claim_rows(
    tasks,
    attack_matrix: dict[str, object],
    *,
    target_records: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    attacks = [
        dict(item)
        for item in attack_matrix.get("attacks", [])
        if isinstance(item, dict)
        and str(item.get("attack_id", "")).strip()
        and str(item.get("attack_id", "")).strip() not in SUPPORT_REQUIRED_ATTACK_IDS
    ]
    if target_records <= 0:
        return [], {"target_records_enabled": False}
    if target_records != len(tasks):
        raise SystemExit(f"target_records_must_match_task_count_for_v3:{target_records}!={len(tasks)}")
    rows: list[dict[str, object]] = []
    used_task_ids: set[str] = set()

    def applicable(task, attack: dict[str, object], *, enforce_subset: bool = True) -> bool:
        attack_id = str(attack["attack_id"])
        if attack_id == "cross_language_reexpression" and str(task.language).strip().lower() == "python":
            return False
        subsets = attack.get("applies_to_subsets", [])
        subset_set = {str(item) for item in subsets if str(item).strip()} if isinstance(subsets, list) else set()
        if enforce_subset and subset_set and task.subset not in subset_set:
            return False
        transformed, _, _ = _transform_code(task, attack_id, tasks=tasks)
        return _attack_sha256_text(transformed) != _attack_sha256_text(task.reference_code) or attack_id in {
            "comment_whitespace_normalize",
            "chronology_shuffle",
            "cross_language_reexpression",
        }

    attack_order = sorted(attacks, key=lambda attack: str(attack["attack_id"]))
    attack_by_id = {str(attack["attack_id"]): attack for attack in attack_order}
    applicable_by_task: dict[str, list[dict[str, object]]] = {}
    tasks_by_attack: dict[str, list[object]] = {attack_id: [] for attack_id in attack_by_id}
    for task in tasks:
        candidates = [attack for attack in attack_order if applicable(task, attack)]
        if not candidates:
            candidates = [attack for attack in attack_order if applicable(task, attack, enforce_subset=False)]
        if not candidates:
            raise SystemExit(f"target_records_task_has_no_claim_attack:{task.task_id}:{task.subset}:{task.language}")
        applicable_by_task[task.task_id] = candidates
        for attack in candidates:
            tasks_by_attack[str(attack["attack_id"])].append(task)

    attack_min_quota = {
        attack_id: min(MIN_ADMISSIBLE_RECORDS_PER_ATTACK, len(available))
        for attack_id, available in tasks_by_attack.items()
    }
    under_capacity = {
        attack_id: len(available)
        for attack_id, available in tasks_by_attack.items()
        if len(available) < MIN_ADMISSIBLE_RECORDS_PER_ATTACK
    }
    if under_capacity:
        raise SystemExit(f"target_records_attack_capacity_below_minimum:{under_capacity}")

    def materialize(task, attack: dict[str, object]) -> None:
        attack_id = str(attack["attack_id"])
        if task.task_id in used_task_ids:
            raise SystemExit(f"target_records_duplicate_task:{task.task_id}")
        metadata = task_metadata(task)
        transformed_code, transform_kind, transform_metadata = _transform_code(task, attack_id, tasks=tasks)
        utility = _utility_preservation(
            task,
            transformed_code,
            attack_id,
            str(attack.get("utility_preservation_check", "")),
        )
        canary_preserved = all(
            str(metadata.get(key, "")).strip()
            for key in ("canary_split", "canary_pack_id", "hidden_test_family")
        )
        source_hash = _attack_sha256_text(task.reference_code)
        transformed_hash = _attack_sha256_text(transformed_code)
        rows.append(
            {
                "attack_id": attack_id,
                "attack_family": str(attack.get("family", "")),
                "task_id": task.task_id,
                "benchmark": task.benchmark,
                "subset": task.subset,
                "language": task.language,
                "target_family": metadata.get("target_family", ""),
                "chronology_split": metadata.get("chronology_split", ""),
                "canary_split": metadata.get("canary_split", ""),
                "hidden_test_family": metadata.get("hidden_test_family", ""),
                "source_code_sha256": source_hash,
                "transformed_code_sha256": transformed_hash,
                "code_changed": transformed_hash != source_hash,
                "transform_kind": transform_kind,
                "transform_metadata_hash": _metadata_hash(transform_metadata),
                "transform_metadata": transform_metadata,
                "placeholder_transform": transform_kind in PLACEHOLDER_TRANSFORM_KINDS,
                "support_only_not_claim_bearing": False,
                "claim_bearing_attack_evidence": True,
                "utility_preservation_check": str(attack.get("utility_preservation_check", "")),
                "canary_preservation_result": "metadata_preserved" if canary_preserved else "metadata_missing",
                "canary_preserved": canary_preserved,
                "null_control_summary": {
                    "method": "task_metadata_matched_null_control",
                    "subset": task.subset,
                    "no_outcome_selection": True,
                },
                **utility,
            }
        )
        used_task_ids.add(task.task_id)

    def attack_counts() -> Counter:
        return Counter(str(row.get("attack_id", "")) for row in rows)

    for attack_id in sorted(attack_by_id, key=lambda item: (len(tasks_by_attack[item]), item)):
        attack = attack_by_id[attack_id]
        while attack_counts()[attack_id] < attack_min_quota[attack_id]:
            candidates = [task for task in tasks_by_attack[attack_id] if task.task_id not in used_task_ids]
            if not candidates:
                raise SystemExit(f"target_records_attack_quota_unfillable:{attack_id}:{attack_counts()[attack_id]}/{attack_min_quota[attack_id]}")
            task = min(
                candidates,
                key=lambda item: (
                    len(applicable_by_task[item.task_id]),
                    item.task_id,
                ),
            )
            materialize(task, attack)

    for task in tasks:
        if task.task_id in used_task_ids:
            continue
        candidates = applicable_by_task[task.task_id]
        counts = attack_counts()
        below_quota = [attack for attack in candidates if counts[str(attack["attack_id"])] < attack_min_quota[str(attack["attack_id"])]]
        pool = below_quota or candidates
        attack = min(
            pool,
            key=lambda item: (
                counts[str(item["attack_id"])],
                len(tasks_by_attack[str(item["attack_id"])]),
                str(item["attack_id"]),
            ),
        )
        materialize(task, attack)
    if len(rows) != target_records:
        raise SystemExit(f"target_records_materialization_mismatch:{len(rows)}!={target_records}")
    unused_tasks = sorted(task.task_id for task in tasks if task.task_id not in used_task_ids)
    return rows, {
        "target_records_enabled": True,
        "target_records": target_records,
        "target_records_mode": "one_claim_row_per_task_balanced_by_attack",
        "support_attack_excluded_for_main_denominator": sorted(SUPPORT_REQUIRED_ATTACK_IDS),
        "pre_target_task_count": len(tasks),
        "post_target_row_count": len(rows),
        "post_target_by_attack": dict(sorted(Counter(str(row.get("attack_id", "")) for row in rows).items())),
        "minimum_claim_records_per_attack": MIN_ADMISSIBLE_RECORDS_PER_ATTACK,
        "attack_min_quota": dict(sorted(attack_min_quota.items())),
        "unused_task_count": len(unused_tasks),
        "unused_task_ids": unused_tasks,
        "target_policy": (
            "CodeDye v3 canonical live evidence uses exactly one claim-bearing row per frozen task. "
            "Support-only query-budget evidence remains outside the 300-row main denominator."
        ),
    }


def summarize_records(records: list[dict[str, object]], declared_attack_ids: set[str]) -> dict[str, object]:
    observed_attack_ids = {str(record.get("attack_id", "")) for record in records}
    claim_declared_attack_ids = declared_attack_ids - SUPPORT_REQUIRED_ATTACK_IDS
    required_missing = sorted(REQUIRED_ATTACK_IDS - observed_attack_ids)
    support_required_missing = sorted(SUPPORT_REQUIRED_ATTACK_IDS - observed_attack_ids)
    declared_missing = sorted(claim_declared_attack_ids - {str(record.get("attack_id", "")) for record in records if _record_claim_admissible(record)})
    support_declared_missing = sorted(declared_attack_ids - observed_attack_ids)
    mock_records = [
        record
        for record in records
        if str(record.get("provider_mode_resolved", "")).strip().lower() != "live"
    ]
    missing_hash_records = [
        record
        for record in records
        if not str(record.get("raw_payload_hash", "")).strip()
        or not str(record.get("structured_payload_hash", "")).strip()
    ]
    utility_failed = [record for record in records if not _record_utility_admissible(record)]
    claim_admissible = [record for record in records if _record_claim_admissible(record)]
    support_utility_admissible = [
        record
        for record in records
        if not _record_claim_admissible(record)
        and _record_utility_admissible(record)
        and bool(record.get("support_only_not_claim_bearing", False))
    ]
    support_only_required = [
        record
        for record in support_utility_admissible
        if str(record.get("attack_id", "")) in REQUIRED_ATTACK_IDS
    ]
    support_required_valid = [
        record
        for record in support_utility_admissible
        if str(record.get("attack_id", "")) in SUPPORT_REQUIRED_ATTACK_IDS
    ]
    by_attack: dict[str, int] = {}
    admissible_by_attack: dict[str, int] = {}
    support_admissible_by_attack: dict[str, int] = {}
    failure_by_attack: dict[str, int] = {}
    for record in records:
        attack_id = str(record.get("attack_id", ""))
        by_attack[attack_id] = by_attack.get(attack_id, 0) + 1
        if _record_claim_admissible(record):
            admissible_by_attack[attack_id] = admissible_by_attack.get(attack_id, 0) + 1
        elif _record_utility_admissible(record) and bool(record.get("support_only_not_claim_bearing", False)):
            support_admissible_by_attack[attack_id] = support_admissible_by_attack.get(attack_id, 0) + 1
        else:
            failure_by_attack[attack_id] = failure_by_attack.get(attack_id, 0) + 1
    claim_denominator = sum(1 for record in records if str(record.get("attack_id", "")) not in SUPPORT_REQUIRED_ATTACK_IDS)
    support_denominator = sum(1 for record in records if str(record.get("attack_id", "")) in declared_attack_ids)
    admissible_rate = len(claim_admissible) / claim_denominator if claim_denominator else 0.0
    support_admissible_rate = len(support_utility_admissible) / support_denominator if support_denominator else 0.0
    canonical_blockers: list[str] = []
    support_blockers: list[str] = []
    shared_blockers: list[str] = []
    if required_missing:
        canonical_blockers.append("required_attack_live_records_missing")
        support_blockers.append("required_attack_live_records_missing")
    if support_required_missing:
        support_blockers.append("support_required_attack_live_records_missing")
    if declared_missing:
        canonical_blockers.append("declared_attack_live_records_missing")
    if support_declared_missing:
        support_blockers.append("declared_support_attack_live_records_missing")
    if mock_records:
        shared_blockers.append(f"mock_or_replay_provider_records:{len(mock_records)}")
    if missing_hash_records:
        shared_blockers.append(f"payload_hash_records_missing:{len(missing_hash_records)}")
    for attack_id in sorted(claim_declared_attack_ids):
        if by_attack.get(attack_id, 0) and admissible_by_attack.get(attack_id, 0) < MIN_ADMISSIBLE_RECORDS_PER_ATTACK:
            canonical_blockers.append(
                f"attack_admissible_records_below_{MIN_ADMISSIBLE_RECORDS_PER_ATTACK}:"
                f"{attack_id}:{admissible_by_attack.get(attack_id, 0)}/{by_attack.get(attack_id, 0)}"
            )
        if by_attack.get(attack_id, 0) and support_admissible_by_attack.get(attack_id, 0) < MIN_ADMISSIBLE_RECORDS_PER_ATTACK:
            support_blockers.append(
                f"support_attack_records_below_{MIN_ADMISSIBLE_RECORDS_PER_ATTACK}:"
                f"{attack_id}:{support_admissible_by_attack.get(attack_id, 0)}/{by_attack.get(attack_id, 0)}"
            )
    if records and admissible_rate < MIN_ADMISSIBLE_RATE:
        canonical_blockers.append(f"attack_admissible_rate_below_{MIN_ADMISSIBLE_RATE:.2f}:{admissible_rate:.4f}")
    if records and support_admissible_rate < MIN_ADMISSIBLE_RATE:
        support_blockers.append(f"support_admissible_rate_below_{MIN_ADMISSIBLE_RATE:.2f}:{support_admissible_rate:.4f}")
    for attack_id in sorted(SUPPORT_REQUIRED_ATTACK_IDS & declared_attack_ids):
        valid_count = len([record for record in support_required_valid if str(record.get("attack_id", "")) == attack_id])
        if by_attack.get(attack_id, 0) and valid_count < MIN_ADMISSIBLE_RECORDS_PER_ATTACK:
            support_blockers.append(f"support_attack_records_below_{MIN_ADMISSIBLE_RECORDS_PER_ATTACK}:{attack_id}:{valid_count}/{by_attack.get(attack_id, 0)}")
    blockers = shared_blockers + canonical_blockers
    support_gate_pass = not shared_blockers and not support_blockers
    return {
        "gate_pass": not blockers,
        "support_gate_pass": support_gate_pass,
        "record_count": len(records),
        "claim_bearing_admissible_record_count": len(claim_admissible),
        "support_utility_admissible_record_count": len(support_utility_admissible),
        "utility_failure_boundary_record_count": len(utility_failed),
        "support_only_required_attack_record_count": len(support_only_required),
        "support_required_valid_record_count": len(support_required_valid),
        "claim_denominator_record_count": claim_denominator,
        "support_denominator_record_count": support_denominator,
        "admissible_rate": round(admissible_rate, 6),
        "support_admissible_rate": round(support_admissible_rate, 6),
        "canonical_promotion_blockers": canonical_blockers,
        "support_blockers": support_blockers,
        "shared_blockers": shared_blockers,
        "minimum_admissible_records_per_attack": MIN_ADMISSIBLE_RECORDS_PER_ATTACK,
        "minimum_admissible_rate": MIN_ADMISSIBLE_RATE,
        "observed_attack_ids": sorted(observed_attack_ids),
        "declared_attack_ids": sorted(declared_attack_ids),
        "claim_required_attack_ids": sorted(REQUIRED_ATTACK_IDS),
        "support_required_attack_ids": sorted(SUPPORT_REQUIRED_ATTACK_IDS),
        "required_attack_ids": sorted(REQUIRED_ATTACK_IDS),
        "missing_required_attack_ids": required_missing,
        "missing_support_required_attack_ids": support_required_missing,
        "missing_declared_attack_ids": declared_missing,
        "missing_declared_support_attack_ids": support_declared_missing,
        "support_admissible_by_attack": dict(sorted(support_admissible_by_attack.items())),
        "by_attack": dict(sorted(by_attack.items())),
        "admissible_by_attack": dict(sorted(admissible_by_attack.items())),
        "utility_failure_by_attack": dict(sorted(failure_by_attack.items())),
        "mock_or_replay_record_count": len(mock_records),
        "payload_hash_missing_count": len(missing_hash_records),
        "selected_utility_failure_count": len(utility_failed),
        "utility_failure_ledger_sample": [
            {
                "attack_id": str(record.get("attack_id", "")),
                "task_id": str(record.get("task_id", "")),
                "language": str(record.get("language", "")),
                "selected_utility_score": _utility_admissible_score(record),
                "selected_utility": record.get("selected_utility", {}),
                "record_hash": str(record.get("record_hash", "")),
            }
            for record in utility_failed[:25]
        ],
        "support_only_required_attack_sample": [
            {
                "attack_id": str(record.get("attack_id", "")),
                "task_id": str(record.get("task_id", "")),
                "language": str(record.get("language", "")),
                "claim_role": str(record.get("claim_role", "")),
                "record_hash": str(record.get("record_hash", "")),
            }
            for record in support_only_required[:25]
        ],
        "claim_boundary": (
            "Main attack-matrix claims use only utility-admissible claim-required live records. "
            "Query-budget-drop is retained as a required support-only budget-stress condition with raw live payloads. "
            "Utility failures remain in the artifact as failure-boundary records and are not relabeled or deleted."
        ),
        "blockers": blockers,
    }


def summarize_targeted_repair_health(
    records: list[dict[str, object]],
    run_filter: dict[str, object],
    full_summary: dict[str, object],
    *,
    requested_claim_bearing: bool,
) -> dict[str, object]:
    filter_enabled = bool(
        run_filter.get("task_filter_enabled")
        or run_filter.get("attack_filter_enabled")
        or run_filter.get("max_records_applied")
    )
    expected_count = int(
        run_filter.get("post_max_records_row_count")
        or run_filter.get("filtered_row_count")
        or 0
    )
    blockers: list[str] = []
    if not filter_enabled:
        blockers.append("targeted_repair_health_requires_filter")
    if requested_claim_bearing:
        blockers.append("targeted_repair_health_must_not_be_claim_bearing")
    if expected_count and len(records) != expected_count:
        blockers.append(f"targeted_repair_health_record_count_mismatch:{len(records)}_expected:{expected_count}")
    if int(full_summary.get("mock_or_replay_record_count", 0) or 0):
        blockers.append(f"mock_or_replay_provider_records:{full_summary.get('mock_or_replay_record_count')}")
    if int(full_summary.get("payload_hash_missing_count", 0) or 0):
        blockers.append(f"payload_hash_records_missing:{full_summary.get('payload_hash_missing_count')}")
    if int(full_summary.get("selected_utility_failure_count", 0) or 0):
        blockers.append(f"selected_utility_failures:{full_summary.get('selected_utility_failure_count')}")
    return {
        "mode": "targeted_repair_health" if filter_enabled else "full_attack_matrix_contract",
        "repair_health_pass": filter_enabled and not blockers,
        "claim_bearing": False,
        "formal_claim_allowed": False,
        "coverage_blockers_allowed": [
            "required_attack_live_records_missing",
            "declared_attack_live_records_missing",
        ],
        "record_count": len(records),
        "expected_record_count": expected_count,
        "blockers": blockers,
        "policy": (
            "Filtered launches may pass only as targeted repair-health evidence. "
            "They remain support-only and never satisfy the canonical full attack-matrix claim gate."
        ),
    }


def main() -> None:
    args = _parse_args()
    env_state = _load_env_file(Path(args.env_file))
    attack_matrix = _read_json(Path(args.attack_matrix))
    declared_attack_ids = {
        str(item.get("attack_id", "")).strip()
        for item in attack_matrix.get("attacks", [])
        if isinstance(item, dict) and str(item.get("attack_id", "")).strip()
    }
    tasks = load_code_dyebench_tasks(ROOT)
    task_by_id = {task.task_id: task for task in tasks}
    target_records = max(int(args.target_records or 0), 0)
    claim_attack_count = max(1, len(declared_attack_ids - SUPPORT_REQUIRED_ATTACK_IDS))
    effective_rows_per_attack = max(args.rows_per_attack, ceil(target_records / claim_attack_count) if target_records else 1)
    if target_records and args.claim_bearing_canonical:
        rows, target_filter = _build_target_claim_rows(tasks, attack_matrix, target_records=target_records)
    else:
        rows = _build_attack_rows(tasks, attack_matrix, max(effective_rows_per_attack, 1))
        target_filter = {}
    task_filter = set(str(item).strip() for item in args.task_id if str(item).strip())
    task_filter.update(_read_filter_file(args.task_id_file))
    attack_filter = set(str(item).strip() for item in args.attack_id if str(item).strip())
    rows, run_filter = _filter_rows(rows, task_ids=task_filter, attack_ids=attack_filter)
    if target_records and args.claim_bearing_canonical:
        run_filter.update(target_filter)
        declared_attack_ids = declared_attack_ids - SUPPORT_REQUIRED_ATTACK_IDS
    if args.max_records > 0:
        rows = rows[: args.max_records]
        run_filter["max_records_applied"] = args.max_records
        run_filter["post_max_records_row_count"] = len(rows)
    config_path = resolve_provider_config_path(ROOT)
    provider_meta = provider_summary(args.provider, str(config_path))
    if args.require_live and str(provider_meta.get("resolved_mode", "")).strip().lower() != "live":
        raise SystemExit(f"provider_resolved_not_live:{provider_meta.get('resolved_mode')}")

    progress_path = Path(args.progress_output) if str(args.progress_output).strip() else None
    records: list[dict[str, object]] = []
    started_at = time.time()
    run_id = str(args.run_id).strip() or f"codedye_attack_matrix_live_{int(started_at)}"
    requested_claim_bearing = bool(args.claim_bearing_canonical)
    claim_bearing = requested_claim_bearing
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        task = task_by_id.get(str(row.get("task_id", "")))
        if task is None:
            continue
        attack_id = str(row.get("attack_id", ""))
        sample_count = 1 if attack_id == "query_budget_drop" else max(args.sample_count, 1)
        prompt = build_attack_prompt(task, row)
        trace = generate_provider_trace(args.provider, prompt, sample_count, str(config_path))
        if args.require_live and trace.provider_mode != "live":
            raise SystemExit(f"attack_record_resolved_not_live:{attack_id}:{task.task_id}:{trace.provider_mode}")
        raw_samples = [sample.response_text for sample in trace.samples]
        normalized_samples = [normalize_code_response(sample, language=task.language) for sample in raw_samples]
        utilities = [evaluate_task(task, sample) for sample in normalized_samples]
        selected_index = _select_sample(utilities)
        selected_code = normalized_samples[selected_index] if normalized_samples else ""
        selected_utility = utilities[selected_index] if utilities else evaluate_task(task, selected_code)
        decision = build_contamination_decision(
            task,
            selected_code,
            tasks,
            query_count=trace.returned_sample_count,
            latency_ms=trace.latency_ms,
            extra_query_cost=max(trace.returned_sample_count - 1, 0),
        )
        samples = _candidate_samples(raw_samples, normalized_samples, utilities, selected_index)
        provenance_hash = _sha256_json(
            {
                "run_id": run_id,
                "attack_id": attack_id,
                "task_id": task.task_id,
                "prompt_hash": trace.prompt_hash,
                "transcript_hash": trace.transcript_hash,
                "request_ids": list(trace.request_ids),
                "attack_transform_metadata_hash": row.get("transform_metadata_hash", ""),
            }
        )
        selected_utility_score = _utility_score(selected_utility)
        row_claim_eligible = _row_claim_eligible(row)
        record_claim_bearing = claim_bearing and selected_utility_score >= 1.0 and row_claim_eligible
        support_only_reason = (
            "row_marked_support_only_not_claim_bearing"
            if not row_claim_eligible
            else "selected_candidate_failed_utility_validation_retained_as_failure_boundary"
            if selected_utility_score < 1.0
            else ""
        )
        record = {
            "schema_version": (
                "codedye_attack_matrix_live_canonical_record_v1"
                if claim_bearing
                else "codedye_attack_matrix_live_support_record_v1"
            ),
            "project": "CodeDye",
            "record_kind": "attack_matrix_live_canonical" if claim_bearing else "attack_matrix_live_support",
            "claim_bearing": record_claim_bearing,
            "claim_bearing_attack_evidence": record_claim_bearing,
            "support_only_not_claim_bearing": not record_claim_bearing,
            "claim_role": (
                "claim_bearing_canonical_attack_matrix_live_evidence"
                if record_claim_bearing
                else "support_only_attack_condition_without_canonical_claim_eligibility"
                if claim_bearing and not row_claim_eligible
                else "utility_inadmissible_failure_boundary_not_main_claim"
                if claim_bearing
                else "support_only_attack_matrix_live_behavior_not_main_claim"
            ),
            "utility_admissible_for_attack_claim": selected_utility_score >= 1.0,
            "admissibility_reason": (
                "selected_candidate_passed_utility_validation"
                if selected_utility_score >= 1.0
                else support_only_reason
            ),
            "row_claim_eligible_for_attack_claim": row_claim_eligible,
            "row_claim_eligibility_reason": "eligible" if row_claim_eligible else support_only_reason,
            "run_id": run_id,
            "attack_id": attack_id,
            "attack_condition": attack_id,
            "attack_family": row.get("attack_family", ""),
            "task_id": task.task_id,
            "benchmark": task.benchmark,
            "subset": task.subset,
            "language": task.language,
            "target_family": row.get("target_family", ""),
            "provider_name": trace.provider_name,
            "provider_mode_resolved": trace.provider_mode,
            "provider_or_backbone": trace.model_name or trace.provider_name,
            "model_name": trace.model_name,
            "prompt_hash": trace.prompt_hash,
            "attack_prompt_hash": _sha256_text(prompt),
            "raw_payload_hash": trace.transcript_hash,
            "raw_provider_transcript_hash": trace.transcript_hash,
            "structured_payload_hash": _sha256_json(samples),
            "task_hash": _task_hash(task),
            "provenance_hash": provenance_hash,
            "task_provenance_hash": _sha256_json({"task_hash": _task_hash(task), "provenance_hash": provenance_hash}),
            "provider_request_ids": list(trace.request_ids),
            "provider_trace_request_count": len(trace.request_ids),
            "candidate_sample_count": len(samples),
            "candidate_samples": samples,
            "selected_sample_index": selected_index,
            "selected_utility": asdict(selected_utility),
            "selected_utility_score": selected_utility_score,
            "attack_transform_kind": row.get("transform_kind", ""),
            "transform_kind": row.get("transform_kind", ""),
            "attack_transform_metadata_hash": row.get("transform_metadata_hash", ""),
            "transform_metadata_hash": row.get("transform_metadata_hash", ""),
            "transform_metadata": row.get("transform_metadata", {}),
            "attack_row_source_code_sha256": row.get("source_code_sha256", ""),
            "source_code_sha256": row.get("source_code_sha256", ""),
            "attack_row_transformed_code_sha256": row.get("transformed_code_sha256", ""),
            "transformed_code_sha256": row.get("transformed_code_sha256", ""),
            "attack_row_code_changed": row.get("code_changed", False),
            "code_changed": row.get("code_changed", False),
            "placeholder_transform": row.get("placeholder_transform", False),
            "utility_preserved": selected_utility_score >= 1.0,
            "canary_preserved": row.get("canary_preserved", False),
            "canary_preservation_result": row.get("canary_preservation_result", ""),
            "attack_prompt_policy": "task_semantics_only_no_expected_canary_or_label_leakage",
            "sample_selection_policy": "utility_preselection_no_contamination_winner_selection",
            "baseline_or_control_name": "codedye_attack_matrix_live_deepseek",
            "is_negative_control": False,
            "threshold_version": "codedye_null_audit_threshold_v1",
            **_decision_payload(decision),
        }
        record["record_hash"] = _record_hash(record)
        records.append(record)
        _write_progress(
            progress_path,
            {
                "schema_version": "codedye_attack_matrix_live_support_progress_v1",
                "status": "running",
                "completed": len(records),
                "total": total,
                "current_attack_id": attack_id,
                "current_task_id": task.task_id,
                "claim_bearing": claim_bearing,
                "run_filter": run_filter,
            },
        )

    summary = summarize_records(records, declared_attack_ids)
    targeted_repair_health = summarize_targeted_repair_health(
        records,
        run_filter,
        summary,
        requested_claim_bearing=requested_claim_bearing,
    )
    if claim_bearing and summary["blockers"]:
        claim_bearing = False
    support_only_full_run_pass = (not requested_claim_bearing) and bool(summary.get("support_gate_pass", False))
    payload_status = (
        "passed"
        if summary["gate_pass"]
        else (
            "support_only_passed"
            if support_only_full_run_pass
            else (
                "support_repair_health_passed"
                if targeted_repair_health["repair_health_pass"]
                else "blocked"
            )
        )
    )
    payload = {
        "schema_version": (
            "codedye_attack_matrix_live_canonical_v1"
            if claim_bearing
            else "codedye_attack_matrix_live_support_v1"
        ),
        "status": payload_status,
        "claim_bearing": claim_bearing,
        "claim_role": (
            "claim_bearing_canonical_live_attack_matrix"
            if claim_bearing
            else "support_only_live_attack_matrix_not_canonical_claim"
        ),
        "formal_claim_allowed": claim_bearing and summary["gate_pass"],
        "utility_admissibility_policy": {
            "claim_scope": "utility_admissible_live_attack_records_only",
            "failure_records_retained": True,
            "failure_records_claim_bearing": False,
            "minimum_admissible_records_per_attack": MIN_ADMISSIBLE_RECORDS_PER_ATTACK,
            "minimum_admissible_rate": MIN_ADMISSIBLE_RATE,
            "no_failed_sample_deletion_or_threshold_relaxation": True,
        },
        "run_id": run_id,
        "claim_policy": (
            "Pre-registered canonical attack-matrix evidence only when --claim-bearing-canonical "
            "was set before launch; existing support-only artifacts are not promoted."
        ),
        "env": env_state,
        "provider": {
            **provider_meta,
            "base_url": f"{args.provider}_placeholder_endpoint",
            "api_key_serialized": False,
        },
        "elapsed_seconds": round(time.time() - started_at, 3),
        "rows_per_attack_requested": args.rows_per_attack,
        "rows_per_attack_effective": effective_rows_per_attack,
        "target_records_requested": target_records,
        "sample_count_requested": args.sample_count,
        "run_filter": run_filter,
        "summary": summary,
        "targeted_repair_health": targeted_repair_health,
        "records": records,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    _write_progress(
        progress_path,
        {
            "schema_version": "codedye_attack_matrix_live_support_progress_v1",
            "status": payload_status,
            "completed": len(records),
            "total": total,
            "output": str(output),
            "claim_bearing": claim_bearing,
            "blockers": [] if support_only_full_run_pass else summary["blockers"],
            "canonical_promotion_blockers": summary.get("canonical_promotion_blockers", []),
            "support_blockers": summary.get("support_blockers", []),
            "support_gate_pass": bool(summary.get("support_gate_pass", False)),
            "targeted_repair_health": targeted_repair_health,
            "run_filter": run_filter,
        },
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "summary": summary,
                "targeted_repair_health": targeted_repair_health,
            },
            indent=2,
            ensure_ascii=True,
        )
    )
    if summary["blockers"] and not support_only_full_run_pass and not targeted_repair_health["repair_health_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
