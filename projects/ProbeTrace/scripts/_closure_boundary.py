from __future__ import annotations

import json
import hashlib
from pathlib import Path

from _bootstrap import ROOT
from _profiles import artifact_name


_REQUIRED_ATTACK_SPLITS = (
    "clean",
    "rename",
    "comment_whitespace_normalize",
    "ast_canonicalization",
    "targeted_paraphrase_rewrite_neutralization",
    "watermark_neutralization_at_inference",
    "continued_sft_washout_on_student",
    "lora_merge_strip_on_student",
    "quantization_on_student",
)

_MIN_MAIN_TABLE_BASELINE_TASKS = 300


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _baseline_task_summary(bundles: object) -> dict[str, int]:
    if not isinstance(bundles, list):
        return {}
    summary: dict[str, int] = {}
    for item in bundles:
        if not isinstance(item, dict):
            continue
        baseline = str(item.get("baseline", "")).strip()
        if not baseline:
            continue
        summary[baseline] = _safe_int(item.get("task_record_count", 0))
    return summary


def _baseline_bundle_task_count(bundle: dict[str, object]) -> int:
    return max(
        _safe_int(bundle.get("task_record_count")),
        _safe_int(bundle.get("task_level_record_count")),
        _safe_int(bundle.get("ready_task_count")),
        _safe_int(bundle.get("task_count")),
    )


def _baseline_bundle_activation_count(bundle: dict[str, object]) -> int:
    return max(
        _safe_int(bundle.get("activated_count")),
        _safe_int(bundle.get("task_level_activated_count")),
        _safe_int(bundle.get("positive_activation_count")),
    )


def _baseline_bundle_admissible_for_main_table(bundle: dict[str, object]) -> bool:
    """Admission rule for official baselines used by main-claim gates.

    Older artifacts carried `meta.baselines_main_table` or a scalar
    `main_table_baseline_count` before the official baseline had positive
    activation and 300 task-level live evidence.  The closure boundary is the
    last line before review/release packaging, so it recomputes admission from
    materialized bundle evidence instead of trusting those stale counters.
    """

    task_count = _baseline_bundle_task_count(bundle)
    if task_count < _MIN_MAIN_TABLE_BASELINE_TASKS:
        return False
    if not any(
        bool(bundle.get(field))
        for field in (
            "main_table_admissible",
            "task_level_main_table_admissible",
            "claim_bearing_main_table_admissible",
        )
    ):
        return False
    if _baseline_bundle_activation_count(bundle) <= 0:
        return False
    activation_rate = _safe_float(
        bundle.get("activation_rate", bundle.get("task_level_activation_rate", 0.0))
    )
    if activation_rate <= 0.0:
        return False
    provider_mode = str(bundle.get("provider_mode", bundle.get("task_level_provider_mode", ""))).strip().lower()
    if provider_mode in {"", "mock", "no_provider", "no-provider", "scaffold"}:
        return False
    return True


def _admitted_main_table_baseline_count(bundles: object) -> int:
    if not isinstance(bundles, list):
        return 0
    admitted: set[str] = set()
    for item in bundles:
        if not isinstance(item, dict):
            continue
        baseline = str(item.get("baseline", "")).strip()
        if baseline and _baseline_bundle_admissible_for_main_table(item):
            admitted.add(baseline)
    return len(admitted)


def _available_publish_truth_main_table_baseline_count(root: Path) -> int:
    admitted: set[str] = set()
    for path in (root / "artifacts" / "generated" / "baselines").glob("*_publish_truth.json"):
        payload = _read_json(path, encoding="utf-8-sig")
        if not payload:
            continue
        baseline = str(payload.get("baseline") or payload.get("name") or "").strip()
        provider_mode = str(payload.get("provider_mode", "")).strip().lower()
        if (
            baseline
            and bool(payload.get("main_table_admissible", False))
            and provider_mode not in {"", "mock", "no_provider", "no-provider", "scaffold"}
            and _safe_int(payload.get("task_record_count")) >= _MIN_MAIN_TABLE_BASELINE_TASKS
            and _safe_int(payload.get("activated_count")) > 0
            and _safe_float(payload.get("activation_rate")) > 0.0
        ):
            admitted.add(baseline)
    return len(admitted)


