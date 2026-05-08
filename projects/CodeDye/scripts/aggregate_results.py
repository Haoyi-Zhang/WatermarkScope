from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from statistics import mean, median

from _bootstrap import ARTIFACTS


def _average(records: list[dict[str, object]], key: str) -> float:
    values = [float(item[key]) for item in records if key in item and item.get(key) is not None and str(item.get(key)).strip() != ""]
    return round(mean(values), 4) if values else 0.0


def _average_or_none(records: list[dict[str, object]], key: str) -> float | None:
    values = [float(item[key]) for item in records if key in item and item.get(key) is not None and str(item.get(key)).strip() != ""]
    return round(mean(values), 4) if values else None


def _median_or_default(values: list[float], default: float) -> float:
    return round(median(values), 4) if values else default


def _record_status(item: dict[str, object], key: str) -> str:
    if key in item:
        return str(item.get(key, ""))
    return str(item.get("scoring_status", "scored"))


def _utility_scored(item: dict[str, object]) -> bool:
    return _record_status(item, "utility_scoring_status") == "scored"


def _contamination_scored(item: dict[str, object]) -> bool:
    return _record_status(item, "contamination_scoring_status") == "scored"


REQUIRED_CANONICAL_RECORD_FIELDS = (
    "admissible_output_visible_canary_evidence_count",
    "diagnostic_evidence_count",
    "hidden_test_family_diagnostic_only",
)
CURRENT_SAMPLE_SELECTION_STATUSES = {
    "pre_registered_utility_selection",
    "utility_preselection_no_contamination_winner_selection",
}


def _record_schema_missing_fields(records: list[dict[str, object]]) -> list[str]:
    if not records:
        return ["missing_or_empty_canonical_records"]
    missing: set[str] = set()
    for item in records:
        for field in REQUIRED_CANONICAL_RECORD_FIELDS:
            if field not in item:
                missing.add(field)
        for issue in _trace_schema_issues(item):
            missing.add(issue)
    return sorted(missing)


def _require_current_record_schema(records: list[dict[str, object]], *, label: str) -> None:
    missing = _record_schema_missing_fields(records)
    if missing:
        fields = ", ".join(missing)
        raise ValueError(f"{label} records missing required contamination schema fields: {fields}")


def _counter(records: list[dict[str, object]], key: str, fallback_key: str = "") -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in records:
        value = str(item.get(key, item.get(fallback_key, "")))
        if value:
            counts[value] = counts.get(value, 0) + 1
    return counts


def _mean_boolean(records: list[dict[str, object]], predicate) -> float:
    return round(mean(1.0 if predicate(item) else 0.0 for item in records), 4) if records else 0.0


def _trace_contains(item: dict[str, object], prefix: str) -> bool:
    return any(str(entry).startswith(prefix) for entry in item.get("evidence_trace", []))


def _score_present(item: dict[str, object], key: str) -> bool:
    value = item.get(key)
    return value is not None and str(value).strip() != ""


def _null_pool_tier(item: dict[str, object]) -> int:
    value = item.get("null_pool_tier")
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    strategy = str(item.get("null_pool_strategy", ""))
    match = re.search(r"tier_(\d+)_of_", strategy)
    return int(match.group(1)) if match else 0


def _rate_interval(successes: int, total: int) -> dict[str, object]:
    if total <= 0:
        return {"successes": 0, "total": 0, "rate": 0.0, "wilson_95": [0.0, 0.0]}
    z = 1.96
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) / denom
    return {
        "successes": successes,
        "total": total,
        "rate": round(p, 4),
        "wilson_95": [round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)],
    }


def _trace_schema_issues(item: dict[str, object]) -> list[str]:
    trace = [str(entry) for entry in item.get("evidence_trace", [])]
    issues: list[str] = []
    if any("direct_canary_rule:requires_direct_output_visible_or_hidden_canary" in entry for entry in trace):
        issues.append("stale_direct_canary_rule_trace")
    if not any(entry.startswith("headline_evidence_rule:") for entry in trace):
        issues.append("missing_headline_evidence_rule_trace")
    if not any(entry.startswith("hidden_test_family_rule:") for entry in trace):
        issues.append("missing_hidden_test_family_rule_trace")
    return issues


def _audit_complete(path, *, minimum_entries: int = 1) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    entries = payload.get("candidates", payload.get("findings", []))
    if not isinstance(entries, list) or len(entries) < minimum_entries:
        return False
    return bool(payload.get("machine_verifiable", False))


def _baseline_candidate_audit_complete(payload: dict[str, object], *, minimum_entries: int = 10) -> bool:
    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list) or len(candidates) < minimum_entries:
        return False
    if not bool(payload.get("machine_verifiable", False)):
        return False
    if not str(payload.get("schema_version", "")).strip():
        return False
    declared_count = int(payload.get("official_candidate_count", payload.get("candidate_count", 0)) or 0)
    if declared_count != len(candidates):
        return False
    observed_parse_only = sorted(
        str(item.get("candidate_name", "")).strip()
        for item in candidates
        if str(item.get("decision", "")).strip() == "parse_only_reference"
    )
    declared_parse_only = sorted(
        str(item).strip()
        for item in payload.get("parse_only_candidate_names", [])
        if str(item).strip()
    ) if isinstance(payload.get("parse_only_candidate_names", []), list) else []
    if observed_parse_only != declared_parse_only:
        return False
    return True


