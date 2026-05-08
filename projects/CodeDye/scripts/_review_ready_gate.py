from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _truthy(value: Any) -> bool:
    return bool(value) and str(value).strip().lower() not in {"0", "false", "no", "none", "null", ""}


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


def _current_source_identity(artifacts: Path) -> dict[str, str]:
    full_eval_path = artifacts / "generated" / "full_eval_results.json"
    payload = _load_json(full_eval_path)
    operator_state = payload.get("operator_state", {})
    operator_state = dict(operator_state) if isinstance(operator_state, dict) else {}
    source_run_id = str(
        operator_state.get("canonical_source_run_id")
        or operator_state.get("run_id")
        or payload.get("run_id")
        or ""
    ).strip()
    source_sha256 = hashlib.sha256(full_eval_path.read_bytes()).hexdigest() if full_eval_path.exists() else ""
    return {
        "canonical_source_run_id": source_run_id,
        "source_full_eval_sha256": source_sha256,
    }


def _utility_first_gate_allows(artifacts: Path) -> bool:
    gate = _load_json(artifacts / "generated" / "utility_first_promotion_gate.json")
    baseline_gate = gate.get("baseline_downgrade_gate", {})
    baseline_gate = dict(baseline_gate) if isinstance(baseline_gate, dict) else {}
    official_baseline_admitted = _truthy(baseline_gate.get("official_baseline_admitted")) or (
        _truthy(baseline_gate.get("official_baseline_gate_pass"))
        and int(baseline_gate.get("official_runnable_baseline_count", 0) or 0) > 0
    )
    return (
        _truthy(gate.get("main_claim_admission_allowed"))
        and _truthy(gate.get("canonical_promotion_allowed"))
        and _truthy(gate.get("review_ready_claim_allowed"))
        and _truthy(baseline_gate.get("gate_pass"))
        and official_baseline_admitted
    )


def _is_downgradable_baseline_blocker(blocker: str) -> bool:
    value = str(blocker).strip()
    if value in DOWNGRADABLE_BASELINE_BLOCKERS:
        return True
    if value.startswith("first_failing_gate:"):
        return value.split(":", 1)[1] in DOWNGRADABLE_BASELINE_BLOCKERS
    return False


def _sample_selection_current(artifacts: Path) -> bool:
    sample = _load_json(artifacts / "generated" / "sample_selection_rerun_audit.json")
    return (
        str(sample.get("current_canonical_status", "")).strip()
        in {"pre_registered_utility_selection", "utility_preselection_no_contamination_winner_selection"}
        and sample.get("rerun_required") is False
        and not str(sample.get("closure_blocker", "")).strip()
    )


def _is_stale_self_latching_blocker(blocker: str, *, project: str, sample_selection_current: bool) -> bool:
    value = str(blocker).strip()
    if value in {"all_gates_pass", "first_failing_gate:all_gates_pass"}:
        return True
    if value.startswith(f"best_paper_cycle_gate_pending:{project}:"):
        return True
    if value.startswith(f"best_paper_cycle_first_p1_p2:"):
        return True
    if sample_selection_current and value == "legacy_sample_selection_requires_rerun":
        return True
    return False


def _best_paper_cycle_blockers(artifacts: Path, *, project: str) -> list[str]:
    ledger = {}
    for base in (artifacts.parent, artifacts.parent.parent, artifacts.parent.parent.parent):
        candidate = base / "best_paper_100_cycle_ledger.json"
        ledger = _load_json(candidate)
        if ledger:
            break
    if not ledger:
        return []
    policy = ledger.get("cycle_policy", {})
    policy = dict(policy) if isinstance(policy, dict) else {}
    projects = ledger.get("projects", {})
    project_state = dict(projects.get(project, {})) if isinstance(projects, dict) and isinstance(projects.get(project, {}), dict) else {}
    min_cycles = int(policy.get("minimum_total_cycles_before_deepseek_claim_run", 100) or 100)
    clean_required = int(policy.get("required_consecutive_clean_reviews", 10) or 10)
    cycles = int(project_state.get("total_review_improvement_cycles_completed", 0) or 0)
    clean = int(project_state.get("consecutive_clean_reviews", 0) or 0)
    allowed = (
        _truthy(project_state.get("deepseek_formal_run_allowed"))
        and cycles >= min_cycles
        and clean >= clean_required
    )
    if allowed:
        return []
    blockers = [f"best_paper_cycle_gate_pending:{project}:{cycles}/{min_cycles}_cycles:{clean}/{clean_required}_clean"]
    first = str(project_state.get("first_p1_p2", "")).strip()
    if first:
        blockers.append(f"best_paper_cycle_first_p1_p2:{first}")
    return blockers


