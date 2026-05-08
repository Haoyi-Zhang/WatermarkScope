from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT


DEFAULT_OUTPUT = ARTIFACTS / "attack_statistics_gate.json"
MIN_ATTACK_STRESS_CASE_COVERAGE = 320
MIN_ATTACK_STRESS_RECORD_COUNT = 320
MIN_ATTACK_STRESS_FAMILY_COUNT = 4
MIN_MARKER_HIDDEN_CASE_COUNT = 320
MIN_MARKER_HIDDEN_PROVIDER_RECORD_COUNT = 1280


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "exists": path.exists(),
        "sha256": _sha256(path),
    }


def _status_count(summary: dict[str, Any], key: str) -> int:
    try:
        return int(summary.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _gate_summary(executable: dict[str, Any], gate_name: str) -> dict[str, Any]:
    case_analysis = _dict(executable.get("case_analysis"))
    gate_summary = _dict(case_analysis.get("gate_summary"))
    return _dict(gate_summary.get(gate_name))


def _case_bound_attack_records(records: list[Any], *, require_analysis_scope: str | None = None) -> tuple[int, int, list[str]]:
    typed = [item for item in records if isinstance(item, dict)]
    case_bound_count = 0
    issue_sample: list[str] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(typed, start=1):
        case_id = str(item.get("case_id", "")).strip()
        transform_id = str(item.get("transform_id") or item.get("scenario") or "").strip()
        expected_direction = str(item.get("expected_metric_direction") or item.get("expected_effect") or "").strip()
        raw_hash = str(item.get("transformed_artifact_sha256") or item.get("raw_output_sha256") or "").strip()
        clean_hash = str(item.get("clean_artifact_sha256", "")).strip()
        observed_direction = str(item.get("observed_direction", "")).strip()
        direction_check = item.get("direction_check_passed")
        has_clean_metrics = all(
            key in item
            for key in (
                "clean_confidence",
                "clean_match_rate",
                "clean_owner_id_hat",
                "attacked_confidence",
                "attacked_match_rate",
                "attacked_owner_id_hat",
                "confidence_delta",
                "match_rate_delta",
            )
        )
        if require_analysis_scope and str(item.get("analysis_scope", "")).strip() != require_analysis_scope:
            issue_sample.append(f"record_{index}:analysis_scope_mismatch")
        if not case_id:
            issue_sample.append(f"record_{index}:case_id_missing")
        if not transform_id:
            issue_sample.append(f"record_{index}:transform_id_missing")
        if not expected_direction:
            issue_sample.append(f"record_{index}:expected_direction_missing")
        if not raw_hash:
            issue_sample.append(f"record_{index}:raw_transformed_artifact_hash_missing")
        if not clean_hash:
            issue_sample.append(f"record_{index}:clean_baseline_hash_missing")
        if not has_clean_metrics:
            issue_sample.append(f"record_{index}:pre_post_metrics_missing")
        if observed_direction != expected_direction:
            issue_sample.append(f"record_{index}:observed_direction_mismatch")
        if direction_check is not True:
            issue_sample.append(f"record_{index}:direction_check_not_passed")
        key = (case_id, transform_id)
        if case_id and transform_id and key in seen:
            issue_sample.append(f"record_{index}:duplicate_case_transform")
        seen.add(key)
        if (
            case_id
            and transform_id
            and expected_direction
            and raw_hash
            and clean_hash
            and has_clean_metrics
            and observed_direction == expected_direction
            and direction_check is True
        ):
            case_bound_count += 1
        if len(issue_sample) >= 8:
            break
    return len(typed), case_bound_count, issue_sample[:8]


def _attack_payload_records(payload: Any) -> tuple[list[Any], dict[str, Any]]:
    if isinstance(payload, dict):
        return _list(payload.get("records")), payload
    return _list(payload), {}


def _gate(
    name: str,
    status: str,
    *,
    artifact: str,
    evidence: dict[str, Any],
    blockers: list[str] | None = None,
    support_ready: bool | None = None,
    claim_ready: bool | None = None,
    support_ready_reason: str = "",
    claim_ready_false_reasons: list[str] | None = None,
) -> dict[str, Any]:
    resolved_blockers = blockers or []
    resolved_support_ready = status in {"passed", "support_ready_not_claim_bearing"} if support_ready is None else support_ready
    resolved_claim_ready = status == "passed" if claim_ready is None else claim_ready
    if not support_ready_reason:
        support_ready_reason = (
            "machine_side_evidence_satisfies_this_gate"
            if resolved_support_ready
            else "machine_side_evidence_missing_or_blocked"
        )
    if claim_ready_false_reasons is None:
        claim_ready_false_reasons = [] if resolved_claim_ready else (
            ["support_evidence_not_formal_claim_bearing"]
            if resolved_support_ready
            else list(resolved_blockers)
        )
    return {
        "gate": name,
        "status": status,
        "artifact": artifact,
        "evidence": evidence,
        "support_ready": resolved_support_ready,
        "claim_ready": resolved_claim_ready,
        "support_ready_reason": support_ready_reason,
        "claim_ready_false_reasons": claim_ready_false_reasons,
        "blockers": resolved_blockers,
    }


def _analysis_payload() -> dict[str, Any]:
    path = ARTIFACTS / "watermark_backdoorbench_v2_analysis_scaffold.json"
    payload = _load_json(path)
    if isinstance(payload, dict):
        return payload
    return {}


def build_gate() -> dict[str, Any]:
    paths = {
        "v2_analysis": ARTIFACTS / "watermark_backdoorbench_v2_analysis_scaffold.json",
        "laundering": ARTIFACTS / "laundering_audit_summary.json",
        "attack_stress": ARTIFACTS / "attack_stress_summary.json",
        "threshold_freeze": ARTIFACTS / "threshold_freeze_report.json",
        "rubric_ablation": ARTIFACTS / "rubric_ablation_report.json",
        "executable_conjunction": ARTIFACTS / "executable_adapter_conjunction.json",
        "blinded_adjudication": ARTIFACTS / "blinded_adjudication_ledger.json",
        "completed_adjudication": ARTIFACTS / "completed_adjudication_ingest_gate.json",
    }
    analysis = _analysis_payload()
    laundering = _list(_load_json(paths["laundering"]))
    attack_stress, attack_stress_summary = _attack_payload_records(_load_json(paths["attack_stress"]))
    threshold_freeze = _dict(_load_json(paths["threshold_freeze"]))
    rubric = _dict(_load_json(paths["rubric_ablation"]))
    executable = _dict(_load_json(paths["executable_conjunction"]))
    adjudication = _dict(_load_json(paths["blinded_adjudication"]))
    completed_adjudication = _dict(_load_json(paths["completed_adjudication"]))

    summary = _dict(analysis.get("summary"))
    hard = _dict(analysis.get("hard_ambiguity_retention"))
    stats = _dict(analysis.get("statistical_sensitivity"))
    final = _dict(analysis.get("final_conjunction_ablation"))
    executable_policy = _dict(executable.get("conjunction_policy"))
    current_prompt_audit = _dict(rubric.get("current_prompt_field_audit"))
    marker_hidden_plan = _dict(rubric.get("marker_hidden_ablation"))
    marker_hidden_subset = _dict(rubric.get("marker_hidden_subset"))
    marker_hidden_results = _dict(rubric.get("rubric_ablation_results"))
    threshold_plan = _dict(threshold_freeze.get("threshold_sensitivity_plan"))
    threshold_results = _dict(threshold_freeze.get("threshold_sensitivity_results"))
    laundering_gate_summary = _gate_summary(executable, "laundering")
    spoofability_gate_summary = _gate_summary(executable, "spoofability")
    laundering_record_count, laundering_case_bound_count, laundering_issues = _case_bound_attack_records(laundering)
    attack_record_count, attack_case_bound_count, attack_issues = _case_bound_attack_records(
        attack_stress,
        require_analysis_scope="attack_stress",
    )
    attack_case_coverage_count = len(
        {
            str(item.get("case_id", "")).strip()
            for item in attack_stress
            if isinstance(item, dict) and str(item.get("case_id", "")).strip()
        }
    )
    attack_family_count = len(
        {
            str(item.get("attack_family") or item.get("scenario") or "").strip()
            for item in attack_stress
            if isinstance(item, dict) and str(item.get("attack_family") or item.get("scenario") or "").strip()
        }
    )
    attack_stress_blockers: list[str] = []
    if attack_case_bound_count < MIN_ATTACK_STRESS_RECORD_COUNT or attack_issues:
        attack_stress_blockers.append("attack_stress_records_not_case_bound")
    if attack_case_coverage_count < MIN_ATTACK_STRESS_CASE_COVERAGE:
        attack_stress_blockers.append("attack_stress_case_coverage_below_320")
    if attack_family_count < MIN_ATTACK_STRESS_FAMILY_COUNT:
        attack_stress_blockers.append("attack_stress_family_count_below_4")
    confusion = _dict(stats.get("confusion_matrix_design_oracle"))
    bootstrap = _dict(stats.get("bootstrap_intervals"))
    threshold_at_0_5 = _dict(stats.get("threshold_at_0_5"))
    threshold_sweep = _list(stats.get("threshold_sweep"))
    executable_pass_count = _status_count(executable_policy, "pass_count")
    executable_blocked_count = _status_count(executable_policy, "blocked_count")
    executable_case_count = executable_pass_count + executable_blocked_count
    executable_case_analysis = _dict(executable.get("case_analysis"))
    executable_source_code_count = max(
        _status_count(executable_case_analysis, "source_candidate_code_present_count"),
        _status_count(executable_case_analysis, "candidate_executable_code_present_count"),
    )
    executable_support_adapter_count = _status_count(executable_case_analysis, "support_adapter_materialized_count")
    executable_final_blockers: list[str] = []
    if executable_case_count < 320:
        executable_final_blockers.append("executable_adapter_conjunction_case_count_below_320")
    if executable_blocked_count > 0:
        executable_final_blockers.append("executable_adapter_conjunction_has_blocked_cases")
    if executable_source_code_count < 320:
        executable_final_blockers.append("source_candidate_executable_code_coverage_below_320")
    marker_hidden_prompt_packet_record_count = int(marker_hidden_results.get("prompt_packet_record_count", 0) or 0)
    marker_hidden_prompt_packet_case_count = int(marker_hidden_results.get("prompt_packet_case_count", 0) or 0)
    marker_hidden_prompt_packet_ready = (
        bool(marker_hidden_results.get("prompt_packet_materialized"))
        and marker_hidden_prompt_packet_case_count >= MIN_MARKER_HIDDEN_CASE_COUNT
        and marker_hidden_prompt_packet_record_count >= MIN_MARKER_HIDDEN_PROVIDER_RECORD_COUNT
        and bool(marker_hidden_results.get("prompt_packet_marker_hidden_leak_gate_pass"))
    )
    marker_hidden_executed_record_count = int(marker_hidden_results.get("executed_record_count", 0) or 0)
    marker_hidden_metrics = _dict(marker_hidden_results.get("metrics"))
    marker_hidden_provider_support_ready = (
        marker_hidden_prompt_packet_ready
        and marker_hidden_executed_record_count >= MIN_MARKER_HIDDEN_PROVIDER_RECORD_COUNT
        and marker_hidden_metrics.get("delta_vs_v3_label_hidden_marker_visible") is not None
        and marker_hidden_metrics.get("threshold_sensitivity_on_threshold_fit_subset") is not None
    )
    adjudication_claim_ready = (
        completed_adjudication.get("status") == "passed"
        and int(completed_adjudication.get("claim_table_admissible_count", 0) or 0) >= 320
        and adjudication.get("adjudication_complete") is True
    )
    marker_hidden_claim_bearing_ready = (
        marker_hidden_provider_support_ready
        and marker_hidden_results.get("claim_bearing") is True
        and adjudication_claim_ready
    )
    marker_hidden_blockers: list[str] = []
    if not marker_hidden_prompt_packet_ready:
        marker_hidden_blockers.append("marker_hidden_prompt_packet_missing_or_blocked")
    if marker_hidden_executed_record_count < MIN_MARKER_HIDDEN_PROVIDER_RECORD_COUNT:
        marker_hidden_blockers.append("executed_marker_hidden_provider_records_missing")
    if marker_hidden_provider_support_ready and not adjudication_claim_ready:
        marker_hidden_blockers.append("marker_hidden_provider_evidence_requires_completed_blinded_adjudication")
    if not marker_hidden_claim_bearing_ready:
        marker_hidden_blockers.append("obfuscation_stress_claim_bearing_records_missing_for_main_claim")
    confusion_blockers: list[str] = []
    if not confusion:
        confusion_blockers.append("confusion_matrix_missing")
    if _list(confusion.get("unknown_label_case_ids")):
        confusion_blockers.append("confusion_matrix_unknown_labels")
    bootstrap_blockers: list[str] = []
    if not bootstrap:
        bootstrap_blockers.append("bootstrap_intervals_missing")
    threshold_blockers: list[str] = []
    if not threshold_sweep:
        threshold_blockers.append("threshold_sweep_missing")
    if not threshold_plan:
        threshold_blockers.append("threshold_freeze_plan_missing")
    threshold_support_executed = (
        threshold_results.get("status") == "executed_support_only"
        and threshold_results.get("claim_bearing") is False
        and int(threshold_results.get("threshold_sweep_count", 0) or 0) == len(threshold_sweep)
        and bool(threshold_results.get("threshold_at_primary"))
    )
    provider_threshold_sweep = _list(threshold_results.get("threshold_sweep"))
    threshold_claim_bearing_executed = (
        threshold_results.get("status") in {"executed", "completed", "passed"}
        and threshold_results.get("claim_bearing") is True
        and int(threshold_results.get("threshold_sweep_count", 0) or 0) == len(provider_threshold_sweep)
        and bool(threshold_results.get("threshold_at_primary"))
        and (
            threshold_results.get("formal_claim_allowed") is True
            or threshold_results.get("machine_formal_claim_preconditions_met") is True
        )
    )
    threshold_claim_ready = threshold_claim_bearing_executed and adjudication_claim_ready
    threshold_execution_ready = threshold_support_executed or threshold_claim_bearing_executed
    if not threshold_execution_ready:
        threshold_blockers.append("threshold_sensitivity_support_execution_missing")
    elif threshold_support_executed:
        threshold_blockers.append("threshold_sensitivity_claim_bearing_records_missing_for_main_claim")
    elif not adjudication_claim_ready:
        threshold_blockers.append("completed_dual_curator_adjudication_missing_or_not_claim_table_admissible")
    if threshold_at_0_5 and float(threshold_at_0_5.get("f1", 0.0) or 0.0) < 1.0:
        threshold_blockers.append("primary_threshold_f1_below_one")
    if threshold_at_0_5 and int(threshold_at_0_5.get("missing_score_count", 0) or 0) > 0:
        threshold_blockers.append("primary_threshold_missing_scores_fail_closed")
    if int(stats.get("threshold_sensitivity_case_count", 0) or 0) < 160:
        threshold_blockers.append("threshold_sensitivity_population_below_160")
    if int(stats.get("threshold_sensitivity_negative_case_count", 0) or 0) <= 0:
        threshold_blockers.append("threshold_sensitivity_negative_population_missing")

    gates = [
        _gate(
            "adjudication_dependency",
            "passed" if adjudication_claim_ready else "blocked",
            artifact=paths["completed_adjudication"].relative_to(ROOT).as_posix(),
            evidence={
                "completed_adjudication_status": completed_adjudication.get("status", "missing"),
                "claim_table_admissible_count": completed_adjudication.get("claim_table_admissible_count", 0),
                "required_claim_table_admissible_count": 320,
                "ledger_status": adjudication.get("status", "missing"),
                "ledger_adjudication_complete": adjudication.get("adjudication_complete", False),
                "machine_labels_are_not_generated": True,
            },
            blockers=[]
            if adjudication_claim_ready
            else ["completed_dual_curator_adjudication_missing_or_not_claim_table_admissible"],
            support_ready=adjudication_claim_ready,
            claim_ready=adjudication_claim_ready,
            support_ready_reason=(
                "completed_human_dual_curator_adjudication_available"
                if adjudication_claim_ready
                else "human_dual_curator_adjudication_missing_not_a_machine_algorithm_failure"
            ),
            claim_ready_false_reasons=[]
            if adjudication_claim_ready
            else ["completed_dual_curator_adjudication_missing_or_not_claim_table_admissible"],
        ),
        _gate(
            "hard_ambiguity_retention",
            "passed" if hard.get("retained_case_count") == 160 and hard.get("threshold_fit_excluded_count") == 160 else "blocked",
            artifact=paths["v2_analysis"].relative_to(ROOT).as_posix(),
            evidence={
                "retained_case_count": hard.get("retained_case_count", 0),
                "threshold_fit_excluded_count": hard.get("threshold_fit_excluded_count", 0),
                "claim_use": hard.get("claim_use", ""),
            },
            blockers=[] if hard.get("retained_case_count") == 160 else ["hard_ambiguity_retention_not_160"],
        ),
        _gate(
            "laundering_attack_support",
            "support_ready_not_claim_bearing"
            if laundering_case_bound_count >= MIN_ATTACK_STRESS_RECORD_COUNT and not laundering_issues
            else "blocked",
            artifact=paths["laundering"].relative_to(ROOT).as_posix(),
            evidence={
                "scenario_count": laundering_record_count,
                "case_bound_record_count": laundering_case_bound_count,
                "required_case_bound_record_count": MIN_ATTACK_STRESS_RECORD_COUNT,
                "record_issue_sample": laundering_issues,
                "verified_count": sum(1 for item in laundering if isinstance(item, dict) and item.get("verified") is True),
                "executable_pass_count": _status_count(laundering_gate_summary, "pass_count"),
                "executable_blocked_count": _status_count(laundering_gate_summary, "blocked_count"),
                "executable_status_counts": _dict(laundering_gate_summary.get("status_counts")),
                "source_candidate_code_count": executable_source_code_count,
                "support_adapter_materialized_count": executable_support_adapter_count,
                "analysis_scope": "support_only",
            },
            blockers=[]
            if laundering_case_bound_count >= MIN_ATTACK_STRESS_RECORD_COUNT and not laundering_issues
            else [
                "laundering_stress_case_bound_coverage_below_320"
                if laundering_case_bound_count < MIN_ATTACK_STRESS_RECORD_COUNT
                else "laundering_stress_records_not_case_bound"
            ],
        ),
        _gate(
            "spoofability_attack_support",
            "blocked" if _status_count(spoofability_gate_summary, "blocked_count") else "support_ready_not_claim_bearing",
            artifact=paths["executable_conjunction"].relative_to(ROOT).as_posix(),
            evidence={
                "pass_count": _status_count(spoofability_gate_summary, "pass_count"),
                "blocked_count": _status_count(spoofability_gate_summary, "blocked_count"),
                "status_counts": _dict(spoofability_gate_summary.get("status_counts")),
                "analysis_scope": "support_only",
            },
            blockers=[] if not _status_count(spoofability_gate_summary, "blocked_count") else ["spoofability_stress_records_missing_or_blocked"],
        ),
        _gate(
            "attack_stress_support",
            "support_ready_not_claim_bearing" if not attack_stress_blockers else "blocked",
            artifact=paths["attack_stress"].relative_to(ROOT).as_posix(),
            evidence={
                "scenario_count": attack_record_count,
                "case_bound_record_count": attack_case_bound_count,
                "required_case_bound_record_count": MIN_ATTACK_STRESS_RECORD_COUNT,
                "case_coverage_count": attack_case_coverage_count,
                "required_case_coverage_count": MIN_ATTACK_STRESS_CASE_COVERAGE,
                "attack_family_count": attack_family_count,
                "required_attack_family_count": MIN_ATTACK_STRESS_FAMILY_COUNT,
                "declared_schema_version": attack_stress_summary.get("schema_version", "legacy_list"),
                "declared_expected_record_count": attack_stress_summary.get("expected_record_count", 0),
                "declared_direction_check_failure_count": attack_stress_summary.get("direction_check_failure_count", 0),
                "record_issue_sample": attack_issues,
                "analysis_scope": "support_only",
            },
            blockers=attack_stress_blockers,
        ),
        _gate(
            "marker_hidden_prompt_packet",
            "support_ready_not_claim_bearing" if marker_hidden_prompt_packet_ready else "blocked",
            artifact=paths["rubric_ablation"].relative_to(ROOT).as_posix(),
            evidence={
                "label_hidden_case_json_failure_count": current_prompt_audit.get("label_hidden_case_json_failure_count"),
                "label_hidden_case_json_gate_pass": current_prompt_audit.get("label_hidden_case_json_gate_pass"),
                "marker_hidden_plan_present": bool(marker_hidden_plan or marker_hidden_subset),
                "marker_hidden_subset_status": marker_hidden_subset.get("status"),
                "marker_hidden_subset_case_count": marker_hidden_subset.get("case_count", 0),
                "prompt_packet_materialized": marker_hidden_prompt_packet_ready,
                "prompt_packet_case_count": marker_hidden_prompt_packet_case_count,
                "prompt_packet_record_count": marker_hidden_prompt_packet_record_count,
                "prompt_packet_variant_count": marker_hidden_results.get("prompt_packet_variant_count", 0),
                "prompt_packet_marker_hidden_leak_gate_pass": marker_hidden_results.get("prompt_packet_marker_hidden_leak_gate_pass"),
                "executed_marker_hidden_provider_records": marker_hidden_executed_record_count,
            },
            blockers=[] if marker_hidden_prompt_packet_ready else ["marker_hidden_prompt_packet_missing_or_blocked"],
        ),
        _gate(
            "marker_hidden_obfuscation_stress",
            "passed"
            if marker_hidden_claim_bearing_ready
            else "support_ready_not_claim_bearing"
            if marker_hidden_provider_support_ready
            else "blocked",
            artifact=paths["rubric_ablation"].relative_to(ROOT).as_posix(),
            evidence={
                "prompt_packet_materialized": marker_hidden_prompt_packet_ready,
                "prompt_packet_case_count": marker_hidden_prompt_packet_case_count,
                "prompt_packet_record_count": marker_hidden_prompt_packet_record_count,
                "executed_marker_hidden_provider_records": marker_hidden_executed_record_count,
                "required_executed_provider_records": MIN_MARKER_HIDDEN_PROVIDER_RECORD_COUNT,
                "claim_bearing": marker_hidden_results.get("claim_bearing"),
                "provider_support_ready": marker_hidden_provider_support_ready,
                "adjudication_claim_ready": adjudication_claim_ready,
                "delta_vs_visible_v3_present": marker_hidden_metrics.get("delta_vs_v3_label_hidden_marker_visible") is not None,
                "threshold_sensitivity_metric_present": marker_hidden_metrics.get("threshold_sensitivity_on_threshold_fit_subset") is not None,
                "posthoc_label_join_required": True,
                "variant_delta_statistics_required": True,
            },
            blockers=marker_hidden_blockers,
            support_ready=marker_hidden_provider_support_ready,
            claim_ready=marker_hidden_claim_bearing_ready,
            support_ready_reason=(
                "provider_marker_hidden_machine_evidence_executed_and_metric_complete"
                if marker_hidden_provider_support_ready
                else "provider_marker_hidden_machine_evidence_missing_or_metric_incomplete"
            ),
            claim_ready_false_reasons=[]
            if marker_hidden_claim_bearing_ready
            else (
                ["completed_dual_curator_adjudication_missing_or_not_claim_table_admissible"]
                if marker_hidden_provider_support_ready and not adjudication_claim_ready
                else marker_hidden_blockers
            ),
        ),
        _gate(
            "confusion_matrix",
            "support_ready_not_claim_bearing" if not confusion_blockers else "blocked",
            artifact=paths["v2_analysis"].relative_to(ROOT).as_posix(),
            evidence={
                "source": stats.get("source", ""),
                "record_count": confusion.get("record_count", 0),
                "labels": _list(confusion.get("labels")),
                "row_totals": _dict(confusion.get("row_totals")),
                "column_totals": _dict(confusion.get("column_totals")),
                "unknown_label_case_ids": _list(confusion.get("unknown_label_case_ids")),
            },
            blockers=confusion_blockers,
        ),
        _gate(
            "bootstrap_ci",
            "support_ready_not_claim_bearing" if not bootstrap_blockers else "blocked",
            artifact=paths["v2_analysis"].relative_to(ROOT).as_posix(),
            evidence={
                "source": stats.get("source", ""),
                "intervals": bootstrap,
            },
            blockers=bootstrap_blockers,
        ),
        _gate(
            "threshold_sensitivity",
            "passed"
            if threshold_claim_ready
            else "support_ready_not_claim_bearing"
            if threshold_support_executed
            or threshold_claim_bearing_executed
            else "blocked",
            artifact=paths["threshold_freeze"].relative_to(ROOT).as_posix(),
            evidence={
                "source": threshold_results.get("source", stats.get("source", "")),
                "threshold_results_source": threshold_results.get("source", ""),
                "threshold_results_source_artifact": threshold_results.get("source_artifact", ""),
                "primary_threshold": _dict(threshold_freeze.get("threshold_freeze")).get("primary_threshold"),
                "threshold_at_0_5": threshold_results.get("threshold_at_primary", threshold_at_0_5),
                "design_oracle_threshold_at_0_5": threshold_at_0_5,
                "threshold_at_primary": threshold_results.get("threshold_at_primary", threshold_at_0_5),
                "threshold_sweep_count": int(threshold_results.get("threshold_sweep_count", len(threshold_sweep)) or 0),
                "threshold_freeze_status": _dict(threshold_freeze.get("threshold_freeze")).get("status"),
                "threshold_plan_status": threshold_plan.get("status"),
                "threshold_results_status": threshold_results.get("status"),
                "threshold_results_claim_bearing": threshold_results.get("claim_bearing"),
                "threshold_sensitivity_case_count": threshold_results.get("threshold_sensitivity_case_count", stats.get("threshold_sensitivity_case_count", 0)),
                "threshold_sensitivity_positive_case_count": threshold_results.get("threshold_sensitivity_positive_case_count", stats.get("threshold_sensitivity_positive_case_count", 0)),
                "threshold_sensitivity_negative_case_count": threshold_results.get("threshold_sensitivity_negative_case_count", stats.get("threshold_sensitivity_negative_case_count", 0)),
                "claim_bearing_statistics_required": True,
                "support_ready": threshold_execution_ready,
                "claim_ready": threshold_claim_ready,
                "claim_ready_requires_completed_dual_curator_adjudication": True,
            },
            blockers=threshold_blockers,
            support_ready=threshold_execution_ready,
            claim_ready=threshold_claim_ready,
            support_ready_reason=(
                "threshold_sensitivity_machine_statistics_executed"
                if threshold_execution_ready
                else "threshold_sensitivity_machine_statistics_missing_or_incomplete"
            ),
            claim_ready_false_reasons=[]
            if threshold_claim_ready
            else (
                ["completed_dual_curator_adjudication_missing_or_not_claim_table_admissible"]
                if threshold_claim_bearing_executed and not adjudication_claim_ready
                else ["claim_bearing_provider_threshold_records_missing_or_not_formally_allowed"]
                if threshold_execution_ready
                else threshold_blockers
            ),
        ),
        _gate(
            "confusion_bootstrap_threshold_sensitivity",
            "support_ready_not_claim_bearing"
            if stats.get("confusion_matrix_design_oracle") and stats.get("bootstrap_intervals") and threshold_plan
            else "blocked",
            artifact=paths["v2_analysis"].relative_to(ROOT).as_posix(),
            evidence={
                "confusion_matrix_present": bool(stats.get("confusion_matrix_design_oracle")),
                "bootstrap_intervals_present": bool(stats.get("bootstrap_intervals")),
                "threshold_sweep_present": bool(stats.get("threshold_sweep")),
                "threshold_freeze_present": bool(threshold_plan),
            },
            blockers=[] if stats.get("bootstrap_intervals") and threshold_plan else ["statistical_sensitivity_artifacts_missing"],
        ),
        _gate(
            "executable_final_conjunction",
            "passed" if not executable_final_blockers and adjudication_claim_ready else "support_ready_not_claim_bearing" if not executable_final_blockers else "blocked",
            artifact=paths["executable_conjunction"].relative_to(ROOT).as_posix(),
            evidence={
                "case_count": executable_case_count,
                "pass_count": executable_pass_count,
                "blocked_count": executable_blocked_count,
                "adjudication_complete": bool(adjudication.get("adjudication_complete", False)),
                "adjudication_is_checked_by_dual_curator_gate": True,
                "support_ready": not executable_final_blockers,
                "claim_ready": not executable_final_blockers and adjudication_claim_ready,
                "claim_ready_requires_completed_dual_curator_adjudication": True,
            },
            blockers=executable_final_blockers,
            support_ready=not executable_final_blockers,
            claim_ready=not executable_final_blockers and adjudication_claim_ready,
            support_ready_reason=(
                "executable_conjunction_machine_subgate_passed"
                if not executable_final_blockers
                else "executable_conjunction_machine_subgate_blocked"
            ),
            claim_ready_false_reasons=[]
            if not executable_final_blockers and adjudication_claim_ready
            else (
                ["completed_dual_curator_adjudication_missing_or_not_claim_table_admissible"]
                if not executable_final_blockers
                else executable_final_blockers
            ),
        ),
    ]
    blockers = [
        f"{gate['gate']}:{blocker}"
        for gate in gates
        for blocker in gate["blockers"]
    ]
    missing_artifacts = [name for name, path in paths.items() if not path.exists()]
    artifact_blockers = [f"artifact_missing:{name}" for name in missing_artifacts]
    blockers = artifact_blockers + blockers
    claim_blockers: list[str] = []
    for blocker in blockers + (
        [] if adjudication_claim_ready else ["adjudication_dependency:completed_dual_curator_adjudication_missing_or_not_claim_table_admissible"]
    ):
        if blocker not in claim_blockers:
            claim_blockers.append(blocker)
    machine_gate_names = {
        "hard_ambiguity_retention",
        "laundering_attack_support",
        "spoofability_attack_support",
        "attack_stress_support",
        "marker_hidden_prompt_packet",
        "marker_hidden_obfuscation_stress",
        "confusion_matrix",
        "bootstrap_ci",
        "threshold_sensitivity",
        "confusion_bootstrap_threshold_sensitivity",
        "executable_final_conjunction",
    }
    machine_blockers = [
        f"{gate['gate']}:{blocker}"
        for gate in gates
        if gate["gate"] in machine_gate_names and not gate.get("support_ready")
        for blocker in gate["blockers"]
    ]
    human_adjudication_blockers = [
        "completed_dual_curator_adjudication_missing_or_not_claim_table_admissible"
    ] if not adjudication_claim_ready else []
    machine_support_ready = not artifact_blockers and not machine_blockers
    claim_ready = machine_support_ready and adjudication_claim_ready and not blockers
    return {
        "schema_version": "sealaudit_attack_statistics_gate_v1",
        "benchmark": "WatermarkBackdoorBench-v2",
        "claim_role": "support_not_claim_bearing",
        "formal_claim_allowed": False,
        "support_ready": machine_support_ready,
        "claim_ready": claim_ready,
        "machine_side_blockers": machine_blockers,
        "human_adjudication_blockers": human_adjudication_blockers,
        "claim_ready_false_reasons": []
        if claim_ready
        else (
            human_adjudication_blockers
            if machine_support_ready and human_adjudication_blockers
            else claim_blockers
        ),
        "case_count": int(summary.get("case_count", 0) or 0),
        "gates": gates,
        "overall_status": "blocked",
        "remaining_blockers": claim_blockers,
        "missing_artifacts": missing_artifacts,
        "claim_policy": {
            "support_ready_not_claim_bearing_means_appendix_or_diagnostic_only": True,
            "main_claim_requires_executed_marker_hidden_obfuscation_and_adjudicated_executable_conjunction": True,
            "provider_marker_hidden_and_threshold_results_remain_support_until_completed_blinded_adjudication": True,
        },
        "artifacts": {name: _artifact(path) for name, path in paths.items()},
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SealAudit attack/statistics gate summary.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = build_gate()
    if args.check:
        if not args.output.exists():
            raise SystemExit(f"missing attack/statistics gate: {args.output}")
        observed = json.loads(args.output.read_text(encoding="utf-8"))
        if observed != payload:
            raise SystemExit(f"stale attack/statistics gate: {args.output}")
        print(f"attack/statistics gate check passed: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
