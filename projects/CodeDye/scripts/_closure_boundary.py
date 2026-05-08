from __future__ import annotations

import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from aggregate_results import (
    _baseline_admission_verification_complete,
    _baseline_candidate_audit_complete,
    _sample_selection_audit_matches_current_full_eval,
)
from codedye.canaries import summarize_local_benchmark_inventory
from integrations.baseline_adapters import describe_baselines
from integrations.benchmark_adapters import describe_benchmark_loaders


def _read_json(path: Path) -> dict[str, object]:
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


REQUIRED_CANONICAL_RECORD_FIELDS = (
    "admissible_output_visible_canary_evidence_count",
    "diagnostic_evidence_count",
    "hidden_test_family_diagnostic_only",
)
CURRENT_SAMPLE_SELECTION_STATUSES = {
    "pre_registered_utility_selection",
    "utility_preselection_no_contamination_winner_selection",
}
DOWNGRADABLE_BASELINE_BLOCKERS = {
    "official_main_table_runnable_baseline_missing",
    "baseline_admission_official_gate_missing",
    "baseline_admission_official_gate_not_passed",
    "baseline_candidate_audit_official_blocker_preserved",
    "comparator_controls_ready_official_baseline_missing",
    "main_table_baseline_or_comparator_control_missing",
    "official_baseline_gate_not_cleared",
    "main_table_baseline_count_zero",
}


def _canonical_record_schema_state(full_eval: dict[str, object]) -> tuple[bool, list[str]]:
    records = full_eval.get("records", [])
    if not isinstance(records, list) or not records:
        return False, []
    missing_fields: set[str] = set()
    for item in records:
        if not isinstance(item, dict):
            continue
        for field in REQUIRED_CANONICAL_RECORD_FIELDS:
            if field not in item:
                missing_fields.add(field)
    return bool(missing_fields), sorted(missing_fields)


def _utility_first_promotion_state(root: Path) -> dict[str, object]:
    gate = _read_json(root / "artifacts" / "generated" / "utility_first_promotion_gate.json")
    baseline_gate = gate.get("baseline_downgrade_gate", {})
    baseline_gate = baseline_gate if isinstance(baseline_gate, dict) else {}
    official_baseline_admitted = bool(baseline_gate.get("official_baseline_admitted")) or (
        bool(baseline_gate.get("official_baseline_gate_pass"))
        and _safe_int(baseline_gate.get("official_runnable_baseline_count"), 0) > 0
    )
    promotion_allowed = (
        bool(gate.get("main_claim_admission_allowed"))
        and bool(gate.get("canonical_promotion_allowed"))
        and bool(gate.get("review_ready_claim_allowed"))
        and bool(baseline_gate.get("gate_pass"))
        and official_baseline_admitted
    )
    return {
        "gate_present": bool(gate),
        "promotion_allowed": promotion_allowed,
        "claim_boundary": str(gate.get("claim_boundary", "")),
        "main_claim_admission_allowed": bool(gate.get("main_claim_admission_allowed")),
        "canonical_promotion_allowed": bool(gate.get("canonical_promotion_allowed")),
        "review_ready_claim_allowed": bool(gate.get("review_ready_claim_allowed")),
        "honest_comparator_downgrade_allowed": bool(baseline_gate.get("honest_comparator_downgrade_allowed")),
        "official_baseline_admitted": official_baseline_admitted,
        "comparator_downgrade_policy": "disabled_comparators_are_support_controls_only",
        "main_table_policy_after_downgrade": str(baseline_gate.get("main_table_policy_after_downgrade", "")),
        "blockers": list(gate.get("blockers", [])) if isinstance(gate.get("blockers", []), list) else [],
    }


def _is_downgradable_baseline_blocker(blocker: str) -> bool:
    value = str(blocker).strip()
    if value in DOWNGRADABLE_BASELINE_BLOCKERS:
        return True
    if value.startswith("first_failing_gate:"):
        return value.split(":", 1)[1] in DOWNGRADABLE_BASELINE_BLOCKERS
    return False


