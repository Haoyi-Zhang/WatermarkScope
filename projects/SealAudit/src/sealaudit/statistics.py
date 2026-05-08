from __future__ import annotations

import random
from collections import Counter
from statistics import mean
from typing import Any, Callable, Iterable, Sequence


def _as_list(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in records if isinstance(item, dict)]


def bootstrap_metric_interval(
    records: Iterable[dict[str, Any]],
    metric: Callable[[list[dict[str, Any]]], float],
    *,
    iterations: int = 1000,
    seed: int = 0,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Return a deterministic nonparametric bootstrap interval for a row-level metric."""

    rows = _as_list(records)
    if not rows:
        return {
            "n": 0,
            "estimate": 0.0,
            "low": 0.0,
            "high": 0.0,
            "iterations": 0,
            "confidence": confidence,
            "method": "nonparametric_bootstrap",
        }
    rng = random.Random(seed)
    estimate = float(metric(rows))
    draws: list[float] = []
    sample_size = len(rows)
    for _ in range(max(1, iterations)):
        sample = [rows[rng.randrange(sample_size)] for _ in range(sample_size)]
        draws.append(float(metric(sample)))
    draws.sort()
    alpha = max(0.0, min(1.0, 1.0 - confidence))
    low_index = int((alpha / 2.0) * (len(draws) - 1))
    high_index = int((1.0 - alpha / 2.0) * (len(draws) - 1))
    return {
        "n": sample_size,
        "estimate": estimate,
        "low": draws[low_index],
        "high": draws[high_index],
        "iterations": len(draws),
        "confidence": confidence,
        "method": "nonparametric_bootstrap",
    }


def confusion_matrix(records: Iterable[dict[str, Any]], *, labels: Sequence[str]) -> dict[str, Any]:
    rows = _as_list(records)
    matrix = {
        expected: {predicted: 0 for predicted in labels}
        for expected in labels
    }
    unknown = 0
    for row in rows:
        expected = str(row.get("expected_verdict", ""))
        predicted = str(row.get("verdict", row.get("predicted_verdict", "")))
        if expected in matrix and predicted in matrix[expected]:
            matrix[expected][predicted] += 1
        else:
            unknown += 1
    return {
        "labels": list(labels),
        "matrix": matrix,
        "row_count": len(rows),
        "unknown_or_out_of_label_count": unknown,
    }


def binary_confusion_at_threshold(
    records: Iterable[dict[str, Any]],
    *,
    score_key: str,
    threshold: float,
    positive_expected_values: Sequence[str],
) -> dict[str, Any]:
    positives = set(str(item) for item in positive_expected_values)
    counts = Counter({"tp": 0, "fp": 0, "tn": 0, "fn": 0})
    rows = _as_list(records)
    for row in rows:
        expected_positive = str(row.get("expected_verdict", "")) in positives
        predicted_positive = float(row.get(score_key, 0.0) or 0.0) >= threshold
        if expected_positive and predicted_positive:
            counts["tp"] += 1
        elif not expected_positive and predicted_positive:
            counts["fp"] += 1
        elif not expected_positive and not predicted_positive:
            counts["tn"] += 1
        else:
            counts["fn"] += 1
    denominator = max(1, len(rows))
    return {
        "threshold": threshold,
        "score_key": score_key,
        "row_count": len(rows),
        "tp": counts["tp"],
        "fp": counts["fp"],
        "tn": counts["tn"],
        "fn": counts["fn"],
        "accuracy": (counts["tp"] + counts["tn"]) / denominator,
        "positive_expected_values": sorted(positives),
    }


def threshold_sweep(
    records: Iterable[dict[str, Any]],
    *,
    score_key: str,
    positive_expected_values: Sequence[str],
    thresholds: Sequence[float],
) -> list[dict[str, Any]]:
    return [
        binary_confusion_at_threshold(
            records,
            score_key=score_key,
            threshold=float(threshold),
            positive_expected_values=positive_expected_values,
        )
        for threshold in thresholds
    ]


def ablation_delta_summary(
    control_records: Iterable[dict[str, Any]],
    ablated_records: Iterable[dict[str, Any]],
    *,
    metric_keys: Sequence[str],
) -> dict[str, Any]:
    control = _as_list(control_records)
    ablated = _as_list(ablated_records)
    summaries: dict[str, Any] = {}
    for key in metric_keys:
        control_values = [float(row.get(key, 0.0) or 0.0) for row in control]
        ablated_values = [float(row.get(key, 0.0) or 0.0) for row in ablated]
        control_mean = mean(control_values) if control_values else 0.0
        ablated_mean = mean(ablated_values) if ablated_values else 0.0
        summaries[key] = {
            "control_mean": control_mean,
            "ablated_mean": ablated_mean,
            "delta": ablated_mean - control_mean,
            "control_n": len(control_values),
            "ablated_n": len(ablated_values),
        }
    return {
        "metric_keys": list(metric_keys),
        "metrics": summaries,
        "method": "paired_or_group_mean_delta_summary",
    }