def _read_json(path: Path, *, encoding: str) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding=encoding))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _append_unique(blockers: list[str], item: str) -> None:
    if item not in blockers:
        blockers.append(item)


def _float_mismatch(left: object, right: object, *, tolerance: float = 1e-6) -> bool:
    return abs(_safe_float(left) - _safe_float(right)) > tolerance


def _generic_utility_score_paths(payload: dict[str, object]) -> list[str]:
    paths: list[str] = []
    for section in ("records", "local_benchmark_summary", "public_benchmark_summary"):
        items = payload.get(section, [])
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if isinstance(item, dict) and "utility_score" in item:
                paths.append(f"{section}[{index}].utility_score")
    return paths


def _stale_baseline_meta_issues(payload: dict[str, object], *, local_task_target: int) -> list[str]:
    meta = payload.get("meta", {})
    if not isinstance(meta, dict):
        return []
    baselines = meta.get("baselines_main_table", [])
    if not isinstance(baselines, list):
        return []
    issues: list[str] = []
    for item in baselines:
        if not isinstance(item, dict) or item.get("name") != "Instructional Fingerprinting":
            continue
        ready = _safe_int(item.get("task_level_ready_task_count"), default=-1)
        pending = _safe_int(item.get("task_level_pending_user_review_count"), default=-1)
        if ready != local_task_target or pending != 0:
            issues.append("baseline_meta_stale:Instructional Fingerprinting")
    return issues


def _no_overfit_ledger_status(root: Path) -> dict[str, object]:
    ledger_path = root / "artifacts" / "generated" / "no_overfit_iteration_ledger.json"
    status: dict[str, object] = {
        "path": ledger_path.relative_to(root).as_posix(),
        "completed": 0,
        "required": 30,
        "ready": False,
    }
    if not ledger_path.exists():
        status["issue"] = "no_overfit_iteration_ledger_missing"
        return status
    payload = _read_json(ledger_path, encoding="utf-8")
    if not payload:
        status["issue"] = "no_overfit_iteration_ledger_invalid"
        return status
    iterations = payload.get("iterations", [])
    if not isinstance(iterations, list):
        iterations = []
    def _valid_no_overfit_entry(item: object) -> bool:
        if not isinstance(item, dict):
            return False
        has_risk = any(key in item for key in ("observed_failure_or_overfit_risk", "observed_risk"))
        has_fix = any(key in item for key in ("method_level_change", "algorithm_level_fix"))
        has_tests = any(key in item for key in ("tests_checks_run", "tests_checks"))
        return (
            has_risk
            and has_fix
            and "why_not_label_or_threshold_gaming" in item
            and has_tests
            and "remaining_blocker" in item
            and str(item.get("result", "")).strip().lower() == "pass"
        )

    valid_entry_count = sum(1 for item in iterations if _valid_no_overfit_entry(item))
    completed = _safe_int(payload.get("completed_iteration_count", len(iterations)))
    required = _safe_int(payload.get("minimum_required_iterations_before_final_rerun", 30), default=30)
    ready = (
        bool(payload.get("ready_for_final_rerun", False))
        and completed >= required
        and len(iterations) >= required
        and valid_entry_count >= required
    )
    status.update(
        {
            "completed": completed,
            "required": required,
            "entry_count": len(iterations),
            "valid_entry_count": valid_entry_count,
            "ready": ready,
        }
    )
    if not ready:
        if len(iterations) < required or valid_entry_count < required:
            status["issue"] = "no_overfit_review_ledger_missing_entries"
        else:
            status["issue"] = "no_overfit_review_rerun_not_ready"
    return status


