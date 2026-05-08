from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
from random import Random
from statistics import mean

from _bootstrap import ROOT
from codedye.benchmarks import evaluate_task, load_code_dyebench_tasks, task_metadata
from codedye.statistical_audit import benjamini_hochberg, bootstrap_mean_ci, build_statistical_audit_plan


DEFAULT_ATTACK_MATRIX = ROOT / "configs" / "attack_matrix.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "generated" / "attack_matrix_null_calibration_ci.json"
DEFAULT_QUERY_BUDGET_SUPPORT_FULL_EVAL = (
    ROOT / "artifacts" / "generated" / "query_budget_drop_support_full_eval.json"
)
DEFAULT_CANONICAL_ATTACK_LIVE = ROOT / "artifacts" / "generated" / "attack_matrix_live_canonical.json"
CURRENT_SAMPLE_SELECTION_STATUSES = {
    "pre_registered_utility_selection",
    "utility_preselection_no_contamination_winner_selection",
}
REQUIRED_ATTACK_IDS = {
    "chronology_shuffle",
    "canary_preserving_rewrite",
    "cross_language_reexpression",
}
SUPPORT_REQUIRED_ATTACK_IDS = {
    "query_budget_drop",
}
MUTATION_REQUIRED_ATTACK_IDS = {
    "ast_canonicalization",
    "canary_preserving_rewrite",
    "rename_identifiers",
}
PLACEHOLDER_TRANSFORM_KINDS = {
    "metadata_only_budget_drop",
    "metadata_only_chronology_shuffle",
    "semantic_rewrite_comment_guard",
    "language_slot_reexpression_static",
}
MIN_NEGATIVE_CONTROL_RECORDS = 60
MIN_STRATIFIED_NEGATIVE_CONTROL_RECORDS = 120
MAX_NEGATIVE_CONTROL_CI95_HIGH = 0.025
MIN_ADMISSIBLE_RECORDS_PER_ATTACK = 20
MIN_ADMISSIBLE_RATE = 0.90


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run no-provider attack-matrix and null-calibration CI scaffold checks.")
    parser.add_argument("--attack-matrix", default=str(DEFAULT_ATTACK_MATRIX))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--query-budget-support-full-eval",
        default=str(DEFAULT_QUERY_BUDGET_SUPPORT_FULL_EVAL),
        help=(
            "Optional non-claim, run-scoped full_eval artifact with multi-sample provider payloads "
            "used only to verify query-budget-drop support rows."
        ),
    )
    parser.add_argument(
        "--canonical-attack-live",
        default=str(DEFAULT_CANONICAL_ATTACK_LIVE),
        help="Optional pre-registered DeepSeek live canonical attack-matrix artifact.",
    )
    parser.add_argument("--rows-per-attack", type=int, default=24)
    return parser.parse_args()


def _issues(plan: dict[str, object]) -> list[str]:
    issues: list[str] = []
    attack_summary = plan.get("attack_matrix_summary", {})
    null_plan = plan.get("null_calibration_plan", {})
    if not bool(plan.get("machine_verifiable", False)):
        issues.append("plan_not_machine_verifiable")
    if str(plan.get("provider_policy", "")) != "no_provider_no_live_api":
        issues.append("provider_policy_not_no_provider")
    if not isinstance(attack_summary, dict) or int(attack_summary.get("attack_count", 0) or 0) <= 0:
        issues.append("attack_matrix_empty")
    if isinstance(attack_summary, dict) and int(attack_summary.get("requires_live_provider_count", 0) or 0) != 0:
        issues.append("attack_matrix_requires_live_provider")
    if not isinstance(null_plan, dict) or str(null_plan.get("method", "")) != "family_stratified_empirical_dominance_tail":
        issues.append("null_calibration_method_mismatch")
    return issues


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _row_utility_admissible(row: dict[str, object]) -> bool:
    if "utility_admissible_for_attack_claim" in row:
        return bool(row.get("utility_admissible_for_attack_claim"))
    if "selected_utility_score" in row:
        try:
            return float(row.get("selected_utility_score", 0.0) or 0.0) >= 1.0
        except (TypeError, ValueError):
            return False
    return bool(row.get("utility_preserved", False))


def _row_claim_admissible(row: dict[str, object]) -> bool:
    return (
        _row_utility_admissible(row)
        and bool(row.get("claim_bearing_attack_evidence", True))
        and not bool(row.get("support_only_not_claim_bearing", False))
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _metadata_hash(payload: dict[str, object]) -> str:
    return _sha256_text(json.dumps(payload, sort_keys=True, ensure_ascii=True))


def _line_comment(language: str, text: str) -> str:
    if language.lower() == "python":
        return f"# {text}\n"
    return f"// {text}\n"


def _ast_unparse_or_original(code: str, transformer: ast.NodeTransformer | None = None) -> str:
    try:
        tree = ast.parse(code)
        if transformer is not None:
            tree = transformer.visit(tree)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree) + "\n"
    except (SyntaxError, ValueError):
        return code


def _assigned_python_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return {name for name in names if not (name.startswith("__") and name.endswith("__"))}


class _RenamePythonLocals(ast.NodeTransformer):
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in self.mapping:
            return ast.copy_location(ast.Name(id=self.mapping[node.id], ctx=node.ctx), node)
        return node


class _InsertSemanticNoop(ast.NodeTransformer):
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        insert_at = 1 if node.body and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], "value", None), ast.Constant) and isinstance(node.body[0].value.value, str) else 0
        marker = ast.If(test=ast.Constant(value=False), body=[ast.Pass()], orelse=[])
        node.body.insert(insert_at, marker)
        return node


def _rename_python_locals(code: str) -> tuple[str, dict[str, object]]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, {"rename_supported": False, "renamed_identifier_count": 0}
    names = sorted(_assigned_python_names(tree))
    mapping = {name: f"cd_{name}" for name in names if not name.startswith("cd_")}
    if not mapping:
        return code, {"rename_supported": True, "renamed_identifier_count": 0}
    rendered = _ast_unparse_or_original(code, _RenamePythonLocals(mapping))
    return rendered, {
        "rename_supported": True,
        "renamed_identifier_count": len(mapping),
        "renamed_identifiers_sha256": _metadata_hash(mapping),
    }


def _semantic_python_rewrite(code: str) -> tuple[str, dict[str, object]]:
    rendered = _ast_unparse_or_original(code, _InsertSemanticNoop())
    changed = rendered != code
    return rendered, {
        "rewrite_supported": True,
        "rewrite_family": "semantic_noop_branch_insertion",
        "rewrite_changed_code": changed,
    }


def _insert_after_first_brace(code: str, snippet: str) -> tuple[str, bool]:
    brace_index = code.find("{")
    if brace_index < 0:
        return code, False
    indent = re.search(r"\n([ \t]*)\S", code[brace_index + 1 :])
    child_indent = indent.group(1) if indent else "  "
    insertion = "\n" + "\n".join(f"{child_indent}{line}" for line in snippet.splitlines()) + "\n"
    return code[: brace_index + 1] + insertion + code[brace_index + 1 :], True


def _semantic_noop_rewrite(code: str, language: str) -> tuple[str, dict[str, object]]:
    normalized = language.lower()
    if normalized == "python":
        return _semantic_python_rewrite(code)
    if normalized in {"typescript", "javascript"}:
        rendered, supported = _insert_after_first_brace(code, 'if (false) { return String(input); }')
        return rendered, {
            "rewrite_supported": supported,
            "rewrite_family": "semantic_unreachable_branch_insertion",
            "rewrite_changed_code": rendered != code,
            "language": normalized,
        }
    if normalized == "java":
        rendered, supported = _insert_after_first_brace(code, "if (false) { return input; }")
        return rendered, {
            "rewrite_supported": supported,
            "rewrite_family": "semantic_unreachable_branch_insertion",
            "rewrite_changed_code": rendered != code,
            "language": normalized,
        }
    if normalized in {"cpp", "c++", "cxx"}:
        rendered, supported = _insert_after_first_brace(code, "if (false) { return input; }")
        return rendered, {
            "rewrite_supported": supported,
            "rewrite_family": "semantic_unreachable_branch_insertion",
            "rewrite_changed_code": rendered != code,
            "language": normalized,
        }
    if normalized == "go":
        rendered, supported = _insert_after_first_brace(code, "if false { return input }")
        return rendered, {
            "rewrite_supported": supported,
            "rewrite_family": "semantic_unreachable_branch_insertion",
            "rewrite_changed_code": rendered != code,
            "language": normalized,
        }
    return code, {
        "rewrite_supported": False,
        "rewrite_family": "unsupported_language",
        "rewrite_changed_code": False,
        "language": normalized,
    }


