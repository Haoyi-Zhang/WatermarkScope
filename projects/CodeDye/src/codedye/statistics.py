from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
import re

from .contamination import ContaminationAssessment, evaluate_contamination
from .gate_freeze import frozen_accusation_threshold, frozen_accusation_threshold_version
from .benchmarks import task_canary_split, task_chronology_split, task_hidden_test_family, task_operator_slice, task_release_window, task_target_family
from .protocol import AssetScorecard, BenchmarkTask, ContaminationDecision


@dataclass(frozen=True, slots=True)
class NullCalibration:
    selected_task_id: str
    selected_asset_id: str
    selected_score: float
    null_scores: tuple[float, ...]
    empirical_p_value: float
    false_positive_bound: float
    familywise_test_count: int
    strongest_null_score: float
    strongest_null_margin: float
    correction: str
    matched_null_sample_size: int = 0
    null_pool_strategy: str = ""
    familywise_adjusted_p_value: float = 1.0
    familywise_decision_gate_pass: bool = False
    strongest_null_task_id: str = ""
    null_pool_tier: int = 0
    null_pool_fallback_used: bool = False
    null_calibration_method: str = "metadata_matched_empirical_dominance_tail_bound"


def _empirical_tail_probability(observed_score: float, null_scores: tuple[float, ...]) -> float:
    if not null_scores:
        return 1.0
    exceedances = sum(1 for item in null_scores if item >= observed_score)
    return round((exceedances + 1) / (len(null_scores) + 1), 4)


def _asset_scorecards(
    assessment: ContaminationAssessment,
    null_scores: tuple[float, ...],
) -> tuple[AssetScorecard, ...]:
    null_mean = round(mean(null_scores), 4) if null_scores else 0.0
    return (
        AssetScorecard(
            asset_id=assessment.accused_asset_ids[0] if assessment.accused_asset_ids else "null_asset",
            score=assessment.suspicion_score,
            mean_agreement=assessment.canary_coverage,
            mean_forensic_weight=assessment.witness_density,
            trace_consistency=assessment.witness_density,
            query_count=max(len(assessment.evidence_trace), 1),
        ),
        AssetScorecard(
            asset_id="null_control",
            score=null_mean,
            mean_agreement=0.0,
            mean_forensic_weight=null_mean,
            trace_consistency=0.0,
            query_count=max(len(null_scores), 1),
        ),
    )


def _protected_asset_id(task: BenchmarkTask) -> str:
    return {str(key): str(value) for key, value in task.metadata}.get("protected_asset_id", task.task_id)


_NULL_POOL_TIERS: tuple[tuple[int, ...], ...] = (
    (1, 1, 1, 1, 1, 1, 1),
    (1, 1, 1, 1, 1, 1, 0),
    (1, 1, 1, 1, 1, 0, 0),
    (1, 1, 1, 1, 0, 0, 0),
    (1, 1, 1, 0, 0, 0, 0),
    (1, 1, 0, 0, 0, 0, 0),
    (1, 0, 0, 0, 0, 0, 0),
    (0, 0, 0, 0, 0, 0, 0),
)


def _null_pool_signature(task: BenchmarkTask, candidate: BenchmarkTask) -> tuple[int, ...]:
    return (
        1 if task.subset == candidate.subset else 0,
        1 if task_chronology_split(task) == task_chronology_split(candidate) else 0,
        1 if task_canary_split(task) == task_canary_split(candidate) else 0,
        1 if task_hidden_test_family(task) == task_hidden_test_family(candidate) else 0,
        1 if task_release_window(task) == task_release_window(candidate) else 0,
        1 if task_operator_slice(task) == task_operator_slice(candidate) else 0,
        1 if task_target_family(task) == task_target_family(candidate) else 0,
    )


def _metadata_null_key(item: tuple[BenchmarkTask, ContaminationAssessment]) -> tuple[str, str, str, str, str, str, str, str]:
    task, _assessment = item
    return (
        task.subset,
        task_chronology_split(task),
        task_canary_split(task),
        task_hidden_test_family(task),
        task_release_window(task),
        task_operator_slice(task),
        task_target_family(task),
        task.task_id,
    )


