from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT


SCHEMA = "semcodebook_negative_control_replay_gate_v1"
DEFAULT_OUTPUT = ARTIFACTS / "negative_control_replay_gate.json"
DEFAULT_CURRENT_DETECTOR_REPLAY = ARTIFACTS / "negative_control_current_detector_replay.json"
DEFAULT_AUDIT_CANDIDATES = (
    ARTIFACTS / "materializer_audits" / "carrier_materializer_audit.local_smoke.json",
    ARTIFACTS / "carrier_materializer_audit.local_smoke.json",
    ARTIFACTS / "carrier_materializer_audit.local_python_include_negative_before.json",
)
OWNER_ID_FIELDS = (
    "owner_id",
    "owner_id_hat",
    "wm_owner_id",
    "wm_owner_id_hat",
    "watermark_owner_id",
    "source_owner_id",
)
SUPPORT_SCORE_FIELDS = (
    "positive_support_score",
    "support_score",
)
NEGATIVE_DECISION_STATUSES = {"", "abstain", "reject", "rejected", "none", "clean", "not_watermarked"}
POSITIVE_DECISION_STATUSES = {"accept", "accepted", "detected", "verified", "watermarked"}
CURRENT_DETECTOR_RERUN_ARTIFACT_ROLE = "current_detector_negative_control_rerun"
CURRENT_DETECTOR_COMPLETE_STATUSES = {"detector_rerun_complete", "rerun_complete", "complete"}
CURRENT_DETECTOR_CLEAN_DECISIONS = {"reject", "rejected", "abstain", "clean", "not_watermarked"}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True).encode("utf-8") + b"\n"