def _scope_decision_allows_utility_rerun(
    artifacts: Path,
    *,
    run_id: str,
    rerun_purpose: str,
    finalize_canonical: bool,
) -> tuple[bool, list[str]]:
    if rerun_purpose != "utility_rematerialization":
        return False, []
    decision = _load_json(artifacts / "generated" / "baseline_scope_decision.json")
    blockers: list[str] = []
    if finalize_canonical:
        blockers.append("utility_rematerialization_cannot_finalize_canonical")
    if not decision:
        blockers.append("baseline_scope_decision_missing")
        return False, blockers
    if decision.get("schema_version") != "codedye_baseline_scope_decision_v1":
        blockers.append("baseline_scope_decision_schema_mismatch")
    decision_name = str(decision.get("decision", ""))
    if decision_name not in {
        "negative_baseline_audit_scope_preserves_main_table_blocker",
        "official_baseline_scope_resolves_main_table_blocker",
    }:
        blockers.append("baseline_scope_decision_unrecognized")
    if not _truthy(decision.get("machine_verifiable")) or not _truthy(decision.get("scope_decision_complete")):
        blockers.append("baseline_scope_decision_incomplete")
    if _truthy(decision.get("review_ready")) or _truthy(decision.get("experiment_entry_allowed")):
        blockers.append("baseline_scope_decision_misstates_review_ready")
    if _truthy(decision.get("claim_bearing_rerun_allowed")) or _truthy(decision.get("canonical_promotion_allowed")):
        blockers.append("baseline_scope_decision_allows_claim_bearing_use")
    if not _truthy(decision.get("utility_rematerialization_rerun_allowed")):
        blockers.append("utility_rematerialization_not_allowed_by_scope_decision")
    if str(decision.get("approved_provider", "")).strip().lower() != "deepseek":
        blockers.append("scope_decision_provider_not_deepseek")
    if str(decision.get("approved_provider_mode", "")).strip().lower() != "live":
        blockers.append("scope_decision_provider_mode_not_live")
    if str(decision.get("approved_run_id", "")).strip() != run_id:
        blockers.append("scope_decision_run_id_mismatch")
    preserved = {
        str(item)
        for item in decision.get("closure_blockers_preserved", [])
        if str(item).strip()
    } if isinstance(decision.get("closure_blockers_preserved", []), list) else set()
    required_preserved = ["legacy_sample_selection_requires_rerun"]
    if decision_name == "negative_baseline_audit_scope_preserves_main_table_blocker":
        required_preserved.insert(0, "official_main_table_runnable_baseline_missing")
    for required in required_preserved:
        if required not in preserved:
            blockers.append(f"scope_decision_does_not_preserve:{required}")
    if decision_name == "negative_baseline_audit_scope_preserves_main_table_blocker" and (
        _truthy(decision.get("baseline_gate_pass")) or int(decision.get("runnable_baseline_count", 0) or 0) != 0
    ):
        blockers.append("scope_decision_does_not_preserve_baseline_gap")
    if decision_name == "official_baseline_scope_resolves_main_table_blocker":
        if not _truthy(decision.get("baseline_gate_pass")):
            blockers.append("scope_decision_missing_official_baseline_gate")
        if int(decision.get("official_runnable_baseline_count", 0) or 0) <= 0:
            blockers.append("scope_decision_official_runnable_baseline_count_zero")
    if not _truthy(decision.get("sample_selection_rerun_required")):
        blockers.append("scope_decision_missing_sample_selection_rerun_need")
    issues = decision.get("scope_decision_issues", [])
    if isinstance(issues, list):
        blockers.extend(f"scope_decision_issue:{item}" for item in issues if str(item).strip())
    return not blockers, blockers


