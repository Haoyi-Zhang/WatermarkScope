from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from codedye.config import default_plan, load_backbone_matrix
from codedye.canaries import summarize_local_benchmark_inventory
from codedye.providers import load_provider_configs, provider_api_key_state, resolve_provider_config_path
from integrations.baseline_adapters import describe_baselines
from integrations.benchmark_adapters import describe_benchmark_loaders
from _closure_boundary import load_closure_boundary


CLAIM_BOUNDARY = "deepseek_live_null_audit_only"
ABSOLUTE_PATH_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?:[A-Za-z]:[\\/])Users[\\/][^\s\"'`<>]+", re.IGNORECASE), "<WINDOWS_USER_HOME>"),
    (re.compile("/" + r"(?:root/data|data/codemark)(?:/[^\s\"'`<>]+)?", re.IGNORECASE), "<CLOUD_ARTIFACT_PATH>"),
)


def _provider_rows() -> list[dict[str, object]]:
    configs = load_provider_configs(str(resolve_provider_config_path(ROOT)))
    payload: list[dict[str, object]] = []
    for name, config in configs.items():
        payload.append(
            {
                "provider": config.name,
                "provider_key": name,
                "env_key": config.api_key_env,
                "model_id": config.model_name,
                "provider_kind": config.provider_kind,
                "api_key_source": "redacted",
                "api_key_state": "redacted",
                "credential_state": "redacted_runtime_config",
            }
        )
    return payload


def _segment_capable(item: dict[str, object]) -> bool:
    return bool(item.get("segment_run_capable", item.get("runnable", False)))


def _full_capable(item: dict[str, object]) -> bool:
    return bool(item.get("full_run_capable", False))


def _executed_public_benchmarks() -> list[str]:
    path = ROOT / "artifacts" / "generated" / "full_eval_results.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return sorted(
        {
            str(item.get("benchmark", ""))
            for item in payload.get("records", [])
            if str(item.get("task_source", item.get("source", ""))) == "external_checkout"
        }
    )


def _artifact_sha256(relative: str) -> str:
    path = ROOT / relative
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def _read_generated_json(name: str) -> dict[str, object]:
    path = ROOT / "artifacts" / "generated" / name
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolved_baseline_count(closure: dict[str, object], aggregate: dict[str, object], key: str) -> int:
    return max(_safe_int(closure.get(key), 0), _safe_int(aggregate.get(key), 0))


def _sanitize_snapshot_payload(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _sanitize_snapshot_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_snapshot_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_snapshot_payload(item) for item in value]
    if isinstance(value, str):
        redacted = value
        for pattern, replacement in ABSOLUTE_PATH_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted
    return value


def _first_failing_gate(closure: dict[str, object]) -> str:
    blockers = closure.get("canonical_full_evidence_blockers", [])
    if isinstance(blockers, list) and blockers:
        return str(blockers[0])
    return "all_gates_pass"


def _gate_payload(*, closure: dict[str, object], implementation_status: str, source_full_eval_sha256: str) -> dict[str, object]:
    review_ready = bool(closure.get("canonical_full_evidence_ready", False))
    blockers = list(closure.get("canonical_full_evidence_blockers", []))
    return {
        "schema_version": 1,
        "project": "CodeDye",
        "review_ready": review_ready,
        "experiment_entry_allowed": review_ready,
        "first_failing_gate": _first_failing_gate(closure),
        "claim_boundary": CLAIM_BOUNDARY,
        "canonical_source_run_id": str(closure.get("canonical_source_run_id", "")).strip(),
        "source_full_eval_sha256": source_full_eval_sha256,
        "zero_mod_validation_pass_count": int(closure.get("zero_mod_validation_pass_count", 0) or 0),
        "closure_blockers": blockers,
        "blockers": blockers,
        "implementation_status": implementation_status,
    }