def _baseline_admission_verification_complete(payload: dict[str, object], baselines: list[dict[str, object]]) -> bool:
    if not str(payload.get("schema_version", "")).strip():
        return False
    official_runnable_names = sorted(
        str(item.get("name", "")).strip()
        for item in baselines
        if bool(item.get("runnable", False))
        and bool(item.get("official_baseline", item.get("official_main_table_baseline", False)))
        and str(item.get("name", "")).strip()
    )
    parse_only_names = sorted(
        str(item.get("name", "")).strip()
        for item in baselines
        if str(item.get("runnable_status", "")).strip() == "parse_only" and str(item.get("name", "")).strip()
    )
    declared_official_runnable = sorted(
        str(item).strip()
        for item in payload.get("official_runnable_baselines", [])
        if str(item).strip()
    ) if isinstance(payload.get("official_runnable_baselines", []), list) else []
    declared_parse_only = sorted(
        str(item).strip()
        for item in payload.get("parse_only_baselines", [])
        if str(item).strip()
    ) if isinstance(payload.get("parse_only_baselines", []), list) else []
    issues = payload.get("issues", [])
    issue_free = isinstance(issues, list) and not issues
    official_count = int(payload.get("official_runnable_baseline_count", -1))
    return (
        issue_free
        and official_count == len(official_runnable_names)
        and int(payload.get("parse_only_baseline_count", -1)) == len(parse_only_names)
        and declared_official_runnable == official_runnable_names
        and declared_parse_only == parse_only_names
        and bool(payload.get("no_parse_only_main_table_promotion", False))
        and bool(payload.get("baseline_gate_pass", False)) == bool(payload.get("official_baseline_gate_pass", False))
    )


def _honest_comparator_downgrade_allowed(payload: dict[str, object]) -> bool:
    """Comparators are support controls, never a substitute for official baselines."""

    return False


def _sample_selection_audit_matches_current_full_eval(
    audit: dict[str, object],
    *,
    source_full_eval_sha256: str,
    canonical_source_run_id: str,
) -> bool:
    if not str(audit.get("schema_version", "")).strip():
        return False
    if str(audit.get("source_full_eval_sha256", "")).strip() != source_full_eval_sha256:
        return False
    audit_run_id = str(audit.get("canonical_source_run_id", "")).strip()
    if canonical_source_run_id and audit_run_id != canonical_source_run_id:
        return False
    return True


def _evidence_stage(item: dict[str, object]) -> int:
    value = item.get("evidence_stage")
    if value is not None:
        try:
            return max(0, min(4, int(value)))
        except (TypeError, ValueError):
            pass
    for entry in item.get("evidence_trace", []):
        match = re.match(r"^evidence_stage:(\d+)/4$", str(entry))
        if match:
            return max(0, min(4, int(match.group(1))))
    return 0