def _select_null_pool(
    task: BenchmarkTask,
    scored: tuple[tuple[BenchmarkTask, ContaminationAssessment, tuple[int, ...]], ...],
) -> tuple[tuple[tuple[BenchmarkTask, ContaminationAssessment], ...], str, int, bool]:
    for tier_index, tier in enumerate(_NULL_POOL_TIERS):
        tier_candidates = tuple(
            sorted(
                (
                    (candidate, assessment)
                    for candidate, assessment, signature in scored
                    if signature >= tier
                ),
                key=_metadata_null_key,
            )
        )
        if len(tier_candidates) >= 20 or (tier_index == len(_NULL_POOL_TIERS) - 1 and tier_candidates):
            tier_number = tier_index + 1
            fallback_used = tier_index == len(_NULL_POOL_TIERS) - 1
            return (
                tier_candidates,
                f"metadata_matched_hard_negative_tier_{tier_number}_of_{len(_NULL_POOL_TIERS)}_no_outcome_selection",
                tier_number,
                fallback_used,
            )
    return (), "empty_null_pool", 0, False


def _null_calibration_method_for_strategy(strategy: str) -> str:
    if "tier_8_of_8" in strategy:
        return "leave_one_task_empirical_dominance_tail_bound"
    if strategy == "empty_null_pool":
        return "empty_null_pool"
    return "metadata_matched_empirical_dominance_tail_bound"


def _null_pool_tier_from_strategy(strategy: str) -> int:
    match = re.search(r"tier_(\d+)_of_", strategy)
    return int(match.group(1)) if match else 0


def _assessment_rank(assessment: ContaminationAssessment) -> tuple[float | int, ...]:
    return (
        assessment.evidence_stage,
        *assessment.gate_vector,
        round(assessment.canary_coverage, 4),
    )


def _applicable_hypothesis_families(task: BenchmarkTask) -> tuple[str, ...]:
    families: list[str] = ["direct_canary", "semantic_witness", "target_family"]
    chronology_split = task_chronology_split(task)
    canary_split = task_canary_split(task)
    if chronology_split in {"same_window", "staggered_window", "post_release_holdout"}:
        families.append("chronology")
    if canary_split == "rewrite_marker" or task.subset == "canary_preserving_rewrites":
        families.append("rewrite")
    if task.subset == "cross_language_variants":
        families.append("cross_language")
    seen: set[str] = set()
    ordered: list[str] = []
    for family in families:
        if family not in seen:
            seen.add(family)
            ordered.append(family)
    return tuple(ordered)


def _dominance_tail_probability(
    observed_assessment: ContaminationAssessment,
    null_assessments: tuple[ContaminationAssessment, ...],
) -> float:
    if not null_assessments:
        return 1.0
    observed_rank = _assessment_rank(observed_assessment)
    exceedances = sum(1 for item in null_assessments if _assessment_rank(item) >= observed_rank)
    return round((exceedances + 1) / (len(null_assessments) + 1), 4)


def _rank_compare(left: ContaminationAssessment, right: ContaminationAssessment | None) -> float:
    if right is None:
        return 1.0
    left_rank = _assessment_rank(left)
    right_rank = _assessment_rank(right)
    if left_rank > right_rank:
        return 1.0
    if left_rank < right_rank:
        return -1.0
    return 0.0


def _familywise_adjusted_p_value(empirical_p_value: float, family_count: int) -> float:
    family_count = max(family_count, 1)
    return round(min(1.0, empirical_p_value * family_count), 4)


def _ranked_candidate_assessments(
    task: BenchmarkTask,
    code: str,
    task_pool: tuple[BenchmarkTask, ...],
) -> tuple[tuple[BenchmarkTask, ContaminationAssessment], tuple[tuple[BenchmarkTask, ContaminationAssessment], ...]]:
    candidate_pool = task_pool or (task,)
    scored = tuple(
        (
            candidate,
            evaluate_contamination(candidate, code, observed_prompt=task.prompt),
        )
        for candidate in candidate_pool
    )
    ranked = tuple(
        sorted(
            scored,
            key=lambda item: (
                _assessment_rank(item[1]),
                -len(item[0].task_id),
            ),
            reverse=True,
        )
    )
    return ranked[0], ranked


