from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT


SCHEMA_VERSION = "sealaudit_v2_adjudication_promotion_gate_v1"
DEFAULT_OUTPUT = ARTIFACTS / "v2_adjudication_promotion_gate.json"
BENCHMARK = "WatermarkBackdoorBench-v2"
REQUIRED_EXECUTABLE_GATES = (
    "static_safety",
    "semantic_drift",
    "laundering",
    "spoofability",
    "provider_judge",
    "baseline_control_evidence",
)
REQUIRED_THRESHOLD_METRICS = (
    "precision",
    "recall",
    "f1",
    "accuracy",
    "false_positive",
    "false_negative",
)
REQUIRED_ATTACK_GATES = (
    "hard_ambiguity_retention",
    "laundering_attack_support",
    "spoofability_attack_support",
    "attack_stress_support",
    "marker_hidden_obfuscation_stress",
    "confusion_matrix",
    "bootstrap_ci",
    "threshold_sensitivity",
    "confusion_bootstrap_threshold_sensitivity",
    "executable_final_conjunction",
)
REQUIRED_MARKER_HIDDEN_RECORD_FIELDS = (
    "prompt_variant_id",
    "blind_case_id",
    "prompt_hash",
    "provider_response_parsed",
    "structured_provider_payload",
    "provider_verdict",
    "provider_positive_score",
    "posthoc_expected_verdict_alignment",
)
INPUT_ARTIFACTS = {
    "aggregate_results": "artifacts/generated/aggregate_results.json",
    "blinded_adjudication_ledger": "artifacts/generated/blinded_adjudication_ledger.json",
    "completed_adjudication_ingest_gate": "artifacts/generated/completed_adjudication_ingest_gate.json",
    "threshold_freeze_report": "artifacts/generated/threshold_freeze_report.json",
    "rubric_ablation_report": "artifacts/generated/rubric_ablation_report.json",
    "executable_adapter_conjunction": "artifacts/generated/executable_adapter_conjunction.json",
    "attack_statistics_gate": "artifacts/generated/attack_statistics_gate.json",
}


def _resolve(path: str | Path, root: Path = ROOT) -> Path:
    resolved = Path(path)
    return resolved if resolved.is_absolute() else root / resolved