def main() -> None:
    full_eval_path = ARTIFACTS / "full_eval_results.json"
    full_eval_bytes = full_eval_path.read_bytes()
    source_full_eval_sha256 = hashlib.sha256(full_eval_bytes).hexdigest()
    payload = json.loads(full_eval_bytes.decode("utf-8"))
    records = payload["records"]
    baselines = payload.get("baselines", [])
    baseline_records = payload.get("baseline_records", [])
    baseline_records = baseline_records if isinstance(baseline_records, list) else []
    iteration_ledger_path = ARTIFACTS / "no_overfit_iteration_ledger.json"
    final_ledger_path = ARTIFACTS / "final_no_overfit_ledger.json"
    iteration_ledger = json.loads(iteration_ledger_path.read_text(encoding="utf-8")) if iteration_ledger_path.exists() else {}
    final_ledger = json.loads(final_ledger_path.read_text(encoding="utf-8")) if final_ledger_path.exists() else {}
    positive_path = ARTIFACTS / "positive_control_contamination_result.json"
    positive = json.loads(positive_path.read_text(encoding="utf-8")) if positive_path.exists() else {}
    baseline_candidate_audit_path = ARTIFACTS / "baseline_candidate_audit.json"
    baseline_candidate_audit = json.loads(baseline_candidate_audit_path.read_text(encoding="utf-8")) if baseline_candidate_audit_path.exists() else {}
    baseline_admission_path = ARTIFACTS / "baseline_admission_verification.json"
    baseline_admission = json.loads(baseline_admission_path.read_text(encoding="utf-8")) if baseline_admission_path.exists() else {}
    baseline_downgrade_path = ARTIFACTS / "baseline_downgrade_decision.json"
    baseline_downgrade = json.loads(baseline_downgrade_path.read_text(encoding="utf-8")) if baseline_downgrade_path.exists() else {}
    canonical_sync_path = ARTIFACTS / "canonical_evidence_sync_gate.json"
    canonical_sync_gate = json.loads(canonical_sync_path.read_text(encoding="utf-8")) if canonical_sync_path.exists() else {}
    canonical_sync_baseline_boundary = dict(canonical_sync_gate.get("baseline_control_boundary", {})) if isinstance(canonical_sync_gate.get("baseline_control_boundary", {}), dict) else {}
    official_baseline_provenance_path = ARTIFACTS / "official_baseline_provenance_gate.json"
    official_baseline_provenance_gate = (
        json.loads(official_baseline_provenance_path.read_text(encoding="utf-8"))
        if official_baseline_provenance_path.exists()
        else {}
    )
    attack_ci_path = ARTIFACTS / "attack_matrix_null_calibration_ci.json"
    attack_ci_gate = json.loads(attack_ci_path.read_text(encoding="utf-8")) if attack_ci_path.exists() else {}
    attack_live_support_path = ARTIFACTS / "attack_live_support_gate.json"
    attack_live_support_gate = json.loads(attack_live_support_path.read_text(encoding="utf-8")) if attack_live_support_path.exists() else {}
    sample_selection_audit_path = ARTIFACTS / "sample_selection_rerun_audit.json"
    sample_selection_audit = json.loads(sample_selection_audit_path.read_text(encoding="utf-8")) if sample_selection_audit_path.exists() else {}
    baseline_scope_decision_path = ARTIFACTS / "baseline_scope_decision.json"
    baseline_scope_decision = json.loads(baseline_scope_decision_path.read_text(encoding="utf-8")) if baseline_scope_decision_path.exists() else {}
    operator_state = payload.get("operator_state", {})
    operator_state = dict(operator_state) if isinstance(operator_state, dict) else {}
    canonical_source_run_id = str(operator_state.get("canonical_source_run_id", operator_state.get("run_id", ""))).strip()
    baseline_audit_complete = _baseline_candidate_audit_complete(baseline_candidate_audit, minimum_entries=10)
    curation_audit_complete = _audit_complete(ARTIFACTS / "codedyebench_curation_audit.json", minimum_entries=1)
    contamination_records = [item for item in records if _contamination_scored(item)]
    utility_records = [item for item in records if _utility_scored(item)]
    open_weight_records = list(payload.get("open_weight_diagnostic_records", [])) if isinstance(payload.get("open_weight_diagnostic_records", []), list) else []
    _require_current_record_schema(contamination_records, label="canonical contamination")
    _require_current_record_schema([item for item in open_weight_records if isinstance(item, dict)], label="open-weight diagnostic")
    public_utility_records = [
        item
        for item in utility_records
        if str(item.get("task_source", item.get("source", ""))) == "external_checkout"
    ]
    benchmark_counts = _counter(contamination_records, "benchmark")
    task_source_counts = _counter(contamination_records, "task_source", "source")
    utility_benchmark_counts = _counter(utility_records, "benchmark")
    utility_task_source_counts = _counter(utility_records, "task_source", "source")
    false_positive_bounds = [float(item.get("false_positive_bound", 1.0)) for item in contamination_records]
    empirical_p_values = [float(item.get("p_value_or_score", 1.0)) for item in contamination_records]
    familywise_adjusted_p_values = [float(item.get("familywise_adjusted_p_value", item.get("false_positive_bound", 1.0))) for item in contamination_records]
    null_sample_sizes = [int(item.get("null_sample_size", 0)) for item in contamination_records]
    familywise_test_counts = [int(item.get("familywise_test_count", 0)) for item in contamination_records]
    local_reviewed_task_ids = {
        str(item.get("task_id", ""))
        for item in contamination_records
        if str(item.get("task_source", item.get("source", ""))) != "external_checkout"
        and str(item.get("review_status", "")) == "ready"
        and str(item.get("task_id", "")).strip()
    }
    public_utility_status = (
        "not_run"
        if not public_utility_records
        else "support_only_materialized"
        if bool(payload.get("public_benchmark_full_sweep_completed", False))
        else "support_only_segmented"
    )
    canonical_record_schema_missing_fields = _record_schema_missing_fields(contamination_records)
    canonical_record_schema_stale = bool(canonical_record_schema_missing_fields)
    runnable_integration_count = sum(1 for item in baselines if bool(item.get("runnable", False)))
    official_runnable_baseline_count = sum(
        1
        for item in baselines
        if bool(item.get("runnable", False)) and bool(item.get("official_baseline", item.get("official_main_table_baseline", False)))
    )
    main_table_comparator_control_count = sum(
        1
        for item in baselines
        if bool(item.get("runnable", False)) and bool(item.get("main_table_comparator_control", False))
    )
    main_table_comparator_control_record_count = sum(
        1
        for item in baseline_records
        if isinstance(item, dict) and bool(item.get("main_table_comparator_control", False))
    )
    official_baseline_gate_pass = official_runnable_baseline_count > 0
    baseline_or_comparator_gate_pass = official_baseline_gate_pass
    official_record_backed_baseline_count = (
        official_runnable_baseline_count if bool(canonical_sync_baseline_boundary.get("official_baseline_record_gate_pass", False)) else 0
    )
    comparator_control_gate_pass = (
        main_table_comparator_control_count >= 4 and main_table_comparator_control_record_count > 0
    )
    parse_only_baseline_count = sum(1 for item in baselines if str(item.get("runnable_status", "")) == "parse_only")
    baseline_admission_gate_pass = bool(baseline_admission.get("baseline_gate_pass", False))
    baseline_admission_official_gate_pass = bool(
        baseline_admission.get("official_baseline_gate_pass", baseline_admission_gate_pass)
    )
    baseline_admission_comparator_gate_pass = bool(
        baseline_admission.get("comparator_control_gate_pass", False)
    )
    baseline_admission_issues = [
        str(item)
        for item in baseline_admission.get("issues", [])
        if str(item).strip()
    ] if isinstance(baseline_admission.get("issues", []), list) else []
    baseline_admission_issue_free = not baseline_admission_issues
    baseline_admission_verification_complete = _baseline_admission_verification_complete(baseline_admission, baselines)
    if (
        baseline_admission_issue_free
        and baseline_admission_gate_pass
        and baseline_admission_official_gate_pass
        and int(baseline_admission.get("official_runnable_baseline_count", 0) or 0) > 0
    ):
        baseline_admission_verification_complete = True
        official_runnable_baseline_count = max(
            official_runnable_baseline_count,
            int(baseline_admission.get("official_runnable_baseline_count", 0) or 0),
        )
        runnable_integration_count = max(
            runnable_integration_count,
            int(baseline_admission.get("runnable_baseline_count", 0) or 0),
        )
        main_table_comparator_control_count = max(
            main_table_comparator_control_count,
            int(baseline_admission.get("main_table_comparator_control_count", 0) or 0),
        )
        parse_only_baseline_count = max(
            parse_only_baseline_count,
            int(baseline_admission.get("parse_only_baseline_count", 0) or 0),
        )
        official_baseline_gate_pass = official_runnable_baseline_count > 0
        baseline_or_comparator_gate_pass = official_baseline_gate_pass
        comparator_control_gate_pass = comparator_control_gate_pass or bool(
            baseline_admission.get("comparator_control_gate_pass", False)
        )
    baseline_unresolved_count = sum(1 for item in baselines if not bool(item.get("promotion_resolved", False)))
    required_pass_target = int(iteration_ledger.get("required_pass_target", 20) or 20)
    recorded_pass_count = int(iteration_ledger.get("recorded_pass_count", 0) or 0)
    zero_mod_validation_target = int(iteration_ledger.get("zero_mod_validation_target", 10) or 10)
    zero_mod_validation_pass_count = int(iteration_ledger.get("zero_mod_validation_pass_count", 0) or 0)
    zero_mod_validation_complete = bool(iteration_ledger.get("zero_mod_validation_complete", False)) and zero_mod_validation_pass_count >= zero_mod_validation_target
    final_open_blockers = final_ledger.get("open_blockers", [])
    final_open_blockers = tuple(str(item) for item in final_open_blockers) if isinstance(final_open_blockers, list) else ()
    final_status = str(final_ledger.get("status", ""))
    final_ledger_exists = final_ledger_path.exists()
    no_overfit_ledger_complete = final_ledger_exists and recorded_pass_count >= required_pass_target and zero_mod_validation_complete and "not_yet_complete" not in final_status and "20-pass ledger not complete" not in final_open_blockers
    null_pool_tiers = [_null_pool_tier(item) for item in contamination_records]
    null_pool_tier_counts = {str(key): value for key, value in sorted(Counter(null_pool_tiers).items()) if key}
    null_pool_fallback_count = sum(1 for item in contamination_records if bool(item.get("null_pool_fallback_used", False)))
    null_pool_interpretation = {
        "tier_counts": null_pool_tier_counts,
        "fallback_record_count": null_pool_fallback_count,
        "fallback_used_for_all_scored_records": bool(contamination_records) and null_pool_fallback_count == len(contamination_records),
        "reported_bound_when_tier8": "leave_one_task_empirical_dominance_tail_bound",
        "reviewer_caveat": "tier-8 fallback is a global hard-negative tail, not a fine metadata-stratum tail",
    }
    familywise_interpretation = {
        "null_calibration_method": "leave_one_task_empirical_dominance_tail_bound" if null_pool_interpretation["fallback_used_for_all_scored_records"] else "metadata_matched_empirical_dominance_tail_bound",
        "familywise_event": "lexicographic_gate_vector_with_coverage_tiebreak_dominance_tail",
        "second_correction_applied": False,
        "headline_form": "lexicographic_gate_vector_not_weighted_sum",
        "null_pool_tier_reporting_required": True,
    }
    positive_control_composite_validity_pass = bool(positive.get("positive_control_composite_validity_pass", False))
    sample_selection_audit_matches_current = _sample_selection_audit_matches_current_full_eval(
        sample_selection_audit,
        source_full_eval_sha256=source_full_eval_sha256,
        canonical_source_run_id=canonical_source_run_id,
    )
    current_sample_selection_status = str(
        sample_selection_audit.get("current_canonical_status", payload.get("sample_selection_adjustment_status", "legacy_or_unknown"))
        if sample_selection_audit_matches_current
        else payload.get("sample_selection_adjustment_status", "legacy_or_unknown")
    )
    sample_selection_rerun_required = bool(
        sample_selection_audit.get("rerun_required", current_sample_selection_status not in CURRENT_SAMPLE_SELECTION_STATUSES)
        if sample_selection_audit_matches_current
        else True
    )
    sample_selection_rerun_required_reason = str(
        sample_selection_audit.get("rerun_required_reason", "")
        if sample_selection_audit_matches_current
        else "sample_selection_rerun_audit_stale_relative_to_current_canonical_full_eval"
    )
    sample_selection_policy = {
        "current_canonical_status": current_sample_selection_status,
        "future_run_policy": "pre_registered_utility_before_contamination_scoring",
        "winner_selection_over_contamination_score_allowed": False,
        "rerun_audit_path": "artifacts/generated/sample_selection_rerun_audit.json" if sample_selection_audit_path.exists() else "",
        "rerun_audit_complete": bool(sample_selection_audit.get("schema_version")),
        "rerun_audit_matches_current_full_eval": sample_selection_audit_matches_current,
        "rerun_required": sample_selection_rerun_required,
        "rerun_required_reason": sample_selection_rerun_required_reason,
        "utility_selection_mismatch_record_count": int(sample_selection_audit.get("utility_selection_mismatch_record_count", 0) or 0) if sample_selection_audit_matches_current else 0,
        "rerun_free_rematerialization_possible": bool(sample_selection_audit.get("rerun_free_rematerialization_possible", False)) if sample_selection_audit_matches_current else False,
    }
    baseline_scope_decision_summary = {
        "path": "artifacts/generated/baseline_scope_decision.json" if baseline_scope_decision_path.exists() else "",
        "schema_version": str(baseline_scope_decision.get("schema_version", "")),
        "decision": str(baseline_scope_decision.get("decision", "")),
        "scope_decision_complete": bool(baseline_scope_decision.get("scope_decision_complete", False)),
        "utility_rematerialization_rerun_allowed": bool(baseline_scope_decision.get("utility_rematerialization_rerun_allowed", False)),
        "claim_bearing_rerun_allowed": bool(baseline_scope_decision.get("claim_bearing_rerun_allowed", False)),
        "canonical_promotion_allowed": bool(baseline_scope_decision.get("canonical_promotion_allowed", False)),
        "approved_run_id": str(baseline_scope_decision.get("approved_run_id", "")),
        "closure_blockers_preserved": [
            str(item)
            for item in baseline_scope_decision.get("closure_blockers_preserved", [])
            if str(item).strip()
        ] if isinstance(baseline_scope_decision.get("closure_blockers_preserved", []), list) else [],
    }
    honest_comparator_downgrade_allowed = _honest_comparator_downgrade_allowed(baseline_downgrade)
    baseline_blockers_downgraded_to_limitation: list[str] = []

    def add_baseline_blocker(blocker: str) -> None:
        if honest_comparator_downgrade_allowed:
            baseline_blockers_downgraded_to_limitation.append(blocker)
        if blocker not in closure_blockers:
            closure_blockers.append(blocker)

    closure_blockers = []
    if baseline_unresolved_count > 0:
        closure_blockers.append("official_baseline_truth_unresolved")
    if not official_baseline_gate_pass:
        add_baseline_blocker("official_main_table_runnable_baseline_missing")
    if not baseline_or_comparator_gate_pass:
        closure_blockers.append("official_main_table_baseline_missing_no_comparator_downgrade")
        if main_table_comparator_control_count >= 4:
            closure_blockers.append("comparator_controls_support_only_not_official_baseline")
    if not baseline_admission_official_gate_pass:
        add_baseline_blocker(
            "baseline_admission_official_gate_missing"
            if not baseline_admission
            else "baseline_admission_official_gate_not_passed"
        )
    if str(baseline_candidate_audit.get("closure_blocker", "")).strip() and not official_baseline_gate_pass:
        add_baseline_blocker("baseline_candidate_audit_official_blocker_preserved")
    official_baseline_provenance_gate_pass = bool(official_baseline_provenance_gate.get("gate_pass", False))
    if official_baseline_gate_pass and not official_baseline_provenance_gate_pass:
        closure_blockers.append(
            "official_baseline_provenance_gate_missing"
            if not official_baseline_provenance_gate
            else "official_baseline_provenance_gate_blocked"
        )
        for item in official_baseline_provenance_gate.get("blockers", []):
            if str(item).strip():
                closure_blockers.append(f"official_baseline_provenance_gate:{item}")
    if (
        baseline_admission_comparator_gate_pass
        and comparator_control_gate_pass
        and not official_baseline_gate_pass
    ):
        closure_blockers.append("comparator_controls_ready_but_support_only_official_baseline_missing")
    if canonical_record_schema_stale:
        closure_blockers.append("canonical_record_schema_stale")
    if canonical_sync_gate and not bool(canonical_sync_gate.get("sync_gate_pass", False)):
        closure_blockers.append("canonical_evidence_sync_gate_blocked")
        for item in canonical_sync_gate.get("blockers", []):
            if str(item).strip():
                closure_blockers.append(f"canonical_evidence_sync_gate:{item}")
    elif not canonical_sync_gate:
        closure_blockers.append("canonical_evidence_sync_gate_missing")
    if attack_ci_gate and str(attack_ci_gate.get("status", "")) != "passed":
        closure_blockers.append("attack_matrix_ci_not_passed")
        for item in attack_ci_gate.get("issues", []):
            if str(item).strip():
                closure_blockers.append(f"attack_matrix_ci_issue:{item}")
    elif not attack_ci_gate:
        closure_blockers.append("attack_matrix_ci_missing")
    if attack_live_support_gate and not bool(attack_live_support_gate.get("gate_pass", False)):
        closure_blockers.append("attack_live_support_gate_blocked")
        for item in attack_live_support_gate.get("blockers", []):
            if str(item).strip():
                closure_blockers.append(f"attack_live_support_gate:{item}")
    elif not attack_live_support_gate:
        closure_blockers.append("attack_live_support_gate_missing")
    if not baseline_audit_complete:
        closure_blockers.append("baseline_candidate_audit_incomplete")
    if not baseline_admission_verification_complete:
        closure_blockers.append("baseline_admission_verification_missing")
    if not curation_audit_complete:
        closure_blockers.append("codedyebench_curation_audit_missing")
    if not positive_control_composite_validity_pass:
        closure_blockers.append("positive_control_calibration_incomplete")
    if sample_selection_audit_path.exists() and not sample_selection_audit_matches_current:
        closure_blockers.append("sample_selection_rerun_audit_stale")
    if sample_selection_policy["current_canonical_status"] not in CURRENT_SAMPLE_SELECTION_STATUSES and sample_selection_policy["rerun_required"]:
        closure_blockers.append("legacy_sample_selection_requires_rerun")
    if not no_overfit_ledger_complete:
        closure_blockers.append("no_overfit_ledger_incomplete")
    if not zero_mod_validation_complete:
        closure_blockers.append("zero_mod_validation_incomplete")
    canonical_full_evidence_ready = not closure_blockers
    submission_closure_eligible = canonical_full_evidence_ready
    first_failing_gate = closure_blockers[0] if closure_blockers else "all_gates_pass"
    claim_boundary = "deepseek_live_null_audit_only"
    aggregate = {
        "source_full_eval_path": "artifacts/generated/full_eval_results.json",
        "source_full_eval_sha256": source_full_eval_sha256,
        "source_full_eval_run_id": str(payload.get("run_id", "")),
        "public_evidence_artifacts": {
            "full_eval": "artifacts/generated/full_eval_results.public.json",
            "positive_control": "artifacts/generated/positive_control_contamination_result.public.json",
            "contamination_audit": "artifacts/generated/contamination_audit_result.public.json",
            "distillation": "artifacts/generated/distillation_result.public.json",
            "manifest": "artifacts/generated/public_evidence_manifest.json",
        },
        "local_utility_score": _average(
            [item for item in utility_records if str(item.get("task_source", item.get("source", ""))) != "external_checkout"],
            "local_utility_score",
        ),
        "average_evidence_stage": round(mean(_evidence_stage(item) for item in contamination_records), 4) if contamination_records else 0.0,
        "average_canary_coverage": _average(contamination_records, "canary_coverage"),
        "final_accusation_rate": round(mean(1.0 if item.get("contaminated") else 0.0 for item in contamination_records), 4) if contamination_records else 0.0,
        "strict_null_control_rate": _mean_boolean(contamination_records, lambda item: float(item.get("false_positive_bound", 1.0)) <= 0.05),
        "cross_language_signal_rate": _average(contamination_records, "cross_language_signal"),
        "transfer_contamination_rate": _average(contamination_records, "transfer_contamination_rate"),
        "extra_query_cost": round(mean(float(item.get("extra_query_cost", 0.0)) for item in contamination_records), 2) if contamination_records else 0.0,
        "latency_overhead": _average(contamination_records, "latency_overhead"),
        "utility_gate_pass_rate": _mean_boolean(
            [item for item in utility_records if str(item.get("task_source", item.get("source", ""))) != "external_checkout"],
            lambda item: _score_present(item, "local_utility_score") and float(item.get("local_utility_score", 0.0) or 0.0) >= 1.0,
        ),
        "direct_canary_gate_rate": _mean_boolean(contamination_records, lambda item: int(item.get("direct_output_visible_canary_count", 0)) > 0),
        "semantic_witness_gate_rate": _mean_boolean(contamination_records, lambda item: _trace_contains(item, "semantic_witness_present:1")),
        "admissible_output_visible_canary_evidence_rate": _mean_boolean(
            contamination_records,
            lambda item: int(item.get("admissible_output_visible_canary_evidence_count", 0)) > 0,
        ),
        "diagnostic_evidence_rate": _mean_boolean(contamination_records, lambda item: int(item.get("diagnostic_evidence_count", 0)) > 0),
        "prompt_context_only_rate": _mean_boolean(
            contamination_records,
            lambda item: int(item.get("admissible_output_visible_canary_evidence_count", 0)) == 0
            and int(item.get("prompt_context_canary_evidence_count", 0)) > 0,
        ),
        "hidden_test_family_diagnostic_only_rate": _mean_boolean(contamination_records, lambda item: bool(item.get("hidden_test_family_diagnostic_only", False))),
        "accusation_eligibility_rate": _mean_boolean(
            contamination_records,
            lambda item: float(item.get("false_positive_bound", 1.0)) <= float(item.get("accusation_eligibility_bound", 0.35)),
        ),
        "familywise_accusation_rate": _mean_boolean(contamination_records, lambda item: bool(item.get("contaminated"))),
        "public_utility_support_state": public_utility_status,
        "public_utility_support_pass_rate": (
            _mean_boolean(
                public_utility_records,
                lambda item: _score_present(item, "public_utility_support_score")
                and float(item.get("public_utility_support_score", 0.0) or 0.0) >= 1.0,
            )
            if public_utility_records
            else None
        ),
        "attack_applicable_count": sum(1 for item in contamination_records if item.get("attack_applicable")),
        "backbone_count": len({str(item.get("backbone_name", "")) for item in contamination_records if str(item.get("backbone_name", ""))}),
        "record_count": len(contamination_records),
        "local_record_count": sum(1 for item in contamination_records if str(item.get("task_source", item.get("source", ""))) != "external_checkout"),
        "contamination_record_count": len(contamination_records),
        "utility_record_count": len(utility_records),
        "total_record_count": len(records),
        "pending_user_review_count": sum(1 for item in records if str(item.get("review_status", "ready")) == "pending_user_review"),
        "unscored_record_count": sum(1 for item in records if str(item.get("scoring_status", "scored")) != "scored"),
        "runtime_unscored_record_count": sum(1 for item in records if str(item.get("scoring_status", "")) == "unscored_runtime_failure"),
        "contamination_not_applicable_record_count": sum(1 for item in records if _record_status(item, "contamination_scoring_status") == "not_applicable_public_benchmark"),
        "utility_only_public_record_count": len(public_utility_records),
        "provider_live_record_count": sum(1 for item in records if str(item.get("provider_mode_resolved", "")) == "live"),
        "provider_live_scored_count": sum(
            1
            for item in records
            if str(item.get("provider_mode_resolved", "")) == "live" and _contamination_scored(item)
        ),
        "provider_live_utility_scored_count": sum(
            1
            for item in records
            if str(item.get("provider_mode_resolved", "")) == "live" and _utility_scored(item)
        ),
        "local_reviewed_task_record_count": len(local_reviewed_task_ids),
        "accused_asset_count": len({str(asset_id) for item in contamination_records for asset_id in item.get("accused_asset_ids", [])}),
        "benchmark_counts": benchmark_counts,
        "task_source_counts": task_source_counts,
        "utility_benchmark_counts": utility_benchmark_counts,
        "utility_task_source_counts": utility_task_source_counts,
        "public_benchmark_task_count": int(payload.get("public_benchmark_task_count", 0)),
        "public_benchmark_record_count": int(payload.get("public_benchmark_record_count", 0)),
        "public_benchmark_utility_record_count": len(public_utility_records),
        "public_benchmark_contamination_record_count": sum(
            1
            for item in contamination_records
            if str(item.get("task_source", item.get("source", ""))) == "external_checkout"
        ),
        "public_benchmark_utility_score": _average_or_none(public_utility_records, "public_utility_support_score"),
        "public_benchmark_compile_rate": _average_or_none(public_utility_records, "compile_rate"),
        "public_benchmark_pass_rate": _average_or_none(public_utility_records, "pass_rate"),
        "runnable_baseline_count": official_runnable_baseline_count,
        "runnable_integration_count": runnable_integration_count,
        "official_runnable_baseline_count": official_runnable_baseline_count,
        "official_record_backed_baseline_count": official_record_backed_baseline_count,
        "main_table_comparator_control_count": main_table_comparator_control_count,
        "main_table_comparator_control_record_count": main_table_comparator_control_record_count,
        "baseline_or_comparator_gate_pass": baseline_or_comparator_gate_pass,
        "official_baseline_gate_pass": official_baseline_gate_pass,
        "comparator_control_gate_pass": comparator_control_gate_pass,
        "baseline_downgrade_decision": {
            "path": "artifacts/generated/baseline_downgrade_decision.json",
            "decision": str(baseline_downgrade.get("decision", "")),
            "downgrade_gate_pass": bool(baseline_downgrade.get("downgrade_gate_pass", False)),
            "baseline_exception_gate_pass": bool(baseline_downgrade.get("baseline_exception_gate_pass", False)),
            "honest_comparator_downgrade_allowed": honest_comparator_downgrade_allowed,
            "main_table_policy_after_downgrade": str(baseline_downgrade.get("main_table_policy_after_downgrade", "")),
            "downgraded_blockers": sorted(dict.fromkeys(baseline_blockers_downgraded_to_limitation)),
        },
        "canonical_evidence_sync_gate": {
            "path": "artifacts/generated/canonical_evidence_sync_gate.json",
            "present": bool(canonical_sync_gate),
            "sync_gate_pass": bool(canonical_sync_gate.get("sync_gate_pass", False)),
            "blockers": [
                str(item)
                for item in canonical_sync_gate.get("blockers", [])
                if str(item).strip()
            ] if isinstance(canonical_sync_gate.get("blockers", []), list) else [],
        },
        "attack_matrix_ci_gate": {
            "path": "artifacts/generated/attack_matrix_null_calibration_ci.json",
            "present": bool(attack_ci_gate),
            "status": str(attack_ci_gate.get("status", "")),
            "issues": [
                str(item)
                for item in attack_ci_gate.get("issues", [])
                if str(item).strip()
            ] if isinstance(attack_ci_gate.get("issues", []), list) else [],
        },
        "attack_live_support_gate": {
            "path": "artifacts/generated/attack_live_support_gate.json",
            "present": bool(attack_live_support_gate),
            "gate_pass": bool(attack_live_support_gate.get("gate_pass", False)),
            "status": str(attack_live_support_gate.get("status", "")),
            "blockers": [
                str(item)
                for item in attack_live_support_gate.get("blockers", [])
                if str(item).strip()
            ] if isinstance(attack_live_support_gate.get("blockers", []), list) else [],
        },
        "parse_only_baseline_count": parse_only_baseline_count,
        "main_table_baseline_count": official_record_backed_baseline_count,
        "runnable_baseline_or_comparator_count": runnable_integration_count,
        "baseline_promotion_resolved_count": sum(1 for item in baselines if bool(item.get("promotion_resolved", False))),
        "baseline_unresolved_count": baseline_unresolved_count,
        "canonical_full_evidence_ready": canonical_full_evidence_ready,
        "submission_closure_eligible": submission_closure_eligible,
        "first_failing_gate": first_failing_gate,
        "claim_boundary": claim_boundary,
        "canonical_source_run_id": canonical_source_run_id,
        "review_ready": canonical_full_evidence_ready,
        "experiment_entry_allowed": canonical_full_evidence_ready,
        "canonical_record_schema_stale": canonical_record_schema_stale,
        "canonical_record_schema_missing_fields": canonical_record_schema_missing_fields,
        "no_overfit_recorded_pass_count": recorded_pass_count,
        "no_overfit_required_pass_target": required_pass_target,
        "no_overfit_ledger_complete": no_overfit_ledger_complete,
        "canonical_full_evidence_blockers": closure_blockers,
        "zero_mod_validation_target": zero_mod_validation_target,
        "zero_mod_validation_pass_count": zero_mod_validation_pass_count,
        "zero_mod_validation_complete": zero_mod_validation_complete,
        "closure_blockers": closure_blockers,
        "closure_blocker_summary": closure_blockers,
        "baseline_candidate_audit_complete": baseline_audit_complete,
        "baseline_candidate_audit_schema_version": str(baseline_candidate_audit.get("schema_version", "")),
        "baseline_candidate_audit_candidate_count": int(baseline_candidate_audit.get("official_candidate_count", baseline_candidate_audit.get("candidate_count", 0)) or 0),
        "baseline_candidate_audit_parse_only_candidate_names": [
            str(item)
            for item in baseline_candidate_audit.get("parse_only_candidate_names", [])
            if str(item).strip()
        ] if isinstance(baseline_candidate_audit.get("parse_only_candidate_names", []), list) else [],
        "baseline_candidate_audit_rejected_candidate_names": [
            str(item)
            for item in baseline_candidate_audit.get("rejected_candidate_names", [])
            if str(item).strip()
        ] if isinstance(baseline_candidate_audit.get("rejected_candidate_names", []), list) else [],
        "baseline_candidate_audit_closure_blocker": str(baseline_candidate_audit.get("closure_blocker", "")),
        "baseline_admission_verification_complete": baseline_admission_verification_complete,
        "baseline_admission_gate_pass": baseline_admission_gate_pass,
        "baseline_admission_verification": {
            "path": "artifacts/generated/baseline_admission_verification.json",
            "baseline_gate_pass": baseline_admission_gate_pass,
            "official_baseline_gate_pass": baseline_admission_official_gate_pass,
            "comparator_control_gate_pass": baseline_admission_comparator_gate_pass,
            "runnable_baseline_count": int(baseline_admission.get("runnable_baseline_count", 0) or 0),
            "official_runnable_baseline_count": int(baseline_admission.get("official_runnable_baseline_count", 0) or 0),
            "main_table_comparator_control_count": int(baseline_admission.get("main_table_comparator_control_count", 0) or 0),
            "parse_only_baseline_count": int(baseline_admission.get("parse_only_baseline_count", 0) or 0),
            "closure_blocker": str(baseline_admission.get("closure_blocker", "")),
            "issues": baseline_admission_issues,
        },
        "official_baseline_provenance_gate": {
            "path": "artifacts/generated/official_baseline_provenance_gate.json",
            "present": bool(official_baseline_provenance_gate),
            "gate_pass": official_baseline_provenance_gate_pass,
            "status": str(official_baseline_provenance_gate.get("status", "")),
            "blockers": [
                str(item)
                for item in official_baseline_provenance_gate.get("blockers", [])
                if str(item).strip()
            ] if isinstance(official_baseline_provenance_gate.get("blockers", []), list) else [],
        },
        "baseline_scope_decision": baseline_scope_decision_summary,
        "baseline_gate_blockers": baseline_admission_issues,
        "baseline_gate_first_issue": baseline_admission_issues[0] if baseline_admission_issues else "",
        "sample_selection_rerun_audit": {
            "path": "artifacts/generated/sample_selection_rerun_audit.json",
            "source_full_eval_sha256": str(sample_selection_audit.get("source_full_eval_sha256", "")) if sample_selection_audit_matches_current else "",
            "matches_current_full_eval": sample_selection_audit_matches_current,
            "rerun_required": sample_selection_policy["rerun_required"],
            "utility_selection_mismatch_record_count": sample_selection_policy["utility_selection_mismatch_record_count"],
            "rerun_free_rematerialization_possible": sample_selection_policy["rerun_free_rematerialization_possible"],
        },
        "codedyebench_curation_audit_complete": curation_audit_complete,
        "positive_control_composite_validity_pass": positive_control_composite_validity_pass,
        "positive_control_interpretation": {
            "positive_arm_power_pass": bool(positive.get("positive_control_familywise_power_pass", False)),
            "clean_control_pass": bool(positive.get("null_control_pass", False)),
            "family_coverage_pass": bool(positive.get("positive_control_family_coverage_pass", False)),
            "composite_validity_pass": positive_control_composite_validity_pass,
            "clean_control_leak_rate": float(positive.get("clean_control_leak_rate", 0.0)),
        },
        "sample_selection_policy": sample_selection_policy,
        "null_pool_interpretation": null_pool_interpretation,
        "rate_intervals": {
            "admissible_output_visible_canary_evidence": _rate_interval(sum(1 for item in contamination_records if int(item.get("admissible_output_visible_canary_evidence_count", 0)) > 0), len(contamination_records)),
            "strict_null_control": _rate_interval(sum(1 for item in contamination_records if float(item.get("false_positive_bound", 1.0)) <= 0.05), len(contamination_records)),
            "familywise_accusation": _rate_interval(sum(1 for item in contamination_records if bool(item.get("contaminated"))), len(contamination_records)),
        },
        "familywise_interpretation": familywise_interpretation,
        "median_false_positive_bound": _median_or_default(false_positive_bounds, 1.0),
        "max_false_positive_bound": round(max(false_positive_bounds), 4) if false_positive_bounds else 1.0,
        "median_empirical_p_value": _median_or_default(empirical_p_values, 1.0),
        "median_familywise_adjusted_p_value": _median_or_default(familywise_adjusted_p_values, 1.0),
        "min_null_sample_size": min(null_sample_sizes) if null_sample_sizes else 0,
        "median_familywise_test_count": _median_or_default([float(item) for item in familywise_test_counts], 0.0),
        "familywise_decision_gate_pass_rate": _mean_boolean(contamination_records, lambda item: bool(item.get("familywise_decision_gate_pass"))),
        "strongest_null_margin_pass_rate": _mean_boolean(contamination_records, lambda item: float(item.get("strongest_null_margin", 0.0)) > 0.0),
        "subset_accusation_counts": _counter(
            [item for item in contamination_records if item.get("contaminated")],
            "subset",
        ),
        "evidence_stage_counts": {
            "stage_0": sum(1 for item in contamination_records if _evidence_stage(item) == 0),
            "stage_1": sum(1 for item in contamination_records if _evidence_stage(item) == 1),
            "stage_2": sum(1 for item in contamination_records if _evidence_stage(item) == 2),
            "stage_3": sum(1 for item in contamination_records if _evidence_stage(item) == 3),
            "stage_4": sum(1 for item in contamination_records if _evidence_stage(item) == 4),
        },
    }
    out_path = ARTIFACTS / "aggregate_results.json"
    out_path.write_text(json.dumps(aggregate, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps(aggregate, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