def _null_candidate_assessments(
    task: BenchmarkTask,
    code: str,
    task_pool: tuple[BenchmarkTask, ...],
) -> tuple[ContaminationAssessment, tuple[tuple[BenchmarkTask, ContaminationAssessment], ...], str, int, bool]:
    selected_assessment = evaluate_contamination(task, code, observed_prompt=task.prompt)
    protected_asset_id = _protected_asset_id(task)
    candidate_pool = task_pool or (task,)
    scored = tuple(
        (
            candidate,
            evaluate_contamination(candidate, code, observed_prompt=task.prompt),
            _null_pool_signature(task, candidate),
        )
        for candidate in candidate_pool
        if _protected_asset_id(candidate) != protected_asset_id
    )
    null_ranked, strategy, tier, fallback_used = _select_null_pool(task, scored)
    return selected_assessment, null_ranked, strategy, tier, fallback_used


def build_null_calibration(
    task: BenchmarkTask,
    code: str,
    task_pool: tuple[BenchmarkTask, ...],
) -> NullCalibration:
    selected_assessment, ranked, null_pool_strategy, null_pool_tier, null_pool_fallback_used = _null_candidate_assessments(task, code, task_pool)
    protected_asset_id = _protected_asset_id(task)
    null_assessments = tuple(assessment for _, assessment in ranked)
    null_scores = tuple(float(assessment.suspicion_score) for assessment in null_assessments)
    empirical_p_value = _dominance_tail_probability(selected_assessment, null_assessments)
    strongest_null_item = max(ranked, key=lambda item: _assessment_rank(item[1]), default=None)
    strongest_null = strongest_null_item[1] if strongest_null_item is not None else None
    strongest_null_task_id = strongest_null_item[0].task_id if strongest_null_item is not None else ""
    familywise_test_count = max(len(null_assessments), 1)
    calibration_method = _null_calibration_method_for_strategy(null_pool_strategy)
    familywise_adjusted_p_value = empirical_p_value if null_scores else 1.0
    corrected = familywise_adjusted_p_value if null_scores else 1.0
    return NullCalibration(
        selected_task_id=task.task_id,
        selected_asset_id=protected_asset_id,
        selected_score=selected_assessment.suspicion_score,
        null_scores=null_scores,
        empirical_p_value=empirical_p_value,
        false_positive_bound=corrected,
        familywise_test_count=familywise_test_count,
        familywise_adjusted_p_value=familywise_adjusted_p_value,
        strongest_null_score=strongest_null.suspicion_score if strongest_null is not None else 0.0,
        strongest_null_margin=_rank_compare(selected_assessment, strongest_null),
        correction=calibration_method,
        matched_null_sample_size=len(null_assessments),
        null_pool_strategy=null_pool_strategy,
        strongest_null_task_id=strongest_null_task_id,
        null_pool_tier=null_pool_tier,
        null_pool_fallback_used=null_pool_fallback_used,
        null_calibration_method=calibration_method,
    )