def _transfer_public_promotion_status(root: Path) -> dict[str, object]:
    gate_path = root / "artifacts" / "generated" / "transfer_public_promotion_gate.json"
    status: dict[str, object] = {
        "path": gate_path.relative_to(root).as_posix(),
        "main_claim_allowed": False,
        "overall_status": "missing",
        "remaining_blocker_count": 0,
        "remaining_blockers": [],
        "ready": False,
    }
    payload = _read_json(gate_path, encoding="utf-8")
    if not payload:
        status["issue"] = "transfer_public_promotion_gate_missing_or_invalid"
        return status
    remaining = [str(item) for item in payload.get("remaining_blockers", []) if str(item).strip()]
    gates = payload.get("gates", [])
    gates = gates if isinstance(gates, list) else []
    gate_status = {
        str(item.get("gate", "")).strip(): str(item.get("status", "")).strip()
        for item in gates
        if isinstance(item, dict)
    }
    current_apis300_baseline_controls_ready = (
        gate_status.get("apis300_live_canonical_support") == "passed"
        and gate_status.get("baseline_activation_and_required_controls") == "passed"
    )
    main_claim_allowed = bool(payload.get("main_claim_allowed", False))
    overall_status = str(payload.get("overall_status", "")).strip()
    ready = main_claim_allowed and overall_status == "passed" and not remaining
    status.update(
        {
            "main_claim_allowed": main_claim_allowed,
            "overall_status": overall_status,
            "remaining_blocker_count": len(remaining),
            "remaining_blockers": remaining,
            "gate_status": gate_status,
            "current_apis300_baseline_controls_ready": current_apis300_baseline_controls_ready,
            "ready": ready,
        }
    )
    if not ready:
        status["issue"] = "transfer_public_promotion_gate_blocked"
    return status


def _best_paper_cycle_status(root: Path) -> dict[str, object]:
    gate_path = root / "artifacts" / "generated" / "best_paper_10pass_gap_review.json"
    status: dict[str, object] = {
        "path": gate_path.relative_to(root).as_posix(),
        "completed": 0,
        "required": 100,
        "clean_review_streak": 0,
        "required_clean_review_streak": 10,
        "p1_p2_blocker_count": 0,
        "ready": False,
    }
    payload = _read_json(gate_path, encoding="utf-8")
    if not payload:
        status["issue"] = "best_paper_10pass_gap_review_missing_or_invalid"
        return status
    completed = _safe_int(payload.get("total_review_improvement_cycles_completed"))
    clean_review_streak = _safe_int(payload.get("consecutive_clean_reviews"))
    required = _safe_int(payload.get("minimum_total_cycles_required"), default=100)
    required_clean = _safe_int(payload.get("required_consecutive_clean_reviews"), default=10)
    p1_p2_blockers = [str(item) for item in payload.get("p1_p2_blockers", []) if str(item).strip()] if isinstance(payload.get("p1_p2_blockers", []), list) else []
    formal_allowed = bool(payload.get("deepseek_formal_run_allowed", False))
    review_status = str(payload.get("review_status", "")).strip()
    ready = (
        formal_allowed
        and review_status == "passed"
        and completed >= required
        and clean_review_streak >= required_clean
        and not p1_p2_blockers
    )
    status.update(
        {
            "completed": completed,
            "required": required,
            "clean_review_streak": clean_review_streak,
            "required_clean_review_streak": required_clean,
            "p1_p2_blocker_count": len(p1_p2_blockers),
            "first_p1_p2_blockers": p1_p2_blockers[:10],
            "deepseek_formal_run_allowed": formal_allowed,
            "review_status": review_status,
            "ready": ready,
        }
    )
    if not ready:
        if completed < required:
            status["issue"] = f"best_paper_cycle_gate_pending:{completed}/{required}_cycles"
        elif clean_review_streak < required_clean:
            status["issue"] = f"best_paper_clean_review_streak_pending:{clean_review_streak}/{required_clean}"
        elif p1_p2_blockers:
            status["issue"] = "best_paper_p1_p2_blockers_remaining"
        elif not formal_allowed:
            status["issue"] = "best_paper_deepseek_formal_run_not_allowed"
        else:
            status["issue"] = "best_paper_review_status_not_passed"
    return status


def _canonical_source_run_artifact(
    operator_state: dict[str, object],
    *,
    root: Path,
) -> tuple[str, str]:
    run_id = str(operator_state.get("canonical_source_run_id", "")).strip()
    if not run_id:
        return "", ""
    artifact = root / "artifacts" / "generated" / "live_runs" / run_id / "full_eval_results.json"
    if artifact.exists():
        return run_id, artifact.relative_to(root).as_posix()

    provenance_path = root / "artifacts" / "generated" / "canonical_run_provenance.json"
    provenance = _read_json(provenance_path, encoding="utf-8")
    if (
        provenance
        and str(provenance.get("canonical_source_run_id", "")).strip() == run_id
        and bool(provenance.get("canonical_eligible", False))
    ):
        promoted_rel = str(provenance.get("canonical_artifact", "")).strip()
        promoted = root / promoted_rel if promoted_rel else root / "__missing_canonical_artifact__"
        if promoted_rel and promoted.exists():
            return run_id, promoted.relative_to(root).as_posix()
    return run_id, ""