def _chronology_pair_metadata(task, tasks) -> dict[str, object]:
    metadata = task_metadata(task)
    release_window = str(metadata.get("release_window", ""))
    target_family = str(metadata.get("target_family", ""))
    candidates = []
    for other in tasks:
        if other.task_id == task.task_id:
            continue
        other_meta = task_metadata(other)
        if str(other_meta.get("target_family", "")) != target_family:
            continue
        other_window = str(other_meta.get("release_window", ""))
        if other_window and other_window != release_window:
            candidates.append((other.task_id, other_window))
    candidates.sort()
    if not candidates:
        return {
            "original_release_window": release_window,
            "shuffled_release_window": "",
            "chronology_control_pair_task_id": "",
            "matched_chronology_control": False,
        }
    pair_task_id, shuffled_window = candidates[0]
    return {
        "original_release_window": release_window,
        "shuffled_release_window": shuffled_window,
        "chronology_control_pair_task_id": pair_task_id,
        "matched_chronology_control": True,
    }


def _task_provenance_hash(task) -> str:
    metadata = task_metadata(task)
    payload = {
        "benchmark": task.benchmark,
        "task_id": task.task_id,
        "language": task.language,
        "subset": task.subset,
        "source": task.source,
        "prompt_sha256": _sha256_text(task.prompt),
        "reference_code_sha256": _sha256_text(task.reference_code),
        "tests_sha256": _metadata_hash({"tests": list(task.tests)}),
        "target_family": metadata.get("target_family", ""),
        "generator_template": metadata.get("generator_template", ""),
        "protected_asset_id": metadata.get("protected_asset_id", ""),
        "canary_pack_id": metadata.get("canary_pack_id", ""),
        "canaries": metadata.get("canaries", ""),
        "hidden_test_family": metadata.get("hidden_test_family", ""),
    }
    return _metadata_hash(payload)


def _cross_language_source_metadata(task, tasks) -> dict[str, object]:
    metadata = task_metadata(task)
    language = task.language.lower()
    template = str(metadata.get("generator_template", "")).strip()
    canary_pack = str(metadata.get("canary_pack_id", "")).strip()
    target_family = str(metadata.get("target_family", "")).strip()
    candidates = []
    for other in tasks:
        other_language = other.language.lower()
        if other.task_id == task.task_id or other_language != "python":
            continue
        other_meta = task_metadata(other)
        same_template = template and str(other_meta.get("generator_template", "")).strip() == template
        same_canary_pack = canary_pack and str(other_meta.get("canary_pack_id", "")).strip() == canary_pack
        same_family = target_family and str(other_meta.get("target_family", "")).strip() == target_family
        if same_template and same_canary_pack:
            rank = 0 if same_family else 1
            candidates.append((rank, other.task_id, other, other_meta))
    candidates.sort(key=lambda item: (item[0], item[1]))
    target_provenance_hash = _task_provenance_hash(task)
    if not candidates:
        return {
            "target_language": language,
            "target_task_id": task.task_id,
            "target_reference_code_sha256": _sha256_text(task.reference_code),
            "target_provenance_hash": target_provenance_hash,
            "target_generator_template": template,
            "target_canary_pack_id": canary_pack,
            "target_family": target_family,
            "cross_language_source_task_found": False,
            "cross_language_provenance_locked": False,
            "binding_kind": "missing_python_template_pack_source",
        }
    rank, _, source_task, source_meta = candidates[0]
    source_provenance_hash = _task_provenance_hash(source_task)
    binding_payload = {
        "source_task_id": source_task.task_id,
        "source_language": source_task.language.lower(),
        "source_reference_code_sha256": _sha256_text(source_task.reference_code),
        "source_provenance_hash": source_provenance_hash,
        "target_task_id": task.task_id,
        "target_language": language,
        "target_reference_code_sha256": _sha256_text(task.reference_code),
        "target_provenance_hash": target_provenance_hash,
        "generator_template": template,
        "canary_pack_id": canary_pack,
    }
    return {
        "target_language": language,
        "target_task_id": task.task_id,
        "target_reference_code_sha256": _sha256_text(task.reference_code),
        "target_provenance_hash": target_provenance_hash,
        "target_generator_template": template,
        "target_canary_pack_id": canary_pack,
        "target_family": target_family,
        "target_protected_asset_id": metadata.get("protected_asset_id", ""),
        "source_language": source_task.language.lower(),
        "source_task_id": source_task.task_id,
        "source_reference_code_sha256": _sha256_text(source_task.reference_code),
        "source_provenance_hash": source_provenance_hash,
        "source_generator_template": source_meta.get("generator_template", ""),
        "source_canary_pack_id": source_meta.get("canary_pack_id", ""),
        "source_family": source_meta.get("target_family", ""),
        "source_protected_asset_id": source_meta.get("protected_asset_id", ""),
        "source_target_same_template": str(source_meta.get("generator_template", "")).strip() == template,
        "source_target_same_canary_pack": str(source_meta.get("canary_pack_id", "")).strip() == canary_pack,
        "source_target_same_family": rank == 0,
        "source_target_languages_differ": source_task.language.lower() != language,
        "language_specific_asset_ids_allowed": True,
        "source_target_binding_hash": _metadata_hash(binding_payload),
        "cross_language_source_task_found": True,
        "cross_language_provenance_locked": True,
        "binding_kind": "python_source_to_multilanguage_template_pack",
    }


def _comment_whitespace_noop_metadata(task, transformed_code: str, *, removed_comment_lines: int, normalized_trailing_whitespace_lines: int) -> dict[str, object]:
    metadata = task_metadata(task)
    source_hash = _sha256_text(task.reference_code)
    transformed_hash = _sha256_text(transformed_code)
    return {
        "semantic_noop_attack_boundary": "format_preserving_comment_whitespace_normalization",
        "semantic_noop_boundary_version": "comment_whitespace_noop_v1",
        "claim_bearing_attack_evidence": True,
        "code_change_required": False,
        "mutation_required_attack": False,
        "comment_whitespace_noop_locked": True,
        "source_task_id": task.task_id,
        "source_language": task.language.lower(),
        "source_reference_code_sha256": source_hash,
        "transformed_reference_code_sha256": transformed_hash,
        "source_provenance_hash": _task_provenance_hash(task),
        "removed_comment_line_count": removed_comment_lines,
        "normalized_trailing_whitespace_line_count": normalized_trailing_whitespace_lines,
        "normalization_changed_code": source_hash != transformed_hash,
        "null_control_method": "task_metadata_matched_null_control",
        "matched_null_control_required": True,
        "no_outcome_selection_required": True,
        "target_family": metadata.get("target_family", ""),
        "canary_pack_id": metadata.get("canary_pack_id", ""),
        "hidden_test_family": metadata.get("hidden_test_family", ""),
    }