def _raw_payload_rehydration_allowed(
    artifacts: Path,
    *,
    run_id: str,
    rerun_purpose: str,
    finalize_canonical: bool,
    current_blockers: list[str],
) -> tuple[bool, list[str]]:
    if rerun_purpose != "raw_payload_rehydration":
        return False, []
    blockers: list[str] = []
    if finalize_canonical:
        blockers.append("raw_payload_rehydration_cannot_finalize_canonical")
    if not run_id.startswith("codedye_deepseek_raw_payload_rehydration_"):
        blockers.append("raw_payload_rehydration_run_id_must_be_prefixed")
    blocker_text = "\n".join(str(item) for item in current_blockers)
    raw_payload_gap_present = any(
        needle in blocker_text
        for needle in (
            "raw_provider_response_payloads_missing_normalized_payloads_only",
            "raw_provider_response_payloads_incomplete",
            "candidate_sample_schema_required_fields_missing",
            "provider_record_schema_required_fields_missing",
            "candidate_payload_schema_current_records_missing",
        )
    )
    if not raw_payload_gap_present:
        blockers.append("raw_payload_rehydration_requires_current_payload_schema_blocker")
    secret_gate = _load_json(artifacts / "generated" / "deepseek_live_secret_preflight_gate.json")
    preflight_status = str(secret_gate.get("status", "")).strip().lower()
    provider_ready = _truthy(secret_gate.get("provider_secret_ready"))
    non_claim_live_ready = _truthy(secret_gate.get("non_claim_live_provider_ready"))
    launchable_allowed = _truthy(secret_gate.get("launchable_allowed"))
    if not provider_ready:
        blockers.append("raw_payload_rehydration_requires_deepseek_secret_preflight")
    if not non_claim_live_ready:
        blockers.append("raw_payload_rehydration_requires_non_claim_live_provider_ready")
    if not launchable_allowed:
        blockers.append("raw_payload_rehydration_requires_launchable_preflight")
    if preflight_status.startswith("blocked") or preflight_status in {"fail", "failed"}:
        blockers.append(f"raw_payload_rehydration_preflight_status_blocked:{preflight_status or 'missing'}")
    return not blockers, blockers


def _collect_artifact_blockers(project: str, artifacts: Path) -> list[str]:
    generated = artifacts / "generated"
    aggregate = _load_json(generated / "aggregate_results.json")
    snapshot = _load_json(generated / "project_snapshot.json")
    ledger = _load_json(generated / "final_no_overfit_ledger.json")
    source_identity = _current_source_identity(artifacts)
    blockers: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value and value not in blockers:
            blockers.append(value)
        elif isinstance(value, list):
            for item in value:
                add(item)

    add(snapshot.get("closure_blockers"))
    add(snapshot.get("canonical_full_evidence_blockers"))
    add(snapshot.get("closure_blocker_summary"))
    add(ledger.get("open_blockers"))
    expected_sha256 = source_identity["source_full_eval_sha256"]
    if expected_sha256:
        aggregate_sha256 = str(aggregate.get("source_full_eval_sha256", "")).strip()
        snapshot_sha256 = str(snapshot.get("source_full_eval_sha256", "")).strip()
        if aggregate_sha256 and aggregate_sha256 != expected_sha256:
            add("aggregate_source_full_eval_sha256_mismatch")
        if snapshot_sha256 and snapshot_sha256 != expected_sha256:
            add("snapshot_source_full_eval_sha256_mismatch")
    expected_run_id = source_identity["canonical_source_run_id"]
    if expected_run_id:
        aggregate_run_id = str(aggregate.get("canonical_source_run_id", "")).strip()
        snapshot_run_id = str(snapshot.get("canonical_source_run_id", "")).strip()
        if aggregate_run_id and aggregate_run_id != expected_run_id:
            add("aggregate_canonical_source_run_id_mismatch")
        if snapshot_run_id and snapshot_run_id != expected_run_id:
            add("snapshot_canonical_source_run_id_mismatch")
    first_failing = aggregate.get("first_failing_gate") or snapshot.get("first_failing_gate")
    if first_failing:
        add(f"first_failing_gate:{first_failing}")

    name = project.strip().lower()
    if name == "codedye":
        utility_first_allows = _utility_first_gate_allows(artifacts)
        sample_current = _sample_selection_current(artifacts)
        if int(aggregate.get("official_runnable_baseline_count", 0) or 0) <= 0 and not utility_first_allows:
            add("official_main_table_runnable_baseline_missing")
        if not _truthy(aggregate.get("official_baseline_gate_pass")) and not utility_first_allows:
            add("official_baseline_gate_not_cleared")
        if not _truthy(aggregate.get("baseline_admission_gate_pass")) and not utility_first_allows:
            gate_path = artifacts / "generated" / "baseline_admission_official_gate.json"
            add("baseline_admission_official_gate_not_passed" if gate_path.exists() else "baseline_admission_official_gate_missing")
        if int(aggregate.get("main_table_baseline_count", 0) or 0) < 1 and not utility_first_allows:
            add("main_table_baseline_count_zero")
        if utility_first_allows:
            blockers[:] = [
                item
                for item in blockers
                if not _is_downgradable_baseline_blocker(item)
                and not _is_stale_self_latching_blocker(item, project="CodeDye", sample_selection_current=sample_current)
            ]
        add(_best_paper_cycle_blockers(artifacts, project="CodeDye"))
        blockers[:] = [
            item
            for item in blockers
            if not _is_stale_self_latching_blocker(item, project="CodeDye", sample_selection_current=sample_current)
        ]

    return blockers


