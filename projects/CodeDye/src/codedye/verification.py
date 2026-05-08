from __future__ import annotations

from collections.abc import Sequence

from .protocol import AssetScorecard, BenchmarkTask, ContaminationDecision
from .statistics import build_contamination_decision


def _scorecard_id(scorecard: AssetScorecard) -> str:
    return str(scorecard.asset_id)


def estimate_null_asset_score(
    scorecards: Sequence[AssetScorecard],
    *,
    winning_asset_id: str | None = None,
) -> float:
    decoy_scores = [
        scorecard.score
        for scorecard in scorecards
        if winning_asset_id is None or _scorecard_id(scorecard) != winning_asset_id
    ]
    return round(max(decoy_scores, default=0.0), 4)


def calibrate_accusation_threshold(
    base_threshold: float,
    *,
    query_budget_used: int,
    scorecards: Sequence[AssetScorecard],
    canary_coverage: float,
    trace_consistency: float,
    winning_asset_id: str | None = None,
) -> float:
    null_asset_baseline = estimate_null_asset_score(scorecards, winning_asset_id=winning_asset_id)
    threshold = max(base_threshold, null_asset_baseline + 0.07)
    if query_budget_used <= 4:
        threshold += 0.06
    elif query_budget_used <= 8:
        threshold += 0.03
    if canary_coverage < 0.75:
        threshold += 0.05
    elif canary_coverage < 1.0:
        threshold += 0.02
    threshold -= 0.03 * max(trace_consistency - 0.85, 0.0)
    return round(min(0.98, max(0.5, threshold)), 4)


def audit_contamination(
    task: BenchmarkTask,
    code: str,
    task_pool: Sequence[BenchmarkTask],
    *,
    query_count: int = 1,
    latency_ms: float = 0.0,
    extra_query_cost: int = 0,
) -> ContaminationDecision:
    return build_contamination_decision(
        task,
        code,
        tuple(task_pool),
        query_count=query_count,
        latency_ms=latency_ms,
        extra_query_cost=extra_query_cost,
    )