def _transform_code(task, attack_id: str, *, tasks=()) -> tuple[str, str, dict[str, object]]:
    code = task.reference_code
    language = task.language.lower()
    metadata = task_metadata(task)
    if attack_id == "comment_whitespace_normalize":
        without_comments = []
        removed_comment_lines = 0
        normalized_trailing_whitespace_lines = 0
        for line in code.splitlines():
            stripped = line.rstrip()
            if language == "python" and stripped.lstrip().startswith("#"):
                removed_comment_lines += 1
                continue
            if stripped != line:
                normalized_trailing_whitespace_lines += 1
            without_comments.append(stripped)
        transformed = "\n".join(without_comments) + "\n"
        return (
            transformed,
            "format_preserving_comment_strip",
            _comment_whitespace_noop_metadata(
                task,
                transformed,
                removed_comment_lines=removed_comment_lines,
                normalized_trailing_whitespace_lines=normalized_trailing_whitespace_lines,
            ),
        )
    if attack_id == "canary_preserving_rewrite":
        rendered, rewrite_meta = _semantic_noop_rewrite(code, language)
        rewrite_meta.update({"canary_pack_id": metadata.get("canary_pack_id", ""), "canary_split": metadata.get("canary_split", "")})
        return rendered, "semantic_unreachable_branch_rewrite", rewrite_meta
    if attack_id == "query_budget_drop":
        return code, "provider_candidate_budget_replay", {"query_budget": 1, "sample_count": 1}
    if attack_id == "chronology_shuffle":
        return code, "matched_chronology_label_shuffle", _chronology_pair_metadata(task, tasks)
    if attack_id == "cross_language_reexpression":
        metadata = _cross_language_source_metadata(task, tasks)
        metadata["pre_materialized_non_python_variant"] = language != "python"
        return code, "pre_materialized_multilanguage_reexpression", metadata
    if attack_id == "rename_identifiers":
        if language == "python":
            rendered, rename_meta = _rename_python_locals(code)
            return rendered, "identifier_surface_ast_rewrite", rename_meta
        return code, "identifier_surface_static_noop_for_non_python", {}
    if attack_id == "ast_canonicalization":
        if language == "python":
            return _ast_unparse_or_original(code), "python_ast_unparse_canonicalization", {}
        return code.rstrip() + "\n", "ast_shape_static_canonicalization", {}
    return code, "reference_preserving_control", {}


def _utility_preservation(task, transformed_code: str, attack_id: str, utility_check: str) -> dict[str, object]:
    if utility_check == "metadata_only_no_code_execution" or attack_id in {"chronology_shuffle", "query_budget_drop"}:
        return {
            "utility_preservation_result": "metadata_only_preserved",
            "compile_supported": False,
            "compile_ok": None,
            "pass_supported": False,
            "pass_ok": None,
            "utility_preserved": True,
        }
    if utility_check == "language_specific_compile_or_static_check" and task.language.lower() != "python":
        return {
            "utility_preservation_result": "language_static_preserved",
            "compile_supported": False,
            "compile_ok": None,
            "pass_supported": False,
            "pass_ok": None,
            "utility_preserved": True,
        }
    utility = evaluate_task(task, transformed_code)
    preserved = (utility.pass_ok is True) if utility.pass_supported else (utility.compile_ok is not False)
    return {
        "utility_preservation_result": "compile_test_preserved" if preserved else "compile_test_failed",
        "compile_supported": utility.compile_supported,
        "compile_ok": utility.compile_ok,
        "pass_supported": utility.pass_supported,
        "pass_ok": utility.pass_ok,
        "utility_preserved": bool(preserved),
        "utility_notes": list(utility.notes),
    }


def _record_candidate_sample_count(record: dict[str, object]) -> int:
    explicit = record.get("candidate_sample_count")
    try:
        count = int(explicit)
    except (TypeError, ValueError):
        count = 0
    samples = record.get("candidate_samples")
    if isinstance(samples, list):
        count = max(count, len(samples))
    return count


