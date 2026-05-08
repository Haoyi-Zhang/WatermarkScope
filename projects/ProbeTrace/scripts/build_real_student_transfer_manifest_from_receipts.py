from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT
from probetrace.reranker import observe_family
from probetrace.signature import (
    DEFAULT_DEMO_OWNER_KEY,
    DEFAULT_OWNER_KEY_ENV,
    DEMO_OWNER_KEY_ENV,
    owner_key_to_owner_id,
)


SCHEMA_VERSION = "probetrace_real_student_transfer_manifest_builder_v1"
MANIFEST_SCHEMA = "probetrace_real_student_transfer_manifest_v1"
VALIDATION_SCHEMA = "probetrace_student_transfer_live_validation_results_v1"
RECEIPT_SCHEMA = "probetrace_real_student_transfer_training_receipt_v1"
REQUIRED_FAMILIES = ("sft", "lora", "quantized")
LIVE_VALIDATION_STATUSES = {"claim_bearing_live_validated", "live_validated", "passed"}
MIN_OWNER_SIGNAL_CONFIDENCE = 0.55
HASH_KEYS = (
    "adapter_artifact_sha256",
    "checkpoint_sha256",
    "model_artifact_sha256",
    "training_run_sha256",
    "weight_artifact_sha256",
)
DEFAULT_RECEIPT_ROOT = ARTIFACTS / "student_transfer_runs"
DEFAULT_DATASET = ARTIFACTS / "student_transfer_training_dataset.jsonl"
DEFAULT_VALIDATION_DATASET = ARTIFACTS / "student_transfer_hidden_validation_dataset.jsonl"
DEFAULT_VALIDATION = ARTIFACTS / "student_transfer_live_validation_results.json"
DEFAULT_OUTPUT = ARTIFACTS / "real_student_transfer_manifest.json"
DEFAULT_GATE = ARTIFACTS / "real_student_transfer_manifest_gate.json"
DEFAULT_TEMPLATE = ARTIFACTS / "student_transfer_live_validation_template.json"
DEFAULT_QUEUE_RECEIPTS = (
    ARTIFACTS / "student_transfer_training_queue_receipt_owner_conditioned_v3.json",
    ARTIFACTS / "student_transfer_training_queue_receipt_owner_conditioned_v2.json",
    ARTIFACTS / "student_transfer_training_queue_receipt.json",
)
DEMO_OWNER_ID = owner_key_to_owner_id(DEFAULT_DEMO_OWNER_KEY)


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return rows
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _rel(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _receipt_path(receipt_root: Path, family: str) -> Path:
    return receipt_root / family / "training_receipt.json"


def _queue_receipt() -> tuple[dict[str, Any], Path | None]:
    for path in DEFAULT_QUEUE_RECEIPTS:
        payload = _load(path)
        if payload:
            return payload, path
    return {}, None


def _queue_job_by_family(queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    jobs = {}
    for item in _as_list(queue.get("jobs")):
        if not isinstance(item, dict):
            continue
        family = str(item.get("family", "")).strip().lower()
        if family:
            jobs[family] = dict(item)
    return jobs


def _receipt_freshness_blockers(path: Path, family: str, queue_jobs: dict[str, dict[str, Any]]) -> list[str]:
    job = queue_jobs.get(family)
    if not job:
        return []
    blockers: list[str] = []
    raw_returncode = job.get("returncode", -1)
    returncode = -1 if raw_returncode is None else _safe_int(raw_returncode)
    if str(job.get("status", "")).strip().lower() != "completed" or returncode != 0:
        blockers.append(f"receipt_queue_job_not_completed:{family}")
    started = _parse_utc(job.get("started_at_utc"))
    finished = _parse_utc(job.get("finished_at_utc"))
    if started is not None and path.exists():
        receipt_mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if receipt_mtime < started:
            blockers.append(f"receipt_stale_before_current_queue_job:{family}")
        if finished is not None and receipt_mtime > finished:
            blockers.append(f"receipt_modified_after_queue_job_finished:{family}")
    return blockers


def _student_from_receipt(
    receipt: dict[str, Any],
    receipt_path: Path,
    *,
    dataset_path: Path,
    dataset_sha256: str,
    dataset_owner_ids: list[str],
) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    family = str(receipt.get("family", "")).strip().lower()
    student_id = f"{family}-student"
    if receipt.get("schema_version") != RECEIPT_SCHEMA:
        blockers.append(f"receipt_schema_missing_or_wrong:{family or '<missing>'}")
    if family not in REQUIRED_FAMILIES:
        blockers.append(f"receipt_family_invalid:{family or '<missing>'}")
    if _safe_int(receipt.get("example_count")) < 300:
        blockers.append(f"receipt_example_count_below_300:{family or '<missing>'}")
    source_hashes = [str(item) for item in _as_list(receipt.get("source_record_hashes")) if str(item).strip()]
    if len(source_hashes) < 300:
        blockers.append(f"receipt_source_record_hashes_below_300:{family or '<missing>'}")
    if not any(str(receipt.get(key, "")).strip() for key in HASH_KEYS):
        blockers.append(f"receipt_training_artifact_hash_missing:{family or '<missing>'}")
    if not str(receipt.get("training_run_sha256", "")).strip():
        blockers.append(f"receipt_training_run_sha256_missing:{family or '<missing>'}")
    output_dir = str(receipt.get("output_dir", "")).strip()
    if not output_dir:
        blockers.append(f"receipt_output_dir_missing:{family or '<missing>'}")
    receipt_dataset = receipt.get("dataset", {})
    receipt_dataset = dict(receipt_dataset) if isinstance(receipt_dataset, dict) else {}
    receipt_dataset_sha = str(receipt_dataset.get("sha256", "")).strip()
    receipt_dataset_path = str(receipt_dataset.get("path", "")).strip()
    if not receipt_dataset_sha:
        blockers.append(f"receipt_dataset_sha256_missing:{family or '<missing>'}")
    elif dataset_sha256 and receipt_dataset_sha != dataset_sha256:
        blockers.append(f"receipt_dataset_sha256_mismatch:{family or '<missing>'}")
    if receipt_dataset_path and _rel(dataset_path) != receipt_dataset_path:
        blockers.append(f"receipt_dataset_path_mismatch:{family or '<missing>'}")
    if len(dataset_owner_ids) != 1:
        blockers.append(f"receipt_dataset_teacher_owner_id_not_singleton:{family or '<missing>'}")
    student = {
        "student_id": student_id,
        "transfer_family": family,
        "family": family,
        "training_kind": str(receipt.get("training_kind", "")).strip(),
        "base_model": str(receipt.get("base_model", "")).strip(),
        "example_count": _safe_int(receipt.get("example_count")),
        "provider_names": ["deepseek"],
        "source_record_hashes": source_hashes,
        "training_run_id": str(receipt.get("training_run_sha256", "")).strip(),
        "training_receipt": _rel(receipt_path),
        "training_receipt_sha256": _sha256(receipt_path),
        "output_dir": output_dir,
        "dataset_path": receipt_dataset_path,
        "dataset_sha256": receipt_dataset_sha,
        "teacher_owner_id": dataset_owner_ids[0] if len(dataset_owner_ids) == 1 else "",
    }
    for key in HASH_KEYS:
        value = str(receipt.get(key, "")).strip()
        if value:
            student[key] = value
    return student, blockers


def _validation_results(validation: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    blockers: list[str] = []
    if validation.get("schema_version") != VALIDATION_SCHEMA:
        blockers.append("validation_schema_missing_or_wrong")
    if validation.get("claim_role") != "claim_bearing_student_transfer_validation":
        blockers.append("validation_claim_role_not_claim_bearing_student_transfer_validation")
    by_id: dict[str, dict[str, Any]] = {}
    for item in _as_list(validation.get("results")):
        if not isinstance(item, dict):
            continue
        student_id = str(item.get("student_id", "")).strip()
        if student_id:
            by_id[student_id] = dict(item)
    if not by_id:
        blockers.append("validation_results_missing")
    return by_id, blockers


def _owner_key_status() -> dict[str, Any]:
    owner_present = bool(os.environ.get(DEFAULT_OWNER_KEY_ENV, "").strip())
    demo_env_present = bool(os.environ.get(DEMO_OWNER_KEY_ENV, "").strip())
    owner_is_default_demo = os.environ.get(DEFAULT_OWNER_KEY_ENV, "").strip() == DEFAULT_DEMO_OWNER_KEY
    return {
        "owner_key_env": DEFAULT_OWNER_KEY_ENV,
        "owner_key_present": owner_present,
        "demo_owner_key_env": DEMO_OWNER_KEY_ENV,
        "demo_owner_key_env_present": demo_env_present,
        "owner_key_is_default_demo": owner_is_default_demo,
        "claim_bearing_owner_key_usable": owner_present and not demo_env_present and not owner_is_default_demo,
        "owner_id": owner_key_to_owner_id(os.environ.get(DEFAULT_OWNER_KEY_ENV, "").strip()) if owner_present else "",
    }


def _row_owner_signal_matches(row: dict[str, Any]) -> bool:
    completion = str(row.get("completion", row.get("code", ""))).strip()
    selected_family = str(row.get("selected_family", "")).strip()
    expected_bit_text = str(row.get("expected_bit", "")).strip()
    if not completion or not selected_family or expected_bit_text not in {"0", "1"}:
        return False
    observation = observe_family(completion, selected_family)
    return observation.observed_bit == int(expected_bit_text) and observation.confidence >= MIN_OWNER_SIGNAL_CONFIDENCE


def _training_dataset_status(dataset_path: Path) -> dict[str, Any]:
    rows = _read_jsonl(dataset_path)
    owner_ids = sorted(
        {
            str(item.get("teacher_owner_id", "")).strip()
            for item in rows
            if str(item.get("teacher_owner_id", "")).strip()
        }
    )
    owner_conditioned_count = sum(
        1 for item in rows if item.get("training_signal_status") == "owner_conditioned_live_probe_trace"
    )
    live_provider_count = sum(
        1
        for item in rows
        if str(item.get("provider_mode", "")).strip().lower() == "live"
        and str(item.get("provider", "")).strip().lower() not in {"", "mock", "no_provider", "unknown"}
    )
    source_hashes = [
        str(item.get("source_record_hash", "")).strip()
        for item in rows
        if str(item.get("source_record_hash", "")).strip()
    ]
    owner_signal_matched_count = sum(1 for item in rows if _row_owner_signal_matches(item))
    metadata_complete_count = sum(
        1
        for item in rows
        if str(item.get("selected_family", "")).strip()
        and str(item.get("expected_bit", "")).strip() in {"0", "1"}
        and str(item.get("completion", item.get("code", ""))).strip()
        and str(item.get("transcript_hash", "")).strip()
        and str(item.get("service_commitment_root", "")).strip()
    )
    blockers: list[str] = []
    if not dataset_path.exists():
        blockers.append("student_transfer_training_dataset_missing")
    if len(rows) < 300:
        blockers.append(f"student_transfer_training_dataset_records_below_300:{len(rows)}")
    if owner_conditioned_count < 300:
        blockers.append(f"student_transfer_training_dataset_owner_conditioned_below_300:{owner_conditioned_count}")
    if live_provider_count < 300:
        blockers.append(f"student_transfer_training_dataset_live_provider_records_below_300:{live_provider_count}")
    if metadata_complete_count < 300:
        blockers.append(f"student_transfer_training_dataset_owner_signal_metadata_complete_below_300:{metadata_complete_count}")
    if owner_signal_matched_count < 300:
        blockers.append(f"student_transfer_training_dataset_owner_signal_matched_below_300:{owner_signal_matched_count}")
    if len(set(source_hashes)) != len(rows):
        blockers.append("student_transfer_training_dataset_source_hashes_missing_or_not_unique")
    if len(owner_ids) != 1:
        blockers.append(f"student_transfer_training_dataset_teacher_owner_id_not_singleton:{len(owner_ids)}")
    return {
        "path": _rel(dataset_path),
        "present": dataset_path.exists(),
        "sha256": _sha256(dataset_path),
        "record_count": len(rows),
        "owner_conditioned_record_count": owner_conditioned_count,
        "live_provider_record_count": live_provider_count,
        "owner_signal_metadata_complete_count": metadata_complete_count,
        "owner_signal_matched_record_count": owner_signal_matched_count,
        "minimum_owner_signal_confidence": MIN_OWNER_SIGNAL_CONFIDENCE,
        "source_record_hash_count": len(source_hashes),
        "unique_source_record_hash_count": len(set(source_hashes)),
        "source_record_hashes": source_hashes,
        "teacher_owner_ids": owner_ids,
        "blockers": blockers,
    }


def _hidden_validation_dataset_status(validation_dataset_path: Path, training_status: dict[str, Any]) -> dict[str, Any]:
    rows = _read_jsonl(validation_dataset_path)
    owner_ids = sorted(
        {
            str(item.get("teacher_owner_id", "")).strip()
            for item in rows
            if str(item.get("teacher_owner_id", "")).strip()
        }
    )
    training_hashes = set(str(item) for item in training_status.get("source_record_hashes", []) if str(item).strip())
    training_rows = {
        str(item.get("source_record_hash", "")).strip(): item
        for item in _read_jsonl(Path(str(training_status.get("path", ""))))
        if str(item.get("source_record_hash", "")).strip()
    }
    # If the status path is relative to the project root, resolve it here.
    if not training_rows:
        resolved_training_path = ROOT / str(training_status.get("path", ""))
        training_rows = {
            str(item.get("source_record_hash", "")).strip(): item
            for item in _read_jsonl(resolved_training_path)
            if str(item.get("source_record_hash", "")).strip()
        }
    source_hashes = [
        str(item.get("source_record_hash", "")).strip()
        for item in rows
        if str(item.get("source_record_hash", "")).strip()
    ]
    bound_count = sum(1 for source_hash in source_hashes if source_hash in training_hashes)
    metadata_consistent_count = 0
    for item in rows:
        source_hash = str(item.get("source_record_hash", "")).strip()
        train = training_rows.get(source_hash, {})
        if not train:
            continue
        if (
            str(item.get("teacher_owner_id", "")).strip() == str(train.get("teacher_owner_id", "")).strip()
            and str(item.get("selected_family", "")).strip() == str(train.get("selected_family", "")).strip()
            and str(item.get("expected_bit", "")).strip() == str(train.get("expected_bit", "")).strip()
        ):
            metadata_consistent_count += 1
    blockers: list[str] = []
    if not validation_dataset_path.exists():
        blockers.append("student_transfer_hidden_validation_dataset_missing")
    if len(rows) < 300:
        blockers.append(f"student_transfer_hidden_validation_dataset_records_below_300:{len(rows)}")
    if len(owner_ids) != 1:
        blockers.append(f"student_transfer_hidden_validation_teacher_owner_id_not_singleton:{len(owner_ids)}")
    if bound_count < 300:
        blockers.append(f"student_transfer_hidden_validation_source_bindings_below_300:{bound_count}")
    if metadata_consistent_count < 300:
        blockers.append(f"student_transfer_hidden_validation_owner_signal_metadata_consistent_below_300:{metadata_consistent_count}")
    return {
        "path": _rel(validation_dataset_path),
        "present": validation_dataset_path.exists(),
        "sha256": _sha256(validation_dataset_path),
        "record_count": len(rows),
        "teacher_owner_ids": owner_ids,
        "source_binding_count": bound_count,
        "metadata_consistent_count": metadata_consistent_count,
        "source_record_hash_count": len(source_hashes),
        "blockers": blockers,
    }


def _split_overlap_status(training_dataset_path: Path, validation_dataset_path: Path) -> dict[str, Any]:
    train_rows = _read_jsonl(training_dataset_path)
    validation_rows = _read_jsonl(validation_dataset_path)
    train_prompt_hashes = {
        str(item.get("prompt_hash", "")).strip()
        for item in train_rows
        if str(item.get("prompt_hash", "")).strip()
    }
    validation_prompt_hashes = {
        str(item.get("prompt_hash", "")).strip()
        for item in validation_rows
        if str(item.get("prompt_hash", "")).strip()
    }
    overlap = sorted(train_prompt_hashes.intersection(validation_prompt_hashes))
    blockers: list[str] = []
    if not validation_dataset_path.exists():
        blockers.append("student_transfer_hidden_validation_dataset_missing")
    if len(validation_rows) < 300:
        blockers.append(f"student_transfer_hidden_validation_dataset_records_below_300:{len(validation_rows)}")
    if overlap:
        blockers.append(f"student_transfer_hidden_validation_prompt_overlap:{len(overlap)}")
    return {
        "training_prompt_hash_count": len(train_prompt_hashes),
        "validation_prompt_hash_count": len(validation_prompt_hashes),
        "prompt_hash_overlap_count": len(overlap),
        "blockers": blockers,
    }


def _template(students: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": VALIDATION_SCHEMA,
        "claim_role": "claim_bearing_student_transfer_validation",
        "claim_boundary": "fill only from live black-box student attribution validation; do not copy pilot diagnostics",
        "results": [
            {
                "student_id": str(student.get("student_id", "")),
                "transfer_family": str(student.get("transfer_family", "")),
                "validation_status": "pending_live_validation",
                "attributed_owner_id": "",
                "coverage": 0.0,
                "confidence": 0.0,
                "inheritance_rate": 0.0,
                "margin": 0.0,
                "validation_prompt_count": 0,
                "expected_owner_id": "",
                "output_record_sha256": "",
                "owner_registry_hash": "",
                "evidence_trace": [],
            }
            for student in students
        ],
    }


def build_manifest(
    *,
    receipt_root: Path = DEFAULT_RECEIPT_ROOT,
    dataset_path: Path = DEFAULT_DATASET,
    validation_dataset_path: Path = DEFAULT_VALIDATION_DATASET,
    validation_path: Path = DEFAULT_VALIDATION,
    output_path: Path = DEFAULT_OUTPUT,
    gate_path: Path = DEFAULT_GATE,
    template_path: Path = DEFAULT_TEMPLATE,
) -> dict[str, Any]:
    blockers: list[str] = []
    students: list[dict[str, Any]] = []
    owner_key_status = _owner_key_status()
    dataset_status = _training_dataset_status(dataset_path)
    blockers.extend(dataset_status["blockers"])
    validation_dataset_status = _hidden_validation_dataset_status(validation_dataset_path, dataset_status)
    split_overlap_status = _split_overlap_status(dataset_path, validation_dataset_path)
    blockers.extend(f"validation:{item}" for item in validation_dataset_status["blockers"])
    blockers.extend(split_overlap_status["blockers"])
    if dataset_status["teacher_owner_ids"] != validation_dataset_status["teacher_owner_ids"]:
        blockers.append("student_transfer_training_validation_teacher_owner_mismatch")
    if not owner_key_status["owner_key_present"]:
        blockers.append(f"{DEFAULT_OWNER_KEY_ENV}_missing_for_live_validation")
    if owner_key_status["demo_owner_key_env_present"]:
        blockers.append(f"{DEMO_OWNER_KEY_ENV}_not_allowed_for_claim_bearing_live_validation")
    if owner_key_status["owner_key_is_default_demo"]:
        blockers.append("default_demo_owner_key_not_allowed_for_claim_bearing_live_validation")
    receipt_artifacts: dict[str, dict[str, Any]] = {}
    use_default_queue_receipt = receipt_root.resolve() == DEFAULT_RECEIPT_ROOT.resolve()
    queue_payload, queue_path = _queue_receipt() if use_default_queue_receipt else ({}, None)
    queue_jobs = _queue_job_by_family(queue_payload)
    for family in REQUIRED_FAMILIES:
        path = _receipt_path(receipt_root, family)
        freshness_blockers = _receipt_freshness_blockers(path, family, queue_jobs)
        receipt = _load(path)
        receipt_artifacts[family] = {
            "path": _rel(path),
            "present": path.exists(),
            "sha256": _sha256(path),
            "queue_job": queue_jobs.get(family, {}),
            "freshness_blockers": freshness_blockers,
        }
        blockers.extend(freshness_blockers)
        if not receipt:
            blockers.append(f"training_receipt_missing:{family}")
            continue
        student, receipt_blockers = _student_from_receipt(
            receipt,
            path,
            dataset_path=dataset_path,
            dataset_sha256=str(dataset_status["sha256"]),
            dataset_owner_ids=[str(item) for item in dataset_status["teacher_owner_ids"]],
        )
        blockers.extend(receipt_blockers)
        students.append(student)
    observed_families = {str(item.get("transfer_family", "")) for item in students}
    for family in REQUIRED_FAMILIES:
        if family not in observed_families:
            blockers.append(f"transfer_family_missing:{family}")

    validation = _load(validation_path)
    validation_by_id, validation_blockers = _validation_results(validation)
    blockers.extend(validation_blockers)
    results: list[dict[str, Any]] = []
    for student in students:
        student_id = str(student.get("student_id", "")).strip()
        result = validation_by_id.get(student_id)
        if result is None:
            blockers.append(f"live_validation_result_missing:{student_id}")
            continue
        if str(result.get("validation_status", "")).strip() not in LIVE_VALIDATION_STATUSES:
            blockers.append(f"live_validation_status_not_passed:{student_id}")
        if not str(result.get("attributed_owner_id", "")).strip():
            blockers.append(f"live_validation_owner_missing:{student_id}")
        expected_owner_id = str(result.get("expected_owner_id", "")).strip()
        if dataset_status["teacher_owner_ids"] and expected_owner_id != str(dataset_status["teacher_owner_ids"][0]):
            blockers.append(f"live_validation_expected_owner_not_dataset_teacher:{student_id}")
        if owner_key_status["owner_id"] and expected_owner_id != owner_key_status["owner_id"]:
            blockers.append(f"live_validation_expected_owner_not_env_owner:{student_id}")
        if expected_owner_id and str(result.get("attributed_owner_id", "")).strip() != expected_owner_id:
            blockers.append(f"live_validation_owner_mismatch:{student_id}")
        if expected_owner_id == DEMO_OWNER_ID or str(result.get("attributed_owner_id", "")).strip() == DEMO_OWNER_ID:
            blockers.append(f"live_validation_demo_owner_id_not_allowed:{student_id}")
        if not _as_list(result.get("evidence_trace")):
            blockers.append(f"live_validation_evidence_trace_missing:{student_id}")
        if _safe_int(result.get("validation_prompt_count")) < 300:
            blockers.append(f"live_validation_prompt_count_below_300:{student_id}")
        if _safe_float(result.get("confidence")) < 0.55:
            blockers.append(f"live_validation_confidence_below_0_55:{student_id}")
        if _safe_float(result.get("coverage")) < 0.5:
            blockers.append(f"live_validation_coverage_below_0_5:{student_id}")
        if not str(result.get("output_record_sha256", "")).strip():
            blockers.append(f"live_validation_output_record_sha256_missing:{student_id}")
        if not str(result.get("owner_registry_hash", "")).strip():
            blockers.append(f"live_validation_owner_registry_hash_missing:{student_id}")
        results.append(result)

    blockers = sorted(dict.fromkeys(blockers))
    gate = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "status": "ready" if not blockers else "blocked",
        "claim_role": "real_student_transfer_manifest_gate_not_evidence",
        "claim_bearing_manifest_ready": not blockers,
        "manifest_output": _rel(output_path),
        "validation_artifact": {"path": _rel(validation_path), "present": validation_path.exists(), "sha256": _sha256(validation_path)},
        "training_queue_receipt": {
            "path": _rel(queue_path) if queue_path is not None else "",
            "present": queue_path is not None,
            "sha256": _sha256(queue_path) if queue_path is not None else "",
            "family_statuses": {
                family: {
                    "status": str(queue_jobs.get(family, {}).get("status", "")),
                    "returncode": queue_jobs.get(family, {}).get("returncode"),
                    "started_at_utc": str(queue_jobs.get(family, {}).get("started_at_utc", "")),
                    "finished_at_utc": str(queue_jobs.get(family, {}).get("finished_at_utc", "")),
                }
                for family in REQUIRED_FAMILIES
                if family in queue_jobs
            },
            "fail_closed_if_receipt_predates_current_queue_job": True,
        },
        "training_dataset_artifact": dataset_status,
        "hidden_validation_dataset_artifact": validation_dataset_status,
        "training_validation_split_overlap": split_overlap_status,
        "receipt_artifacts": receipt_artifacts,
        "required_transfer_families": list(REQUIRED_FAMILIES),
        "observed_transfer_families": sorted(observed_families),
        "student_count": len(students),
        "validation_result_count": len(validation_by_id),
        "owner_key_status": owner_key_status,
        "blockers": blockers,
        "external_secret_blockers": [
            item
            for item in blockers
            if item
            in {
                f"{DEFAULT_OWNER_KEY_ENV}_missing_for_live_validation",
                f"{DEMO_OWNER_KEY_ENV}_not_allowed_for_claim_bearing_live_validation",
                "default_demo_owner_key_not_allowed_for_claim_bearing_live_validation",
            }
        ],
        "next_step": (
            f"python scripts/run_student_transfer_experiment.py --profile full --claim-bearing --real-transfer-manifest {_rel(output_path)}"
            if not blockers
            else (
                f"set a non-demo {DEFAULT_OWNER_KEY_ENV} and run scripts/run_real_student_transfer_live_validation.py; "
                f"then rebuild {_rel(gate_path)}"
                if f"{DEFAULT_OWNER_KEY_ENV}_missing_for_live_validation" in blockers
                else f"complete receipts and live validation template at {_rel(template_path)}"
            )
        ),
    }
    _write(gate_path, gate)
    if blockers:
        _write(template_path, _template(students))
        return gate

    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "artifact_type": "real_student_transfer_manifest",
        "claim_role": "claim_bearing_student_transfer_evidence",
        "evidence_scope": "claim_bearing_live_student_transfer",
        "generated_at_utc": _utc_now(),
        "student_count": len(students),
        "students": students,
        "results": results,
        "receipt_artifacts": receipt_artifacts,
        "validation_artifact": gate["validation_artifact"],
        "claim_boundary": "real SFT/LoRA/quantized receipts plus live black-box validation only; no pilot diagnostics admitted",
    }
    _write(output_path, manifest)
    return gate


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a fail-closed real student-transfer manifest from training receipts.")
    parser.add_argument("--receipt-root", type=Path, default=DEFAULT_RECEIPT_ROOT)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--validation-dataset", type=Path, default=DEFAULT_VALIDATION_DATASET)
    parser.add_argument("--validation", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--gate-output", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--template-output", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    gate = build_manifest(
        receipt_root=args.receipt_root,
        dataset_path=args.dataset,
        validation_dataset_path=args.validation_dataset,
        validation_path=args.validation,
        output_path=args.output,
        gate_path=args.gate_output,
        template_path=args.template_output,
    )
    print(json.dumps({"status": gate["status"], "blockers": gate["blockers"], "gate": str(args.gate_output)}, ensure_ascii=True))
    if args.check and gate["status"] != "ready":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
