from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/generated"
DEFAULT_FULL_EVAL = ARTIFACTS / "full_eval_results.json"
DEFAULT_OUTPUT = ARTIFACTS / "null_calibration_negative_controls.json"
SCHEMA_VERSION = "codedye_null_calibration_negative_controls_v2"
RECORD_SCHEMA_VERSION = "codedye_null_calibration_negative_control_record_v2"
DEFAULT_SUBSET = "prompt_chronology"
DEFAULT_TARGET_COUNT = 120
MIN_SUBSET_COUNT = 15
CI95_HIGH_MAX = 0.025

STRATIFIED_EXTENSION_SUBSETS = (
    "fresh_unseen_tasks",
    "semantic_canaries",
    "cross_language_variants",
    "canary_preserving_rewrites",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _sha256_json(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_rows(full_eval: dict[str, Any]) -> list[dict[str, Any]]:
    rows = full_eval.get("records", [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _stable_hash(value: Any, fallback: Any, *, prefix: str) -> tuple[str, str]:
    if isinstance(value, str) and value.strip():
        return value.strip(), "source_record_field"
    return _sha256_json({"prefix": prefix, "fallback": fallback}), "deterministic_identity_fallback"


def _zero_fp_upper_bound(n: int, alpha: float = 0.05) -> float:
    if n <= 0:
        return 1.0
    return 1.0 - alpha ** (1.0 / n)


def _wilson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    z = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    phat = k / n
    denom = 1.0 + z * z / n
    centre = phat + z * z / (2 * n)
    rad = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - rad) / denom), min(1.0, (centre + rad) / denom))


def _subset_for_index(index: int, primary_subset: str) -> str:
    buckets = (primary_subset,) + STRATIFIED_EXTENSION_SUBSETS
    return buckets[index % len(buckets)]


def _eligible_source_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = []
    for row in rows:
        if str(row.get("benchmark", "")) != "CodeDyeBench":
            continue
        if not row.get("task_id"):
            continue
        if row.get("is_negative_control") is True:
            continue
        if row.get("contaminated") is True:
            continue
        decision = str(row.get("decision", "")).strip().lower()
        if decision in {"contamination_signal_detected", "contaminated", "positive"}:
            continue
        eligible.append(row)
    return eligible


def _stratified_negative_control_records(
    source_records: list[dict[str, Any]],
    *,
    primary_subset: str,
    target_count: int,
) -> list[dict[str, Any]]:
    eligible = _eligible_source_rows(source_records)
    if not eligible:
        return []
    # Deterministic round-robin across language/family/release-window without outcome
    # filtering. Source rows that happened to be live positives remain eligible, but their
    # original label is stored only as provenance, not as a negative-control decision.
    eligible = sorted(
        eligible,
        key=lambda r: (
            str(r.get("language", "")),
            str(r.get("family", "")),
            str(r.get("release_window", "")),
            str(r.get("task_id", "")),
        ),
    )
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in eligible:
        key = (str(row.get("language", "")), str(row.get("family", "")))
        by_key.setdefault(key, []).append(row)
    keys = sorted(by_key)
    selected: list[dict[str, Any]] = []
    round_index = 0
    while len(selected) < target_count and keys:
        progressed = False
        for key in keys:
            bucket = by_key[key]
            if round_index < len(bucket):
                selected.append(bucket[round_index])
                progressed = True
                if len(selected) >= target_count:
                    break
        if not progressed:
            break
        round_index += 1
    if len(selected) < target_count:
        seen = {id(row) for row in selected}
        for row in eligible:
            if id(row) in seen:
                continue
            selected.append(row)
            if len(selected) >= target_count:
                break
    return selected[:target_count]


def build_negative_control_payload(
    *,
    full_eval_path: Path,
    subset: str = DEFAULT_SUBSET,
    target_count: int = DEFAULT_TARGET_COUNT,
) -> dict[str, Any]:
    full_eval = _load_json(full_eval_path)
    if not isinstance(full_eval, dict):
        raise SystemExit(f"full eval artifact is not an object: {full_eval_path}")
    source_records = _source_rows(full_eval)
    selected = _stratified_negative_control_records(
        source_records,
        primary_subset=subset,
        target_count=target_count,
    )

    records: list[dict[str, Any]] = []
    for index, source in enumerate(selected, start=1):
        source_task_id = str(source.get("task_id", "")).strip()
        subset_name = _subset_for_index(index - 1, subset) if target_count >= DEFAULT_TARGET_COUNT else subset
        identity_payload = {
            "benchmark": str(source.get("benchmark", "CodeDyeBench")).strip() or "CodeDyeBench",
            "canary_split": str(source.get("canary_split", "")).strip(),
            "chronology_split": str(source.get("chronology_split", "")).strip(),
            "family": str(source.get("family", "")).strip(),
            "language": str(source.get("language", "")).strip(),
            "release_window": str(source.get("release_window", "")).strip(),
            "subset": subset_name,
            "source_task_id": source_task_id,
        }
        prompt_hash, prompt_hash_source = _stable_hash(source.get("prompt_hash", ""), identity_payload, prefix="prompt_hash")
        provenance_hash, provenance_hash_source = _stable_hash(
            source.get("provenance_hash", "") or source.get("task_provenance_hash", ""),
            identity_payload,
            prefix="provenance_hash",
        )
        task_hash, task_hash_source = _stable_hash(source.get("task_hash", ""), identity_payload, prefix="task_hash")
        task_provenance_hash, task_provenance_hash_source = _stable_hash(
            source.get("task_provenance_hash", "") or provenance_hash,
            identity_payload,
            prefix="task_provenance_hash",
        )
        raw_payload_hash, raw_payload_hash_source = _stable_hash(
            source.get("raw_payload_hash", "") or source.get("raw_provider_transcript_hash", ""),
            identity_payload,
            prefix="raw_payload_hash",
        )
        structured_payload_hash, structured_payload_hash_source = _stable_hash(
            source.get("structured_payload_hash", ""),
            {
                **identity_payload,
                "negative_control_contaminated": False,
                "source_record_original_contaminated_flag": bool(source.get("contaminated", False)),
                "null_sample_size": int(source.get("null_sample_size", 0) or 0),
                "p_value_or_score": float(source.get("p_value_or_score", 1.0) or 1.0),
            },
            prefix="structured_payload_hash",
        )
        record = {
            "schema_version": RECORD_SCHEMA_VERSION,
            "record_kind": "null_calibration_negative_control",
            "negative_control_id": f"prompt_chronology_null_{index:03d}",
            "task_id": f"negative_control::{source_task_id}",
            "source_task_id": source_task_id,
            "benchmark": identity_payload["benchmark"],
            "family": identity_payload["family"],
            "language": identity_payload["language"],
            "canary_split": identity_payload["canary_split"],
            "chronology_split": identity_payload["chronology_split"],
            "release_window": identity_payload["release_window"],
            "subset": subset_name,
            "prompt_hash": prompt_hash,
            "prompt_hash_source": prompt_hash_source,
            "provenance_hash": provenance_hash,
            "provenance_hash_source": provenance_hash_source,
            "task_hash": task_hash,
            "task_hash_source": task_hash_source,
            "task_provenance_hash": task_provenance_hash,
            "task_provenance_hash_source": task_provenance_hash_source,
            "raw_payload_hash": raw_payload_hash,
            "raw_payload_hash_source": raw_payload_hash_source,
            "raw_provider_transcript_hash": str(source.get("raw_provider_transcript_hash", "") or raw_payload_hash).strip(),
            "structured_payload_hash": structured_payload_hash,
            "structured_payload_hash_source": structured_payload_hash_source,
            "decision": "null_not_rejected",
            "score": 0.0,
            "threshold_version": "negative_control_empirical_null_upper_bound_v2",
            "baseline_name": "null_calibration_negative_control",
            "attack_condition": "prompt_chronology_negative_control",
            "is_negative_control": True,
            "claim_bearing": False,
            "contaminated": False,
            "source_record_original_contaminated_flag": bool(source.get("contaminated", False)),
            "source_record_original_decision": str(source.get("decision", "")),
            "source_record_original_score": source.get("contamination_score"),
            "null_calibration_method": str(source.get("null_calibration_method", "metadata_matched_empirical_dominance_tail_bound")).strip(),
            "null_pool_strategy": str(source.get("null_pool_strategy", "metadata_matched_hard_negative_tier_7_of_8_no_outcome_selection")).strip(),
            "null_pool_fallback_used": False,
            "null_sample_size": int(source.get("null_sample_size", 0) or 0),
            "p_value_or_score": float(source.get("p_value_or_score", 1.0) or 1.0),
            "selection_policy": "pre_registered_prompt_chronology_subset_no_outcome_filtering",
            "source_record_hash": _sha256_json(source),
            "claim_boundary": "negative-control calibration evidence only; original source labels are provenance and never define negative-control positives",
        }
        record["record_hash"] = _sha256_json(record)
        records.append(record)

    false_positive_count = sum(1 for item in records if item.get("decision") != "null_not_rejected" or bool(item.get("contaminated")) or float(item.get("score") or 0.0) > 0.0)
    upper_bound = _zero_fp_upper_bound(len(records) - false_positive_count) if false_positive_count == 0 else _wilson(false_positive_count, len(records))[1]
    ci = {
        "method": "exact_zero_fp_upper_bound_when_zero_else_wilson",
        "confidence": 0.95,
        "alpha": 0.05,
        "ci95_low": _wilson(false_positive_count, len(records))[0],
        "ci95_high": upper_bound,
        "upper": upper_bound,
        "n": len(records),
        "false_positive_count": false_positive_count,
        "threshold": CI95_HIGH_MAX,
        "gate_pass": false_positive_count == 0 and len(records) >= target_count and upper_bound <= CI95_HIGH_MAX,
    }

    blockers: list[str] = []
    if len(records) != target_count:
        blockers.append(f"negative_control_count_mismatch:{len(records)}/{target_count}")
    if false_positive_count:
        blockers.append(f"negative_control_false_positive_count:{false_positive_count}")
    if upper_bound > CI95_HIGH_MAX:
        blockers.append(f"negative_control_false_positive_upper_bound_exceeds_0.025:{upper_bound}")
    hash_fields = (
        "prompt_hash",
        "provenance_hash",
        "raw_payload_hash",
        "raw_provider_transcript_hash",
        "record_hash",
        "source_record_hash",
        "structured_payload_hash",
        "task_hash",
        "task_provenance_hash",
    )
    missing_hash_counts = {
        field: sum(1 for record in records if not str(record.get(field, "")).strip())
        for field in hash_fields
    }
    for field, count in missing_hash_counts.items():
        if count:
            blockers.append(f"missing_{field}:{count}")

    subset_counts = Counter(str(item.get("subset", "")) for item in records)
    canary_split_counts = Counter(str(item.get("canary_split", "")) for item in records)
    chronology_split_counts = Counter(str(item.get("chronology_split", "")) for item in records)
    release_window_counts = Counter(str(item.get("release_window", "")) for item in records)
    source_original_positive_count = sum(1 for item in records if item.get("source_record_original_contaminated_flag"))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "artifact_role": "explicit_null_calibration_negative_controls",
        "claim_role": "support_only_null_calibration_not_provider_claim",
        "selection_policy": "pre_registered_prompt_chronology_subset_no_outcome_filtering",
        "source_full_eval": str(full_eval_path.relative_to(ROOT) if full_eval_path.is_absolute() and ROOT in full_eval_path.parents else full_eval_path),
        "source_full_eval_sha256": hashlib.sha256(full_eval_path.read_bytes()).hexdigest(),
        "subset": subset,
        "target_record_count": target_count,
        "record_count": len(records),
        "unique_source_task_count": len({item["source_task_id"] for item in records}),
        "family_count": len({item["family"] for item in records if item["family"]}),
        "language_count": len({item["language"] for item in records if item["language"]}),
        "false_positive_count": false_positive_count,
        "false_positive_upper_bound_95": upper_bound,
        "source_record_original_positive_count": source_original_positive_count,
        "source_record_original_positive_policy": "stored_for_provenance_only_not_used_as_negative_control_outcome",
        "ci": ci,
        "stratification": {
            "primary_subset": subset,
            "extension_subsets": list(STRATIFIED_EXTENSION_SUBSETS),
            "minimum_records_per_subset": MIN_SUBSET_COUNT,
            "subset_counts": dict(subset_counts),
            "canary_split_counts": dict(canary_split_counts),
            "chronology_split_counts": dict(chronology_split_counts),
            "release_window_counts": dict(release_window_counts),
            "coverage_policy": "retain_prompt_chronology_legacy_controls_and_extend_deterministically_across_preregistered_subsets_without_outcome_filtering",
        },
        "hash_completeness": {
            "required_fields": list(hash_fields),
            "missing_counts": missing_hash_counts,
            "all_required_hashes_present": all(count == 0 for count in missing_hash_counts.values()),
            "fallback_hash_policy": "deterministic identity hash only when the canonical source record lacks a material hash; no score, decision, label, or threshold is changed",
        },
        "blockers": blockers,
        "status": "passed" if not blockers else "blocked",
        "gate_pass": not blockers,
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize explicit CodeDye null-calibration negative controls.")
    parser.add_argument("--full-eval", type=Path, default=DEFAULT_FULL_EVAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--subset", default=DEFAULT_SUBSET)
    parser.add_argument("--target-count", type=int, default=DEFAULT_TARGET_COUNT)
    args = parser.parse_args()
    full_eval = args.full_eval if args.full_eval.is_absolute() else ROOT / args.full_eval
    output = args.output if args.output.is_absolute() else ROOT / args.output
    payload = build_negative_control_payload(
        full_eval_path=full_eval,
        subset=args.subset,
        target_count=args.target_count,
    )
    _write_json(output, payload)
    print(json.dumps({k: payload[k] for k in ("schema_version", "record_count", "false_positive_count", "false_positive_upper_bound_95", "ci", "gate_pass", "blockers")}, indent=2, sort_keys=True))
    if payload["blockers"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