def _apply_utility_first_downgrade(blockers: list[str], utility_state: dict[str, object]) -> tuple[list[str], list[str]]:
    if not bool(utility_state.get("promotion_allowed")):
        return blockers, []
    remaining: list[str] = []
    downgraded: list[str] = []
    for blocker in blockers:
        if _is_downgradable_baseline_blocker(blocker):
            downgraded.append(blocker)
        else:
            remaining.append(blocker)
    return list(dict.fromkeys(remaining)), list(dict.fromkeys(downgraded))


def _best_paper_cycle_gate(root: Path, *, project: str) -> dict[str, object]:
    ledger_path = root.parent / "best_paper_100_cycle_ledger.json"
    ledger = _read_json(ledger_path)
    if not ledger:
        return {
            "gate_present": False,
            "deepseek_formal_run_allowed": False,
            "blockers": [f"best_paper_cycle_ledger_missing:{project}"],
        }
    policy = ledger.get("cycle_policy", {})
    policy = policy if isinstance(policy, dict) else {}
    projects = ledger.get("projects", {})
    project_state = projects.get(project, {}) if isinstance(projects, dict) else {}
    project_state = project_state if isinstance(project_state, dict) else {}
    min_cycles = _safe_int(policy.get("minimum_total_cycles_before_deepseek_claim_run"), 100)
    clean_required = _safe_int(policy.get("required_consecutive_clean_reviews"), 10)
    cycles = _safe_int(project_state.get("total_review_improvement_cycles_completed"), 0)
    clean = _safe_int(project_state.get("consecutive_clean_reviews"), 0)
    project_allowed = bool(project_state.get("deepseek_formal_run_allowed"))
    allowed = project_allowed and cycles >= min_cycles and clean >= clean_required
    blockers: list[str] = []
    if not allowed:
        blockers.append(f"best_paper_cycle_gate_pending:{project}:{cycles}/{min_cycles}_cycles:{clean}/{clean_required}_clean")
        first = str(project_state.get("first_p1_p2", "")).strip()
        if first:
            blockers.append(f"best_paper_cycle_first_p1_p2:{first}")
    return {
        "gate_present": True,
        "deepseek_formal_run_allowed": allowed,
        "total_review_improvement_cycles_completed": cycles,
        "minimum_total_cycles_before_deepseek_claim_run": min_cycles,
        "consecutive_clean_reviews": clean,
        "required_consecutive_clean_reviews": clean_required,
        "p1_p2_count": _safe_int(project_state.get("p1_p2_count"), 0),
        "first_p1_p2": str(project_state.get("first_p1_p2", "")),
        "blockers": blockers,
    }


