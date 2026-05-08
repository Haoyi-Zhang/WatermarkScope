from __future__ import annotations

import json
from statistics import mean

from _bootstrap import ARTIFACTS, ROOT
from _closure_boundary import load_closure_boundary
from _profiles import artifact_name, normalize_artifact_profile
from integrations.baseline_adapters import describe_baselines


LIVE_MODES = {"deepseek_live_full_eval", "deepseek_live_segmented_eval"}
ACCEPT_QUERY_FLOOR = 6
MIN_MAIN_TABLE_BASELINE_TASKS = 300


def _safe_int(value: object, *, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _mean_rate(records: list[dict[str, object]], predicate) -> float:
    if not records:
        return 0.0
    return round(mean(1.0 if predicate(item) else 0.0 for item in records), 4)


def _subset_mean_rate(records: list[dict[str, object]], selector, predicate) -> float:
    subset = [item for item in records if selector(item)]
    if not subset:
        return 0.0
    return round(mean(1.0 if predicate(item) else 0.0 for item in subset), 4)


def _subset_rate(records: list[dict[str, object]], predicate) -> float:
    subset = [item for item in records if predicate(item)]
    if not subset:
        return 0.0
    return round(mean(1.0 if item.get("verified") else 0.0 for item in subset), 4)


def _planned_query_budget() -> int:
    config_path = ROOT / "configs" / "default_experiment.json"
    if not config_path.exists():
        return 16
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return int(payload.get("wrapper", {}).get("query_budget", 16))


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _required_full_eval_path(profile: str):
    path = ARTIFACTS / artifact_name(profile, smoke_name="full_eval_smoke_results.json", full_name="full_eval_results.json")
    if not path.exists():
        raise RuntimeError(
            f"ProbeTrace aggregate requires the {profile} full-eval artifact at {path}; "
            "refusing cross-profile fallback between smoke and full artifacts"
        )
    return path


def _local_task_target() -> int:
    spec_path = ROOT / "benchmarks" / "api_stealbench_spec.json"
    if not spec_path.exists():
        task_path = ROOT / "benchmarks" / "api_stealbench_tasks.json"
        if not task_path.exists():
            return 0
        payload = _read_json(task_path)
        if isinstance(payload, dict):
            declared_target = int(payload.get("task_count_target") or 0)
            if declared_target > 0:
                return declared_target
            tasks = payload.get("tasks", [])
            if isinstance(tasks, list):
                return len(tasks)
        return 0
    payload = _read_json(spec_path)
    return int(payload.get("local_task_count_target") or payload.get("ready_task_count_target") or 0)


def _payload_local_task_target(payload: dict[str, object], *, strict: bool) -> int:
    aggregate = payload.get("aggregate", {})
    aggregate = dict(aggregate) if isinstance(aggregate, dict) else {}
    target = _safe_int(aggregate.get("local_task_target"), default=0)
    if target > 0:
        return target
    if strict:
        raise RuntimeError(
            "canonical ProbeTrace live aggregate requires local_task_target in the run-scoped full-eval payload; "
            "refusing to infer coverage from the current checkout benchmark spec"
        )
    return _local_task_target()


def _public_task_target(payload: dict[str, object]) -> int:
    aggregate = payload.get("aggregate", {})
    if isinstance(aggregate, dict):
        try:
            value = int(aggregate.get("public_task_target", 0))
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    public_task_records = payload.get("public_task_records", [])
    if isinstance(public_task_records, list) and public_task_records:
        return len(public_task_records)
    return int(sum(int(item.get("task_count", 0)) for item in payload.get("public_benchmark_summary", [])))


def _publish_truth_main_table_baseline_names() -> tuple[str, ...]:
    admitted: list[str] = []
    for path in sorted((ARTIFACTS / "baselines").glob("*_publish_truth.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        name = str(payload.get("baseline") or payload.get("name") or "").strip()
        provider_mode = str(payload.get("provider_mode", "")).strip().lower()
        if not name:
            continue
        if not bool(payload.get("main_table_admissible", False)):
            continue
        if provider_mode in {"", "mock", "no_provider", "no-provider", "scaffold"}:
            continue
        if _safe_int(payload.get("task_record_count"), default=0) < MIN_MAIN_TABLE_BASELINE_TASKS:
            continue
        if _safe_int(payload.get("activated_count"), default=0) <= 0:
            continue
        activation_rate = float(payload.get("activation_rate", 0.0) or 0.0)
        if activation_rate <= 0.0:
            continue
        admitted.append(name)
    return tuple(dict.fromkeys(admitted))


def _main_table_baseline_count() -> int:
    """Fail closed: runtime metadata alone is never main-table baseline evidence."""

    return len(_publish_truth_main_table_baseline_names())


def _payload_requested_main_table_baseline_names(payload: dict[str, object]) -> tuple[str, ...]:
    meta = payload.get("meta", {})
    meta = dict(meta) if isinstance(meta, dict) else {}
    items = meta.get("baselines_main_table", [])
    names: list[str] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
            else:
                name = str(item).strip()
            if name and name not in names:
                names.append(name)
    return tuple(names)


def _payload_main_table_baseline_names(payload: dict[str, object]) -> tuple[str, ...]:
    requested_names = set(_payload_requested_main_table_baseline_names(payload))
    admitted: list[str] = []
    bundles = payload.get("baseline_task_bundles", [])
    if isinstance(bundles, list):
        for item in bundles:
            if not isinstance(item, dict):
                continue
            baseline_name = str(item.get("baseline") or item.get("baseline_id") or "").strip()
            if not baseline_name:
                continue
            if requested_names and baseline_name not in requested_names:
                continue
            if _baseline_bundle_admissible_for_main_table(item) and baseline_name not in admitted:
                admitted.append(baseline_name)
    return tuple(admitted)


def _baseline_bundle_task_count(item: dict[str, object]) -> int:
    return max(
        _safe_int(item.get("task_record_count"), default=0),
        _safe_int(item.get("task_level_record_count"), default=0),
    )


def _baseline_bundle_activation_count(item: dict[str, object]) -> int:
    return max(
        _safe_int(item.get("activated_count"), default=0),
        _safe_int(item.get("task_level_activated_count"), default=0),
    )


def _baseline_bundle_admissible_for_main_table(item: dict[str, object]) -> bool:
    task_count = _baseline_bundle_task_count(item)
    activation_count = _baseline_bundle_activation_count(item)
    activation_rate = float(item.get("activation_rate", item.get("task_level_activation_rate", 0.0)) or 0.0)
    return (
        task_count >= MIN_MAIN_TABLE_BASELINE_TASKS
        and bool(item.get("main_table_admissible", item.get("task_level_main_table_admissible", False)))
        and activation_count > 0
        and activation_rate > 0.0
        and str(item.get("provider_mode", "")).strip().lower() not in {"", "mock", "no_provider"}
    )


def _materialized_main_table_baseline_count(payload: dict[str, object], *, strict: bool = False) -> int:
    bundle_names: set[str] = set()
    requested_main_table_names = set(_payload_requested_main_table_baseline_names(payload))
    bundles = payload.get("baseline_task_bundles", [])
    if isinstance(bundles, list):
        for item in bundles:
            if not isinstance(item, dict):
                continue
            baseline_name = str(item.get("baseline") or item.get("baseline_id") or "").strip()
            if not baseline_name:
                continue
            if requested_main_table_names and baseline_name not in requested_main_table_names:
                continue
            if not _baseline_bundle_admissible_for_main_table(item):
                continue
            bundle_names.add(baseline_name)
    if bundle_names:
        return len(bundle_names)
    if strict:
        return 0
    aggregate = payload.get("aggregate", {})
    aggregate = dict(aggregate) if isinstance(aggregate, dict) else {}
    if "main_table_baseline_count" in aggregate:
        return 0
    return _main_table_baseline_count()


def _aggregate_provenance(payload: dict[str, object], resolved_profile: str) -> dict[str, object]:
    operator_state = payload.get("operator_state", {})
    operator_state = dict(operator_state) if isinstance(operator_state, dict) else {}
    mode = str(payload.get("mode", "")).strip()
    raw_blockers = payload.get("canonical_full_evidence_blockers", [])
    blockers = []
    if isinstance(raw_blockers, list):
        blockers = [str(item).strip() for item in raw_blockers if str(item).strip()]
    raw_blocker_summary = payload.get("closure_blocker_summary", [])
    blocker_summary = []
    if isinstance(raw_blocker_summary, list):
        blocker_summary = [str(item).strip() for item in raw_blocker_summary if str(item).strip()]
    source_artifact = str(operator_state.get("canonical_source_artifact", "")).strip()
    source_artifact_sha256 = str(operator_state.get("canonical_source_artifact_sha256", "")).strip()
    if source_artifact:
        source_artifact_digest_policy = "pinned_sha256" if source_artifact_sha256 else "missing_pinned_sha256"
    else:
        source_artifact_digest_policy = "missing_source_artifact"
    live_full_scope = resolved_profile == "full" and mode in LIVE_MODES
    if live_full_scope:
        budget_gate_scope = "run_scoped_deepseek_live_query_budget_gate"
        latency_metric_scope = "run_scoped_deepseek_live_latency_diagnostic"
        source_run_id = str(operator_state.get("canonical_source_run_id", "")).strip()
        canonical_source_run_id = source_run_id
        source_run_id_policy = "canonical_live_source_run"
    else:
        budget_gate_scope = "smoke_mock_or_replay_pipeline_regression_not_submission_claim"
        latency_metric_scope = "smoke_mock_or_replay_latency_diagnostic_not_live_provider_measurement"
        source_run_id = str(operator_state.get("run_id", "")).strip()
        canonical_source_run_id = ""
        source_run_id_policy = "noncanonical_smoke_or_replay_run_id"
    return {
        "schema_version": "probetrace_aggregate_v2",
        "artifact_profile": resolved_profile,
        "artifact_role": str(operator_state.get("artifact_role", "")).strip(),
        "source_full_eval_schema_version": str(payload.get("schema_version", "")).strip(),
        "source_full_eval_mode": mode,
        "source_run_id": source_run_id,
        "source_run_id_policy": source_run_id_policy,
        "canonical_source_run_id": canonical_source_run_id,
        "canonical_source_artifact": source_artifact,
        "canonical_source_artifact_sha256": source_artifact_sha256,
        "canonical_source_artifact_digest_policy": source_artifact_digest_policy,
        "source_external_task_count": int(payload.get("external_task_count", 0) or 0),
        "source_requested_main_table_baseline_names": list(_payload_requested_main_table_baseline_names(payload)),
        "source_main_table_baseline_names": list(_payload_main_table_baseline_names(payload)),
        "metric_aggregation_contract": "non_weighted_lexicographic_gate_vector",
        "budget_gate_scope": budget_gate_scope,
        "latency_metric_scope": latency_metric_scope,
        "diagnostic_metric_scope": (
            "diagnostic_fields_do_not_select_the_owner_or_relax_the_acceptance_gate"
        ),
        "canonical_full_evidence_ready": bool(payload.get("canonical_full_evidence_ready", False)),
        "canonical_full_evidence_blockers": blockers,
        "closure_blocker_summary": blocker_summary,
        "claim_boundary": str(payload.get("claim_boundary", "deepseek_live_only")).strip() or "deepseek_live_only",
        "provider_readiness_scope": (
            str(payload.get("provider_readiness_scope", "deepseek_openai_claude")).strip()
            or "deepseek_openai_claude"
        ),
        "provider_readiness_note": (
            str(payload.get("provider_readiness_note", "implementation_readiness_only_not_live_evidence")).strip()
            or "implementation_readiness_only_not_live_evidence"
        ),
    }


def _dedupe_strings(items: object) -> list[str]:
    values: list[str] = []
    if not isinstance(items, list):
        return values
    for item in items:
        text = str(item).strip()
        if text and text not in values:
            values.append(text)
    return values


def _optional_json(path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = _read_json(path)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _apis300_expanded_evidence_summary() -> dict[str, object]:
    evidence_path = ARTIFACTS / "apis300_live_attribution_evidence.json"
    support_path = ARTIFACTS / "probetrace_apis300_support_materialization.json"
    evidence = _optional_json(evidence_path)
    support = _optional_json(support_path)
    if not evidence and not support:
        return {
            "status": "missing",
            "claim_bearing": False,
            "record_count": 0,
            "negative_control_record_count": 0,
        }
    evidence_record_count = max(
        _safe_int(evidence.get("record_count"), default=0),
        _safe_int(evidence.get("local_task_count"), default=0),
    )
    support_record_count = max(
        _safe_int(support.get("record_count"), default=0),
        _safe_int(support.get("local_task_count"), default=0),
    )
    return {
        "status": "passed" if bool(evidence.get("gate_pass")) else "blocked",
        "claim_bearing": str(evidence.get("claim_role", "")).strip()
        == "claim_bearing_apis300_live_canonical_evidence",
        "evidence_scope": str(evidence.get("evidence_scope", "")).strip(),
        "record_count": max(evidence_record_count, support_record_count),
        "negative_control_record_count": max(
            _safe_int(evidence.get("negative_control_record_count"), default=0),
            _safe_int(support.get("negative_control_record_count"), default=0),
        ),
        "gate_pass": bool(evidence.get("gate_pass")),
        "blockers": _dedupe_strings(evidence.get("blockers", [])),
        "source_artifact": str(evidence.get("source_artifact", "")).strip(),
        "support_artifact": "artifacts/generated/probetrace_apis300_support_materialization.json"
        if support
        else "",
        "aggregate_policy": (
            "expanded APIS300 evidence is surfaced for project status and transfer promotion; "
            "the legacy v6 canonical artifact remains unpromoted until transfer/statistics gates pass"
        ),
    }


def _student_transfer_launch_summary() -> dict[str, object]:
    launch_path = ARTIFACTS / "student_transfer_training_launch_manifest.json"
    launch = _optional_json(launch_path)
    if not launch:
        return {"launch_ready": False, "record_count": 0, "blockers": ["student_transfer_launch_missing"]}
    dataset = launch.get("dataset", {})
    dataset = dict(dataset) if isinstance(dataset, dict) else {}
    jobs = launch.get("jobs", [])
    families = sorted(
        {
            str(item.get("family", "")).strip()
            for item in jobs
            if isinstance(item, dict) and str(item.get("family", "")).strip()
        }
    )
    return {
        "launch_ready": bool(launch.get("launch_ready")),
        "claim_role": str(launch.get("claim_role", "")).strip(),
        "evidence_scope": str(launch.get("evidence_scope", "")).strip(),
        "record_count": _safe_int(dataset.get("record_count"), default=0),
        "owner_conditioned_training_count": _safe_int(dataset.get("owner_conditioned_training_count"), default=0),
        "owner_signal_matched_training_count": _safe_int(
            dataset.get("owner_signal_matched_training_count"),
            default=0,
        ),
        "owner_signal_mismatch_count": _safe_int(dataset.get("owner_signal_mismatch_count"), default=0),
        "teacher_owner_id_count": len(dataset.get("teacher_owner_ids", []))
        if isinstance(dataset.get("teacher_owner_ids"), list)
        else 0,
        "training_families": families,
        "blockers": _dedupe_strings(launch.get("blockers", [])),
        "dataset_sha256": str(dataset.get("sha256", "")).strip(),
        "aggregate_policy": (
            "launch manifest is a prerequisite and never a transfer result; "
            "claim promotion still requires completed receipts and live validation"
        ),
    }


def _apply_closure_boundary(payload: dict[str, object], boundary: dict[str, object]) -> dict[str, object]:
    """Make aggregate truth subordinate to the full closure boundary.

    The source full-eval artifact can be a valid frozen anchor while still being
    non-admissible for a main claim because transfer, expanded-evidence, or
    best-paper-cycle gates remain open.  Aggregate artifacts are what portfolio
    and release checks read, so they must carry the stricter boundary.
    """

    merged = dict(payload)
    blockers = _dedupe_strings(boundary.get("canonical_full_evidence_blockers", []))
    ready = bool(boundary.get("canonical_full_evidence_ready", False)) and not blockers
    merged["canonical_full_evidence_ready"] = ready
    merged["canonical_full_evidence_blockers"] = blockers
    merged["closure_blocker_summary"] = blockers[:25] if blockers else []
    first_failing = str(boundary.get("first_failing_gate", "")).strip()
    merged["first_failing_gate"] = first_failing or ("all_gates_pass" if ready else _first_failing_gate(merged))
    merged["current_full_eval_artifact_role"] = str(boundary.get("current_full_eval_artifact_role", "")).strip()
    for field in (
        "canonical_source_run_id",
        "canonical_source_artifact",
        "canonical_source_artifact_sha256",
        "canonical_source_artifact_digest_policy",
    ):
        if field in boundary:
            merged[field] = boundary.get(field, "")
    merged["closure_boundary_source"] = "scripts/_closure_boundary.py"
    return merged


def _closure_boundary_fail_closed(payload: dict[str, object], exc: Exception) -> dict[str, object]:
    merged = dict(payload)
    blocker = f"closure_boundary_load_failed:{type(exc).__name__}"
    blockers = _dedupe_strings(list(merged.get("canonical_full_evidence_blockers", [])) + [blocker])
    merged["canonical_full_evidence_ready"] = False
    merged["canonical_full_evidence_blockers"] = blockers
    merged["closure_blocker_summary"] = blockers[:25]
    merged["first_failing_gate"] = blocker
    merged["closure_boundary_source"] = "scripts/_closure_boundary.py"
    return merged


def _utility_gate_pass(item: dict[str, object], *, strict: bool = False) -> bool:
    if "utility_gate_pass" in item:
        return bool(item.get("utility_gate_pass"))
    if strict:
        raise RuntimeError("canonical ProbeTrace aggregate requires explicit utility_gate_pass fields")
    if "local_utility_score" in item:
        return float(item.get("local_utility_score", 0.0)) >= 1.0
    raise RuntimeError("ProbeTrace aggregate requires explicit local_utility_score/utility_gate_pass fields")


def _public_utility_support_pass(item: dict[str, object], *, strict: bool = False) -> bool:
    if "public_utility_support_pass" in item:
        return bool(item.get("public_utility_support_pass"))
    raise RuntimeError("ProbeTrace aggregate requires explicit public_utility_support_pass fields")


def _budget_feasible_pass(item: dict[str, object], planned_query_budget: int) -> bool:
    if "query_budget_used" not in item:
        return False
    accept_query_floor = max(_safe_int(item.get("accept_query_floor"), default=0), ACCEPT_QUERY_FLOOR)
    return (
        bool(item.get("verified"))
        and _utility_gate_pass(item, strict=True)
        and int(item.get("query_budget_used", planned_query_budget)) <= planned_query_budget
        and int(item.get("query_budget_used", 0) or 0) >= accept_query_floor
        and float(item.get("commitment_valid_rate", 0.0)) >= 1.0
        and int(item.get("support_count", 0) or 0) >= 4
        and int(item.get("support_family_count", 0) or 0) >= 3
        and int(item.get("support_bucket_count", 0) or 0) >= 2
        and int(item.get("held_out_decoy_survivor_count", 0) or 0) <= 0
    )


def _payload_planned_query_budget(payload: dict[str, object], *, strict: bool) -> int:
    aggregate = payload.get("aggregate", {})
    aggregate = dict(aggregate) if isinstance(aggregate, dict) else {}
    operator_state = payload.get("operator_state", {})
    operator_state = dict(operator_state) if isinstance(operator_state, dict) else {}
    value = _safe_int(
        aggregate.get(
            "planned_query_budget",
            operator_state.get("planned_query_budget", -1),
        ),
        default=-1,
    )
    if value > 0:
        return value
    if strict:
        raise RuntimeError("canonical ProbeTrace live aggregate requires explicit planned_query_budget in the artifact")
    return _planned_query_budget()


def _public_support_rate(public_benchmark_summary: list[dict[str, object]]) -> float:
    if not public_benchmark_summary:
        return 0.0
    missing = [
        index
        for index, item in enumerate(public_benchmark_summary)
        if not isinstance(item, dict) or "public_utility_support_pass" not in item
    ]
    if missing:
        raise RuntimeError(
            "canonical ProbeTrace live aggregate refused public utility fallback; "
            "rerun full eval to materialize explicit public_utility_support_pass fields "
            f"for public summary indexes {missing[:8]}"
        )
    return round(mean(1.0 if bool(item.get("public_utility_support_pass")) else 0.0 for item in public_benchmark_summary), 4)


def _coverage_gate_pass(local_task_count: int, local_task_target: int) -> bool:
    return local_task_target > 0 and local_task_count == local_task_target


def _first_failing_gate(payload: dict[str, object]) -> str:
    if not bool(payload.get("coverage_gate_pass")):
        if float(payload.get("local_task_coverage_rate", 0.0) or 0.0) < 1.0:
            return "aggregate_local_coverage_gate_failed"
        if float(payload.get("public_task_coverage_rate", 0.0) or 0.0) < 1.0:
            return "aggregate_public_support_coverage_gate_failed"
        return "aggregate_coverage_gate_failed"
    if not bool(payload.get("budget_feasible_attribution_pass")):
        return "aggregate_budget_feasible_attribution_gate_failed"
    if float(payload.get("support_count_gate_pass_rate", 0.0)) < 1.0:
        return "hard_decoy_support_count_gate_failed"
    if float(payload.get("support_family_diversity_gate_pass_rate", 0.0)) < 1.0:
        return "hard_decoy_support_family_gate_failed"
    if float(payload.get("support_bucket_diversity_gate_pass_rate", 0.0)) < 1.0:
        return "hard_decoy_support_bucket_gate_failed"
    if float(payload.get("winner_support_conjunction_pass_rate", 0.0)) < 1.0:
        return "winner_support_conjunction_gate_failed"
    return "all_gates_pass"


def _budget_feasible_attribution_pass(records: list[dict[str, object]], planned_query_budget: int) -> bool:
    return bool(records) and all(_budget_feasible_pass(item, planned_query_budget) for item in records)


def _support_count_from_decision(decision: dict[str, object]) -> int:
    evidence = decision.get("probe_evidence", [])
    if not isinstance(evidence, list):
        return 0
    count = 0
    for item in evidence:
        if not isinstance(item, dict):
            continue
        matches = tuple(str(match) for match in item.get("matches", ()) if isinstance(match, str))
        if "outcome:support" in matches:
            count += 1
    return count


def _support_diversity_from_decision(decision: dict[str, object]) -> tuple[int, int]:
    evidence = decision.get("probe_evidence", [])
    if not isinstance(evidence, list):
        return 0, 0
    families: set[str] = set()
    buckets: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict):
            continue
        matches = tuple(str(match) for match in item.get("matches", ()) if isinstance(match, str))
        if "outcome:support" not in matches:
            continue
        family = str(item.get("target_family", "")).strip()
        if family:
            families.add(family)
        for match in matches:
            if match.startswith("bucket:"):
                bucket = match.split(":", 1)[1].strip()
                if bucket:
                    buckets.add(bucket)
    return len(families), len(buckets)


def _hard_decoy_registry_class_inventory() -> dict[str, object]:
    registry_path = ROOT / "benchmarks" / "api_stealbench_hard_negative_registry.json"
    if not registry_path.exists():
        return {"class_count": 0, "class_counts": {}, "class_order": []}
    try:
        payload = _read_json(registry_path)
    except json.JSONDecodeError:
        return {"class_count": 0, "class_counts": {}, "class_order": []}
    class_counts = payload.get("frozen_decoy_class_counts", {})
    if not isinstance(class_counts, dict) or not class_counts:
        class_counts = payload.get("candidate_decoy_class_counts", {})
    normalized_counts = {
        str(key): int(value)
        for key, value in (class_counts.items() if isinstance(class_counts, dict) else ())
        if str(key).strip()
    }
    class_order = [
        str(item)
        for item in payload.get("decoy_class_order", [])
        if str(item).strip()
    ]
    if not class_order:
        class_order = sorted(normalized_counts)
    declared_count = int(
        payload.get(
            "frozen_decoy_class_count",
            payload.get("candidate_decoy_class_count", len(normalized_counts)),
        )
        or 0
    )
    return {
        "class_count": max(declared_count, len(normalized_counts)),
        "class_counts": normalized_counts,
        "class_order": class_order,
    }


def _hard_decoy_diagnostics_from_payload(payload: dict[str, object]) -> dict[str, object]:
    verification_segments = payload.get("verification_segments", {})
    if not (isinstance(verification_segments, dict) and verification_segments):
        existing = payload.get("hard_decoy_diagnostics")
        if isinstance(existing, dict) and existing.get("segments"):
            return existing
    rows: list[dict[str, object]] = []
    aggregate = payload.get("aggregate", {})
    aggregate = dict(aggregate) if isinstance(aggregate, dict) else {}
    if isinstance(verification_segments, dict):
        for attack, segment in verification_segments.items():
            if not isinstance(segment, dict):
                continue
            decision = segment.get("decision", {})
            if not isinstance(decision, dict):
                decision = {}
            family_count, bucket_count = _support_diversity_from_decision(decision)
            survivor_count = int(decision.get("held_out_decoy_survivor_count", 0) or 0)
            registry_count = int(decision.get("held_out_decoy_registry_count", 0) or 0)
            class_trace = decision.get("held_out_decoy_class_trace", [])
            if not isinstance(class_trace, list):
                class_trace = []
            rows.append(
                {
                    "attack": str(attack),
                    "verified": bool(decision.get("verified", False)),
                    "support_count": _support_count_from_decision(decision),
                    "support_family_count": family_count,
                    "support_bucket_count": bucket_count,
                    "held_out_decoy_registry_count": registry_count,
                    "held_out_decoy_survivor_count": survivor_count,
                    "held_out_decoy_elimination_rate": float(decision.get("held_out_decoy_elimination_rate", 0.0) or 0.0),
                    "class_survival_curves": [dict(item, attack=str(attack)) for item in class_trace if isinstance(item, dict)],
                    "survivor_curve_point": {
                        "attack": str(attack),
                        "survivors": survivor_count,
                        "eliminated": max(registry_count - survivor_count, 0),
                        "registry_count": registry_count,
                    },
                }
            )
    rows.sort(key=lambda item: (0 if item["attack"] == "clean" else 1, str(item["attack"])))
    if rows:
        max_survivor = max(int(row["held_out_decoy_survivor_count"]) for row in rows)
        registry_count = max(int(row["held_out_decoy_registry_count"]) for row in rows)
        registry_count = max(registry_count, int(payload.get("hard_decoy_registry_count", 0) or 0), int(aggregate.get("hard_decoy_registry_count", 0) or 0))
        min_support = min(int(row["support_count"]) for row in rows)
        min_family = min(int(row["support_family_count"]) for row in rows)
        min_bucket = min(int(row["support_bucket_count"]) for row in rows)
        mean_support = round(mean(int(row["support_count"]) for row in rows), 4)
        mean_elimination = round(mean(float(row["held_out_decoy_elimination_rate"]) for row in rows), 4)
        verified_rate = round(mean(1.0 if bool(row.get("verified")) else 0.0 for row in rows), 4)
    else:
        max_survivor = min_support = min_family = min_bucket = 0
        registry_count = max(int(payload.get("hard_decoy_registry_count", 0) or 0), int(aggregate.get("hard_decoy_registry_count", 0) or 0))
        mean_support = mean_elimination = verified_rate = 0.0
    class_inventory = _hard_decoy_registry_class_inventory()
    class_curves = [item for row in rows for item in row.get("class_survival_curves", [])]
    materialized_class_count = len(
        {str(item.get("decoy_class", "")) for item in class_curves if isinstance(item, dict)}
    )
    decoy_class_count = materialized_class_count if class_curves else int(class_inventory["class_count"])
    return {
        "schema_version": "probetrace_hard_decoy_diagnostics_v2",
        "segment_count": len(rows),
        "registry_count": registry_count,
        "registry_class_count": int(class_inventory["class_count"]),
        "registry_class_counts": dict(class_inventory["class_counts"]),
        "registry_class_order": list(class_inventory["class_order"]),
        "max_survivor_count": max_survivor,
        "min_support_count": min_support,
        "min_support_family_count": min_family,
        "min_support_bucket_count": min_bucket,
        "mean_support_count": mean_support,
        "mean_elimination_rate": mean_elimination,
        "verified_rate": verified_rate,
        "decoy_survival_curves": [row["survivor_curve_point"] for row in rows],
        "decoy_class_survival_curves": class_curves,
        "decoy_class_count": decoy_class_count,
        "decoy_class_survival_curve_status": (
            "segment_class_survival_curves_materialized"
            if class_curves
            else "registry_class_inventory_only_no_per_class_survival_curve_in_v6_segments"
        ),
        "segments": rows,
    }


def _hard_decoy_gate_rates(hard_decoy_diagnostics: dict[str, object]) -> dict[str, float]:
    rows = hard_decoy_diagnostics.get("segments", [])
    if not isinstance(rows, list) or not rows:
        return {
            "support_count_gate_pass_rate": 0.0,
            "support_family_diversity_gate_pass_rate": 0.0,
            "support_bucket_diversity_gate_pass_rate": 0.0,
            "winner_support_conjunction_pass_rate": 0.0,
        }
    support = round(mean(1.0 if int(row.get("support_count", 0)) >= 4 else 0.0 for row in rows), 4)
    family = round(mean(1.0 if int(row.get("support_family_count", 0)) >= 3 else 0.0 for row in rows), 4)
    bucket = round(mean(1.0 if int(row.get("support_bucket_count", 0)) >= 2 else 0.0 for row in rows), 4)
    conjunction = round(
        mean(
            1.0
            if int(row.get("support_count", 0)) >= 4
            and int(row.get("support_family_count", 0)) >= 3
            and int(row.get("support_bucket_count", 0)) >= 2
            else 0.0
            for row in rows
        ),
        4,
    )
    return {
        "support_count_gate_pass_rate": support,
        "support_family_diversity_gate_pass_rate": family,
        "support_bucket_diversity_gate_pass_rate": bucket,
        "winner_support_conjunction_pass_rate": conjunction,
    }


def _aggregate_from_live_payload(payload: dict[str, object]) -> dict[str, object]:
    records = payload.get("records", [])
    records = list(records) if isinstance(records, list) else []
    if not records:
        raise RuntimeError("live ProbeTrace aggregate refused empty canonical record set")
    public_benchmark_summary = payload.get("public_benchmark_summary", [])
    missing_gate_schema = [
        index
        for index, item in enumerate(records)
        if not isinstance(item, dict)
        or "utility_gate_pass" not in item
        or "public_utility_support_pass" not in item
        or "local_utility_score" not in item
    ]
    if missing_gate_schema:
        raise RuntimeError(
            "live ProbeTrace aggregate refused stale schema; rerun segmented full eval to materialize gate-based fields "
            f"for record indexes {missing_gate_schema[:8]}"
        )
    generic_utility_indexes = [
        index for index, item in enumerate(records) if isinstance(item, dict) and "utility_score" in item
    ]
    if generic_utility_indexes:
        raise RuntimeError(
            "canonical ProbeTrace live aggregate refused generic utility_score in live records; "
            "rerun full eval with split local/public utility fields only for record indexes "
            f"{generic_utility_indexes[:8]}"
        )
    hard_negative_split = payload.get("hard_negative_split", {})
    if not isinstance(hard_negative_split, dict):
        hard_negative_split = {}
    planned_query_budget = _payload_planned_query_budget(payload, strict=True)
    missing_query_budget_indexes = [
        index
        for index, item in enumerate(records)
        if not isinstance(item, dict) or "query_budget_used" not in item
    ]
    if missing_query_budget_indexes:
        raise RuntimeError(
            "canonical ProbeTrace live aggregate requires explicit query_budget_used for every record; "
            f"missing on indexes {missing_query_budget_indexes[:8]}"
        )
    local_task_count = int(sum(int(item.get("task_count", 0)) for item in payload.get("local_benchmark_summary", [])))
    public_task_count = int(sum(int(item.get("task_count", 0)) for item in payload.get("public_benchmark_summary", [])))
    local_task_target = _payload_local_task_target(payload, strict=True)
    public_task_target = _public_task_target(payload)
    coverage_gate_pass = _coverage_gate_pass(local_task_count, local_task_target)
    if not coverage_gate_pass:
        raise RuntimeError(
            "canonical ProbeTrace live aggregate refused promotion because APIStealBench coverage gate failed: "
            f"{local_task_count}/{local_task_target} local tasks materialized"
        )
    if public_task_target > 0 and public_task_count != public_task_target:
        raise RuntimeError(
            "canonical ProbeTrace live aggregate refused promotion because public benchmark coverage gate failed: "
            f"{public_task_count}/{public_task_target} public tasks materialized"
        )
    public_utility_support_pass_rate = _public_support_rate(public_benchmark_summary)
    verification_segments = payload.get("verification_segments", {})
    if not isinstance(verification_segments, dict) or not verification_segments:
        raise RuntimeError(
            "canonical ProbeTrace live aggregate refused stale hard-decoy fallback; "
            "verification_segments must be materialized in the source run artifact"
        )
    hard_decoy_diagnostics = _hard_decoy_diagnostics_from_payload(payload)
    hard_decoy_gate_rates = _hard_decoy_gate_rates(hard_decoy_diagnostics)
    budget_feasible_attribution_pass = _budget_feasible_attribution_pass(records, planned_query_budget)
    clean_rate = _subset_mean_rate(
        records,
        lambda item: item.get("attack") == "clean",
        lambda item: _budget_feasible_pass(item, planned_query_budget),
    )
    attacked_rate = _subset_mean_rate(
        records,
        lambda item: item.get("attack") != "clean",
        lambda item: _budget_feasible_pass(item, planned_query_budget),
    )
    return {
        "metric_aggregation_contract": "non_weighted_lexicographic_gate_vector",
        "budget_gate_scope": "run_scoped_deepseek_live_query_budget_gate",
        "latency_metric_scope": "run_scoped_deepseek_live_latency_diagnostic",
        "diagnostic_metric_scope": (
            "diagnostic_fields_do_not_select_the_owner_or_relax_the_acceptance_gate"
        ),
        "coverage_gate_pass": coverage_gate_pass,
        "budget_feasible_attribution_pass": budget_feasible_attribution_pass,
        "utility_gate_pass_rate": _mean_rate(records, lambda item: _utility_gate_pass(item, strict=True)),
        "public_utility_support_pass_rate": public_utility_support_pass_rate,
        "budget_feasible_verification_rate": _mean_rate(
            records,
            lambda item: _budget_feasible_pass(item, planned_query_budget),
        ),
        "clean_budget_feasible_verification_rate": clean_rate,
        "attacked_budget_feasible_verification_rate": attacked_rate,
        "clean_attacked_budget_gap": round(abs(clean_rate - attacked_rate), 4),
        "clean_raw_verified_rate": _subset_rate(records, lambda item: item.get("attack") == "clean"),
        "attacked_raw_verified_rate": _subset_rate(records, lambda item: item.get("attack") != "clean"),
        "commitment_gate_pass_rate": _mean_rate(records, lambda item: float(item.get("commitment_valid_rate", 0.0)) >= 1.0),
        "query_budget_gate_pass_rate": _mean_rate(
            records,
            lambda item: int(item.get("query_budget_used", planned_query_budget)) <= planned_query_budget,
        ),
        "verification_confidence_diagnostic": round(mean(float(item["verification_confidence"]) for item in records), 4),
        "inheritance_rate_diagnostic": round(mean(float(item["inheritance_rate"]) for item in records), 4),
        "held_out_decoy_survivor_count_diagnostic": round(
            mean(float(item.get("held_out_decoy_survivor_count", 0.0)) for item in records),
            4,
        ),
        "held_out_decoy_elimination_rate_diagnostic": round(
            mean(float(item.get("held_out_decoy_elimination_rate", 0.0)) for item in records),
            4,
        ),
        "hard_negative_split_present": bool(hard_negative_split),
        "hard_negative_split_owner_count": int(hard_negative_split.get("held_out_owner_count", 0)),
        "hard_negative_split_survivor_count": int(hard_negative_split.get("survivor_count", 0)),
        "hard_negative_split_elimination_rate": float(hard_negative_split.get("elimination_rate", 0.0)),
        "hard_decoy_segment_count": int(hard_decoy_diagnostics.get("segment_count", 0)),
        "hard_decoy_class_count": int(hard_decoy_diagnostics.get("decoy_class_count", 0)),
        "hard_decoy_registry_count": int(hard_decoy_diagnostics.get("registry_count", 0)),
        "hard_decoy_max_survivor_count": int(hard_decoy_diagnostics.get("max_survivor_count", 0)),
        "hard_decoy_min_support_count": int(hard_decoy_diagnostics.get("min_support_count", 0)),
        "hard_decoy_min_support_family_count": int(hard_decoy_diagnostics.get("min_support_family_count", 0)),
        "hard_decoy_min_support_bucket_count": int(hard_decoy_diagnostics.get("min_support_bucket_count", 0)),
        "hard_decoy_mean_support_count": float(hard_decoy_diagnostics.get("mean_support_count", 0.0)),
        "hard_decoy_mean_elimination_rate": float(hard_decoy_diagnostics.get("mean_elimination_rate", 0.0)),
        "hard_decoy_diagnostics": hard_decoy_diagnostics,
        "decoy_survival_curves": list(hard_decoy_diagnostics.get("decoy_survival_curves", [])),
        "decoy_class_survival_curves": list(hard_decoy_diagnostics.get("decoy_class_survival_curves", [])),
        "decoy_class_survival_curve_status": str(
            hard_decoy_diagnostics.get("decoy_class_survival_curve_status", "")
        ),
        "hard_decoy_registry_class_count": int(hard_decoy_diagnostics.get("registry_class_count", 0)),
        "hard_decoy_registry_class_counts": dict(hard_decoy_diagnostics.get("registry_class_counts", {})),
        "support_count_gate_pass_rate": float(hard_decoy_gate_rates["support_count_gate_pass_rate"]),
        "support_family_diversity_gate_pass_rate": float(hard_decoy_gate_rates["support_family_diversity_gate_pass_rate"]),
        "support_bucket_diversity_gate_pass_rate": float(hard_decoy_gate_rates["support_bucket_diversity_gate_pass_rate"]),
        "winner_support_conjunction_pass_rate": float(hard_decoy_gate_rates["winner_support_conjunction_pass_rate"]),
        "extra_query_cost": round(mean(float(item["extra_query_cost"]) for item in records), 2),
        "latency_overhead": round(mean(float(item["latency_overhead"]) for item in records), 4),
        "attack_applicable_count": sum(1 for item in records if item.get("attack") != "clean" and item.get("attack_applicable")),
        "backbone_count": 1,
        "record_count": len(records),
        "public_task_count": public_task_count,
        "public_task_target": public_task_target,
        "public_task_coverage_rate": round(public_task_count / public_task_target, 4) if public_task_target else 0.0,
        "local_task_count": local_task_count,
        "local_task_target": local_task_target,
        "local_task_coverage_rate": round(local_task_count / local_task_target, 4) if local_task_target else 0.0,
        "planned_query_budget": planned_query_budget,
        "main_table_baseline_count": _materialized_main_table_baseline_count(payload, strict=True),
        "baseline_task_evidence_count": int(
            sum(
                int(item.get("task_record_count", 0))
                for item in payload.get("baseline_task_bundles", [])
                if isinstance(item, dict)
            )
        ),
    }


def main() -> None:
    profile = normalize_artifact_profile(root=ROOT)
    resolved_profile = profile
    full_eval_path = _required_full_eval_path(profile)
    full_eval_payload = _read_json(full_eval_path)
    if str(full_eval_payload.get("mode", "")) in LIVE_MODES:
        payload = _aggregate_from_live_payload(full_eval_payload)
    else:
        pilot_payload = _read_json(ARTIFACTS / artifact_name(resolved_profile, smoke_name="pilot_smoke_results.json", full_name="pilot_results.json"))
        full_records = full_eval_payload["records"]
        pilot_records = pilot_payload["records"]
        attacked_raw_verified_rate = mean(1.0 if item["verified"] else 0.0 for item in full_records)
        clean_raw_verified_rate = mean(1.0 if item["verified"] else 0.0 for item in pilot_records) if pilot_records else 0.0
        planned_query_budget = _planned_query_budget()
        payload = {
            "coverage_gate_pass": False,
            "budget_feasible_attribution_pass": False,
            "utility_gate_pass_rate": _mean_rate(full_records, _utility_gate_pass),
            "public_utility_support_pass_rate": _mean_rate(full_records, _public_utility_support_pass),
            "budget_feasible_verification_rate": round(
                mean(
                    1.0
                    if _budget_feasible_pass(item, planned_query_budget)
                    else 0.0
                    for item in full_records
                ),
                4,
            ),
            "clean_budget_feasible_verification_rate": _subset_mean_rate(
                full_records,
                lambda item: item.get("attack") == "clean",
                lambda item: _budget_feasible_pass(item, planned_query_budget),
            ),
            "attacked_budget_feasible_verification_rate": _subset_mean_rate(
                full_records,
                lambda item: item.get("attack") != "clean",
                lambda item: _budget_feasible_pass(item, planned_query_budget),
            ),
            "clean_attacked_budget_gap": round(
                abs(
                    _subset_mean_rate(
                        full_records,
                        lambda item: item.get("attack") == "clean",
                        lambda item: _budget_feasible_pass(item, planned_query_budget),
                    )
                    - _subset_mean_rate(
                        full_records,
                        lambda item: item.get("attack") != "clean",
                        lambda item: _budget_feasible_pass(item, planned_query_budget),
                    )
                ),
                4,
            ),
            "clean_raw_verified_rate": round(clean_raw_verified_rate, 4),
            "attacked_raw_verified_rate": round(attacked_raw_verified_rate, 4),
            "commitment_gate_pass_rate": round(
                mean(1.0 if float(item.get("commitment_valid_rate", 0.0)) >= 1.0 else 0.0 for item in full_records),
                4,
            ),
            "query_budget_gate_pass_rate": round(
                mean(1.0 if int(item.get("query_budget_used", planned_query_budget)) <= planned_query_budget else 0.0 for item in full_records),
                4,
            ),
            "verification_confidence_diagnostic": round(
                mean([float(item["verification_confidence"]) for item in pilot_records + full_records]),
                4,
            ),
            "inheritance_rate_diagnostic": round(mean(float(item["inheritance_rate"]) for item in full_records), 4),
            "held_out_decoy_survivor_count_diagnostic": round(
                mean(float(item.get("held_out_decoy_survivor_count", 0.0)) for item in full_records),
                4,
            ),
            "held_out_decoy_elimination_rate_diagnostic": round(
                mean(float(item.get("held_out_decoy_elimination_rate", 0.0)) for item in full_records),
                4,
            ),
            "extra_query_cost": round(mean(float(item["extra_query_cost"]) for item in full_records), 2),
            "latency_overhead": round(mean(float(item["latency_overhead"]) for item in full_records), 4),
            "attack_applicable_count": sum(1 for item in full_records if item["attack_applicable"]),
            "backbone_count": len({item.get("backbone_name", "") for item in full_records}),
            "record_count": len(full_records),
            "public_task_count": 0,
            "local_task_count": 0,
            "local_task_target": _payload_local_task_target(full_eval_payload, strict=False),
            "local_task_coverage_rate": 0.0,
            "main_table_baseline_count": _main_table_baseline_count(),
            "baseline_task_evidence_count": 0,
            "public_task_target": 0,
            "public_task_coverage_rate": 0.0,
            "hard_negative_split_present": False,
            "hard_negative_split_owner_count": 0,
            "hard_negative_split_survivor_count": 0,
            "hard_negative_split_elimination_rate": 0.0,
            "hard_decoy_segment_count": 0,
            "hard_decoy_class_count": 0,
            "hard_decoy_registry_count": 0,
            "hard_decoy_max_survivor_count": 0,
            "hard_decoy_min_support_count": 0,
            "hard_decoy_min_support_family_count": 0,
            "hard_decoy_min_support_bucket_count": 0,
            "hard_decoy_mean_support_count": 0.0,
            "hard_decoy_mean_elimination_rate": 0.0,
        }
    payload = {**_aggregate_provenance(full_eval_payload, resolved_profile), **payload}
    payload["canonical_source_run_id"] = str(payload.get("canonical_source_run_id", "")).strip()
    payload["claim_boundary"] = "deepseek_live_only"
    payload["provider_readiness_scope"] = "deepseek_openai_claude"
    payload["first_failing_gate"] = _first_failing_gate(payload)
    out_path = ARTIFACTS / artifact_name(resolved_profile, smoke_name="aggregate_smoke_results.json", full_name="aggregate_results.json")
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    if resolved_profile == "full":
        try:
            payload = _apply_closure_boundary(payload, load_closure_boundary(resolved_profile, root=ROOT))
        except Exception as exc:  # pragma: no cover - defensive fail-closed path
            payload = _closure_boundary_fail_closed(payload, exc)
        payload["expanded_apis300_evidence"] = _apis300_expanded_evidence_summary()
        payload["student_transfer_launch"] = _student_transfer_launch_summary()
        payload["claim_boundary"] = "deepseek_live_only"
        payload["provider_readiness_scope"] = "deepseek_openai_claude"
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