def _relative(path: Path, root: Path = ROOT) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def _load_artifacts(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    payloads: dict[str, Any] = {}
    records: dict[str, dict[str, Any]] = {}
    for name, rel_path in INPUT_ARTIFACTS.items():
        path = root / rel_path
        record: dict[str, Any] = {
            "path": rel_path,
            "exists": path.exists(),
            "sha256": _sha256(path),
            "json_type": "missing",
            "schema_version": "",
        }
        payload: Any = None
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    record["json_type"] = "object"
                    record["schema_version"] = str(payload.get("schema_version", ""))
                elif isinstance(payload, list):
                    record["json_type"] = "list"
                else:
                    record["json_type"] = type(payload).__name__
            except (OSError, json.JSONDecodeError) as exc:
                record["json_type"] = "invalid"
                record["load_error"] = str(exc)
        payloads[name] = payload
        records[name] = record
    return payloads, records


def _gate(
    gate_id: str,
    *,
    passed: bool,
    evidence: dict[str, Any],
    blockers: list[str],
    status: str | None = None,
) -> dict[str, Any]:
    return {
        "gate": gate_id,
        "status": status or ("passed" if passed else "blocked"),
        "pass": passed,
        "required_for_final_claim": True,
        "evidence": evidence,
        "blockers": blockers,
    }


def _artifact_presence_gate(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    blockers: list[str] = []
    for name, record in records.items():
        if not record["exists"]:
            blockers.append(f"artifact_missing:{name}")
        elif record["json_type"] == "invalid":
            blockers.append(f"artifact_invalid_json:{name}")
        elif record["json_type"] not in {"object", "list"}:
            blockers.append(f"artifact_unexpected_json_type:{name}")
    return _gate(
        "required_input_artifacts",
        passed=not blockers,
        evidence={"artifact_count": len(records), "artifacts": records},
        blockers=blockers,
    )


def _aggregate_gate(aggregate: dict[str, Any]) -> dict[str, Any]:
    source_v2_run_id = str(aggregate.get("source_v2_run_id", "")).strip()
    prompt_rubric_version = str(aggregate.get("prompt_rubric_version", "")).strip()
    blockers: list[str] = []
    if not source_v2_run_id:
        blockers.append("aggregate_results_missing_source_v2_run_id")
    if aggregate.get("prompt_blinding_gate_pass") is not True:
        blockers.append("aggregate_results_prompt_blinding_gate_not_passed")
    if aggregate.get("prompt_rubric_version_gate_pass") is not True:
        blockers.append("aggregate_results_prompt_rubric_gate_not_passed")
    if prompt_rubric_version and prompt_rubric_version != "label_hidden_marker_rubric_v3":
        blockers.append("aggregate_results_unexpected_prompt_rubric_version")
    return _gate(
        "aggregate_results_v2_alignment",
        passed=not blockers,
        evidence={
            "final_claim_status": aggregate.get("final_claim_status", ""),
            "review_ready": bool(aggregate.get("review_ready", False)),
            "submission_closure_eligible": bool(aggregate.get("submission_closure_eligible", False)),
            "source_v2_run_id": source_v2_run_id,
            "prompt_blinding_policy": aggregate.get("prompt_blinding_policy", ""),
            "prompt_blinding_gate_pass": bool(aggregate.get("prompt_blinding_gate_pass", False)),
            "prompt_rubric_version": prompt_rubric_version,
            "prompt_rubric_version_gate_pass": bool(aggregate.get("prompt_rubric_version_gate_pass", False)),
            "note": "Aggregate readiness is advisory; v2 promotion requires every gate in this artifact to pass.",
        },
        blockers=blockers,
    )


def _visible_marker_mapping_gate(rubric: dict[str, Any], threshold: dict[str, Any]) -> dict[str, Any]:
    audit = _dict(rubric.get("current_prompt_field_audit"))
    plan = _dict(rubric.get("rubric_ablation_plan"))
    variants = [item for item in _list(plan.get("variants")) if isinstance(item, dict)]
    results = _dict(rubric.get("rubric_ablation_results"))
    metrics = _dict(results.get("metrics"))
    prompt_rubric_version = str(
        audit.get("prompt_rubric_version")
        or _dict(rubric.get("prompt_policy")).get("prompt_rubric_version")
        or threshold.get("prompt_rubric_version")
        or threshold.get("rubric_version")
        or ""
    )
    visible_variant_count = sum(
        1
        for variant in variants
        if variant.get("marker_requirements_visible") is True
        or variant.get("decision_precedence_marker_rules_visible") is True
    )
    marker_exposure_count = _int(audit.get("current_marker_requirement_exposure_count")) + _int(
        audit.get("current_rubric_marker_rule_exposure_count")
    )
    marker_hidden_executed = (
        results.get("claim_bearing") is True
        and _int(results.get("executed_record_count")) > 0
        and metrics.get("delta_vs_v3_label_hidden_marker_visible") is not None
    )
    mapping_visible = (
        prompt_rubric_version == "label_hidden_marker_rubric_v3"
        and (
            marker_exposure_count > 0
            or visible_variant_count > 0
            or audit.get("current_marker_hidden_prompt_gate_pass") is False
        )
    )
    blockers: list[str] = []
    if mapping_visible and not marker_hidden_executed:
        blockers.append("v3_visible_marker_to_label_mapping_unresolved")
    return _gate(
        "v3_visible_marker_to_label_mapping",
        passed=not blockers,
        evidence={
            "prompt_rubric_version": prompt_rubric_version,
            "current_marker_hidden_prompt_gate_pass": audit.get("current_marker_hidden_prompt_gate_pass"),
            "current_marker_requirement_exposure_count": _int(
                audit.get("current_marker_requirement_exposure_count")
            ),
            "current_rubric_marker_rule_exposure_count": _int(
                audit.get("current_rubric_marker_rule_exposure_count")
            ),
            "visible_marker_rule_variant_count": visible_variant_count,
            "marker_hidden_ablation_claim_bearing": bool(results.get("claim_bearing", False)),
            "marker_hidden_ablation_executed_record_count": _int(results.get("executed_record_count")),
            "mapping_visible": mapping_visible,
        },
        blockers=blockers,
    )


def _adjudication_gate(ledger: dict[str, Any]) -> dict[str, Any]:
    roles = _dict(ledger.get("roles"))
    rubric = _dict(ledger.get("rubric"))
    summary = _dict(ledger.get("summary"))
    claim_gate = _dict(ledger.get("claim_gate"))
    curators = [item for item in _list(roles.get("curators")) if isinstance(item, dict)]
    adjudicator = _dict(roles.get("adjudicator"))
    case_count = _int(summary.get("case_count"))
    curator_slot_count = _int(summary.get("curator_label_slot_count"))
    human_label_count = _int(summary.get("human_curator_label_count"))
    pending_human_label_count = _int(summary.get("pending_human_label_count"))
    pending_agreement_count = _int(summary.get("pending_agreement_count"))
    adjudication_complete_count = _int(summary.get("adjudication_complete_count"))
    entries = [item for item in _list(ledger.get("entries")) if isinstance(item, dict)]
    agreement_records = [
        item
        for item in _list(_dict(ledger.get("agreement_disagreement_ledger")).get("records"))
        if isinstance(item, dict)
    ]
    structural_entry_issues: list[str] = []
    human_pending_entry_issues: list[str] = []
    blockers: list[str] = []
    if len(curators) < 2 or _int(rubric.get("minimum_independent_curators")) < 2:
        blockers.append("missing_dual_curator_roles")
    if not adjudicator.get("adjudicator_id"):
        blockers.append("missing_adjudicator_role")
    if curator_slot_count <= 0 or human_label_count < curator_slot_count or pending_human_label_count:
        blockers.append("dual_curator_labels_missing")
    if pending_agreement_count:
        blockers.append("curator_agreement_or_disagreement_missing")
    if ledger.get("adjudication_complete") is not True or adjudication_complete_count < case_count:
        blockers.append("adjudication_pending")
    if ledger.get("admitted_to_claim_table") is not True or claim_gate.get("admitted_to_claim_table") is not True:
        blockers.append("adjudication_not_admitted_to_claim_table")
    if len(entries) != case_count:
        blockers.append("adjudication_entry_level_records_missing_or_incomplete")
        structural_entry_issues.append(f"entry_count:{len(entries)}_expected:{case_count}")
    if len(agreement_records) != case_count:
        blockers.append("adjudication_agreement_ledger_records_missing_or_incomplete")
        structural_entry_issues.append(f"agreement_record_count:{len(agreement_records)}_expected:{case_count}")
    for index, entry in enumerate(entries[: max(case_count, 0)], start=1):
        curation = _dict(entry.get("curation"))
        slots = [slot for slot in _list(curation.get("curator_slots")) if isinstance(slot, dict)]
        adjudication = _dict(entry.get("adjudication"))
        entry_claim_gate = _dict(entry.get("claim_gate"))
        if len(slots) < 2:
            structural_entry_issues.append(f"entry_{index}:curator_slots_missing")
            continue
        if any(
            not _nonempty(slot.get("label"))
            or not (
                _nonempty(slot.get("rationale_hash"))
                or _nonempty(slot.get("rationale_sha256"))
            )
            for slot in slots[:2]
        ):
            human_pending_entry_issues.append(f"entry_{index}:curator_label_or_rationale_missing")
        if adjudication.get("adjudication_complete") is not True:
            human_pending_entry_issues.append(f"entry_{index}:adjudication_incomplete")
        if not _nonempty(adjudication.get("adjudicated_label")):
            human_pending_entry_issues.append(f"entry_{index}:adjudicated_label_missing")
        if entry_claim_gate.get("admitted_to_claim_table") is not True:
            human_pending_entry_issues.append(f"entry_{index}:claim_gate_not_admitted")
        if len(structural_entry_issues) + len(human_pending_entry_issues) >= 8:
            break
    if structural_entry_issues:
        blockers.append("adjudication_entry_level_validation_failed")
    if blockers:
        blockers.insert(0, "dual_curator_adjudicator_evidence_incomplete")
    return _gate(
        "dual_curator_adjudicator",
        passed=not blockers,
        evidence={
            "curator_role_count": len(curators),
            "minimum_independent_curators": _int(rubric.get("minimum_independent_curators")),
            "adjudicator_id_present": bool(adjudicator.get("adjudicator_id")),
            "case_count": case_count,
            "curator_label_slot_count": curator_slot_count,
            "human_curator_label_count": human_label_count,
            "pending_human_label_count": pending_human_label_count,
            "pending_agreement_count": pending_agreement_count,
            "adjudication_complete": bool(ledger.get("adjudication_complete", False)),
            "adjudication_complete_count": adjudication_complete_count,
            "admitted_to_claim_table": bool(ledger.get("admitted_to_claim_table", False)),
            "claim_gate_blockers": _list(claim_gate.get("blockers")),
            "entry_count": len(entries),
            "agreement_record_count": len(agreement_records),
            "structural_entry_issue_sample": structural_entry_issues[:8],
            "human_pending_entry_issue_sample": human_pending_entry_issues[:8],
        },
        blockers=blockers,
    )


def _completed_adjudication_ingest_gate(gate: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    upstream_blockers = [str(item) for item in _list(gate.get("blockers"))]
    case_count = _int(gate.get("case_count"))
    curator_label_slot_count = _int(gate.get("curator_label_slot_count"))
    curator_label_count = _int(gate.get("curator_label_count"))
    claim_table_admissible_count = _int(gate.get("claim_table_admissible_count"))
    if gate.get("schema_version") != "sealaudit_completed_adjudication_ingest_gate_v1":
        blockers.append("completed_adjudication_ingest_schema_mismatch")
    if gate.get("status") != "passed" or gate.get("final_claim_promotion_allowed") is not True:
        blockers.append("completed_adjudication_ingest_gate_blocked")
    if case_count != 320:
        blockers.append(f"completed_adjudication_case_count_mismatch:{case_count}")
    if curator_label_slot_count != 640 or curator_label_count != 640:
        blockers.append("completed_adjudication_dual_curator_labels_incomplete")
    if claim_table_admissible_count != 320:
        blockers.append(f"completed_adjudication_claim_table_count_mismatch:{claim_table_admissible_count}")
    if upstream_blockers:
        blockers.append("completed_adjudication_ingest_has_remaining_blockers")
    if not _nonempty(gate.get("completed_claim_ledger_sha256")):
        blockers.append("completed_claim_ledger_sha256_missing")
    return _gate(
        "completed_adjudication_ingest",
        passed=not blockers,
        evidence={
            "status": gate.get("status", ""),
            "final_claim_promotion_allowed": bool(gate.get("final_claim_promotion_allowed", False)),
            "case_count": case_count,
            "curator_label_slot_count": curator_label_slot_count,
            "curator_label_count": curator_label_count,
            "claim_table_admissible_count": claim_table_admissible_count,
            "agreement_count": _int(gate.get("agreement_count")),
            "disagreement_count": _int(gate.get("disagreement_count")),
            "adjudication_complete_count": _int(gate.get("adjudication_complete_count")),
            "upstream_blocker_count": len(upstream_blockers),
            "completed_claim_ledger_sha256": gate.get("completed_claim_ledger_sha256", ""),
        },
        blockers=blockers,
    )


def _executable_gate(executable: dict[str, Any]) -> dict[str, Any]:
    policy = _dict(executable.get("conjunction_policy"))
    analysis = _dict(executable.get("case_analysis"))
    gate_summary = _dict(analysis.get("gate_summary"))
    case_count = _int(analysis.get("record_count")) or _int(policy.get("pass_count")) + _int(policy.get("blocked_count"))
    pass_count = _int(policy.get("pass_count"))
    blocked_count = _int(policy.get("blocked_count"))
    records = [item for item in _list(analysis.get("records")) if isinstance(item, dict)]
    blockers: list[str] = []
    if not executable:
        blockers.append("executable_adapter_conjunction_missing_or_blocked")
    if policy.get("claim_table_admissible") is not True:
        blockers.append("executable_adapter_conjunction_not_claim_table_admissible")
    if case_count <= 0 or pass_count != case_count or blocked_count != 0:
        blockers.append("executable_adapter_conjunction_missing_or_blocked")
    if _int(analysis.get("final_conjunction_pass_count")) != case_count:
        blockers.append("executable_final_conjunction_not_all_cases_passed")
    if _int(analysis.get("candidate_executable_code_present_count")) != case_count:
        blockers.append("candidate_executable_code_not_present_for_all_cases")
    record_issues: list[str] = []
    if len(records) != case_count:
        blockers.append("executable_case_analysis_records_missing_or_incomplete")
        record_issues.append(f"record_count:{len(records)}_expected:{case_count}")
    for index, record in enumerate(records[: max(case_count, 0)], start=1):
        statuses = _dict(record.get("gate_statuses"))
        if record.get("final_conjunction_pass") is not True:
            record_issues.append(f"record_{index}:final_conjunction_not_passed")
        if record.get("claim_table_admissible") is not True:
            record_issues.append(f"record_{index}:claim_table_not_admissible")
        if _list(record.get("blockers")):
            record_issues.append(f"record_{index}:record_blockers_not_empty")
        missing_gates = [gate for gate in REQUIRED_EXECUTABLE_GATES if gate not in statuses]
        if missing_gates:
            record_issues.append(f"record_{index}:missing_gates:{','.join(missing_gates[:3])}")
        for gate_name in REQUIRED_EXECUTABLE_GATES:
            gate_record = _dict(statuses.get(gate_name))
            if gate_record.get("pass") is not True:
                record_issues.append(f"record_{index}:gate_not_passed:{gate_name}")
                continue
            if _list(gate_record.get("blockers")):
                record_issues.append(f"record_{index}:gate_blockers_not_empty:{gate_name}")
            evidence_rows = [item for item in _list(gate_record.get("evidence")) if isinstance(item, dict)]
            if not evidence_rows:
                record_issues.append(f"record_{index}:gate_evidence_missing:{gate_name}")
                continue
            if gate_name == "provider_judge" and not any(
                _nonempty(row.get("provider_response_sha256"))
                or _nonempty(row.get("provider_trace_sha256"))
                or _nonempty(row.get("raw_provider_response_sha256"))
                for row in evidence_rows
            ):
                record_issues.append(f"record_{index}:provider_judge_trace_hash_missing")
            if gate_name == "baseline_control_evidence" and not any(
                _nonempty(row.get("executed_control_outcomes"))
                or _nonempty(row.get("control_outcomes"))
                or _nonempty(row.get("baseline_control_sha256"))
                for row in evidence_rows
            ):
                record_issues.append(f"record_{index}:baseline_control_outcomes_missing")
        if len(record_issues) >= 8:
            break
    if record_issues:
        blockers.append("executable_record_level_validation_failed")
    gate_evidence: dict[str, Any] = {}
    for gate_name in REQUIRED_EXECUTABLE_GATES:
        summary = _dict(gate_summary.get(gate_name))
        gate_pass_count = _int(summary.get("pass_count"))
        gate_blocked_count = _int(summary.get("blocked_count"))
        gate_evidence[gate_name] = {
            "pass_count": gate_pass_count,
            "blocked_count": gate_blocked_count,
            "status_counts": _dict(summary.get("status_counts")),
        }
        if gate_pass_count != case_count or gate_blocked_count != 0:
            blockers.append(f"executable_gate_blocked:{gate_name}")
    blockers = list(dict.fromkeys(blockers))
    return _gate(
        "executable_adapter_conjunction",
        passed=not blockers,
        evidence={
            "case_count": case_count,
            "pass_count": pass_count,
            "blocked_count": blocked_count,
            "claim_table_admissible": bool(policy.get("claim_table_admissible", False)),
            "candidate_executable_code_present_count": _int(
                analysis.get("candidate_executable_code_present_count")
            ),
            "final_conjunction_pass_count": _int(analysis.get("final_conjunction_pass_count")),
            "case_analysis_record_count": len(records),
            "record_level_issue_sample": record_issues[:8],
            "required_gates": list(REQUIRED_EXECUTABLE_GATES),
            "gate_summary": gate_evidence,
        },
        blockers=blockers,
    )


def _marker_hidden_ablation_gate(rubric: dict[str, Any]) -> dict[str, Any]:
    subset = _dict(rubric.get("marker_hidden_subset"))
    prompt_surface = _dict(rubric.get("marker_hidden_prompt_surface_audit"))
    results = _dict(rubric.get("rubric_ablation_results"))
    metrics = _dict(results.get("metrics"))
    plan = _dict(rubric.get("rubric_ablation_plan"))
    variants = [item for item in _list(plan.get("variants")) if isinstance(item, dict)]
    marker_hidden_variants = [
        variant
        for variant in variants
        if variant.get("marker_requirements_visible") is False
        and variant.get("decision_precedence_marker_rules_visible") is False
    ]
    executed_record_count = _int(results.get("executed_record_count"))
    executed_variant_count = _int(results.get("executed_variant_count"))
    records = [item for item in _list(results.get("records")) if isinstance(item, dict)]
    subset_case_count = _int(subset.get("case_count"))
    expected_record_count = subset_case_count * max(1, len(variants)) if subset_case_count else 0
    pair_keys: set[tuple[str, str]] = set()
    record_issues: list[str] = []
    for index, record in enumerate(records, start=1):
        missing = [field for field in REQUIRED_MARKER_HIDDEN_RECORD_FIELDS if not _nonempty(record.get(field))]
        if not (_nonempty(record.get("raw_provider_response")) or _nonempty(record.get("raw_provider_response_sha256"))):
            missing.append("raw_provider_response_or_sha256")
        key = (str(record.get("prompt_variant_id", "")), str(record.get("blind_case_id", "")))
        if key in pair_keys:
            record_issues.append(f"record_{index}:duplicate_variant_case")
        pair_keys.add(key)
        if missing:
            record_issues.append(f"record_{index}:missing_" + ",".join(missing[:6]))
        if record.get("posthoc_expected_verdict_join_only_after_provider_response") is not True:
            record_issues.append(f"record_{index}:posthoc_join_guard_missing")
        if len(record_issues) >= 8:
            break
    blockers: list[str] = []
    if prompt_surface.get("marker_hidden_prompt_gate_pass") is not True:
        blockers.append("marker_hidden_prompt_surface_gate_not_passed")
    if results.get("status") not in {"executed", "completed", "passed"}:
        blockers.append("marker_hidden_rubric_ablation_not_executed")
    if results.get("claim_bearing") is not True:
        blockers.append("rubric_ablation_not_claim_bearing")
    if executed_record_count <= 0 or executed_variant_count < max(1, len(marker_hidden_variants)):
        blockers.append("marker_hidden_ablation_records_missing")
    if len(records) != executed_record_count:
        blockers.append("marker_hidden_ablation_record_count_mismatch")
    if expected_record_count and executed_record_count != expected_record_count:
        blockers.append("marker_hidden_ablation_expected_variant_case_coverage_missing")
    if record_issues:
        blockers.append("marker_hidden_ablation_record_level_validation_failed")
    if metrics.get("delta_vs_v3_label_hidden_marker_visible") is None:
        blockers.append("marker_hidden_delta_metric_missing")
    if metrics.get("threshold_sensitivity_on_threshold_fit_subset") is None:
        blockers.append("marker_hidden_threshold_sensitivity_metric_missing")
    return _gate(
        "marker_hidden_rubric_ablation",
        passed=not blockers,
        evidence={
            "marker_hidden_subset_status": subset.get("status", ""),
            "marker_hidden_subset_case_count": _int(subset.get("case_count")),
            "marker_hidden_prompt_surface_gate_pass": bool(prompt_surface.get("marker_hidden_prompt_gate_pass", False)),
            "marker_hidden_prompt_count": _int(prompt_surface.get("prompt_count")),
            "marker_hidden_prompt_leak_count": _int(prompt_surface.get("marker_value_leak_count"))
            + _int(prompt_surface.get("scheme_descriptor_leak_count"))
            + _int(prompt_surface.get("case_json_forbidden_field_failure_count")),
            "planned_marker_hidden_variant_count": len(marker_hidden_variants),
            "planned_total_variant_count": len(variants),
            "results_status": results.get("status", ""),
            "claim_bearing": bool(results.get("claim_bearing", False)),
            "executed_variant_count": executed_variant_count,
            "executed_record_count": executed_record_count,
            "record_count": len(records),
            "expected_record_count": expected_record_count,
            "unique_variant_case_pairs": len(pair_keys),
            "record_level_issue_sample": record_issues[:8],
            "delta_vs_visible_v3_present": metrics.get("delta_vs_v3_label_hidden_marker_visible") is not None,
            "threshold_sensitivity_metric_present": metrics.get("threshold_sensitivity_on_threshold_fit_subset")
            is not None,
        },
        blockers=blockers,
    )


def _attack_gate_by_name(attack: dict[str, Any], name: str) -> dict[str, Any]:
    for item in _list(attack.get("gates")):
        if isinstance(item, dict) and item.get("gate") == name:
            return item
    return {}


def _threshold_sensitivity_gate(threshold: dict[str, Any], attack: dict[str, Any]) -> dict[str, Any]:
    freeze = _dict(threshold.get("threshold_freeze"))
    plan = _dict(threshold.get("threshold_sensitivity_plan"))
    fit_population = _dict(plan.get("fit_population"))
    stress_population = _dict(plan.get("stress_population"))
    integrity = _dict(threshold.get("integrity_checks"))
    metrics = [str(item) for item in _list(plan.get("metrics"))]
    sweep_grid = _list(plan.get("sweep_grid"))
    attack_threshold = _attack_gate_by_name(attack, "threshold_sensitivity")
    attack_evidence = _dict(attack_threshold.get("evidence"))
    threshold_sweep_count = _int(attack_evidence.get("threshold_sweep_count"))
    blockers: list[str] = []
    if freeze.get("status") != "frozen":
        blockers.append("threshold_freeze_not_frozen")
    if freeze.get("no_result_tuning") is not True:
        blockers.append("threshold_freeze_allows_result_tuning")
    plan_status = str(plan.get("status", ""))
    claim_ready_plan_statuses = {"executed", "completed", "passed"}
    support_ready_plan_statuses = {"predeclared_plan_only", "executed_support_only"}
    if plan_status not in support_ready_plan_statuses.union(claim_ready_plan_statuses):
        blockers.append("threshold_sensitivity_plan_missing")
    if plan_status == "executed_support_only":
        blockers.append("threshold_sensitivity_executed_support_only_requires_claim_bearing_adjudication_join")
    elif plan_status not in claim_ready_plan_statuses:
        blockers.append("threshold_sensitivity_not_executed_for_claim")
    missing_metrics = sorted(set(REQUIRED_THRESHOLD_METRICS).difference(metrics))
    if missing_metrics:
        blockers.append("threshold_sensitivity_metrics_missing:" + ",".join(missing_metrics))
    if len(sweep_grid) < 3:
        blockers.append("threshold_sensitivity_sweep_grid_missing")
    if fit_population.get("hard_ambiguity_included") is not False:
        blockers.append("hard_ambiguity_included_in_threshold_fit")
    if _int(fit_population.get("positive_case_count")) <= 0:
        blockers.append("threshold_sensitivity_positive_cases_missing")
    if _int(fit_population.get("negative_case_count")) <= 0:
        blockers.append("threshold_sensitivity_negative_cases_missing")
    if fit_population.get("threshold_selection_allowed") is not False:
        blockers.append("threshold_sensitivity_population_allows_threshold_selection")
    if stress_population.get("threshold_fit_allowed") is not False:
        blockers.append("hard_ambiguity_stress_threshold_fit_not_blocked")
    if integrity.get("no_threshold_change_for_result_improvement") is not True:
        blockers.append("threshold_result_tuning_guard_missing")
    if not attack_threshold or attack_threshold.get("status") == "blocked":
        blockers.append("attack_statistics_threshold_sensitivity_missing_or_blocked")
    if attack_threshold.get("status") != "passed":
        blockers.append("attack_statistics_threshold_sensitivity_not_claim_bearing")
    if threshold_sweep_count and len(sweep_grid) and threshold_sweep_count != len(sweep_grid):
        blockers.append("threshold_sweep_count_mismatch")
    return _gate(
        "threshold_sensitivity",
        passed=not blockers,
        evidence={
            "threshold_freeze_status": freeze.get("status", ""),
            "no_result_tuning": bool(freeze.get("no_result_tuning", False)),
            "primary_threshold": _float(freeze.get("primary_threshold")),
            "plan_status": plan.get("status", ""),
            "sweep_grid_count": len(sweep_grid),
            "required_metrics": list(REQUIRED_THRESHOLD_METRICS),
            "observed_metrics": metrics,
            "fit_population_case_count": _int(fit_population.get("case_count")),
            "fit_population_positive_case_count": _int(fit_population.get("positive_case_count")),
            "fit_population_negative_case_count": _int(fit_population.get("negative_case_count")),
            "fit_population_threshold_selection_allowed": fit_population.get("threshold_selection_allowed"),
            "fit_population_hard_ambiguity_included": fit_population.get("hard_ambiguity_included"),
            "stress_population_case_count": _int(stress_population.get("case_count")),
            "stress_population_threshold_fit_allowed": stress_population.get("threshold_fit_allowed"),
            "attack_statistics_threshold_gate_status": attack_threshold.get("status", ""),
            "attack_statistics_threshold_sweep_count": threshold_sweep_count,
        },
        blockers=blockers,
    )


def _attack_statistics_formal_gate(attack: dict[str, Any]) -> dict[str, Any]:
    remaining_blockers = [str(item) for item in _list(attack.get("remaining_blockers"))]
    gates = [item for item in _list(attack.get("gates")) if isinstance(item, dict)]
    gate_ids = {str(item.get("gate")) for item in gates}
    missing_gate_ids = sorted(set(REQUIRED_ATTACK_GATES).difference(gate_ids))
    blockers: list[str] = []
    if attack.get("schema_version") != "sealaudit_attack_statistics_gate_v1":
        blockers.append("attack_statistics_gate_schema_mismatch")
    if _int(attack.get("case_count")) != 320:
        blockers.append("attack_statistics_gate_case_count_not_320")
    if missing_gate_ids:
        blockers.append("attack_statistics_gate_missing_required_gates:" + ",".join(missing_gate_ids))
    if attack.get("formal_claim_allowed") is not True:
        blockers.append("attack_statistics_gate_blocks_formal_claim")
    if attack.get("overall_status") != "passed":
        blockers.append("attack_statistics_gate_not_passed")
    if remaining_blockers:
        blockers.append("attack_statistics_gate_has_remaining_blockers")
    return _gate(
        "attack_statistics_formal_claim",
        passed=not blockers,
        evidence={
            "formal_claim_allowed": bool(attack.get("formal_claim_allowed", False)),
            "overall_status": attack.get("overall_status", ""),
            "schema_version": attack.get("schema_version", ""),
            "case_count": _int(attack.get("case_count")),
            "required_gates": list(REQUIRED_ATTACK_GATES),
            "observed_gates": sorted(gate_ids),
            "missing_required_gates": missing_gate_ids,
            "remaining_blocker_count": len(remaining_blockers),
            "remaining_blockers": remaining_blockers,
            "claim_policy": _dict(attack.get("claim_policy")),
        },
        blockers=blockers,
    )


def build_gate(root: Path = ROOT) -> dict[str, Any]:
    payloads, artifact_records = _load_artifacts(root)
    aggregate = _dict(payloads["aggregate_results"])
    ledger = _dict(payloads["blinded_adjudication_ledger"])
    completed_adjudication = _dict(payloads["completed_adjudication_ingest_gate"])
    threshold = _dict(payloads["threshold_freeze_report"])
    rubric = _dict(payloads["rubric_ablation_report"])
    executable = _dict(payloads["executable_adapter_conjunction"])
    attack = _dict(payloads["attack_statistics_gate"])
    gates = [
        _artifact_presence_gate(artifact_records),
        _aggregate_gate(aggregate),
        _visible_marker_mapping_gate(rubric, threshold),
        _adjudication_gate(ledger),
        _completed_adjudication_ingest_gate(completed_adjudication),
        _executable_gate(executable),
        _marker_hidden_ablation_gate(rubric),
        _threshold_sensitivity_gate(threshold, attack),
        _attack_statistics_formal_gate(attack),
    ]
    blockers = [
        f"{gate['gate']}:{blocker}"
        for gate in gates
        for blocker in _list(gate.get("blockers"))
    ]
    final_claim_promotion_allowed = not blockers
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": BENCHMARK,
        "artifact_role": "v2_adjudication_executable_promotion_gate",
        "claim_role": "final_claim_promotion_gate",
        "final_claim_promotion_allowed": final_claim_promotion_allowed,
        "overall_status": "promotion_allowed" if final_claim_promotion_allowed else "promotion_blocked",
        "gate_policy": {
            "all_gates_required": True,
            "aggregate_results_cannot_override_v2_promotion_gate": True,
            "visible_v3_marker_to_label_mapping_blocks_final_claim": True,
            "dual_curator_and_adjudicator_required": True,
            "dual_curator_entry_level_records_required": True,
            "completed_adjudication_ingest_gate_required": True,
            "executable_adapter_conjunction_required": True,
            "marker_hidden_rubric_ablation_required": True,
            "marker_hidden_record_level_payloads_required": True,
            "threshold_sensitivity_required": True,
            "attack_statistics_gate_recomputed_inventory_required": True,
        },
        "gates": gates,
        "remaining_blockers": blockers,
        "blocked_final_claim_inputs": sorted(
            {
                gate["gate"]
                for gate in gates
                if _list(gate.get("blockers"))
            }
        ),
        "input_artifacts": artifact_records,
    }


def validate_payload(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append("schema_version_mismatch")
    gates = payload.get("gates")
    if not isinstance(gates, list) or not gates:
        issues.append("gates_missing")
        gates = []
    gate_ids = {str(item.get("gate")) for item in gates if isinstance(item, dict)}
    required = {
        "required_input_artifacts",
        "aggregate_results_v2_alignment",
        "v3_visible_marker_to_label_mapping",
        "dual_curator_adjudicator",
        "executable_adapter_conjunction",
        "marker_hidden_rubric_ablation",
        "threshold_sensitivity",
        "attack_statistics_formal_claim",
    }
    missing = sorted(required.difference(gate_ids))
    if missing:
        issues.append("missing_gates:" + ",".join(missing))
    blockers = payload.get("remaining_blockers")
    if not isinstance(blockers, list):
        issues.append("remaining_blockers_not_list")
        blockers = []
    if bool(payload.get("final_claim_promotion_allowed")) != (len(blockers) == 0):
        issues.append("promotion_flag_blocker_mismatch")
    policy = _dict(payload.get("gate_policy"))
    for key in (
        "visible_v3_marker_to_label_mapping_blocks_final_claim",
        "dual_curator_and_adjudicator_required",
        "executable_adapter_conjunction_required",
        "marker_hidden_rubric_ablation_required",
        "threshold_sensitivity_required",
        "dual_curator_entry_level_records_required",
        "marker_hidden_record_level_payloads_required",
        "attack_statistics_gate_recomputed_inventory_required",
    ):
        if policy.get(key) is not True:
            issues.append(f"policy_missing:{key}")
    return issues


def _render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=True) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or check the SealAudit v2 promotion gate.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = build_gate(ROOT)
    issues = validate_payload(payload)
    if issues:
        raise SystemExit("v2 promotion gate builder produced invalid payload: " + "; ".join(issues))
    output = _resolve(args.output, ROOT)
    rendered = _render(payload)
    if args.check:
        if not output.exists():
            raise SystemExit(f"v2 promotion gate missing: {_relative(output, ROOT)}")
        if output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"v2 promotion gate stale: {_relative(output, ROOT)}")
        print(
            json.dumps(
                {
                    "status": "ok",
                    "checked": _relative(output, ROOT),
                    "overall_status": payload["overall_status"],
                    "remaining_blocker_count": len(payload["remaining_blockers"]),
                },
                indent=2,
                ensure_ascii=True,
            )
        )
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "written",
                "path": _relative(output, ROOT),
                "overall_status": payload["overall_status"],
                "final_claim_promotion_allowed": payload["final_claim_promotion_allowed"],
                "remaining_blocker_count": len(payload["remaining_blockers"]),
            },
            indent=2,
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