def load_closure_boundary(*, root: Path = ROOT) -> dict[str, object]:
    aggregate_path = root / "artifacts" / "generated" / "aggregate_results.json"
    full_eval_path = root / "artifacts" / "generated" / "full_eval_results.json"
    iteration_ledger_path = root / "artifacts" / "generated" / "no_overfit_iteration_ledger.json"
    final_ledger_path = root / "artifacts" / "generated" / "final_no_overfit_ledger.json"
    aggregate = _read_json(aggregate_path)
    full_eval = _read_json(full_eval_path)
    iteration_ledger = _read_json(iteration_ledger_path)
    final_ledger = _read_json(final_ledger_path)
    baseline_audit = _read_json(root / "artifacts" / "generated" / "baseline_candidate_audit.json")
    baseline_admission = _read_json(root / "artifacts" / "generated" / "baseline_admission_verification.json")
    sample_selection_audit = _read_json(root / "artifacts" / "generated" / "sample_selection_rerun_audit.json")
    canonical_sync_gate = _read_json(root / "artifacts" / "generated" / "canonical_evidence_sync_gate.json")
    curation_audit = _read_json(root / "artifacts" / "generated" / "codedyebench_curation_audit.json")
    operator_state = full_eval.get("operator_state", {})
    operator_state = dict(operator_state) if isinstance(operator_state, dict) else {}
    canonical_source_run_id = str(operator_state.get("canonical_source_run_id", operator_state.get("run_id", ""))).strip()
    source_full_eval_sha256 = hashlib.sha256(full_eval_path.read_bytes()).hexdigest() if full_eval_path.exists() else ""
    local_inventory = summarize_local_benchmark_inventory(root)
    benchmark_spec = _read_json(root / "benchmarks" / "code_dyebench_spec.json")
    benchmark_integrations = describe_benchmark_loaders(root, limit=None)
    baseline_integrations = describe_baselines(root)
    utility_first_promotion = _utility_first_promotion_state(root)
    best_paper_cycle_gate = _best_paper_cycle_gate(root, project="CodeDye")

    target_local = _safe_int(benchmark_spec.get("local_task_count_target"), 0)
    ready_local = _safe_int(local_inventory.get("ready_task_count"), 0)
    pending_local = _safe_int(local_inventory.get("pending_user_review_count"), 0)
    provider_live_record_count = _safe_int(aggregate.get("provider_live_record_count"), 0)
    local_reviewed_task_record_count = _safe_int(aggregate.get("local_reviewed_task_record_count"), 0)
    public_task_count = _safe_int(aggregate.get("public_benchmark_task_count"), 0)
    public_record_count = _safe_int(aggregate.get("public_benchmark_record_count"), 0)
    public_contamination_record_count = _safe_int(aggregate.get("public_benchmark_contamination_record_count"), 0)
    public_full = bool(full_eval.get("public_benchmark_full_sweep_completed", False))
    artifact_role = str(operator_state.get("artifact_role", "")).strip() or "canonical_local_seed_eval"
    canonical_provider_name = str(operator_state.get("provider_name", "")).strip().lower()
    executed_public_benchmarks = sorted(
        {
            str(item.get("benchmark", ""))
            for item in full_eval.get("records", [])
            if str(item.get("task_source", item.get("source", ""))) == "external_checkout"
        }
    )
    expected_public_task_count = sum(
        _safe_int(item.get("loaded_tasks"), 0)
        for item in benchmark_integrations
        if bool(item.get("full_run_capable", False))
    )
    expected_public_benchmark_names = {
        str(item.get("benchmark", ""))
        for item in benchmark_integrations
        if bool(item.get("full_run_capable", False))
    }
    baseline_unresolved_count = sum(1 for item in baseline_integrations if not bool(item.get("promotion_resolved", False)))
    runnable_baseline_or_comparator_count = sum(1 for item in baseline_integrations if bool(item.get("runnable", False)))
    official_runnable_baseline_count = sum(
        1
        for item in baseline_integrations
        if bool(item.get("runnable", False))
        and bool(item.get("official_baseline", item.get("official_main_table_baseline", False)))
    )
    runnable_baseline_count = official_runnable_baseline_count
    main_table_comparator_control_count = sum(
        1
        for item in baseline_integrations
        if bool(item.get("runnable", False)) and bool(item.get("main_table_comparator_control", False))
    )
    parse_only_baseline_count = sum(1 for item in baseline_integrations if str(item.get("runnable_status", "")) == "parse_only")
    required_pass_target = _safe_int(iteration_ledger.get("required_pass_target"), 20)
    recorded_pass_count = _safe_int(iteration_ledger.get("recorded_pass_count"), 0)
    zero_mod_validation_target = _safe_int(iteration_ledger.get("zero_mod_validation_target"), 10)
    zero_mod_validation_pass_count = _safe_int(iteration_ledger.get("zero_mod_validation_pass_count"), 0)
    zero_mod_validation_complete = bool(iteration_ledger.get("zero_mod_validation_complete", False)) and zero_mod_validation_pass_count >= zero_mod_validation_target
    final_open_blockers = final_ledger.get("open_blockers", [])
    final_open_blockers = tuple(str(item) for item in final_open_blockers) if isinstance(final_open_blockers, list) else ()
    final_status = str(final_ledger.get("status", ""))
    no_overfit_iteration_ledger_exists = iteration_ledger_path.exists()
    final_ledger_exists = final_ledger_path.exists()
    no_overfit_ledger_complete = bool(no_overfit_iteration_ledger_exists) and bool(final_ledger_exists) and recorded_pass_count >= required_pass_target and zero_mod_validation_complete and "not_yet_complete" not in final_status and "20-pass ledger not complete" not in final_open_blockers
    baseline_audit_entries = baseline_audit.get("candidates", []) if isinstance(baseline_audit.get("candidates", []), list) else []
    baseline_candidate_audit_complete = _baseline_candidate_audit_complete(baseline_audit, minimum_entries=10)
    baseline_candidate_audit_schema_version = str(baseline_audit.get("schema_version", "")).strip()
    baseline_candidate_audit_candidate_count = _safe_int(
        baseline_audit.get("official_candidate_count", baseline_audit.get("candidate_count", 0)),
        0,
    )
    baseline_candidate_audit_parse_only_candidate_names = [
        str(item)
        for item in baseline_audit.get("parse_only_candidate_names", [])
        if str(item).strip()
    ] if isinstance(baseline_audit.get("parse_only_candidate_names", []), list) else []
    baseline_candidate_audit_rejected_candidate_names = [
        str(item)
        for item in baseline_audit.get("rejected_candidate_names", [])
        if str(item).strip()
    ] if isinstance(baseline_audit.get("rejected_candidate_names", []), list) else []
    baseline_candidate_audit_closure_blocker = str(baseline_audit.get("closure_blocker", "")).strip()
    baseline_admission_verification_complete = _baseline_admission_verification_complete(baseline_admission, baseline_integrations)
    curation_audit_complete = bool(curation_audit.get("machine_verifiable", False)) and bool(curation_audit.get("benchmark", ""))
    positive_control_composite_validity_pass = bool(aggregate.get("positive_control_composite_validity_pass", False))
    sample_selection_rerun_audit_complete = _sample_selection_audit_matches_current_full_eval(
        sample_selection_audit,
        source_full_eval_sha256=source_full_eval_sha256,
        canonical_source_run_id=canonical_source_run_id,
    )
    sample_selection_current = str(sample_selection_audit.get("current_canonical_status", "")).strip() if sample_selection_rerun_audit_complete else ""
    if not sample_selection_current:
        sample_selection_current = str(aggregate.get("sample_selection_policy", {}).get("current_canonical_status", "legacy_or_unknown")) if isinstance(aggregate.get("sample_selection_policy", {}), dict) else "legacy_or_unknown"
    sample_selection_rerun_required = bool(
        sample_selection_audit.get("rerun_required", sample_selection_current not in CURRENT_SAMPLE_SELECTION_STATUSES)
        if sample_selection_rerun_audit_complete
        else True
    )
    sample_selection_rerun_required_reason = (
        str(sample_selection_audit.get("rerun_required_reason", "")).strip()
        if sample_selection_rerun_audit_complete
        else "sample_selection_rerun_audit_stale_relative_to_current_canonical_full_eval"
    )
    sample_selection_utility_mismatch_count = (
        _safe_int(sample_selection_audit.get("utility_selection_mismatch_record_count"), 0)
        if sample_selection_rerun_audit_complete
        else 0
    )
    canonical_record_schema_stale, canonical_record_schema_missing_fields = _canonical_record_schema_state(full_eval)
    frozen_family_complete = local_inventory.get("frozen_family_complete", {})
    frozen_family_complete = frozen_family_complete if isinstance(frozen_family_complete, dict) else {}

    blockers: list[str] = []
    if target_local <= 0:
        blockers.append("codedyebench_target_missing")
    if ready_local < target_local:
        blockers.append("codedyebench_ready_task_coverage_incomplete")
    if pending_local > 0:
        blockers.append("codedyebench_pending_user_review_remaining")
    if frozen_family_complete and not all(bool(value) for value in frozen_family_complete.values()):
        blockers.append("codedyebench_frozen_family_matrix_incomplete")
    if local_reviewed_task_record_count < ready_local:
        blockers.append("codedyebench_local_reviewed_record_coverage_incomplete")
    if provider_live_record_count <= 0:
        blockers.append("deepseek_live_canonical_evidence_missing")
    if canonical_provider_name and canonical_provider_name != "deepseek":
        blockers.append("canonical_live_provider_not_deepseek")
    if not public_full:
        blockers.append("public_benchmark_full_sweep_not_materialized")
    if expected_public_task_count > 0 and public_task_count < expected_public_task_count:
        blockers.append("public_benchmark_task_coverage_incomplete")
    if public_record_count < public_task_count:
        blockers.append("public_benchmark_record_materialization_incomplete")
    if expected_public_benchmark_names and set(executed_public_benchmarks) != expected_public_benchmark_names:
        blockers.append("public_benchmark_identity_coverage_incomplete")
    if public_contamination_record_count > 0:
        blockers.append("public_benchmark_contamination_leakage")
    if baseline_unresolved_count > 0:
        blockers.append("official_baseline_truth_unresolved")
    if official_runnable_baseline_count <= 0 and not bool(utility_first_promotion.get("promotion_allowed")):
        blockers.append("official_main_table_runnable_baseline_missing")
    if canonical_record_schema_stale:
        blockers.append("canonical_record_schema_stale")
    if not baseline_candidate_audit_complete:
        blockers.append("baseline_candidate_audit_incomplete")
    if not baseline_admission_verification_complete:
        blockers.append("baseline_admission_verification_missing")
    if not curation_audit_complete:
        blockers.append("codedyebench_curation_audit_missing")
    if not positive_control_composite_validity_pass:
        blockers.append("positive_control_calibration_incomplete")
    if sample_selection_audit and not sample_selection_rerun_audit_complete:
        blockers.append("sample_selection_rerun_audit_stale")
    if sample_selection_current not in CURRENT_SAMPLE_SELECTION_STATUSES and sample_selection_rerun_required:
        blockers.append("legacy_sample_selection_requires_rerun")
    if not no_overfit_ledger_complete:
        blockers.append("no_overfit_ledger_incomplete")
    if not zero_mod_validation_complete:
        blockers.append("zero_mod_validation_incomplete")
    if artifact_role != "canonical_live_eval":
        blockers.append("canonical_live_finalize_pending")
    if artifact_role == "canonical_live_eval" and not str(operator_state.get("canonical_source_run_id", "")).strip():
        blockers.append("canonical_source_run_id_missing")
    aggregate_blockers = [
        str(item)
        for item in aggregate.get("closure_blockers", [])
        if str(item).strip()
    ] if isinstance(aggregate.get("closure_blockers", []), list) else []
    if aggregate_blockers:
        blockers = list(dict.fromkeys(aggregate_blockers + blockers))
    blockers, downgraded_baseline_blockers = _apply_utility_first_downgrade(blockers, utility_first_promotion)
    aggregate_review_ready = aggregate.get("review_ready")
    if aggregate_review_ready is False and not bool(utility_first_promotion.get("promotion_allowed")) and "aggregate_review_ready_false" not in blockers:
        blockers.append("aggregate_review_ready_false")
    for blocker in best_paper_cycle_gate.get("blockers", []):
        if str(blocker).strip() and str(blocker) not in blockers:
            blockers.append(str(blocker))
    if canonical_sync_gate:
        if not bool(canonical_sync_gate.get("sync_gate_pass", False)):
            blockers.append("canonical_evidence_sync_gate_blocked")
            blockers.extend(f"canonical_evidence_sync_gate:{item}" for item in canonical_sync_gate.get("blockers", []) if str(item).strip())
    else:
        blockers.append("canonical_evidence_sync_gate_missing")
    blockers = list(dict.fromkeys(blockers))

    return {
        "aggregate_path": aggregate_path.relative_to(root).as_posix(),
        "full_eval_path": full_eval_path.relative_to(root).as_posix(),
        "source_full_eval_sha256": source_full_eval_sha256,
        "current_full_eval_artifact_role": artifact_role,
        "canonical_source_run_id": canonical_source_run_id,
        "canonical_full_evidence_ready": not blockers and (aggregate_review_ready is not False or bool(utility_first_promotion.get("promotion_allowed"))),
        "canonical_full_evidence_blockers": blockers,
        "utility_first_promotion": utility_first_promotion,
        "best_paper_cycle_gate": best_paper_cycle_gate,
        "canonical_evidence_sync_gate": canonical_sync_gate,
        "baseline_blockers_downgraded_to_limitation": downgraded_baseline_blockers,
        "local_ready_task_count": ready_local,
        "local_task_count_target": target_local,
        "local_pending_user_review_count": pending_local,
        "provider_live_record_count": provider_live_record_count,
        "local_reviewed_task_record_count": local_reviewed_task_record_count,
        "public_benchmark_task_count": public_task_count,
        "public_benchmark_record_count": public_record_count,
        "public_benchmark_contamination_record_count": public_contamination_record_count,
        "public_benchmark_expected_task_count": expected_public_task_count,
        "public_benchmark_expected_benchmarks": sorted(expected_public_benchmark_names),
        "public_benchmark_full_sweep_completed": public_full,
        "canonical_provider_name": canonical_provider_name,
        "baseline_unresolved_count": baseline_unresolved_count,
        "runnable_baseline_count": runnable_baseline_count,
        "runnable_baseline_or_comparator_count": runnable_baseline_or_comparator_count,
        "official_runnable_baseline_count": official_runnable_baseline_count,
        "main_table_comparator_control_count": main_table_comparator_control_count,
        "parse_only_baseline_count": parse_only_baseline_count,
        "baseline_candidate_audit_complete": baseline_candidate_audit_complete,
        "baseline_candidate_audit_schema_version": baseline_candidate_audit_schema_version,
        "baseline_candidate_audit_candidate_count": baseline_candidate_audit_candidate_count,
        "baseline_candidate_audit_parse_only_candidate_names": baseline_candidate_audit_parse_only_candidate_names,
        "baseline_candidate_audit_rejected_candidate_names": baseline_candidate_audit_rejected_candidate_names,
        "baseline_candidate_audit_closure_blocker": baseline_candidate_audit_closure_blocker,
        "baseline_admission_verification_complete": baseline_admission_verification_complete,
        "baseline_admission_gate_pass": bool(baseline_admission.get("baseline_gate_pass", False)),
        "official_baseline_gate_pass": bool(baseline_admission.get("official_baseline_gate_pass", False)),
        "comparator_control_gate_pass": bool(baseline_admission.get("comparator_control_gate_pass", False)),
        "codedyebench_curation_audit_complete": curation_audit_complete,
        "positive_control_composite_validity_pass": positive_control_composite_validity_pass,
        "sample_selection_current": sample_selection_current,
        "sample_selection_rerun_audit_complete": sample_selection_rerun_audit_complete,
        "sample_selection_rerun_required": sample_selection_rerun_required,
        "sample_selection_rerun_required_reason": sample_selection_rerun_required_reason,
        "sample_selection_utility_mismatch_count": sample_selection_utility_mismatch_count,
        "canonical_record_schema_stale": canonical_record_schema_stale,
        "canonical_record_schema_required_fields": list(REQUIRED_CANONICAL_RECORD_FIELDS),
        "canonical_record_schema_missing_fields": canonical_record_schema_missing_fields,
        "no_overfit_iteration_ledger_exists": no_overfit_iteration_ledger_exists,
        "no_overfit_recorded_pass_count": recorded_pass_count,
        "no_overfit_required_pass_target": required_pass_target,
        "no_overfit_ledger_complete": no_overfit_ledger_complete,
        "zero_mod_validation_target": zero_mod_validation_target,
        "zero_mod_validation_pass_count": zero_mod_validation_pass_count,
        "zero_mod_validation_complete": zero_mod_validation_complete,
        "frozen_family_complete": frozen_family_complete,
        "executed_public_benchmarks": executed_public_benchmarks,
    }