def build_contamination_decision(
    task: BenchmarkTask,
    code: str,
    task_pool: tuple[BenchmarkTask, ...],
    *,
    query_count: int = 1,
    latency_ms: float = 0.0,
    extra_query_cost: int = 0,
) -> ContaminationDecision:
    assessment, null_ranked, null_pool_strategy, null_pool_tier, null_pool_fallback_used = _null_candidate_assessments(task, code, task_pool)
    calibration = build_null_calibration(task, code, task_pool)
    accusation_eligibility_bound = 0.05
    null_control_supported = (
        calibration.matched_null_sample_size >= 5
        and calibration.familywise_test_count >= 15
        and calibration.strongest_null_margin > 0.0
    )
    familywise_decision_gate_pass = (
        assessment.contaminated
        and null_control_supported
        and calibration.familywise_adjusted_p_value <= accusation_eligibility_bound
        and assessment.witness_density >= 0.25
        and assessment.canary_coverage >= 0.5
        and assessment.admissible_output_visible_canary_evidence_count >= 2
    )
    contaminated = familywise_decision_gate_pass
    strongest_null = max((item[1] for item in null_ranked), key=_assessment_rank, default=None)
    evidence_trace = assessment.evidence_trace + (
        f"selected_task_id:{task.task_id}",
        f"selected_asset_id:{_protected_asset_id(task)}",
        f"selected_score:{calibration.selected_score:.4f}",
        f"selected_stage:{assessment.evidence_stage}",
        f"selected_gate_vector:{'|'.join(str(bit) for bit in assessment.gate_vector)}",
        f"null_sample_size:{len(calibration.null_scores)}",
        f"matched_null_sample_size:{calibration.matched_null_sample_size}",
        f"null_pool_strategy:{calibration.null_pool_strategy or null_pool_strategy}",
        f"null_pool_tier:{calibration.null_pool_tier or null_pool_tier}",
        f"null_pool_fallback_used:{int(calibration.null_pool_fallback_used or null_pool_fallback_used)}",
        f"strongest_null_task_id:{calibration.strongest_null_task_id}",
        f"strongest_null_score:{calibration.strongest_null_score:.4f}",
        f"strongest_null_margin:{calibration.strongest_null_margin:.4f}",
        f"empirical_p_value:{calibration.empirical_p_value:.4f}",
        f"familywise_adjusted_p_value:{calibration.familywise_adjusted_p_value:.4f}",
        f"false_positive_bound:{calibration.false_positive_bound:.4f}",
        f"accusation_eligibility_bound:{accusation_eligibility_bound:.4f}",
        f"familywise_test_count:{calibration.familywise_test_count}",
        f"correction:{calibration.correction}",
        f"null_calibration_method:{calibration.null_calibration_method}",
        "familywise_event:lexicographic_gate_vector_with_coverage_tiebreak_dominance_tail",
        f"null_control_supported:{int(null_control_supported)}",
        f"familywise_decision_gate_pass:{int(familywise_decision_gate_pass)}",
        f"witness_density:{assessment.witness_density:.4f}",
        f"output_visible_canary_evidence_count:{assessment.output_visible_canary_evidence_count}",
        f"admissible_output_visible_canary_evidence_count:{assessment.admissible_output_visible_canary_evidence_count}",
        f"diagnostic_evidence_count:{assessment.diagnostic_evidence_count}",
        f"hidden_test_family_diagnostic_only:{int(assessment.hidden_test_family_diagnostic_only)}",
        f"direct_output_visible_canary_count:{assessment.direct_output_visible_canary_count}",
        f"semantic_output_visible_canary_count:{assessment.semantic_output_visible_canary_count}",
        f"prompt_context_canary_evidence_count:{assessment.prompt_context_canary_evidence_count}",
        f"familywise_control:{calibration.null_calibration_method}",
        f"threshold_freeze_version:{frozen_accusation_threshold_version()}",
    )
    return ContaminationDecision(
        contaminated=contaminated,
        accused_asset_ids=assessment.accused_asset_ids if contaminated else (),
        contamination_score=assessment.suspicion_score,
        p_value_or_score=calibration.empirical_p_value,
        false_positive_bound=calibration.false_positive_bound,
        accusation_eligibility_bound=accusation_eligibility_bound,
        familywise_test_count=calibration.familywise_test_count,
        familywise_adjusted_p_value=calibration.familywise_adjusted_p_value,
        null_sample_size=len(calibration.null_scores),
        strongest_null_score=calibration.strongest_null_score,
        strongest_null_margin=calibration.strongest_null_margin,
        query_count=query_count,
        matched_null_sample_size=calibration.matched_null_sample_size,
        null_pool_strategy=calibration.null_pool_strategy or null_pool_strategy,
        null_pool_tier=calibration.null_pool_tier or null_pool_tier,
        null_pool_fallback_used=calibration.null_pool_fallback_used or null_pool_fallback_used,
        null_calibration_method=calibration.null_calibration_method,
        strongest_null_task_id=calibration.strongest_null_task_id,
        witness_density=assessment.witness_density,
        output_visible_canary_evidence_count=assessment.output_visible_canary_evidence_count,
        admissible_output_visible_canary_evidence_count=assessment.admissible_output_visible_canary_evidence_count,
        diagnostic_evidence_count=assessment.diagnostic_evidence_count,
        hidden_test_family_diagnostic_only=assessment.hidden_test_family_diagnostic_only,
        direct_output_visible_canary_count=assessment.direct_output_visible_canary_count,
        semantic_output_visible_canary_count=assessment.semantic_output_visible_canary_count,
        prompt_context_canary_evidence_count=assessment.prompt_context_canary_evidence_count,
        latency_ms=round(latency_ms, 4),
        extra_query_cost=extra_query_cost,
        margin=_rank_compare(assessment, strongest_null),
        query_budget_used=query_count,
        calibrated_threshold=frozen_accusation_threshold(),
        canary_coverage=assessment.canary_coverage,
        familywise_decision_gate_pass=familywise_decision_gate_pass,
        trace_consistency=assessment.witness_density,
        service_commitment_root="",
        commitment_trace_root="",
        probe_evidence=(),
        top_asset_scores=_asset_scorecards(assessment, calibration.null_scores),
        evidence_trace=evidence_trace,
        notes=(
            "contamination_native_accusation",
            "cross_asset_null_calibration",
            "empirical_dominance_tail_bound",
            "familywise_corrected_false_positive_bound",
            "matched_hard_negative_null_pool",
            "strict_null_control_gate",
            "familywise_decision_gate_pass",
            "witness_density_gate",
        ),
    )


