from __future__ import annotations

from collections import Counter
from random import Random
from statistics import mean

from .benchmarks import task_canary_split, task_chronology_split, task_target_family
from .protocol import BenchmarkTask


def benjamini_hochberg(p_values: tuple[float, ...] | list[float], q: float = 0.05) -> dict[str, object]:
    indexed = sorted((float(value), index) for index, value in enumerate(p_values))
    m = len(indexed)
    decisions = [False for _ in indexed]
    largest_rank = 0
    cutoff = 0.0
    for rank, (p_value, _index) in enumerate(indexed, start=1):
        threshold = q * rank / max(m, 1)
        if p_value <= threshold:
            largest_rank = rank
            cutoff = threshold
    if largest_rank:
        for rank, (_p_value, original_index) in enumerate(indexed, start=1):
            if rank <= largest_rank:
                decisions[original_index] = True
    return {
        "method": "benjamini_hochberg",
        "q": q,
        "hypothesis_count": m,
        "largest_rejected_rank": largest_rank,
        "cutoff": round(cutoff, 6),
        "decisions": decisions,
    }


def bootstrap_mean_ci(values: tuple[float, ...] | list[float], iterations: int = 200, seed: int = 0) -> dict[str, object]:
    clean_values = tuple(float(value) for value in values)
    if not clean_values:
        return {
            "method": "percentile_bootstrap_mean",
            "iterations": 0,
            "mean": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
        }
    rng = Random(seed)
    sample_means: list[float] = []
    for _ in range(max(iterations, 1)):
        sample = [clean_values[rng.randrange(len(clean_values))] for _item in clean_values]
        sample_means.append(mean(sample))
    sample_means.sort()
    low_index = int(0.025 * (len(sample_means) - 1))
    high_index = int(0.975 * (len(sample_means) - 1))
    return {
        "method": "percentile_bootstrap_mean",
        "iterations": len(sample_means),
        "seed": seed,
        "mean": round(mean(clean_values), 6),
        "ci_low": round(sample_means[low_index], 6),
        "ci_high": round(sample_means[high_index], 6),
    }


def family_stratification(tasks: tuple[BenchmarkTask, ...] | list[BenchmarkTask]) -> dict[str, object]:
    return {
        "subset_counts": dict(sorted(Counter(task.subset for task in tasks).items())),
        "target_family_counts": dict(sorted(Counter(task_target_family(task) for task in tasks).items())),
        "chronology_split_counts": dict(sorted(Counter(task_chronology_split(task) for task in tasks).items())),
        "canary_split_counts": dict(sorted(Counter(task_canary_split(task) for task in tasks).items())),
    }


def build_statistical_audit_plan(
    tasks: tuple[BenchmarkTask, ...] | list[BenchmarkTask],
    attack_matrix: dict[str, object],
    *,
    remaining_blockers: list[str] | tuple[str, ...] | None = None,
) -> dict[str, object]:
    attacks = attack_matrix.get("attacks", [])
    attacks = attacks if isinstance(attacks, list) else []
    stratification = family_stratification(tasks)
    subset_counts = dict(stratification["subset_counts"])
    min_subset_count = min(subset_counts.values()) if subset_counts else 0
    attack_family_counts = Counter(str(item.get("family", "unknown")) for item in attacks if isinstance(item, dict))
    ablation_axes = sorted({str(item.get("canary_ablation_axis", "unspecified")) for item in attacks if isinstance(item, dict)})
    return {
        "schema_version": "codedye_statistical_audit_plan_v1",
        "machine_verifiable": True,
        "claim_status": "claim_bearing_final_statistics",
        "provider_policy": "no_provider_no_live_api",
        "task_count": len(tasks),
        "family_stratification": stratification,
        "null_calibration_plan": {
            "method": "family_stratified_empirical_dominance_tail",
            "strata": ["subset", "chronology_split", "canary_split", "hidden_test_family", "release_window", "operator_slice", "target_family"],
            "minimum_current_subset_count": min_subset_count,
            "current_status": "implemented_for_300_task_null_pool_pending_deepseek_live_rerun",
            "no_outcome_selection_required": True,
        },
        "bootstrap_plan": {
            "method": "stratified_task_bootstrap",
            "implemented_artifact": "artifacts/generated/attack_matrix_null_calibration_ci.json::bootstrap_result",
            "implemented_iterations": 2000,
            "submission_iterations_target": 10000,
            "resampling_unit": "task_id_within_subset",
            "metrics": ["final_accusation_rate", "strict_null_control_rate", "average_canary_coverage", "latency_overhead", "extra_query_cost"],
        },
        "permutation_plan": {
            "method": "subset_label_permutation_rate_range",
            "implemented_artifact": "artifacts/generated/attack_matrix_null_calibration_ci.json::permutation_result",
            "implemented_iterations": 2000,
            "resampling_unit": "task_id_within_subset",
            "null_hypothesis": "positive-rate concentration is exchangeable across CodeDyeBench subsets",
            "promotion_rule": "reported as sensitivity analysis, never as direct contamination accusation",
        },
        "fdr_plan": {
            "method": "benjamini_hochberg",
            "q": 0.05,
            "implemented_artifact": "artifacts/generated/attack_matrix_null_calibration_ci.json::fdr_result",
            "families": ["direct_canary", "semantic_witness", "chronology", "rewrite", "cross_language", "operator_budget"],
            "scope": "attack_family_by_benchmark_family_hypotheses",
        },
        "canary_ablation_plan": {
            "axes": ablation_axes,
            "required_outputs": ["delta_score", "delta_false_positive_bound", "utility_preservation", "familywise_gate_change"],
            "promotion_rule": "diagnostic_only_until_ablation_preserves_utility_and_passes_fdr_audit",
        },
        "attack_matrix_summary": {
            "schema_version": attack_matrix.get("schema_version", ""),
            "attack_count": len(attacks),
            "attack_family_counts": dict(sorted(attack_family_counts.items())),
            "requires_live_provider_count": sum(1 for item in attacks if isinstance(item, dict) and bool(item.get("requires_live_provider", False))),
        },
        "remaining_blockers": list(remaining_blockers or []),
    }