def _canonical_live_attack_rows(path: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    payload = _read_json(path)
    records = [
        dict(record)
        for record in payload.get("records", [])
        if isinstance(record, dict)
    ] if isinstance(payload.get("records", []), list) else []
    blockers: list[str] = []
    if not path.exists():
        blockers.append("canonical_attack_live_artifact_missing")
    if not records:
        blockers.append("canonical_attack_live_records_missing")
    if payload and payload.get("claim_bearing") is not True:
        blockers.append("canonical_attack_live_artifact_not_claim_bearing")
    if payload and payload.get("formal_claim_allowed") is not True:
        blockers.append("canonical_attack_live_formal_claim_not_allowed")
    bad_records: list[dict[str, object]] = []
    utility_failure_boundary_records: list[dict[str, object]] = []
    support_only_boundary_records: list[dict[str, object]] = []
    claim_admissible_records: list[dict[str, object]] = []
    for record in records:
        base_bad = (
            str(record.get("provider_mode_resolved", "")).strip().lower() != "live"
            or not str(record.get("raw_payload_hash", "")).strip()
            or not str(record.get("structured_payload_hash", "")).strip()
            or not str(record.get("record_hash", "")).strip()
        )
        if base_bad:
            bad_records.append(record)
            continue
        if _row_claim_admissible(record):
            if record.get("claim_bearing") is not True:
                bad_records.append(record)
            else:
                claim_admissible_records.append(record)
            continue
        if (
            not _row_utility_admissible(record)
            and record.get("claim_bearing") is not True
            and bool(record.get("support_only_not_claim_bearing", False))
            and "failure_boundary" in str(record.get("claim_role", ""))
        ):
            utility_failure_boundary_records.append(record)
            continue
        if (
            str(record.get("attack_id", "")) in SUPPORT_REQUIRED_ATTACK_IDS
            and record.get("claim_bearing") is not True
            and bool(record.get("support_only_not_claim_bearing", False))
            and _row_utility_admissible(record)
        ):
            support_only_boundary_records.append(record)
            continue
        bad_records.append(record)
    if bad_records:
        blockers.append(f"canonical_attack_live_bad_records:{len(bad_records)}")
    by_attack: dict[str, int] = {}
    admissible_by_attack: dict[str, int] = {}
    failure_by_attack: dict[str, int] = {}
    for record in records:
        attack_id = str(record.get("attack_id", ""))
        by_attack[attack_id] = by_attack.get(attack_id, 0) + 1
        if _row_claim_admissible(record):
            admissible_by_attack[attack_id] = admissible_by_attack.get(attack_id, 0) + 1
        elif not _row_utility_admissible(record):
            failure_by_attack[attack_id] = failure_by_attack.get(attack_id, 0) + 1
    claim_denominator = len(claim_admissible_records) + len(utility_failure_boundary_records)
    admissible_rate = len(claim_admissible_records) / claim_denominator if claim_denominator else 0.0
    return records, {
        "path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix(),
        "exists": path.exists(),
        "claim_bearing": payload.get("claim_bearing"),
        "formal_claim_allowed": payload.get("formal_claim_allowed"),
        "record_count": len(records),
        "claim_admissible_record_count": len(claim_admissible_records),
        "utility_failure_boundary_record_count": len(utility_failure_boundary_records),
        "support_only_boundary_record_count": len(support_only_boundary_records),
        "claim_denominator_record_count": claim_denominator,
        "admissible_rate": round(admissible_rate, 6),
        "by_attack": dict(sorted(by_attack.items())),
        "admissible_by_attack": dict(sorted(admissible_by_attack.items())),
        "utility_failure_by_attack": dict(sorted(failure_by_attack.items())),
        "admissibility_policy": (
            "Utility-inadmissible live records may be retained only as non-claim failure-boundary rows; "
            "claim coverage is computed over utility-admissible rows."
        ),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "",
        "blockers": blockers,
    }


def _iter_provider_records(path: Path, *, source_role: str) -> list[dict[str, object]]:
    full_eval = _read_json(path)
    records = full_eval.get("records", [])
    if not isinstance(records, list):
        return []
    run_id = str(full_eval.get("run_id", "") or dict(full_eval.get("operator_state", {}) if isinstance(full_eval.get("operator_state"), dict) else {}).get("run_id", ""))
    output: list[dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        task_id = str(record.get("task_id", "")).strip()
        if not task_id:
            continue
        enriched = dict(record)
        enriched["_provider_record_source_role"] = source_role
        enriched["_provider_record_source_path"] = path.as_posix()
        enriched["_provider_record_source_run_id"] = run_id
        output.append(enriched)
    return output


def _full_eval_records_by_task(query_budget_support_full_eval: Path | None = None) -> dict[str, dict[str, object]]:
    records = _iter_provider_records(
        ROOT / "artifacts" / "generated" / "full_eval_results.json",
        source_role="canonical_live_full_eval",
    )
    if query_budget_support_full_eval is not None and query_budget_support_full_eval.exists():
        records.extend(
            _iter_provider_records(
                query_budget_support_full_eval,
                source_role="query_budget_multisample_support_full_eval",
            )
        )
    by_task: dict[str, dict[str, object]] = {}
    for record in records:
        task_id = str(record.get("task_id", "")).strip()
        current = by_task.get(task_id)
        if current is None or _record_candidate_sample_count(record) > _record_candidate_sample_count(current):
            by_task[task_id] = record
    return by_task


def _build_attack_rows(
    tasks,
    attack_matrix: dict[str, object],
    rows_per_attack: int,
    *,
    query_budget_support_full_eval: Path | None = None,
) -> list[dict[str, object]]:
    attacks = [dict(item) for item in attack_matrix.get("attacks", []) if isinstance(item, dict)]
    provider_records = _full_eval_records_by_task(query_budget_support_full_eval)
    rows: list[dict[str, object]] = []
    for attack in attacks:
        attack_id = str(attack.get("attack_id", "")).strip()
        applicable_subsets = {str(item) for item in attack.get("applies_to_subsets", []) if str(item).strip()} if isinstance(attack.get("applies_to_subsets"), list) else set()
        selected = [task for task in tasks if not applicable_subsets or task.subset in applicable_subsets]
        if attack_id == "canary_preserving_rewrite":
            supported_languages = {"python", "typescript", "javascript", "java", "cpp", "c++", "cxx", "go"}
            supported_selected = [task for task in selected if task.language.lower() in supported_languages]
            if supported_selected:
                selected = supported_selected
        if attack_id == "cross_language_reexpression":
            non_python = [task for task in selected if task.language.lower() != "python"]
            if len({task.language.lower() for task in non_python}) < 3:
                non_python = [task for task in tasks if task.language.lower() != "python"]
            if non_python:
                selected = non_python
        if attack_id in MUTATION_REQUIRED_ATTACK_IDS:
            mutation_supported = []
            for task in selected:
                transformed_code, _, _ = _transform_code(task, attack_id, tasks=tasks)
                if _sha256_text(transformed_code) != _sha256_text(task.reference_code):
                    mutation_supported.append(task)
            selected = mutation_supported
        subset_seen: set[str] = set()
        balanced: list[object] = []
        for task in selected:
            if task.subset not in subset_seen:
                balanced.append(task)
                subset_seen.add(task.subset)
        if attack_id == "cross_language_reexpression":
            by_language: dict[str, list[object]] = {}
            for task in selected:
                by_language.setdefault(task.language.lower(), []).append(task)
            offset = 0
            while len(balanced) < rows_per_attack:
                added = False
                for language in sorted(by_language):
                    items = by_language[language]
                    if offset < len(items) and items[offset] not in balanced:
                        balanced.append(items[offset])
                        added = True
                        if len(balanced) >= rows_per_attack:
                            break
                if not added:
                    break
                offset += 1
        else:
            for task in selected:
                if task in balanced:
                    continue
                balanced.append(task)
                if len(balanced) >= rows_per_attack:
                    break
        for task in balanced[:rows_per_attack]:
            transformed_code, transform_kind, transform_metadata = _transform_code(task, attack_id, tasks=tasks)
            utility = _utility_preservation(
                task,
                transformed_code,
                attack_id,
                str(attack.get("utility_preservation_check", "")),
            )
            metadata = task_metadata(task)
            canary_preserved = all(
                str(metadata.get(key, "")).strip()
                for key in ("canary_split", "canary_pack_id", "hidden_test_family")
            )
            source_hash = _sha256_text(task.reference_code)
            transformed_hash = _sha256_text(transformed_code)
            provider_record = provider_records.get(task.task_id, {})
            candidate_sample_count = _record_candidate_sample_count(provider_record) if provider_record else 0
            query_budget_support_only = False
            query_budget_claim_bearing = attack_id != "query_budget_drop"
            if attack_id == "query_budget_drop":
                provider_source_role = str(provider_record.get("_provider_record_source_role", "") if provider_record else "")
                query_budget_support_only = provider_source_role != "canonical_live_full_eval"
                query_budget_claim_bearing = candidate_sample_count >= 2 and not query_budget_support_only
                transform_metadata = {
                    **transform_metadata,
                    "provider_record_present": bool(provider_record),
                    "candidate_sample_count": candidate_sample_count,
                    "query_budget_drop_supported": candidate_sample_count >= 2,
                    "query_budget_drop_requires_multi_sample_records": True,
                    "provider_record_source_role": provider_source_role,
                    "provider_record_source_run_id": provider_record.get("_provider_record_source_run_id", "") if provider_record else "",
                    "support_only_not_claim_bearing": query_budget_support_only,
                    "claim_bearing_attack_evidence": query_budget_claim_bearing,
                }
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
                    "support_only_not_claim_bearing": query_budget_support_only,
                    "claim_bearing_attack_evidence": query_budget_claim_bearing,
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
    return rows


def _sample_selection_gate() -> dict[str, object]:
    full_eval_path = ROOT / "artifacts" / "generated" / "full_eval_results.json"
    audit = _read_json(ROOT / "artifacts" / "generated" / "sample_selection_rerun_audit.json")
    full_eval = _read_json(full_eval_path)
    operator_state = full_eval.get("operator_state", {})
    operator_state = dict(operator_state) if isinstance(operator_state, dict) else {}
    source_sha = hashlib.sha256(full_eval_path.read_bytes()).hexdigest() if full_eval_path.exists() else ""
    run_id = str(operator_state.get("canonical_source_run_id") or operator_state.get("run_id") or full_eval.get("run_id") or "").strip()
    status = str(audit.get("current_canonical_status", "")).strip()
    provider_count = int(audit.get("provider_record_count", 0) or 0)
    raw_count = int(audit.get("raw_candidate_payload_record_count", 0) or 0)
    structured_count = int(audit.get("structured_candidate_payload_record_count", 0) or 0)
    gate_pass = (
        bool(audit)
        and str(audit.get("source_full_eval_sha256", "")).strip() == source_sha
        and str(audit.get("canonical_source_run_id", "")).strip() == run_id
        and status in CURRENT_SAMPLE_SELECTION_STATUSES
        and not bool(audit.get("rerun_required", True))
        and provider_count > 0
        and raw_count == provider_count
        and structured_count == provider_count
    )
    blockers: list[str] = []
    if not audit:
        blockers.append("sample_selection_audit_missing")
    if str(audit.get("source_full_eval_sha256", "")).strip() != source_sha:
        blockers.append("sample_selection_audit_sha256_mismatch")
    if str(audit.get("canonical_source_run_id", "")).strip() != run_id:
        blockers.append("sample_selection_audit_run_id_mismatch")
    if status not in CURRENT_SAMPLE_SELECTION_STATUSES:
        blockers.append("sample_selection_status_not_current")
    if bool(audit.get("rerun_required", True)):
        blockers.append("sample_selection_rerun_required")
    if provider_count <= 0 or raw_count != provider_count or structured_count != provider_count:
        blockers.append("sample_selection_candidate_payload_contract_incomplete")
    return {
        "gate_pass": gate_pass,
        "current_canonical_status": status,
        "provider_record_count": provider_count,
        "raw_candidate_payload_record_count": raw_count,
        "structured_candidate_payload_record_count": structured_count,
        "source_full_eval_sha256": source_sha,
        "canonical_source_run_id": run_id,
        "blockers": blockers,
    }


def _canonical_live_records() -> tuple[list[dict[str, object]], dict[str, object], list[str]]:
    full_eval_path = ROOT / "artifacts" / "generated" / "full_eval_results.json"
    payload = _read_json(full_eval_path)
    records = [dict(item) for item in payload.get("records", []) if isinstance(item, dict)] if isinstance(payload.get("records", []), list) else []
    local_records = [
        item
        for item in records
        if str(item.get("benchmark", "")).strip() == "CodeDyeBench"
        and str(item.get("study_kind", "")).strip() == "deepseek_live_null_audit"
    ]
    blockers: list[str] = []
    if not full_eval_path.exists():
        blockers.append("canonical_full_eval_missing")
    if len(local_records) < 300:
        blockers.append(f"canonical_live_local_records_below_300:{len(local_records)}")
    if any(str(item.get("provider_mode_resolved", "")).strip() != "live" for item in local_records):
        blockers.append("canonical_live_records_include_non_live_provider_mode")
    if any(str(item.get("provider_name", "")).strip().lower() != "deepseek" for item in local_records):
        blockers.append("canonical_live_records_include_non_deepseek_provider")
    if any(not bool(item.get("candidate_payload_capture_complete", False)) for item in local_records):
        blockers.append("canonical_live_records_missing_candidate_payload_capture")
    if any("raw_provider_transcript_hash" not in item or not str(item.get("raw_provider_transcript_hash", "")).strip() for item in local_records):
        blockers.append("canonical_live_records_missing_raw_provider_transcript_hash")
    source_sha = hashlib.sha256(full_eval_path.read_bytes()).hexdigest() if full_eval_path.exists() else ""
    return local_records, {
        "path": "artifacts/generated/full_eval_results.json",
        "sha256": source_sha,
        "schema_version": str(payload.get("schema_version", "")),
        "local_record_count": len(local_records),
        "total_record_count": len(records),
    }, sorted(dict.fromkeys(blockers))


def _as_float(value: object, default: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _permutation_subset_sensitivity(
    decisions: list[float],
    subsets: list[str],
    *,
    iterations: int = 2000,
    seed: int = 2026,
) -> dict[str, object]:
    if not decisions or len(decisions) != len(subsets):
        return {
            "method": "subset_label_permutation_rate_range",
            "iterations": 0,
            "seed": seed,
            "p_value": 1.0,
            "observed_rate_range": 0.0,
            "blockers": ["permutation_inputs_missing_or_misaligned"],
        }
    grouped: dict[str, list[float]] = {}
    for decision, subset in zip(decisions, subsets, strict=True):
        grouped.setdefault(subset, []).append(decision)
    observed_rates = {key: mean(values) if values else 0.0 for key, values in grouped.items()}
    observed_range = max(observed_rates.values()) - min(observed_rates.values()) if observed_rates else 0.0
    sizes = [len(grouped[key]) for key in sorted(grouped)]
    rng = Random(seed)
    extreme_count = 0
    for _ in range(max(iterations, 1)):
        shuffled = list(decisions)
        rng.shuffle(shuffled)
        offset = 0
        rates: list[float] = []
        for size in sizes:
            group = shuffled[offset : offset + size]
            offset += size
            rates.append(mean(group) if group else 0.0)
        if (max(rates) - min(rates) if rates else 0.0) >= observed_range:
            extreme_count += 1
    p_value = (extreme_count + 1) / (max(iterations, 1) + 1)
    return {
        "method": "subset_label_permutation_rate_range",
        "iterations": max(iterations, 1),
        "seed": seed,
        "hypothesis": "canonical positive-rate concentration is not driven by one CodeDyeBench subset",
        "observed_subset_rates": {key: round(value, 6) for key, value in sorted(observed_rates.items())},
        "observed_rate_range": round(observed_range, 6),
        "p_value": round(p_value, 6),
        "decision": "no_subset_concentration_flag" if p_value >= 0.05 else "subset_concentration_flag",
        "claim_bearing": True,
        "blockers": [],
    }


def _canonical_claim_bearing_statistics() -> dict[str, object]:
    local_records, source, blockers = _canonical_live_records()
    decisions = [1.0 if bool(item.get("familywise_decision_gate_pass", False)) else 0.0 for item in local_records]
    p_values = [_as_float(item.get("p_value_or_score"), 1.0) for item in local_records]
    subsets = [str(item.get("subset", "")).strip() or "unknown" for item in local_records]
    bootstrap_result = bootstrap_mean_ci(decisions, iterations=2000, seed=2026)
    bootstrap_result.update(
        {
            "metric": "familywise_positive_rate",
            "n": len(decisions),
            "positive_count": int(sum(decisions)),
            "claim_bearing": True,
            "interpretation": "null-audit positive-rate interval, not a direct contamination accusation",
        }
    )
    permutation_result = _permutation_subset_sensitivity(decisions, subsets)
    fdr_result = benjamini_hochberg(p_values, q=0.05)
    rejected = sum(1 for item in fdr_result.get("decisions", []) if item)
    fdr_result.update(
        {
            "p_value_source": "canonical_full_eval_results.records[].empirical_null_p_value",
            "source_field": "p_value_or_score",
            "source_field_contract": (
                "For CodeDye canonical null-audit records this field is the "
                "predeclared empirical null p-value emitted by the detector, "
                "not a score threshold or post-hoc calibrated label."
            ),
            "n": len(p_values),
            "rejected_count": rejected,
            "min_p_value": round(min(p_values), 6) if p_values else 1.0,
            "claim_bearing": True,
            "interpretation": "familywise FDR sensitivity over canonical null-audit records",
        }
    )
    blockers.extend(str(item) for item in permutation_result.get("blockers", []))
    return {
        "claim_bearing": not blockers,
        "claim_role": "claim_bearing_final_statistics" if not blockers else "statistics_gate_blocked",
        "source_full_eval": source,
        "record_scope": "CodeDyeBench DeepSeek live null-audit records only",
        "record_count": len(local_records),
        "positive_count": int(sum(decisions)),
        "positive_rate": round(mean(decisions), 6) if decisions else 0.0,
        "bootstrap_result": bootstrap_result if not blockers else {},
        "permutation_result": permutation_result if not blockers else {},
        "fdr_result": fdr_result if not blockers else {},
        "blockers": sorted(dict.fromkeys(blockers)),
    }


def _attack_record_contract(rows: list[dict[str, object]], attack_matrix: dict[str, object]) -> dict[str, object]:
    attack_ids = {str(item.get("attack_id", "")) for item in attack_matrix.get("attacks", []) if isinstance(item, dict)}
    claim_rows = [row for row in rows if _row_claim_admissible(row)]
    claim_attack_ids = attack_ids - SUPPORT_REQUIRED_ATTACK_IDS
    observed_ids = {str(row.get("attack_id", "")) for row in claim_rows}
    observed_all_ids = {str(row.get("attack_id", "")) for row in rows}
    missing_required = sorted(REQUIRED_ATTACK_IDS - observed_ids)
    missing_support_required = sorted(SUPPORT_REQUIRED_ATTACK_IDS - observed_all_ids)
    missing_declared = sorted(claim_attack_ids - observed_ids)
    utility_failed = [row for row in rows if not bool(row.get("utility_preserved", False))]
    claim_utility_failed = [row for row in claim_rows if not bool(row.get("utility_preserved", False))]
    canary_failed = [row for row in claim_rows if not bool(row.get("canary_preserved", False))]
    placeholder_rows = [row for row in claim_rows if bool(row.get("placeholder_transform", False))]
    canary_rewrite_rows = [row for row in claim_rows if row.get("attack_id") == "canary_preserving_rewrite"]
    canary_rewrite_changed = [row for row in canary_rewrite_rows if bool(row.get("code_changed", False))]
    chronology_rows = [row for row in claim_rows if row.get("attack_id") == "chronology_shuffle"]
    chronology_matched = [
        row for row in chronology_rows
        if bool(dict(row.get("transform_metadata", {})).get("matched_chronology_control", False))
        and dict(row.get("transform_metadata", {})).get("original_release_window") != dict(row.get("transform_metadata", {})).get("shuffled_release_window")
    ]
    cross_language_rows = [row for row in claim_rows if row.get("attack_id") == "cross_language_reexpression"]
    cross_language_non_python_count = sum(1 for row in cross_language_rows if str(row.get("language", "")).lower() != "python")
    cross_language_languages = sorted({str(row.get("language", "")).lower() for row in cross_language_rows if str(row.get("language", "")).strip()})
    cross_language_provenance_locked = [
        row
        for row in cross_language_rows
        if bool(dict(row.get("transform_metadata", {})).get("cross_language_provenance_locked", False))
        and bool(dict(row.get("transform_metadata", {})).get("cross_language_source_task_found", False))
        and bool(dict(row.get("transform_metadata", {})).get("source_target_languages_differ", False))
        and bool(dict(row.get("transform_metadata", {})).get("source_target_same_template", False))
        and bool(dict(row.get("transform_metadata", {})).get("source_target_same_canary_pack", False))
        and str(dict(row.get("transform_metadata", {})).get("source_task_id", "")).strip()
        and str(dict(row.get("transform_metadata", {})).get("source_provenance_hash", "")).strip()
        and str(dict(row.get("transform_metadata", {})).get("target_provenance_hash", "")).strip()
        and str(dict(row.get("transform_metadata", {})).get("source_target_binding_hash", "")).strip()
    ]
    cross_language_unlocked = [
        row for row in cross_language_rows if row not in cross_language_provenance_locked
    ]
    query_budget_rows = [row for row in rows if row.get("attack_id") == "query_budget_drop"]
    query_budget_supported = [
        row for row in query_budget_rows
        if bool(dict(row.get("transform_metadata", {})).get("query_budget_drop_supported", False))
        or (
            _row_utility_admissible(row)
            and bool(row.get("support_only_not_claim_bearing", False))
            and not bool(row.get("claim_bearing_attack_evidence", False))
            and str(row.get("provider_mode_resolved", "")).strip().lower() == "live"
            and str(row.get("raw_payload_hash", "")).strip()
            and str(row.get("structured_payload_hash", "")).strip()
        )
    ]
    comment_whitespace_rows = [row for row in claim_rows if row.get("attack_id") == "comment_whitespace_normalize"]
    comment_whitespace_locked = [
        row
        for row in comment_whitespace_rows
        if dict(row.get("transform_metadata", {})).get("semantic_noop_attack_boundary") == "format_preserving_comment_whitespace_normalization"
        and dict(row.get("transform_metadata", {})).get("comment_whitespace_noop_locked") is True
        and dict(row.get("transform_metadata", {})).get("code_change_required") is False
        and dict(row.get("transform_metadata", {})).get("mutation_required_attack") is False
        and dict(row.get("transform_metadata", {})).get("matched_null_control_required") is True
        and dict(row.get("transform_metadata", {})).get("no_outcome_selection_required") is True
        and str(dict(row.get("transform_metadata", {})).get("source_task_id", "")).strip()
        and str(dict(row.get("transform_metadata", {})).get("source_reference_code_sha256", "")).strip()
        and str(dict(row.get("transform_metadata", {})).get("source_provenance_hash", "")).strip()
    ]
    required_support_only_rows = [
        row
        for row in rows
        if str(row.get("attack_id", "")) in REQUIRED_ATTACK_IDS
        and (
            bool(row.get("support_only_not_claim_bearing", False))
            or bool(dict(row.get("transform_metadata", {})).get("support_only_not_claim_bearing", False))
        )
    ]
    support_required_rows = [
        row
        for row in rows
        if str(row.get("attack_id", "")) in SUPPORT_REQUIRED_ATTACK_IDS
    ]
    support_required_valid = [
        row
        for row in support_required_rows
        if _row_utility_admissible(row)
        and bool(row.get("support_only_not_claim_bearing", False))
        and not bool(row.get("claim_bearing_attack_evidence", False))
        and str(row.get("provider_mode_resolved", "")).strip().lower() == "live"
        and str(row.get("raw_payload_hash", "")).strip()
        and str(row.get("structured_payload_hash", "")).strip()
    ]
    query_budget_claim_bearing_supported = [
        row
        for row in query_budget_supported
        if bool(row.get("claim_bearing_attack_evidence", False))
        and not bool(row.get("support_only_not_claim_bearing", False))
    ]
    mutation_required_rows = [
        row for row in claim_rows if str(row.get("attack_id", "")) in MUTATION_REQUIRED_ATTACK_IDS
    ]
    mutation_required_noop = [
        row for row in mutation_required_rows if not bool(row.get("code_changed", False))
    ]
    mutation_required_counts = {
        attack_id: sum(1 for row in mutation_required_rows if str(row.get("attack_id", "")) == attack_id)
        for attack_id in sorted(MUTATION_REQUIRED_ATTACK_IDS)
    }
    mutation_required_noop_counts = {
        attack_id: sum(1 for row in mutation_required_noop if str(row.get("attack_id", "")) == attack_id)
        for attack_id in sorted(MUTATION_REQUIRED_ATTACK_IDS)
    }
    by_attack_subset: dict[str, int] = {}
    by_attack: dict[str, int] = {}
    admissible_by_attack: dict[str, int] = {}
    utility_failure_by_attack: dict[str, int] = {}
    for row in rows:
        attack_id = str(row.get("attack_id", ""))
        by_attack[attack_id] = by_attack.get(attack_id, 0) + 1
        if _row_claim_admissible(row):
            admissible_by_attack[attack_id] = admissible_by_attack.get(attack_id, 0) + 1
        elif not _row_utility_admissible(row):
            utility_failure_by_attack[attack_id] = utility_failure_by_attack.get(attack_id, 0) + 1
    for row in claim_rows:
        key = f"{row.get('attack_id')}::{row.get('subset')}"
        by_attack_subset[key] = by_attack_subset.get(key, 0) + 1
    claim_denominator = sum(1 for row in rows if str(row.get("attack_id", "")) not in SUPPORT_REQUIRED_ATTACK_IDS)
    admissible_rate = len(claim_rows) / claim_denominator if claim_denominator else 0.0
    blockers: list[str] = []
    if missing_required:
        blockers.append("required_attack_rows_missing")
    if missing_support_required:
        blockers.append("support_required_attack_rows_missing")
    if missing_declared:
        blockers.append("declared_attack_rows_missing")
    if claim_utility_failed:
        blockers.append("attack_utility_preservation_failed")
    if canary_failed:
        blockers.append("attack_canary_preservation_failed")
    if placeholder_rows:
        blockers.append("placeholder_attack_transform_detected")
    if canary_rewrite_rows and len(canary_rewrite_changed) != len(canary_rewrite_rows):
        blockers.append("canary_preserving_rewrite_not_code_changing")
    if chronology_rows and len(chronology_matched) != len(chronology_rows):
        blockers.append("chronology_shuffle_unmatched_or_unchanged")
    if cross_language_rows and (cross_language_non_python_count <= 0 or len(set(cross_language_languages) - {"python"}) < 3):
        blockers.append("cross_language_reexpression_multilanguage_coverage_insufficient")
    if cross_language_rows and cross_language_unlocked:
        blockers.append("cross_language_reexpression_source_target_provenance_unlocked")
    if query_budget_rows and len(query_budget_supported) != len(query_budget_rows):
        blockers.append("query_budget_drop_requires_multi_sample_provider_records")
    if comment_whitespace_rows and len(comment_whitespace_locked) != len(comment_whitespace_rows):
        blockers.append("comment_whitespace_normalize_semantic_noop_boundary_missing")
    if required_support_only_rows:
        blockers.append("required_attack_rows_support_only_not_claim_bearing")
    if "query_budget_drop" in attack_ids and len(support_required_valid) < MIN_ADMISSIBLE_RECORDS_PER_ATTACK:
        blockers.append("query_budget_drop_support_records_below_minimum")
    for attack_id in sorted(claim_attack_ids):
        if by_attack.get(attack_id, 0) and admissible_by_attack.get(attack_id, 0) < MIN_ADMISSIBLE_RECORDS_PER_ATTACK:
            blockers.append(
                f"attack_admissible_records_below_{MIN_ADMISSIBLE_RECORDS_PER_ATTACK}:"
                f"{attack_id}:{admissible_by_attack.get(attack_id, 0)}/{by_attack.get(attack_id, 0)}"
            )
    if rows and admissible_rate < MIN_ADMISSIBLE_RATE:
        blockers.append(f"attack_admissible_rate_below_{MIN_ADMISSIBLE_RATE:.2f}:{admissible_rate:.4f}")
    for attack_id, count in mutation_required_counts.items():
        if attack_id in attack_ids and count <= 0:
            blockers.append(f"mutation_required_attack_no_changed_rows:{attack_id}")
    if mutation_required_noop:
        blockers.append("mutation_required_attack_noop_rows_detected")
    if not rows:
        blockers.append("attack_records_empty")
    return {
        "gate_pass": not blockers,
        "attack_record_count": len(rows),
        "claim_admissible_record_count": len(claim_rows),
        "utility_failure_boundary_record_count": len(utility_failed),
        "claim_denominator_record_count": claim_denominator,
        "admissible_rate": round(admissible_rate, 6),
        "minimum_admissible_records_per_attack": MIN_ADMISSIBLE_RECORDS_PER_ATTACK,
        "minimum_admissible_rate": MIN_ADMISSIBLE_RATE,
        "declared_attack_ids": sorted(attack_ids),
        "claim_required_attack_ids": sorted(REQUIRED_ATTACK_IDS),
        "support_required_attack_ids": sorted(SUPPORT_REQUIRED_ATTACK_IDS),
        "observed_attack_ids": sorted(observed_ids),
        "observed_attack_ids_all_records": sorted(observed_all_ids),
        "required_attack_ids": sorted(REQUIRED_ATTACK_IDS),
        "missing_required_attack_ids": missing_required,
        "missing_support_required_attack_ids": missing_support_required,
        "missing_declared_attack_ids": missing_declared,
        "by_attack_subset": dict(sorted(by_attack_subset.items())),
        "by_attack": dict(sorted(by_attack.items())),
        "admissible_by_attack": dict(sorted(admissible_by_attack.items())),
        "utility_failure_by_attack": dict(sorted(utility_failure_by_attack.items())),
        "utility_failed_count": len(utility_failed),
        "claim_utility_failed_count": len(claim_utility_failed),
        "canary_failed_count": len(canary_failed),
        "placeholder_transform_count": len(placeholder_rows),
        "canary_preserving_rewrite_changed_count": len(canary_rewrite_changed),
        "chronology_shuffle_matched_count": len(chronology_matched),
        "cross_language_non_python_record_count": cross_language_non_python_count,
        "cross_language_languages": cross_language_languages,
        "cross_language_provenance_locked_count": len(cross_language_provenance_locked),
        "cross_language_provenance_unlocked_count": len(cross_language_unlocked),
        "cross_language_binding_policy": (
            "Each non-Python cross-language row must bind to a Python source task with the same "
            "generator_template and canary_pack_id, and must include source/target code and provenance hashes."
        ),
        "query_budget_supported_record_count": len(query_budget_supported),
        "query_budget_claim_bearing_supported_record_count": len(query_budget_claim_bearing_supported),
        "query_budget_support_required_valid_record_count": len(support_required_valid),
        "query_budget_record_count": len(query_budget_rows),
        "comment_whitespace_record_count": len(comment_whitespace_rows),
        "comment_whitespace_noop_boundary_locked_count": len(comment_whitespace_locked),
        "comment_whitespace_noop_boundary_unlocked_count": len(comment_whitespace_rows) - len(comment_whitespace_locked),
        "required_support_only_record_count": len(required_support_only_rows),
        "required_support_only_counts": {
            attack_id: sum(1 for row in required_support_only_rows if str(row.get("attack_id", "")) == attack_id)
            for attack_id in sorted(REQUIRED_ATTACK_IDS)
        },
        "mutation_required_attack_ids": sorted(MUTATION_REQUIRED_ATTACK_IDS),
        "mutation_required_record_counts": mutation_required_counts,
        "mutation_required_noop_counts": mutation_required_noop_counts,
        "mutation_required_noop_count": len(mutation_required_noop),
        "utility_failure_ledger_sample": [
            {
                "attack_id": str(row.get("attack_id", "")),
                "task_id": str(row.get("task_id", "")),
                "language": str(row.get("language", "")),
                "selected_utility_score": row.get("selected_utility_score", None),
                "record_hash": str(row.get("record_hash", "")),
            }
            for row in utility_failed[:25]
        ],
        "admissibility_policy": (
            "Main attack claims are computed from utility-admissible claim-required rows only. Query-budget-drop "
            "is required as a support-only budget-stress condition with retained live payloads, but it is not "
            "placed in the main-claim denominator."
        ),
        "blockers": blockers,
    }


def _null_calibration_contract() -> dict[str, object]:
    full_eval = _read_json(ROOT / "artifacts" / "generated" / "full_eval_results.json")
    records = [record for record in full_eval.get("records", []) if isinstance(record, dict)] if isinstance(full_eval.get("records", []), list) else []
    artifact_path = ROOT / "artifacts" / "generated" / "null_calibration_negative_controls.json"
    artifact = _read_json(artifact_path)
    artifact_records = [record for record in artifact.get("records", []) if isinstance(record, dict)] if isinstance(artifact.get("records", []), list) else []
    negative_controls = [record for record in records if bool(record.get("is_negative_control", False))]
    empirical_null_records = [
        record
        for record in records
        if str(record.get("null_calibration_method", "")).strip() == "metadata_matched_empirical_dominance_tail_bound"
        and str(record.get("null_pool_strategy", "")).strip()
        and not bool(record.get("null_pool_fallback_used", True))
        and int(record.get("null_sample_size", 0) or 0) > 0
    ]
    empirical_null_sample_count = sum(int(record.get("null_sample_size", 0) or 0) for record in empirical_null_records)
    empirical_null_family_count = len({str(record.get("family", "")).strip() for record in empirical_null_records if str(record.get("family", "")).strip()})
    explicit_controls = artifact_records if artifact_records else negative_controls
    contaminated_negative_controls = [record for record in negative_controls if bool(record.get("contaminated", False))]
    contaminated_artifact_controls = [record for record in artifact_records if bool(record.get("contaminated", False))]
    ci = dict(artifact.get("ci", {})) if isinstance(artifact.get("ci"), dict) else {}
    try:
        ci95_high = float(ci.get("ci95_high", artifact.get("false_positive_upper_bound_95", 1.0)) or 1.0)
    except (TypeError, ValueError):
        ci95_high = 1.0
    if artifact_records and bool(artifact.get("gate_pass", False)):
        false_positive_bounds = [ci95_high]
    else:
        false_positive_bounds = [float(record.get("false_positive_bound", 1.0) or 1.0) for record in explicit_controls]
    stratification = dict(artifact.get("stratification", {})) if isinstance(artifact.get("stratification"), dict) else {}
    subset_counts = dict(stratification.get("subset_counts", {})) if isinstance(stratification.get("subset_counts", {}), dict) else {}
    required_subsets = {"prompt_chronology", "fresh_unseen_tasks", "semantic_canaries", "cross_language_variants", "canary_preserving_rewrites"}
    blockers: list[str] = []
    has_explicit_negative_controls = len(explicit_controls) >= MIN_STRATIFIED_NEGATIVE_CONTROL_RECORDS
    has_embedded_empirical_null_pool = empirical_null_sample_count >= MIN_NEGATIVE_CONTROL_RECORDS
    if not has_explicit_negative_controls:
        blockers.append(f"negative_control_record_count_below_{MIN_STRATIFIED_NEGATIVE_CONTROL_RECORDS}:{len(explicit_controls)}")
    if contaminated_negative_controls or contaminated_artifact_controls:
        blockers.append(f"negative_control_false_positive_count:{len(contaminated_negative_controls) + len(contaminated_artifact_controls)}")
    if ci95_high > MAX_NEGATIVE_CONTROL_CI95_HIGH:
        blockers.append(f"negative_control_ci95_high_exceeds_{MAX_NEGATIVE_CONTROL_CI95_HIGH}:{ci95_high}")
    if false_positive_bounds and max(false_positive_bounds) > MAX_NEGATIVE_CONTROL_CI95_HIGH:
        blockers.append(f"negative_control_false_positive_bound_exceeds_{MAX_NEGATIVE_CONTROL_CI95_HIGH}")
    if not artifact_records:
        blockers.append("explicit_negative_control_artifact_missing")
    if artifact and not bool(artifact.get("gate_pass", False)):
        blockers.append("explicit_negative_control_artifact_gate_failed")
    stratified_gate_pass = bool(artifact.get("gate_pass", False)) and artifact_records
    if not stratified_gate_pass and required_subsets - set(str(key) for key in subset_counts):
        blockers.append("negative_control_stratified_subset_counts_missing")
    for subset_name in required_subsets:
        try:
            subset_count = int(subset_counts.get(subset_name, 0) or 0)
        except (TypeError, ValueError):
            subset_count = 0
        if not stratified_gate_pass and subset_count < 15:
            blockers.append(f"negative_control_subset_count_below_15:{subset_name}:{subset_count}")
    if not explicit_controls and not has_embedded_empirical_null_pool:
        blockers.append("null_control_records_missing")
    p_values = (
        false_positive_bounds
        if false_positive_bounds
        else [
            float(record.get("p_value_or_score", record.get("false_positive_bound", 1.0)) or 1.0)
            for record in empirical_null_records
        ]
        or [1.0]
    )
    return {
        "gate_pass": not blockers,
        "record_count": len(records),
        "negative_control_record_count": len(explicit_controls),
        "canonical_embedded_negative_control_record_count": len(negative_controls),
        "explicit_negative_control_artifact_path": artifact_path.relative_to(ROOT).as_posix(),
        "explicit_negative_control_artifact_gate_pass": bool(artifact.get("gate_pass", False)),
        "minimum_negative_control_record_count": MIN_STRATIFIED_NEGATIVE_CONTROL_RECORDS,
        "negative_control_ci95_high": round(ci95_high, 6),
        "negative_control_ci": ci,
        "negative_control_stratification": stratification,
        "empirical_null_record_count": len(empirical_null_records),
        "empirical_null_sample_count": empirical_null_sample_count,
        "empirical_null_family_count": empirical_null_family_count,
        "negative_control_source": (
            "explicit_negative_control_records"
            if artifact_records
            else "canonical_embedded_negative_control_records"
            if negative_controls
            else "embedded_metadata_matched_empirical_null_pool_support_only"
            if has_embedded_empirical_null_pool
            else "missing"
        ),
        "negative_control_false_positive_count": len(contaminated_negative_controls) + len(contaminated_artifact_controls),
        "max_negative_control_false_positive_bound": round(max(false_positive_bounds), 6) if false_positive_bounds else None,
        "median_negative_control_false_positive_bound": round(sorted(false_positive_bounds)[len(false_positive_bounds) // 2], 6) if false_positive_bounds else None,
        "p_values_for_fdr": p_values,
        "blockers": blockers,
    }


def main() -> None:
    args = _parse_args()
    attack_matrix = json.loads(Path(args.attack_matrix).read_text(encoding="utf-8"))
    tasks = load_code_dyebench_tasks(ROOT)
    plan = build_statistical_audit_plan(tasks, attack_matrix)
    query_budget_support_full_eval = Path(args.query_budget_support_full_eval)
    scaffold_attack_rows = _build_attack_rows(
        tasks,
        attack_matrix,
        max(args.rows_per_attack, 1),
        query_budget_support_full_eval=query_budget_support_full_eval,
    )
    canonical_live_rows, canonical_live_gate = _canonical_live_attack_rows(Path(args.canonical_attack_live))
    attack_rows = canonical_live_rows if not canonical_live_gate["blockers"] else scaffold_attack_rows
    attack_contract = _attack_record_contract(attack_rows, attack_matrix)
    sample_selection = _sample_selection_gate()
    null_calibration = _null_calibration_contract()
    canonical_statistics = _canonical_claim_bearing_statistics()
    utility_scores = [1.0 if row.get("utility_preserved") else 0.0 for row in attack_rows]
    ci = bootstrap_mean_ci(utility_scores, iterations=200, seed=13)
    attack_ids = sorted({str(row.get("attack_id", "")) for row in attack_rows})
    p_values = list(null_calibration["p_values_for_fdr"])
    fdr = benjamini_hochberg(p_values, q=0.05)
    issues = _issues(plan)
    issues.extend(f"canonical_attack_live:{item}" for item in canonical_live_gate["blockers"])
    issues.extend(attack_contract["blockers"])
    issues.extend(f"sample_selection:{item}" for item in sample_selection["blockers"])
    issues.extend(f"null_calibration:{item}" for item in null_calibration["blockers"])
    issues.extend(f"canonical_statistics:{item}" for item in canonical_statistics["blockers"])
    issues = sorted(dict.fromkeys(issues))
    payload = {
        "schema_version": "codedye_attack_matrix_null_calibration_ci_v1",
        "machine_verifiable": True,
        "provider_policy": "no_provider_no_live_api",
        "status": "passed" if not issues else "failed",
        "claim_bearing": bool(canonical_statistics.get("claim_bearing", False)) and not issues,
        "claim_role": canonical_statistics.get("claim_role", "statistics_gate_blocked"),
        "issues": issues,
        "statistical_plan_schema_version": plan.get("schema_version", ""),
        "attack_matrix_summary": plan.get("attack_matrix_summary", {}),
        "attack_record_contract": attack_contract,
        "attack_records": attack_rows,
        "canonical_attack_live_gate": canonical_live_gate,
        "attack_record_source": (
            "canonical_attack_live"
            if not canonical_live_gate["blockers"]
            else "no_provider_scaffold_blocked_until_canonical_attack_live"
        ),
        "sample_selection_gate": sample_selection,
        "null_calibration_contract": null_calibration,
        "query_budget_support_artifact": {
            "path": query_budget_support_full_eval.as_posix(),
            "present": query_budget_support_full_eval.exists(),
            "role": "support_only_not_claim_bearing",
        },
        "null_calibration_plan": plan.get("null_calibration_plan", {}),
        "bootstrap_smoke": ci,
        "fdr_smoke": fdr,
        "bootstrap_result": canonical_statistics.get("bootstrap_result", {}),
        "permutation_result": canonical_statistics.get("permutation_result", {}),
        "fdr_result": canonical_statistics.get("fdr_result", {}),
        "canonical_claim_bearing_statistics": canonical_statistics,
        "attack_family_utility_mean": round(mean(utility_scores), 6) if utility_scores else 0.0,
        "ci_scaffold_commands": [
            "python scripts/build_statistical_audit_plan.py",
            "python scripts/run_attack_matrix_ci_scaffold.py",
        ],
        "remaining_blockers": plan.get("remaining_blockers", []),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    print(output.relative_to(ROOT) if output.is_relative_to(ROOT) else output)
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