def _record_status(item: dict[str, object], key: str) -> str:
    if key in item:
        return str(item.get(key, ""))
    return str(item.get("scoring_status", "scored"))


def _utility_scored(item: dict[str, object]) -> bool:
    return _record_status(item, "utility_scoring_status") == "scored"


def _contamination_scored(item: dict[str, object]) -> bool:
    return _record_status(item, "contamination_scoring_status") == "scored"


def _increment(counter: dict[str, int], value: str) -> None:
    if value:
        counter[value] = counter.get(value, 0) + 1


def batch_contamination_stats(
    records: tuple[dict[str, object], ...] | list[dict[str, object]],
) -> dict[str, object]:
    subset_counts: dict[str, int] = {}
    benchmark_counts: dict[str, int] = {}
    task_source_counts: dict[str, int] = {}
    utility_benchmark_counts: dict[str, int] = {}
    utility_task_source_counts: dict[str, int] = {}
    chronology_split_counts: dict[str, int] = {}
    release_window_counts: dict[str, int] = {}
    canary_split_counts: dict[str, int] = {}
    review_status_counts: dict[str, int] = {}
    scoring_status_counts: dict[str, int] = {}
    utility_scoring_status_counts: dict[str, int] = {}
    contamination_scoring_status_counts: dict[str, int] = {}
    protected_assets: set[str] = set()
    accusation_scores: list[float] = []
    false_positive_bounds: list[float] = []
    empirical_p_values: list[float] = []
    null_sample_sizes: list[int] = []
    familywise_test_counts: list[int] = []
    strongest_null_margins: list[float] = []
    accusation_eligibility_hits: list[float] = []
    output_visible_canary_counts: list[int] = []
    diagnostic_evidence_counts: list[int] = []
    hidden_test_family_diagnostic_only_flags: list[int] = []
    prompt_context_canary_counts: list[int] = []
    provider_live_record_count = 0
    provider_live_scored_count = 0
    provider_live_utility_scored_count = 0
    contamination_scored_records = [item for item in records if _contamination_scored(item)]
    utility_scored_records = [item for item in records if _utility_scored(item)]
    for item in records:
        review_status = str(item.get("review_status", "ready"))
        _increment(review_status_counts, review_status)
        scoring_status = str(item.get("scoring_status", "scored"))
        _increment(scoring_status_counts, scoring_status)
        _increment(utility_scoring_status_counts, _record_status(item, "utility_scoring_status"))
        _increment(contamination_scoring_status_counts, _record_status(item, "contamination_scoring_status"))
        if str(item.get("provider_mode_resolved", "")) == "live":
            provider_live_record_count += 1
            if _contamination_scored(item):
                provider_live_scored_count += 1
            if _utility_scored(item):
                provider_live_utility_scored_count += 1
    for item in contamination_scored_records:
        benchmark = str(item.get("benchmark", ""))
        _increment(benchmark_counts, benchmark)
        task_source = str(item.get("task_source", item.get("source", "")))
        _increment(task_source_counts, task_source)
        subset = str(item.get("subset", ""))
        _increment(subset_counts, subset)
        chronology_split = str(item.get("chronology_split", ""))
        _increment(chronology_split_counts, chronology_split)
        release_window = str(item.get("release_window", ""))
        _increment(release_window_counts, release_window)
        canary_split = str(item.get("canary_split", ""))
        _increment(canary_split_counts, canary_split)
        accusation_scores.append(float(item.get("contamination_score", 0.0)))
        false_positive_bounds.append(float(item.get("false_positive_bound", 1.0)))
        empirical_p_values.append(float(item.get("p_value_or_score", 1.0)))
        null_sample_sizes.append(int(item.get("null_sample_size", 0)))
        familywise_test_counts.append(int(item.get("familywise_test_count", 0)))
        strongest_null_margins.append(float(item.get("strongest_null_margin", 0.0)))
        eligibility_bound = float(item.get("accusation_eligibility_bound", 0.05) or 0.05)
        accusation_eligibility_hits.append(1.0 if float(item.get("false_positive_bound", 1.0)) <= eligibility_bound else 0.0)
        output_visible_canary_counts.append(
            int(item.get("admissible_output_visible_canary_evidence_count", item.get("output_visible_canary_evidence_count", 0)))
        )
        diagnostic_evidence_counts.append(int(item.get("diagnostic_evidence_count", 0)))
        hidden_test_family_diagnostic_only_flags.append(1 if bool(item.get("hidden_test_family_diagnostic_only", False)) else 0)
        prompt_context_canary_counts.append(int(item.get("prompt_context_canary_evidence_count", 0)))
        for asset_id in item.get("accused_asset_ids", []):
            protected_assets.add(str(asset_id))
    for item in utility_scored_records:
        _increment(utility_benchmark_counts, str(item.get("benchmark", "")))
        _increment(utility_task_source_counts, str(item.get("task_source", item.get("source", ""))))
    return {
        "benchmark_counts": benchmark_counts,
        "task_source_counts": task_source_counts,
        "utility_benchmark_counts": utility_benchmark_counts,
        "utility_task_source_counts": utility_task_source_counts,
        "subset_counts": subset_counts,
        "chronology_split_counts": chronology_split_counts,
        "release_window_counts": release_window_counts,
        "canary_split_counts": canary_split_counts,
        "review_status_counts": review_status_counts,
        "scoring_status_counts": scoring_status_counts,
        "utility_scoring_status_counts": utility_scoring_status_counts,
        "contamination_scoring_status_counts": contamination_scoring_status_counts,
        "pending_user_review_count": review_status_counts.get("pending_user_review", 0),
        "unscored_record_count": sum(count for status, count in scoring_status_counts.items() if status != "scored"),
        "utility_unscored_record_count": len(records) - len(utility_scored_records),
        "contamination_unscored_record_count": len(records) - len(contamination_scored_records),
        "utility_only_record_count": scoring_status_counts.get("utility_only_public_benchmark", 0),
        "provider_live_record_count": provider_live_record_count,
        "provider_live_scored_count": provider_live_scored_count,
        "provider_live_utility_scored_count": provider_live_utility_scored_count,
        "scored_record_count": len(contamination_scored_records),
        "contamination_scored_record_count": len(contamination_scored_records),
        "utility_scored_record_count": len(utility_scored_records),
        "strict_null_control_rate": round(mean(1.0 if item <= 0.05 else 0.0 for item in false_positive_bounds), 4)
        if false_positive_bounds
        else 0.0,
        "accusation_eligibility_rate": round(mean(accusation_eligibility_hits), 4)
        if accusation_eligibility_hits
        else 0.0,
        "public_utility_record_count": sum(
            1 for item in utility_scored_records if str(item.get("task_source", item.get("source", ""))) == "external_checkout"
        ),
        "public_contamination_scored_record_count": sum(
            1 for item in contamination_scored_records if str(item.get("task_source", item.get("source", ""))) == "external_checkout"
        ),
        "accused_asset_count": len(protected_assets),
        "average_contamination_score": round(mean(accusation_scores), 4) if accusation_scores else 0.0,
        "average_false_positive_bound": round(mean(false_positive_bounds), 4) if false_positive_bounds else 1.0,
        "median_false_positive_bound": round(median(false_positive_bounds), 4) if false_positive_bounds else 1.0,
        "max_false_positive_bound": round(max(false_positive_bounds), 4) if false_positive_bounds else 1.0,
        "median_empirical_p_value": round(median(empirical_p_values), 4) if empirical_p_values else 1.0,
        "min_null_sample_size": min(null_sample_sizes) if null_sample_sizes else 0,
        "median_familywise_test_count": round(median(familywise_test_counts), 4) if familywise_test_counts else 0.0,
        "strongest_null_margin_pass_rate": round(mean(1.0 if item > 0.0 else 0.0 for item in strongest_null_margins), 4)
        if strongest_null_margins
        else 0.0,
        "output_visible_canary_evidence_record_count": sum(1 for item in output_visible_canary_counts if item > 0),
        "output_visible_canary_evidence_rate": round(mean(1.0 if item > 0 else 0.0 for item in output_visible_canary_counts), 4)
        if output_visible_canary_counts
        else 0.0,
        "admissible_output_visible_canary_evidence_record_count": sum(1 for item in output_visible_canary_counts if item > 0),
        "admissible_output_visible_canary_evidence_rate": round(mean(1.0 if item > 0 else 0.0 for item in output_visible_canary_counts), 4)
        if output_visible_canary_counts
        else 0.0,
        "diagnostic_evidence_record_count": sum(1 for item in diagnostic_evidence_counts if item > 0),
        "diagnostic_evidence_rate": round(mean(1.0 if item > 0 else 0.0 for item in diagnostic_evidence_counts), 4)
        if diagnostic_evidence_counts
        else 0.0,
        "hidden_test_family_diagnostic_only_rate": round(mean(hidden_test_family_diagnostic_only_flags), 4)
        if hidden_test_family_diagnostic_only_flags
        else 0.0,
        "prompt_context_only_canary_record_count": sum(
            1 for output_count, context_count in zip(output_visible_canary_counts, prompt_context_canary_counts)
            if output_count == 0 and context_count > 0
        ),
        "prompt_context_only_canary_rate": round(
            mean(
                1.0 if output_count == 0 and context_count > 0 else 0.0
                for output_count, context_count in zip(output_visible_canary_counts, prompt_context_canary_counts)
            ),
            4,
        )
        if prompt_context_canary_counts
        else 0.0,
        "prompt_context_only_rate": round(
            mean(
                1.0 if output_count == 0 and context_count > 0 else 0.0
                for output_count, context_count in zip(output_visible_canary_counts, prompt_context_canary_counts)
            ),
            4,
        )
        if prompt_context_canary_counts
        else 0.0,
        "familywise_interpretation": {
            "null_calibration_method": "leave_one_task_empirical_dominance_tail_bound",
            "familywise_event": "lexicographic_gate_vector_with_coverage_tiebreak_dominance_tail",
            "second_correction_applied": False,
            "headline_form": "lexicographic_gate_vector_not_weighted_sum",
        },
    }