def _stable_id(record: dict[str, Any]) -> str:
    material = "|".join(
        str(record.get(key) or "")
        for key in ("model_name", "benchmark", "task_id", "language", "attack_name", "attack_category")
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _normalise_attack_category(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "clean_control"


def _normalise_attack_name(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "clean_reference"


def _benchmark_family(record: dict[str, Any]) -> str:
    benchmark = str(record.get("benchmark") or record.get("benchmark_name") or "").strip()
    task_id = str(record.get("task_id") or "").strip()
    if benchmark:
        return benchmark
    if "/" in task_id:
        return task_id.split("/", 1)[0]
    return "unknown"


def _task_family_map() -> dict[str, str]:
    path = ROOT / "benchmarks" / "carrier_stressbench_tasks.json"
    if not path.exists():
        return {}
    payload = _load_json(path)
    tasks = payload.get("tasks", []) if isinstance(payload, dict) else []
    return {
        str(item.get("task_id")): str(item.get("family") or item.get("task_family") or item.get("carrier_family") or "unknown")
        for item in tasks
        if isinstance(item, dict) and item.get("task_id")
    }


def _record_family(record: dict[str, Any], task_families: dict[str, str]) -> str:
    task_id = str(record.get("task_id") or "")
    return task_families.get(task_id) or _benchmark_family(record)


def _is_negative_control(record: dict[str, Any]) -> bool:
    return bool(record.get("negative_control") or record.get("is_negative_control"))


def _is_nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _positive_number(value: Any) -> bool:
    try:
        return float(value or 0.0) > 0.0
    except (TypeError, ValueError):
        return False


def _support_reasons(record: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for field in SUPPORT_SCORE_FIELDS:
        if _positive_number(record.get(field)):
            reasons.append(f"{field}_positive")
    for field in ("positive_support_family_count", "positive_support_level_count"):
        if _positive_number(record.get(field)):
            reasons.append(f"{field}_positive")
    return reasons


def _owner_reasons(record: dict[str, Any]) -> list[str]:
    return [
        f"{field}_nonempty"
        for field in OWNER_ID_FIELDS
        if _is_nonempty(record.get(field))
    ]


def _negative_hit_reasons(record: dict[str, Any]) -> list[str]:
    if not _is_negative_control(record):
        return []

    decision_status = str(record.get("decision_status") or "").strip().lower()
    reasons: list[str] = []
    if bool(record.get("detected")):
        reasons.append("detected_true")
    if bool(record.get("is_watermarked")) or bool(record.get("watermarked")):
        reasons.append("watermarked_flag_true")
    if decision_status in POSITIVE_DECISION_STATUSES:
        reasons.append(f"decision_status_{decision_status}")
    if _is_nonempty(record.get("wm_id_hat")):
        reasons.append("wm_id_hat_nonempty")
    owner_reasons = _owner_reasons(record)
    reasons.extend(owner_reasons)

    base_reasons = list(reasons)
    support_reasons = _support_reasons(record)
    if support_reasons and base_reasons:
        reasons.extend(support_reasons)
    return reasons


def _schema_inconsistency_reasons(record: dict[str, Any], hit_reasons: list[str] | None = None) -> list[str]:
    if not _is_negative_control(record):
        return []

    reasons = hit_reasons if hit_reasons is not None else _negative_hit_reasons(record)
    decision_status = str(record.get("decision_status") or "").strip().lower()
    inconsistencies: list[str] = []
    if reasons and not bool(record.get("detected")):
        inconsistencies.append("negative_control_schema_hit_without_detected_true")
    if decision_status in {"abstain", "reject"} and _is_nonempty(record.get("wm_id_hat")):
        inconsistencies.append("fail_closed_decision_exposes_wm_id_hat")
    if decision_status == "watermarked" and not _positive_number(record.get("positive_support_score")):
        inconsistencies.append("watermarked_decision_without_positive_support_score")
    return inconsistencies


def _is_negative_hit(record: dict[str, Any]) -> bool:
    return bool(_negative_hit_reasons(record))


def _schema_inconsistency_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    examples: list[dict[str, Any]] = []
    reason_counter: Counter[str] = Counter()
    for index, record in enumerate(records):
        hit_reasons = _negative_hit_reasons(record)
        inconsistencies = _schema_inconsistency_reasons(record, hit_reasons)
        if not inconsistencies:
            continue
        reason_counter.update(inconsistencies)
        examples.append(
            {
                "record_index": index,
                "task_id": record.get("task_id"),
                "hit_reasons": hit_reasons,
                "schema_inconsistency_reasons": inconsistencies,
                "detected": bool(record.get("detected")),
                "decision_status": record.get("decision_status"),
                "wm_id_hat": record.get("wm_id_hat"),
            }
        )
    return {
        "schema_inconsistency_count": len(examples),
        "reasons": [
            {"reason": reason, "count": count}
            for reason, count in sorted(reason_counter.items(), key=lambda item: (-item[1], item[0]))
        ],
        "examples": examples[:20],
    }


def _compact_record(record: dict[str, Any], task_families: dict[str, str]) -> dict[str, Any]:
    family = _record_family(record, task_families)
    notes = record.get("notes") if isinstance(record.get("notes"), list) else []
    carrier_evidence = record.get("carrier_evidence") if isinstance(record.get("carrier_evidence"), list) else []
    hit_reasons = _negative_hit_reasons(record)
    schema_inconsistency_reasons = _schema_inconsistency_reasons(record, hit_reasons)
    return {
        "candidate_id": _stable_id(record),
        "source": "current_full_eval_negative_control_hit",
        "priority": "P0",
        "task_id": record.get("task_id"),
        "family": family,
        "benchmark": record.get("benchmark") or record.get("benchmark_name"),
        "language": record.get("language"),
        "model_name": record.get("model_name"),
        "split": record.get("split"),
        "attack_name": _normalise_attack_name(record.get("attack_name")),
        "attack_category": _normalise_attack_category(record.get("attack_category")),
        "detected": bool(record.get("detected")),
        "is_watermarked": record.get("is_watermarked"),
        "watermarked": record.get("watermarked"),
        "decision_status": record.get("decision_status"),
        "wm_id_expected": record.get("wm_id_expected"),
        "wm_id_hat": record.get("wm_id_hat"),
        "owner_id": record.get("owner_id"),
        "owner_id_hat": record.get("owner_id_hat"),
        "wm_owner_id": record.get("wm_owner_id"),
        "wm_owner_id_hat": record.get("wm_owner_id_hat"),
        "watermark_owner_id": record.get("watermark_owner_id"),
        "source_owner_id": record.get("source_owner_id"),
        "exact_recovery": record.get("exact_recovery"),
        "confidence": record.get("confidence"),
        "positive_support_score": record.get("positive_support_score"),
        "support_score": record.get("support_score"),
        "positive_support_family_count": record.get("positive_support_family_count"),
        "positive_support_level_count": record.get("positive_support_level_count"),
        "support_ratio": record.get("support_ratio"),
        "support_count": record.get("support_count"),
        "carrier_coverage": record.get("carrier_coverage"),
        "negative_control_score": record.get("negative_control_score"),
        "decoder_status": record.get("decoder_status"),
        "erasure_count": record.get("erasure_count"),
        "raw_bit_error_count": record.get("raw_bit_error_count"),
        "code_changed": record.get("code_changed"),
        "semantic_ok": record.get("semantic_ok"),
        "compile_ok": record.get("compile_ok"),
        "pass_ok": record.get("pass_ok"),
        "generation_result_scope": record.get("generation_result_scope"),
        "generation_claim_status": record.get("generation_claim_status"),
        "carrier_evidence": carrier_evidence,
        "notes": notes,
        "negative_hit_reasons": hit_reasons,
        "schema_inconsistency_reasons": schema_inconsistency_reasons,
        "replay_reason": "old negative-control hit in current canonical full_eval",
    }


def _sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(item.get("confidence") or 0.0),
        -float(item.get("support_ratio") or 0.0),
        str(item.get("family") or ""),
        str(item.get("task_id") or ""),
        str(item.get("attack_name") or ""),
    )


def _counter_summary(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counter = Counter(str(item.get(key) or "unknown") for item in items)
    return [
        {"value": value, "hit_count": count}
        for value, count in sorted(counter.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


def _reason_summary(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for item in items:
        counter.update(str(reason) for reason in item.get("negative_hit_reasons", []) if str(reason).strip())
    return [
        {"reason": reason, "hit_count": count}
        for reason, count in sorted(counter.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


def _grouped_risk(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[str(item.get(key) or "unknown")].append(item)
    rows: list[dict[str, Any]] = []
    for value, records in grouped.items():
        rows.append(
            {
                "value": value,
                "hit_count": len(records),
                "max_confidence": max(float(item.get("confidence") or 0.0) for item in records),
                "max_support_ratio": max(float(item.get("support_ratio") or 0.0) for item in records),
                "attack_categories": sorted({str(item.get("attack_category") or "unknown") for item in records}),
                "attack_names": sorted({str(item.get("attack_name") or "unknown") for item in records}),
            }
        )
    return sorted(
        rows,
        key=lambda item: (-int(item["hit_count"]), -float(item["max_confidence"]), str(item["value"])),
    )


def _repair_ledger(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in candidates:
        reasons = [str(reason) for reason in item.get("negative_hit_reasons", []) if str(reason).strip()]
        actions: list[str] = []
        if any(reason in {"detected_true", "watermarked_flag_true"} for reason in reasons):
            actions.append("apply_declared_negative_control_veto_before_detection_flags")
        if any(reason.endswith("_nonempty") for reason in reasons) or "wm_id_hat_nonempty" in reasons:
            actions.append("suppress_owner_and_payload_fields_on_negative_controls")
        if any(reason.startswith("positive_support") or reason.startswith("support_score") for reason in reasons):
            actions.append("zero_positive_support_counters_on_negative_controls")
        if any(reason.startswith("decision_status_") for reason in reasons):
            actions.append("force_negative_control_decision_status_to_reject_or_abstain")
        if not actions:
            actions.append("rerun_current_detector_replay_and inspect carrier evidence path")
        rows.append(
            {
                "candidate_id": item.get("candidate_id"),
                "task_id": item.get("task_id"),
                "family": item.get("family"),
                "language": item.get("language"),
                "attack_name": item.get("attack_name"),
                "negative_hit_reasons": reasons,
                "required_repair_actions": sorted(dict.fromkeys(actions)),
                "fresh_rerun_policy": (
                    "After repair, this task must be regenerated in canonical full_eval; support-only replay "
                    "cannot retire the old negative hit."
                ),
            }
        )
    return rows


def _aggregate_evidence(aggregate: dict[str, Any]) -> dict[str, Any]:
    headline = aggregate.get("headline_gate_vector", {})
    negative_gate = headline.get("negative_control_gate", {}) if isinstance(headline, dict) else {}
    return {
        "path": "artifacts/generated/aggregate_results.json",
        "negative_control_detection_count": int(aggregate.get("negative_control_detection_count") or 0),
        "negative_control_gate_pass": bool(negative_gate.get("pass")) if isinstance(negative_gate, dict) else False,
        "first_failing_gate": aggregate.get("first_failing_gate"),
        "final_claim_status": aggregate.get("final_claim_status"),
        "claim_supporting": bool(aggregate.get("claim_supporting")),
        "claim_supporting_reason": aggregate.get("claim_supporting_reason"),
        "closure_blockers": list(aggregate.get("closure_blockers") or []),
    }


def _discover_audit_path(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    for path in DEFAULT_AUDIT_CANDIDATES:
        if path.exists():
            return path
    return None


def _audit_support_evidence(path: Path | None, canonical_hit_count: int) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "available": False,
            "status": "missing",
            "support_only": True,
            "canonical_replacement_allowed": False,
            "reason": "fresh materializer negative split audit was not found",
        }

    audit = _load_json(path)
    summary = audit.get("summary", {}) if isinstance(audit, dict) else {}
    negative_count = int(audit.get("negative_control_task_count") or summary.get("negative_control_task_count") or 0)
    negative_contract = int(
        audit.get("negative_control_contract_task_count") or summary.get("negative_control_contract_task_count") or 0
    )
    negative_fp = int(
        audit.get("negative_control_false_positive_task_count")
        or summary.get("negative_control_false_positive_task_count")
        or 0
    )
    semantic_failed = int(summary.get("semantic_failed_task_count") or 0)
    semantic_supported_negative = negative_contract + negative_fp
    clean_supported_slice = semantic_supported_negative > 0 and negative_fp == 0
    clean_full_split = negative_count > 0 and negative_contract == negative_count and negative_fp == 0

    replacement_blockers = []
    if canonical_hit_count:
        replacement_blockers.append(f"canonical_negative_control_hits_present:{canonical_hit_count}")
    if not clean_full_split:
        replacement_blockers.append("audit_not_full_negative_split_replacement")
    replacement_blockers.append("audit_scope_is_materializer_support_not_canonical_full_eval")

    return {
        "available": True,
        "path": str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path),
        "schema": audit.get("schema"),
        "task_count": int(audit.get("task_count") or summary.get("task_count") or 0),
        "positive_contract_eligible_task_count": int(
            audit.get("positive_contract_eligible_task_count") or summary.get("positive_contract_eligible_task_count") or 0
        ),
        "negative_control_task_count": negative_count,
        "negative_control_contract_task_count": negative_contract,
        "negative_control_false_positive_task_count": negative_fp,
        "semantic_supported_negative_task_count": semantic_supported_negative,
        "semantic_failed_task_count": semantic_failed,
        "clean_supported_negative_slice": clean_supported_slice,
        "clean_full_negative_split": clean_full_split,
        "language_seen": audit.get("language_seen", {}),
        "by_language_family": audit.get("by_language_family", {}),
        "status": "support_only",
        "support_only": True,
        "canonical_replacement_allowed": False,
        "replacement_blockers": replacement_blockers,
        "proof": (
            "The fresh materializer audit can support the repair because its semantic-supported negative slice has "
            "zero false positives, but current aggregate/full_eval remains canonical and still contains replay hits."
        ),
    }


def _current_detector_replay_evidence(path: Path | None, canonical_hit_count: int) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "available": False,
            "status": "missing",
            "support_only": True,
            "canonical_replacement_allowed": False,
            "current_detector_supports_repair": False,
            "reason": "current-detector replay artifact was not found",
        }

    replay = _load_json(path)
    records = [item for item in replay.get("records", []) if isinstance(item, dict)] if isinstance(replay, dict) else []
    record_contract = _replay_record_contract_summary(records)
    source_contract = _source_preservation_contract_summary(records)
    artifact_role = str(replay.get("artifact_role", "")).strip()
    old_count = int(replay.get("old_negative_hit_count") or 0)
    replay_count = max(int(replay.get("replay_record_count") or 0), len(records))
    remaining_count = max(int(replay.get("remaining_detected_count") or 0), int(record_contract["remaining_detected_count"]))
    missing_count = max(int(replay.get("missing_task_count") or 0), int(record_contract["missing_record_count"]))
    source_count_matches = old_count == canonical_hit_count and replay_count == canonical_hit_count
    artifact_role_ok = artifact_role == CURRENT_DETECTOR_RERUN_ARTIFACT_ROLE
    clean_current_detector = (
        source_count_matches
        and canonical_hit_count > 0
        and missing_count == 0
        and remaining_count == 0
        and artifact_role_ok
        and record_contract["record_contract_passed"]
        and replay.get("canonical_replacement_allowed") is False
    )
    replacement_blockers: list[str] = []
    if canonical_hit_count:
        replacement_blockers.append(f"canonical_negative_control_hits_present:{canonical_hit_count}")
    replacement_blockers.append("current_detector_replay_scope_is_support_only_not_canonical_full_eval")
    if not artifact_role_ok:
        replacement_blockers.append("current_detector_replay_not_real_detector_rerun")
        if artifact_role:
            replacement_blockers.append("current_detector_replay_legacy_or_wrong_artifact_role")
    if not source_count_matches:
        replacement_blockers.append("current_detector_replay_count_mismatch")
    if missing_count:
        replacement_blockers.append(f"current_detector_replay_missing_tasks:{missing_count}")
    replacement_blockers.extend(f"current_detector_source_preservation:{item}" for item in source_contract["blockers"])
    if remaining_count:
        replacement_blockers.append(f"current_detector_replay_remaining_detected:{remaining_count}")
    replacement_blockers.extend(f"current_detector_replay_record_contract:{item}" for item in record_contract["blockers"])

    return {
        "available": True,
        "path": str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path),
        "schema": replay.get("schema"),
        "artifact_role": artifact_role,
        "required_artifact_role": CURRENT_DETECTOR_RERUN_ARTIFACT_ROLE,
        "artifact_role_ok": artifact_role_ok,
        "claim_bearing": bool(replay.get("claim_bearing")),
        "support_only": True,
        "canonical_replacement_allowed": False,
        "old_negative_hit_count": old_count,
        "replay_record_count": replay_count,
        "record_count": len(records),
        "remaining_detected_count": remaining_count,
        "missing_task_count": missing_count,
        "record_contract": record_contract,
        "source_preservation_contract": source_contract,
        "source_count_matches_canonical_candidates": source_count_matches,
        "current_detector_supports_repair": clean_current_detector,
        "replacement_blockers": replacement_blockers,
        "source_preservation_blocked_record_count": int(
            source_contract.get("blocked_record_count", 0) if isinstance(source_contract, dict) else 0
        ),
        "proof": (
            "A clean current-detector replay supports the method repair, but it remains support-only and cannot "
            "retire stale canonical negative-control hits until a fresh full canonical run is clean."
        ),
    }


def _source_preservation_contract_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    blockers: list[str] = []
    examples: list[dict[str, Any]] = []
    blocked_record_count = 0
    missing_source_count = 0
    missing_hash_count = 0
    missing_claim_scope_count = 0
    missing_source_artifact_sha_count = 0
    if not records:
        blockers.append("current_detector_replay_records_missing")
    for index, record in enumerate(records):
        issues: list[str] = []
        preservation = record.get("source_preservation") if isinstance(record.get("source_preservation"), dict) else {}
        if not preservation.get("rerunnable_code_field_present"):
            missing_source_count += 1
            issues.append("rerunnable_code_field_missing")
        if not preservation.get("source_hash_fields_present"):
            missing_hash_count += 1
            issues.append("source_hash_or_payload_hash_missing")
        if record.get("claim_bearing") is not False or not str(record.get("claim_bearing_scope") or "").strip():
            missing_claim_scope_count += 1
            issues.append("support_only_claim_scope_missing")
        if not str(record.get("source_full_eval_sha256") or record.get("source_artifact_sha256") or "").strip():
            missing_source_artifact_sha_count += 1
            issues.append("source_full_eval_sha256_missing")
        if issues:
            blocked_record_count += 1
            examples.append(
                {
                    "record_index": index,
                    "task_id": record.get("task_id"),
                    "candidate_id": record.get("candidate_id"),
                    "issues": issues,
                    "source_preservation": preservation,
                }
            )
    if missing_source_count:
        blockers.append(f"rerunnable_code_field_missing:{missing_source_count}")
    if missing_hash_count:
        blockers.append(f"source_hash_or_payload_hash_missing:{missing_hash_count}")
    if missing_claim_scope_count:
        blockers.append(f"support_only_claim_scope_missing:{missing_claim_scope_count}")
    if missing_source_artifact_sha_count:
        blockers.append(f"source_full_eval_sha256_missing:{missing_source_artifact_sha_count}")
    return {
        "contract_passed": bool(records) and not blockers,
        "record_count": len(records),
        "blocked_record_count": blocked_record_count,
        "missing_rerunnable_code_field_count": missing_source_count,
        "missing_source_hash_or_payload_hash_count": missing_hash_count,
        "missing_support_only_claim_scope_count": missing_claim_scope_count,
        "missing_source_full_eval_sha256_count": missing_source_artifact_sha_count,
        "blockers": blockers,
        "issue_examples": examples[:20],
        "fresh_canonical_run_required_fields": {
            "required_any_rerunnable_code_field": [
                "evaluated_code",
                "attacked_code",
                "watermarked_code",
                "generated_code",
                "code",
                "source_code",
            ],
            "required_hash_or_payload_field": [
                "raw_payload_hash",
                "structured_payload_hash",
                "evaluated_code_sha256",
                "attacked_code_sha256",
                "watermarked_code_sha256",
                "generated_code_sha256",
                "code_sha256",
                "source_code_sha256",
            ],
            "claim_boundary": "negative-control replay artifacts remain support-only until a fresh canonical full run is clean",
        },
    }


def _replay_record_contract_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    blockers: list[str] = []
    issue_examples: list[dict[str, Any]] = []
    if not records:
        blockers.append("current_detector_replay_records_missing")
    missing_record_count = 0
    remaining_detected_count = 0
    passed_count = 0
    for index, record in enumerate(records):
        record_issues: list[str] = []
        rerun_status = str(record.get("rerun_status") or _nested(record, "current_detector_contract", "rerun_status") or "").strip()
        contract_passed = _nested(record, "current_detector_contract", "contract_passed")
        decision_status = str(
            record.get("decision_status")
            or record.get("current_detector_decision_status")
            or _nested(record, "current_detector_contract", "decision_status")
            or ""
        ).strip().lower()
        wm_id_hat = record.get("wm_id_hat", _nested(record, "current_detector_contract", "wm_id_hat"))
        decoded_candidate = record.get(
            "decoded_wm_id_candidate",
            _nested(record, "current_detector_contract", "decoded_wm_id_candidate"),
        )
        positive_support_score = record.get(
            "positive_support_score",
            _nested(record, "current_detector_contract", "positive_support_score"),
        )
        positive_support_family_count = record.get(
            "positive_support_family_count",
            _nested(record, "current_detector_contract", "positive_support_family_count"),
        )
        positive_support_level_count = record.get(
            "positive_support_level_count",
            _nested(record, "current_detector_contract", "positive_support_level_count"),
        )
        if rerun_status not in CURRENT_DETECTOR_COMPLETE_STATUSES:
            record_issues.append(f"rerun_status_not_complete:{rerun_status or 'missing'}")
            missing_record_count += 1
        if contract_passed is not True:
            record_issues.append("current_detector_contract_not_passed")
        if decision_status not in CURRENT_DETECTOR_CLEAN_DECISIONS:
            record_issues.append(f"decision_status_not_clean:{decision_status or 'missing'}")
        if _is_nonempty(wm_id_hat):
            record_issues.append("wm_id_hat_nonempty")
        if _is_nonempty(decoded_candidate):
            record_issues.append("decoded_wm_id_candidate_nonempty")
        if _positive_number(positive_support_score):
            record_issues.append("positive_support_score_positive")
        if _positive_number(positive_support_family_count):
            record_issues.append("positive_support_family_count_positive")
        if _positive_number(positive_support_level_count):
            record_issues.append("positive_support_level_count_positive")
        if bool(record.get("remaining_detected_after_contract")) or bool(record.get("detected")):
            record_issues.append("remaining_detected_after_contract")
            remaining_detected_count += 1
        if record_issues:
            blockers.extend(record_issues)
            issue_examples.append(
                {
                    "record_index": index,
                    "task_id": record.get("task_id"),
                    "candidate_id": record.get("candidate_id"),
                    "issues": record_issues[:8],
                    "rerun_status": rerun_status,
                    "decision_status": decision_status,
                }
            )
        else:
            passed_count += 1
    blockers = list(dict.fromkeys(blockers))
    return {
        "record_contract_passed": bool(records) and not blockers,
        "record_count": len(records),
        "passed_record_count": passed_count,
        "missing_record_count": missing_record_count,
        "remaining_detected_count": remaining_detected_count,
        "blockers": blockers,
        "issue_examples": issue_examples[:20],
        "required_record_contract": {
            "rerun_status": sorted(CURRENT_DETECTOR_COMPLETE_STATUSES),
            "decision_status": sorted(CURRENT_DETECTOR_CLEAN_DECISIONS),
            "current_detector_contract_passed": True,
            "wm_id_hat": None,
            "decoded_wm_id_candidate": None,
            "positive_support_score": 0,
            "positive_support_family_count": 0,
            "positive_support_level_count": 0,
        },
    }


def _nested(record: dict[str, Any], *keys: str) -> Any:
    value: Any = record
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _candidate_replay_signature(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(item.get("task_id") or ""),
        str(item.get("benchmark") or item.get("benchmark_name") or ""),
        str(item.get("language") or ""),
        str(item.get("attack_name") or ""),
    )


def _replay_record_join_issues(record: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    rerun_status = str(record.get("rerun_status") or _nested(record, "current_detector_contract", "rerun_status") or "").strip()
    decision_status = str(
        record.get("decision_status")
        or record.get("current_detector_decision_status")
        or _nested(record, "current_detector_contract", "decision_status")
        or ""
    ).strip().lower()
    preservation = record.get("source_preservation") if isinstance(record.get("source_preservation"), dict) else {}
    if rerun_status not in CURRENT_DETECTOR_COMPLETE_STATUSES:
        issues.append(f"rerun_status_not_complete:{rerun_status or 'missing'}")
    if decision_status not in CURRENT_DETECTOR_CLEAN_DECISIONS:
        issues.append(f"decision_status_not_clean:{decision_status or 'missing'}")
    if _nested(record, "current_detector_contract", "contract_passed") is not True:
        issues.append("current_detector_contract_not_passed")
    if _is_nonempty(record.get("wm_id_hat")):
        issues.append("wm_id_hat_nonempty")
    if _is_nonempty(record.get("decoded_wm_id_candidate")):
        issues.append("decoded_wm_id_candidate_nonempty")
    if _positive_number(record.get("positive_support_score")):
        issues.append("positive_support_score_positive")
    if not preservation.get("rerunnable_code_field_present"):
        issues.append("rerunnable_code_field_missing")
    if not preservation.get("source_hash_fields_present"):
        issues.append("source_hash_or_payload_hash_missing")
    if not str(record.get("source_full_eval_sha256") or record.get("source_artifact_sha256") or "").strip():
        issues.append("source_full_eval_sha256_missing")
    return list(dict.fromkeys(issues))


def _current_detector_replay_join_diagnostics(candidates: list[dict[str, Any]], path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "available": False,
            "status": "missing",
            "candidate_count": len(candidates),
            "matched_candidate_count": 0,
            "missing_candidate_count": len(candidates),
            "orphan_replay_record_count": 0,
            "rows": [],
        }
    replay = _load_json(path)
    records = [item for item in replay.get("records", []) if isinstance(item, dict)] if isinstance(replay, dict) else []
    by_candidate_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_signature: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    by_task_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        candidate_id = str(record.get("candidate_id") or "").strip()
        if candidate_id:
            by_candidate_id[candidate_id].append(record)
        by_signature[_candidate_replay_signature(record)].append(record)
        by_task_id[str(record.get("task_id") or "")].append(record)

    consumed_record_ids: set[int] = set()
    rows: list[dict[str, Any]] = []
    duplicate_join_keys = 0
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id") or "").strip()
        matches = [record for record in by_candidate_id.get(candidate_id, []) if id(record) not in consumed_record_ids] if candidate_id else []
        join_key = "candidate_id"
        if not matches:
            matches = [record for record in by_signature.get(_candidate_replay_signature(candidate), []) if id(record) not in consumed_record_ids]
            join_key = "task_benchmark_language_attack"
        if not matches:
            matches = [record for record in by_task_id.get(str(candidate.get("task_id") or ""), []) if id(record) not in consumed_record_ids]
            join_key = "task_id_ordered_fallback"
        if len(matches) > 1:
            duplicate_join_keys += 1
        record = matches[0] if matches else {}
        if record:
            consumed_record_ids.add(id(record))
        issues = _replay_record_join_issues(record) if record else ["current_detector_replay_record_missing"]
        rows.append(
            {
                "candidate_id": candidate_id,
                "task_id": candidate.get("task_id"),
                "benchmark": candidate.get("benchmark"),
                "language": candidate.get("language"),
                "attack_name": candidate.get("attack_name"),
                "join_status": "matched" if record else "missing",
                "join_key": join_key if record else "unmatched",
                "matched_replay_candidate_id": record.get("candidate_id") if record else None,
                "rerun_status": record.get("rerun_status") if record else None,
                "decision_status": record.get("decision_status") if record else None,
                "remaining_detected_after_contract": bool(record.get("remaining_detected_after_contract")) if record else None,
                "issues": issues,
            }
        )
    matched_count = sum(1 for row in rows if row["join_status"] == "matched")
    return {
        "available": True,
        "status": "joined" if matched_count == len(candidates) else "incomplete_join",
        "candidate_count": len(candidates),
        "replay_record_count": len(records),
        "matched_candidate_count": matched_count,
        "missing_candidate_count": len(candidates) - matched_count,
        "orphan_replay_record_count": sum(1 for record in records if id(record) not in consumed_record_ids),
        "duplicate_join_key_count": duplicate_join_keys,
        "rows": rows,
    }


def build_manifest(
    *,
    aggregate_path: Path,
    full_eval_path: Path,
    audit_path: Path | None,
    current_detector_replay_path: Path | None,
) -> dict[str, Any]:
    aggregate = _load_json(aggregate_path)
    full_eval = _load_json(full_eval_path)
    records = full_eval.get("records", []) if isinstance(full_eval, dict) else full_eval
    if not isinstance(records, list):
        raise ValueError("full_eval records must be a list")

    task_families = _task_family_map()
    dict_records = [record for record in records if isinstance(record, dict)]
    candidates = sorted(
        (_compact_record(record, task_families) for record in dict_records if _is_negative_hit(record)),
        key=_sort_key,
    )
    schema_inconsistency = _schema_inconsistency_summary(dict_records)
    aggregate_negative_count = int(aggregate.get("negative_control_detection_count") or 0)
    source_count_matches = aggregate_negative_count == len(candidates)
    aggregate_block = _aggregate_evidence(aggregate)
    audit_block = _audit_support_evidence(audit_path, len(candidates))
    current_replay_block = _current_detector_replay_evidence(current_detector_replay_path, len(candidates))
    current_replay_join = _current_detector_replay_join_diagnostics(candidates, current_detector_replay_path)
    blockers: list[str] = []
    canonical_closure_blockers: list[str] = []
    clean_current_detector_admits_fresh_canonical = bool(current_replay_block.get("current_detector_supports_repair"))
    if candidates:
        missing_count = int(current_replay_block.get("missing_task_count") or 0)
        if missing_count:
            blockers.append(f"current_detector_replay_missing_tasks:{missing_count}")
        source_contract = current_replay_block.get("source_preservation_contract")
        source_contract_blockers = (
            source_contract.get("blockers", []) if isinstance(source_contract, dict) else []
        )
        if source_contract_blockers:
            blocked_record_count = int(source_contract.get("blocked_record_count", 0) or 0)
            blockers.append(f"current_detector_source_preservation_blocked_records:{blocked_record_count}")
            for item in source_contract_blockers[:4]:
                blockers.append(f"current_detector_source_preservation:{item}")
        if clean_current_detector_admits_fresh_canonical:
            canonical_closure_blockers.append(
                f"fresh_canonical_rerun_required_after_clean_current_detector_replay:{len(candidates)}"
            )
        else:
            blockers.append(f"negative_control_current_detector_replay_required:{len(candidates)}")
    if not source_count_matches:
        blockers.append("negative_control_count_mismatch_between_full_eval_and_aggregate")
    schema_inconsistency_count = int(schema_inconsistency["schema_inconsistency_count"])
    if schema_inconsistency_count:
        blockers.append(f"negative_control_schema_inconsistency_count:{schema_inconsistency_count}")
    if not bool(aggregate_block.get("negative_control_gate_pass")):
        if clean_current_detector_admits_fresh_canonical and source_count_matches and not schema_inconsistency_count:
            canonical_closure_blockers.append("aggregate_negative_control_gate_not_passed")
        else:
            blockers.append("aggregate_negative_control_gate_not_passed")

    fresh_canonical_rerun_admitted = bool(candidates) and clean_current_detector_admits_fresh_canonical and not blockers
    repair_blockers = list(dict.fromkeys(blockers))
    release_surface_blockers = list(blockers)
    release_surface_blockers.extend(f"canonical_closure:{item}" for item in canonical_closure_blockers)
    release_surface_blockers = list(dict.fromkeys(release_surface_blockers))
    claim_table_blockers = list(release_surface_blockers)
    claim_table_blockers.extend(f"canonical_closure:{item}" for item in canonical_closure_blockers)
    if candidates and not canonical_closure_blockers:
        claim_table_blockers.append(f"canonical_negative_control_hits_present:{len(candidates)}")
    claim_table_blockers = list(dict.fromkeys(claim_table_blockers))
    claim_table_admission_allowed = not candidates and not blockers and not canonical_closure_blockers
    fresh_canonical_rerun_launch_allowed = fresh_canonical_rerun_admitted or not candidates

    return {
        "schema": SCHEMA,
        "status": (
            "fresh_canonical_rerun_admitted"
            if fresh_canonical_rerun_admitted
            else "fail_replay_required"
            if candidates
            else "pass_no_negative_control_hits"
        ),
        "formal_experiment_allowed": claim_table_admission_allowed,
        "formal_experiment_scope": (
            "main_table_claim_admission"
            if claim_table_admission_allowed
            else "blocked_until_fresh_canonical_negative_controls_are_clean"
        ),
        "fresh_canonical_rerun_launch_allowed": fresh_canonical_rerun_launch_allowed,
        "fresh_canonical_rerun_launch_scope": (
            "fresh_canonical_health_or_repair_run_not_claim_bearing"
            if fresh_canonical_rerun_launch_allowed and not claim_table_admission_allowed
            else "not_needed_or_claim_clean"
        ),
        "claim_table_admission_allowed": claim_table_admission_allowed,
        "claim_bearing": claim_table_admission_allowed,
        "claim_role": "negative_control_claim_table_clean" if claim_table_admission_allowed else "support_only_repair_gate_not_claim_bearing",
        "blockers": repair_blockers,
        "repair_blockers": repair_blockers,
        "release_surface_blockers": release_surface_blockers,
        "blocker_policy": {
            "blockers_scope": "release_and_main_claim_surface",
            "repair_blockers_scope": "support_only_fresh_canonical_rerun_admission",
            "canonical_closure_mirrored_to_top_level_blockers": True,
            "reason": (
                "Clean current-detector replay can support a fresh canonical rerun, but stale canonical "
                "negative-control hits remain main-claim blockers until a fresh canonical full_eval is clean."
            ),
        },
        "claim_table_blockers": claim_table_blockers,
        "canonical_closure_blockers": canonical_closure_blockers,
        "fresh_canonical_rerun_admission": {
            "admission_allowed": fresh_canonical_rerun_launch_allowed,
            "scope": "fresh_canonical_negative_control_or_full_eval_rerun",
            "claim_bearing": False if fresh_canonical_rerun_launch_allowed and not claim_table_admission_allowed else claim_table_admission_allowed,
            "formal_claim_experiment_allowed": claim_table_admission_allowed,
            "candidate_count": len(candidates),
            "current_detector_replay_clean": clean_current_detector_admits_fresh_canonical,
            "canonical_negative_hits_retired": False,
            "canonical_closure_blockers": canonical_closure_blockers,
            "claim_boundary": (
                "Clean current-detector replay may admit the next fresh canonical rerun, but it does not "
                "replace or retire stale canonical negative-control hits."
            ),
        },
        "source_artifacts": {
            "aggregate": str(aggregate_path.relative_to(ROOT) if aggregate_path.is_relative_to(ROOT) else aggregate_path),
            "full_eval": str(full_eval_path.relative_to(ROOT) if full_eval_path.is_relative_to(ROOT) else full_eval_path),
            "negative_split_audit": audit_block.get("path"),
            "current_detector_replay": current_replay_block.get("path"),
        },
        "canonical_evidence": aggregate_block,
        "source_count_matches_aggregate": source_count_matches,
        "candidate_count": len(candidates),
        "candidate_count_expected_from_aggregate": aggregate_negative_count,
        "candidate_count_mismatch_reason": None
        if source_count_matches
        else "full_eval negative hit extraction disagrees with aggregate negative_control_detection_count",
        "negative_control_schema_consistency": schema_inconsistency,
        "fresh_materializer_negative_split_audit": audit_block,
        "current_detector_negative_control_replay": current_replay_block,
        "current_detector_replay_join_diagnostics": current_replay_join,
        "canonical_replacement_policy": {
            "fresh_materializer_negative_split_can_replace_canonical": False,
            "fresh_materializer_negative_split_can_support_repair": bool(audit_block.get("clean_supported_negative_slice")),
            "current_detector_replay_can_replace_canonical": False,
            "current_detector_replay_can_support_repair": bool(
                current_replay_block.get("current_detector_supports_repair")
            ),
            "reason": (
                "support-only evidence cannot retire old canonical negative hits until current full_eval/aggregate "
                "are clean; a clean replay can only admit the next fresh canonical rerun"
            ),
        },
        "highest_risk": {
            "task_ids": _grouped_risk(candidates, "task_id"),
            "families": _grouped_risk(candidates, "family"),
            "languages": _counter_summary(candidates, "language"),
            "attack_categories": _counter_summary(candidates, "attack_category"),
            "attack_names": _counter_summary(candidates, "attack_name"),
            "negative_hit_reasons": _reason_summary(candidates),
        },
        "negative_control_repair_ledger": _repair_ledger(candidates),
        "replay_candidates": candidates,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the SemCodebook negative-control replay gate manifest.")
    parser.add_argument("--aggregate", type=Path, default=ARTIFACTS / "aggregate_results.json")
    parser.add_argument("--full-eval", type=Path, default=ARTIFACTS / "full_eval_results.json")
    parser.add_argument("--negative-split-audit", type=Path, default=None)
    parser.add_argument("--current-detector-replay", type=Path, default=DEFAULT_CURRENT_DETECTOR_REPLAY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Fail if the output manifest is missing or stale.")
    parser.add_argument("--require-clean", action="store_true", help="In check mode, fail if any negative-control blocker remains.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    audit_path = _discover_audit_path(args.negative_split_audit)
    manifest = build_manifest(
        aggregate_path=args.aggregate,
        full_eval_path=args.full_eval,
        audit_path=audit_path,
        current_detector_replay_path=args.current_detector_replay,
    )
    rendered = _json_bytes(manifest)

    if args.check:
        if not args.output.exists():
            print(f"{args.output} is missing; run build_negative_control_replay_gate.py", file=sys.stderr)
            return 1
        current = args.output.read_bytes()
        if current != rendered:
            print(f"{args.output} is stale; rerun build_negative_control_replay_gate.py", file=sys.stderr)
            return 1
        if args.require_clean and (
            not manifest["formal_experiment_allowed"]
            or manifest["candidate_count"]
            or manifest.get("canonical_closure_blockers")
        ):
            print(
                json.dumps(
                    {
                        "status": manifest["status"],
                        "candidate_count": manifest["candidate_count"],
                        "blockers": manifest["blockers"],
                        "claim_table_blockers": manifest.get("claim_table_blockers", []),
                        "canonical_closure_blockers": manifest.get("canonical_closure_blockers", []),
                    },
                    ensure_ascii=True,
                ),
                file=sys.stderr,
            )
            return 1
        print(json.dumps({"status": "ok", "path": str(args.output), "candidate_count": manifest["candidate_count"]}))
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rendered)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "path": str(args.output),
                "candidate_count": manifest["candidate_count"],
                "source_count_matches_aggregate": manifest["source_count_matches_aggregate"],
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