def _canonical_source_artifact_digest_status(
    operator_state: dict[str, object],
    artifact_relative_path: str,
    *,
    root: Path,
) -> dict[str, object]:
    status: dict[str, object] = {
        "sha256": "",
        "policy": "missing_source_artifact",
        "issue": "",
    }
    if not artifact_relative_path:
        return status
    artifact = root / artifact_relative_path
    if not artifact.exists():
        return status
    digest = _sha256_file(artifact)
    pinned_digest = str(operator_state.get("canonical_source_artifact_sha256", "")).strip()
    provenance_path = root / "artifacts" / "generated" / "canonical_run_provenance.json"
    provenance = _read_json(provenance_path, encoding="utf-8")
    provenance_digest = ""
    if (
        provenance
        and str(provenance.get("canonical_artifact", "")).strip() == artifact_relative_path
        and bool(provenance.get("canonical_eligible", False))
    ):
        provenance_digest = str(provenance.get("canonical_artifact_sha256", "")).strip()
    if provenance_digest:
        status["pinned_sha256"] = provenance_digest
        if provenance_digest != digest:
            status["policy"] = "canonical_run_provenance_sha256_mismatch"
            status["issue"] = "canonical_source_artifact_sha256_mismatch"
            return status
        if pinned_digest and pinned_digest != digest:
            status["operator_state_sha256_superseded"] = pinned_digest
        status["policy"] = "canonical_run_provenance_sha256"
        return status
    status["sha256"] = digest
    if not pinned_digest:
        status["policy"] = "missing_pinned_sha256"
        status["issue"] = "canonical_source_artifact_sha256_missing"
        return status
    status["pinned_sha256"] = pinned_digest
    if pinned_digest != digest:
        status["policy"] = "pinned_sha256_mismatch"
        status["issue"] = "canonical_source_artifact_sha256_mismatch"
        return status
    status["policy"] = "pinned_sha256" if operator_state.get("canonical_source_artifact_sha256") else "canonical_run_provenance_sha256"
    return status