def _write_snapshot_artifacts(payload: dict[str, object], *, closure: dict[str, object]) -> None:
    generated = ROOT / "artifacts" / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    source_hashes = payload.get("source_artifact_hashes", {})
    source_hashes = source_hashes if isinstance(source_hashes, dict) else {}
    gate_payload = _gate_payload(
        closure=closure,
        implementation_status=str(payload.get("implementation_status", "")),
        source_full_eval_sha256=str(source_hashes.get("full_eval_results", "")),
    )
    snapshot_payload = dict(payload)
    snapshot_payload.update(
        {
            "schema_version": "codedye_project_snapshot_v1",
            "artifact_role": "project_snapshot",
            "claim_boundary": CLAIM_BOUNDARY,
            "canonical_source_run_id": gate_payload["canonical_source_run_id"],
            "first_failing_gate": gate_payload["first_failing_gate"],
            "review_ready": gate_payload["review_ready"],
            "experiment_entry_allowed": gate_payload["experiment_entry_allowed"],
            "closure_blockers": list(gate_payload["closure_blockers"]),
        }
    )
    (generated / "project_snapshot.json").write_text(
        json.dumps(_sanitize_snapshot_payload(snapshot_payload), indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    (generated / "review_ready_gate.json").write_text(
        json.dumps(_sanitize_snapshot_payload(gate_payload), indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def main() -> None:
    payload = default_plan().to_dict()
    closure = load_closure_boundary(root=ROOT)
    aggregate = _read_generated_json("aggregate_results.json")
    recorded_pass_count = int(closure.get("no_overfit_recorded_pass_count", 0) or 0)
    required_pass_target = int(closure.get("no_overfit_required_pass_target", 20) or 20)
    zero_mod_pass_count = int(closure.get("zero_mod_validation_pass_count", 0) or 0)
    local_record_count = int(closure.get("local_reviewed_task_record_count", 0) or 0)
    public_record_count = int(closure.get("public_benchmark_record_count", 0) or 0)
    official_runnable_baseline_count = _resolved_baseline_count(
        closure,
        aggregate,
        "official_runnable_baseline_count",
    )
    official_record_backed_baseline_count = _resolved_baseline_count(
        closure,
        aggregate,
        "official_record_backed_baseline_count",
    )
    runnable_baseline_count = official_runnable_baseline_count
    record_backed_baseline_count = official_record_backed_baseline_count
    comparator_control_count = _resolved_baseline_count(closure, aggregate, "main_table_comparator_control_count")
    parse_only_baseline_count = int(closure.get("parse_only_baseline_count", 0) or 0)
    utility_first_promotion = closure.get("utility_first_promotion", {})
    utility_first_promotion = utility_first_promotion if isinstance(utility_first_promotion, dict) else {}
    comparator_policy = "that remain support/control evidence only and do not clear the official baseline gate"
    sample_selection_mismatch_count = int(closure.get("sample_selection_utility_mismatch_count", 0) or 0)
    sample_selection_rerun_required = bool(closure.get("sample_selection_rerun_required", False))
    sample_selection_rerun_required_reason = str(closure.get("sample_selection_rerun_required_reason", "")).strip()
    blockers = ", ".join(str(item) for item in closure.get("canonical_full_evidence_blockers", []))
    if sample_selection_rerun_required:
        sample_selection_status = (
            "sample-selection rematerialization still requires a fresh utility-first rerun because "
            f"{sample_selection_mismatch_count} canonical records diverge from the stored utility-selected sample indices and "
            f"{sample_selection_rerun_required_reason or 'the run-scoped artifact does not preserve a rerun-free rematerialization path'}"
        )
    else:
        sample_selection_status = (
            "sample-selection rematerialization is clean for the current canonical artifact: "
            f"{sample_selection_mismatch_count} canonical records diverge from the stored utility-selected sample indices, "
            "so the legacy sample-selection blocker is cleared"
        )
    payload["implementation_status"] = (
        "The canonical DeepSeek null-audit surface is materialized but not submission-ready: "
        f"it covers {local_record_count} reviewed local tasks, reports {public_record_count} public benchmark rows as utility support with contamination scoring disabled and not reported for those public tasks, and aligns full-eval records to the admissible-versus-diagnostic evidence contract; "
        f"the no-overfit ledger records {recorded_pass_count} passes against its {required_pass_target}-pass target and {zero_mod_pass_count} consecutive zero-mod validation passes, the baseline inventory records {official_runnable_baseline_count} qualifying runnable official baselines, {record_backed_baseline_count} record-backed official main-table baselines, {parse_only_baseline_count} parse-only official references, and {comparator_control_count} disclosed runnable comparator controls {comparator_policy}; "
        f"{sample_selection_status}, while submission closure remains blocked by {blockers}"
    )
    payload["backbones"] = [item.name for item in load_backbone_matrix(ROOT / "configs" / "backbone_matrix.json")]
    payload["provider_modes"] = ["mock", "replay", "live"]
    payload["providers"] = _provider_rows()
    payload["local_benchmark_inventory"] = summarize_local_benchmark_inventory(ROOT)
    payload["baselines"] = describe_baselines(ROOT)
    payload["official_baselines"] = [
        item for item in payload["baselines"] if bool(item.get("official_baseline", item.get("official_main_table_baseline", False)))
    ]
    payload["main_table_comparator_controls"] = [
        item["name"] for item in payload["baselines"] if bool(item.get("main_table_comparator_control", False))
    ]
    payload["parse_only_baselines"] = [
        item["name"] for item in payload["baselines"] if str(item.get("runnable_status", "")) == "parse_only"
    ]
    payload["runnable_baselines"] = [
        item["name"] for item in payload["baselines"] if bool(item.get("runnable", False))
    ]
    payload["benchmark_integrations"] = describe_benchmark_loaders(ROOT, limit=None)
    payload["sampled_segment_run_capable_public_benchmarks"] = [
        item["benchmark"] for item in payload["benchmark_integrations"] if _segment_capable(item)
    ]
    payload["sampled_full_run_capable_public_benchmarks"] = [
        item["benchmark"] for item in payload["benchmark_integrations"] if _full_capable(item)
    ]
    payload["segment_run_capable_public_benchmarks"] = payload["sampled_segment_run_capable_public_benchmarks"]
    payload["full_run_capable_public_benchmarks"] = payload["sampled_full_run_capable_public_benchmarks"]
    payload["executed_public_benchmarks"] = closure["executed_public_benchmarks"]
    payload["reference_only_benchmarks"] = [
        item["benchmark"] for item in payload["benchmark_integrations"] if str(item.get("runnable_status", "")) == "reference_only"
    ]
    payload["public_benchmark_capability_registry"] = {
        "sampled_segment_run_capable": payload["sampled_segment_run_capable_public_benchmarks"],
        "sampled_full_run_capable": payload["sampled_full_run_capable_public_benchmarks"],
        "executed": payload["executed_public_benchmarks"],
    }
    payload["closure_boundary"] = closure
    payload["canonical_full_evidence_ready"] = closure["canonical_full_evidence_ready"]
    payload["submission_closure_eligible"] = closure["canonical_full_evidence_ready"]
    payload["canonical_full_evidence_blockers"] = closure["canonical_full_evidence_blockers"]
    payload["main_table_baseline_count"] = record_backed_baseline_count
    payload["runnable_baseline_count"] = runnable_baseline_count
    payload["official_record_backed_baseline_count"] = official_record_backed_baseline_count
    payload["runnable_baseline_or_comparator_count"] = max(
        _safe_int(closure.get("runnable_baseline_or_comparator_count"), 0),
        _safe_int(aggregate.get("runnable_baseline_or_comparator_count"), 0),
        runnable_baseline_count + comparator_control_count,
    )
    payload["main_table_comparator_control_count"] = comparator_control_count
    payload["parse_only_baseline_count"] = closure["parse_only_baseline_count"]
    payload["baseline_admission_verification_complete"] = closure["baseline_admission_verification_complete"]
    payload["baseline_admission_gate_pass"] = closure["baseline_admission_gate_pass"]
    payload["baseline_candidate_audit_summary"] = {
        "schema_version": closure.get("baseline_candidate_audit_schema_version", ""),
        "candidate_count": closure.get("baseline_candidate_audit_candidate_count", 0),
        "parse_only_candidate_names": list(closure.get("baseline_candidate_audit_parse_only_candidate_names", [])),
        "rejected_candidate_names": list(closure.get("baseline_candidate_audit_rejected_candidate_names", [])),
        "closure_blocker": closure.get("baseline_candidate_audit_closure_blocker", ""),
    }
    payload["source_artifact_hashes"] = {
        "full_eval_results": _artifact_sha256("artifacts/generated/full_eval_results.json"),
        "aggregate_results": _artifact_sha256("artifacts/generated/aggregate_results.json"),
        "public_full_eval_results": _artifact_sha256("artifacts/generated/full_eval_results.public.json"),
    }
    loader_scopes = {str(item.get("loader_execution_scope", "")) for item in payload["benchmark_integrations"]}
    payload["benchmark_loader_execution_scope"] = "full" if loader_scopes == {"full"} else "mixed"
    payload["benchmark_loader_status"] = [
        {
            "benchmark": item["benchmark"],
            "loaded_tasks": item["loaded_tasks"],
            "segment_run_capable": _segment_capable(item),
            "full_run_capable": _full_capable(item),
            "runnable_status": item["runnable_status"],
            "loader_execution_scope": item.get("loader_execution_scope", ""),
            "task_limit": item.get("task_limit", ""),
        }
        for item in payload["benchmark_integrations"]
    ]
    payload["claim_boundary"] = CLAIM_BOUNDARY
    payload["canonical_source_run_id"] = str(closure.get("canonical_source_run_id", "")).strip()
    payload["first_failing_gate"] = _first_failing_gate(closure)
    payload["review_ready"] = bool(closure.get("canonical_full_evidence_ready", False))
    payload["experiment_entry_allowed"] = bool(closure.get("canonical_full_evidence_ready", False))
    payload["closure_blockers"] = list(closure.get("canonical_full_evidence_blockers", []))
    _write_snapshot_artifacts(payload, closure=closure)
    print(json.dumps(_sanitize_snapshot_payload(payload), indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