def enforce_review_ready_gate(
    project: str,
    artifacts: Path,
    *,
    experiment_requested: bool,
    reason: str,
    run_id: str = "",
    rerun_purpose: str = "",
    finalize_canonical: bool = False,
) -> None:
    if os.environ.get("CODEMARK_REVIEW_READY_GATE_BYPASS", "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    if not experiment_requested:
        return
    gate_path = artifacts / "generated" / "review_ready_gate.json"
    gate = _load_json(gate_path)
    source_identity = _current_source_identity(artifacts)
    blockers = _collect_artifact_blockers(project, artifacts)
    utility_rerun_allowed, utility_rerun_blockers = _scope_decision_allows_utility_rerun(
        artifacts,
        run_id=run_id.strip(),
        rerun_purpose=rerun_purpose.strip(),
        finalize_canonical=finalize_canonical,
    )
    if utility_rerun_allowed:
        return
    raw_rehydration_allowed, raw_rehydration_blockers = _raw_payload_rehydration_allowed(
        artifacts,
        run_id=run_id.strip(),
        rerun_purpose=rerun_purpose.strip(),
        finalize_canonical=finalize_canonical,
        current_blockers=blockers,
    )
    if raw_rehydration_allowed:
        return
    gate_allows = (
        bool(gate.get("review_ready"))
        and bool(gate.get("experiment_entry_allowed"))
        and not blockers
        and str(gate.get("canonical_source_run_id", "")).strip() == source_identity["canonical_source_run_id"]
        and str(gate.get("source_full_eval_sha256", "")).strip() == source_identity["source_full_eval_sha256"]
    )
    if gate_allows:
        return
    blockers = list(gate.get("blockers") or []) + blockers + utility_rerun_blockers + raw_rehydration_blockers
    if bool(gate.get("review_ready")) and bool(gate.get("experiment_entry_allowed")):
        if str(gate.get("canonical_source_run_id", "")).strip() != source_identity["canonical_source_run_id"]:
            blockers.append("review_ready_gate_canonical_source_run_id_stale")
        if str(gate.get("source_full_eval_sha256", "")).strip() != source_identity["source_full_eval_sha256"]:
            blockers.append("review_ready_gate_source_full_eval_sha256_stale")
    blockers = list(dict.fromkeys(item for item in blockers if str(item).strip()))
    if not blockers:
        blockers = ["review_ready_gate_missing_or_closed"]
    message = {
        "status": "blocked_by_review_ready_gate",
        "project": project,
        "reason": reason,
        "gate_path": str(gate_path),
        "blockers": blockers,
        "next_step": "Resolve blockers, pass zero-mod validation, then write review_ready=true and experiment_entry_allowed=true from canonical artifacts only.",
    }
    raise SystemExit(json.dumps(message, indent=2, ensure_ascii=True))