def load_closure_boundary(profile: str, *, root: Path = ROOT) -> dict[str, object]:
    aggregate_path = root / artifact_name(
        profile,
        smoke_name="artifacts/generated/aggregate_smoke_results.json",
        full_name="artifacts/generated/aggregate_results.json",
    )
    aggregate = _read_json(aggregate_path, encoding="utf-8")

    full_eval_path = root / artifact_name(
        profile,
        smoke_name="artifacts/generated/full_eval_smoke_results.json",
        full_name="artifacts/generated/full_eval_results.json",
    )
    full_eval_payload = _read_json(full_eval_path, encoding="utf-8-sig")

    live_aggregate = full_eval_payload.get("aggregate", {})
    live_aggregate = dict(live_aggregate) if isinstance(live_aggregate, dict) else {}
    operator_state = full_eval_payload.get("operator_state", {})
    operator_state = dict(operator_state) if isinstance(operator_state, dict) else {}
    verification_segments = full_eval_payload.get("verification_segments", {})
    verification_segments = dict(verification_segments) if isinstance(verification_segments, dict) else {}
    segmented_execution = full_eval_payload.get("segmented_execution", {})
    segmented_execution = dict(segmented_execution) if isinstance(segmented_execution, dict) else {}
    baseline_task_bundles = full_eval_payload.get("baseline_task_bundles", [])
    baseline_task_summary = _baseline_task_summary(baseline_task_bundles)
    baseline_task_evidence_count = _safe_int(
        live_aggregate.get("baseline_task_evidence_count"),
        default=0,
    )
    admitted_main_table_baseline_count = _admitted_main_table_baseline_count(baseline_task_bundles)
    available_main_table_baseline_count = _available_publish_truth_main_table_baseline_count(root)
    live_reported_main_table_baseline_count = _safe_int(
        live_aggregate.get("main_table_baseline_count", aggregate.get("main_table_baseline_count", 0))
    )
    coverage_gate_pass = _safe_bool(aggregate.get("coverage_gate_pass"))
    budget_feasible_attribution_pass = _safe_bool(aggregate.get("budget_feasible_attribution_pass"))
    live_budget_feasible_attribution_pass = _safe_bool(live_aggregate.get("budget_feasible_attribution_pass"))
    local_task_count = _safe_int(live_aggregate.get("local_task_count", aggregate.get("local_task_count", 0)))
    local_task_target = _safe_int(live_aggregate.get("local_task_target", aggregate.get("local_task_target", 0)))
    local_task_coverage_rate = _safe_float(
        live_aggregate.get("local_task_coverage_rate", aggregate.get("local_task_coverage_rate", 0.0))
    )
    public_task_count = _safe_int(live_aggregate.get("public_task_count"))
    public_task_target = _safe_int(live_aggregate.get("public_task_target"))
    public_task_coverage_rate = _safe_float(live_aggregate.get("public_task_coverage_rate"))
    main_table_baseline_count = admitted_main_table_baseline_count
    verification_segment_keys = tuple(sorted(str(key) for key in verification_segments.keys()))
    completed_verification_segments = tuple(
        sorted(str(item) for item in segmented_execution.get("completed_verification_segments", ()))
    )
    canonical_gate = operator_state.get("canonical_gate", {})
    canonical_gate = dict(canonical_gate) if isinstance(canonical_gate, dict) else {}
    canonical_source_run_id, canonical_source_run_artifact = _canonical_source_run_artifact(operator_state, root=root)
    canonical_source_digest = _canonical_source_artifact_digest_status(
        operator_state,
        canonical_source_run_artifact,
        root=root,
    )
    no_overfit_ledger = _no_overfit_ledger_status(root)
    transfer_public_promotion = _transfer_public_promotion_status(root)
    transfer_current_baseline_ready = bool(
        transfer_public_promotion.get("current_apis300_baseline_controls_ready", False)
    )
    best_paper_cycle = _best_paper_cycle_status(root)

    blockers: list[str] = []
    if not aggregate:
        blockers.append("aggregate_results_missing_or_invalid")
    if coverage_gate_pass is None:
        blockers.append("aggregate_coverage_gate_not_materialized")
    elif not coverage_gate_pass:
        blockers.append("aggregate_coverage_gate_failed")
    if budget_feasible_attribution_pass is None:
        blockers.append("aggregate_budget_feasible_attribution_gate_not_materialized")
    elif not budget_feasible_attribution_pass:
        blockers.append("aggregate_budget_feasible_attribution_gate_failed")
    if "budget_feasible_attribution_pass" not in live_aggregate:
        blockers.append("canonical_live_budget_feasible_attribution_gate_not_materialized")
    elif live_budget_feasible_attribution_pass is None:
        blockers.append("canonical_live_budget_feasible_attribution_gate_invalid")
    elif budget_feasible_attribution_pass is not None and live_budget_feasible_attribution_pass != budget_feasible_attribution_pass:
        blockers.append("aggregate_budget_feasible_attribution_gate_mismatch")
    if "hard_decoy_registry_count" not in live_aggregate:
        blockers.append("canonical_live_hard_decoy_registry_count_not_materialized")
    elif "hard_decoy_registry_count" in aggregate and _safe_int(aggregate.get("hard_decoy_registry_count", 0)) != _safe_int(live_aggregate.get("hard_decoy_registry_count", 0)):
        blockers.append("aggregate_hard_decoy_registry_count_mismatch")
    if "support_count_gate_pass_rate" not in live_aggregate:
        blockers.append("canonical_live_support_count_gate_not_materialized")
    elif "support_count_gate_pass_rate" in aggregate and _float_mismatch(aggregate.get("support_count_gate_pass_rate", 0.0), live_aggregate.get("support_count_gate_pass_rate", 0.0)):
        blockers.append("aggregate_support_count_gate_mismatch")
    if "support_family_diversity_gate_pass_rate" not in live_aggregate:
        blockers.append("canonical_live_support_family_diversity_gate_not_materialized")
    elif "support_family_diversity_gate_pass_rate" in aggregate and _float_mismatch(aggregate.get("support_family_diversity_gate_pass_rate", 0.0), live_aggregate.get("support_family_diversity_gate_pass_rate", 0.0)):
        blockers.append("aggregate_support_family_diversity_gate_mismatch")
    if "support_bucket_diversity_gate_pass_rate" not in live_aggregate:
        blockers.append("canonical_live_support_bucket_diversity_gate_not_materialized")
    elif "support_bucket_diversity_gate_pass_rate" in aggregate and _float_mismatch(aggregate.get("support_bucket_diversity_gate_pass_rate", 0.0), live_aggregate.get("support_bucket_diversity_gate_pass_rate", 0.0)):
        blockers.append("aggregate_support_bucket_diversity_gate_mismatch")
    if aggregate:
        if _safe_int(aggregate.get("local_task_count", 0)) != _safe_int(live_aggregate.get("local_task_count", 0)):
            blockers.append("aggregate_local_task_count_mismatch")
        if _safe_int(aggregate.get("local_task_target", 0)) != _safe_int(live_aggregate.get("local_task_target", 0)):
            blockers.append("aggregate_local_task_target_mismatch")
        if _float_mismatch(aggregate.get("local_task_coverage_rate", 0.0), live_aggregate.get("local_task_coverage_rate", 0.0)):
            blockers.append("aggregate_local_task_coverage_mismatch")
        if _safe_int(aggregate.get("public_task_count", 0)) != _safe_int(live_aggregate.get("public_task_count", 0)):
            blockers.append("aggregate_public_task_count_mismatch")
        if _safe_int(aggregate.get("public_task_target", 0)) != _safe_int(live_aggregate.get("public_task_target", 0)):
            blockers.append("aggregate_public_task_target_mismatch")
        if _float_mismatch(aggregate.get("public_task_coverage_rate", 0.0), live_aggregate.get("public_task_coverage_rate", 0.0)):
            blockers.append("aggregate_public_task_coverage_mismatch")
        if (
            _safe_int(aggregate.get("main_table_baseline_count", 0)) != main_table_baseline_count
            and not transfer_current_baseline_ready
        ):
            blockers.append("aggregate_main_table_baseline_count_mismatch")
    if (
        "main_table_baseline_count" in live_aggregate
        and live_reported_main_table_baseline_count != main_table_baseline_count
        and not transfer_current_baseline_ready
    ):
        blockers.append("canonical_live_main_table_baseline_count_stale_or_not_admission_checked")
    if local_task_target <= 0:
        blockers.append("missing_local_task_target")
    if local_task_count < local_task_target:
        blockers.append("apistealbench_local_coverage_incomplete")
    if local_task_coverage_rate < 1.0:
        blockers.append("local_task_coverage_rate_below_one")
    if public_task_target > 0 and public_task_count < public_task_target:
        blockers.append("public_benchmark_coverage_incomplete")
    if public_task_target > 0 and public_task_coverage_rate < 1.0:
        blockers.append("public_task_coverage_rate_below_one")
    if main_table_baseline_count <= 0 and available_main_table_baseline_count <= 0 and not transfer_current_baseline_ready:
        blockers.append("no_runnable_main_table_baselines")
    elif main_table_baseline_count <= 0 < available_main_table_baseline_count and not transfer_current_baseline_ready:
        blockers.append("canonical_live_main_table_baseline_missing_from_current_run")
    if baseline_task_evidence_count <= 0:
        blockers.append("baseline_task_level_evidence_missing")
    if "baseline_task_evidence_count" not in live_aggregate:
        blockers.append("baseline_task_evidence_count_not_materialized")
    if str(full_eval_payload.get("schema_version", "")) != "probetrace_live_gate_v3":
        blockers.append("updated_owner_decoy_live_schema_not_materialized")
    generic_utility_paths = _generic_utility_score_paths(full_eval_payload)
    if generic_utility_paths:
        _append_unique(blockers, "generic_utility_score_present")
    for issue in _stale_baseline_meta_issues(full_eval_payload, local_task_target=local_task_target):
        _append_unique(blockers, issue)
    if operator_state.get("artifact_role") != "canonical_live_eval":
        blockers.append("canonical_live_finalize_pending")
    if not canonical_source_run_id:
        blockers.append("canonical_source_run_id_missing")
    elif not canonical_source_run_artifact:
        blockers.append("canonical_source_run_artifact_missing")
    elif canonical_source_digest.get("issue"):
        blockers.append(str(canonical_source_digest["issue"]))
    if verification_segment_keys != tuple(sorted(_REQUIRED_ATTACK_SPLITS)):
        blockers.append("verification_segments_incomplete")
    if completed_verification_segments != tuple(sorted(_REQUIRED_ATTACK_SPLITS)):
        blockers.append("completed_verification_segments_incomplete")
    if not canonical_gate:
        blockers.append("canonical_gate_missing")
    elif not bool(canonical_gate.get("eligible", False)):
        blockers.append("canonical_gate_not_eligible")
    for issue in canonical_gate.get("issues", []):
        normalized = str(issue).strip()
        if normalized:
            _append_unique(blockers, normalized)
    if profile == "full" and not bool(no_overfit_ledger.get("ready", False)):
        _append_unique(blockers, str(no_overfit_ledger.get("issue", "no_overfit_review_ledger_incomplete")))
    if profile == "full" and not bool(transfer_public_promotion.get("ready", False)):
        _append_unique(blockers, str(transfer_public_promotion.get("issue", "transfer_public_promotion_gate_blocked")))
        for blocker in list(transfer_public_promotion.get("remaining_blockers", []))[:25]:
            _append_unique(blockers, f"transfer_public_promotion_gate:{blocker}")
    if profile == "full" and not bool(best_paper_cycle.get("ready", False)):
        _append_unique(blockers, str(best_paper_cycle.get("issue", "best_paper_cycle_gate_blocked")))
        for blocker in list(best_paper_cycle.get("first_p1_p2_blockers", []))[:10]:
            _append_unique(blockers, f"best_paper_cycle_first_p1_p2:{blocker}")

    canonical_full_evidence_ready = not blockers
    aggregate_first_failing_gate = str(aggregate.get("first_failing_gate", "")).strip()
    if blockers:
        if not aggregate_first_failing_gate or aggregate_first_failing_gate == "all_gates_pass":
            first_failing_gate = blockers[0]
        else:
            first_failing_gate = aggregate_first_failing_gate
    else:
        first_failing_gate = aggregate_first_failing_gate or "all_gates_pass"
    current_full_eval_artifact_role = str(operator_state.get("artifact_role", "")).strip() or (
        "canonical_full_evidence" if canonical_full_evidence_ready else "partial_segmented_noncanonical"
    )
    return {
        "aggregate_path": aggregate_path.relative_to(root).as_posix(),
        "full_eval_path": full_eval_path.relative_to(root).as_posix(),
        "local_task_count": local_task_count,
        "local_task_target": local_task_target,
        "local_task_coverage_rate": round(local_task_coverage_rate, 4),
        "public_task_count": public_task_count,
        "public_task_target": public_task_target,
        "public_task_coverage_rate": round(public_task_coverage_rate, 4),
        "main_table_baseline_count": main_table_baseline_count,
        "available_main_table_baseline_count": available_main_table_baseline_count,
        "baseline_task_evidence_count": baseline_task_evidence_count,
        "baseline_task_summary": baseline_task_summary,
        "verification_segment_keys": list(verification_segment_keys),
        "completed_verification_segments": list(completed_verification_segments),
        "canonical_source_run_id": canonical_source_run_id,
        "canonical_source_run_artifact": canonical_source_run_artifact,
        "canonical_source_artifact_sha256": canonical_source_digest.get("sha256", ""),
        "canonical_source_artifact_digest_policy": canonical_source_digest.get("policy", ""),
        "no_overfit_revision": no_overfit_ledger,
        "transfer_public_promotion": transfer_public_promotion,
        "best_paper_cycle": best_paper_cycle,
        "canonical_full_evidence_ready": canonical_full_evidence_ready,
        "current_full_eval_artifact_role": current_full_eval_artifact_role,
        "canonical_full_evidence_blockers": blockers,
        "first_failing_gate": first_failing_gate,
    }
