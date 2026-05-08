from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT
from build_sample_selection_rerun_audit import _provider_record_key


SCHEMA = "codedye_provider_payload_canonical_sync_v1"
DEFAULT_RUN_ID = "codedye_deepseek_utilityfirst_rerun_next"
DEFAULT_REPORT = ARTIFACTS / "provider_payload_canonical_sync_report.json"
RAW_FIELDS = ("raw_response_text", "response_text", "provider_response_text")


def _sha256_bytes(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _has_raw_payload(record: dict[str, Any]) -> bool:
    samples = record.get("candidate_samples")
    if not isinstance(samples, list) or not samples:
        return False
    return all(
        isinstance(sample, dict)
        and any(str(sample.get(field, "")).strip() for field in RAW_FIELDS)
        for sample in samples
    )


def _display(path: Path) -> str:
    if not str(path):
        return ""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _stable_record_identity(record: dict[str, Any]) -> str:
    surface = (
        "codedye_contamination"
        if str(record.get("contamination_scoring_status", "")).strip() == "scored"
        else "public_utility_support"
    )
    return "|".join(
        (
            surface,
            str(record.get("provider_name", "")).strip().lower(),
            str(record.get("provider_mode_requested", "")).strip().lower(),
            str(record.get("task_source", record.get("source", ""))).strip(),
            str(record.get("benchmark", "")).strip(),
            str(record.get("task_id", "")).strip(),
        )
    )


def _build_provider_index(provider_records: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], set[str], set[str]]:
    index: dict[str, dict[str, Any]] = {}
    stable_index: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    stable_duplicates: set[str] = set()
    for record in provider_records:
        key = _provider_record_key(record)
        if key in index:
            duplicates.add(key)
        else:
            index[key] = record
        stable_key = _stable_record_identity(record)
        if stable_key in stable_index:
            stable_duplicates.add(stable_key)
        else:
            stable_index[stable_key] = record
    return index, stable_index, duplicates, stable_duplicates


def build_sync_report(
    *,
    run_id: str,
    full_eval_path: Path,
    provider_records_path: Path,
    output_path: Path,
    apply: bool,
    allow_partial: bool,
) -> dict[str, Any]:
    full_eval = _read_json(full_eval_path)
    records = [dict(item) for item in full_eval.get("records", []) if isinstance(item, dict)]
    provider_records = _read_jsonl(provider_records_path)
    provider_index, stable_provider_index, duplicate_keys, stable_duplicate_keys = _build_provider_index(provider_records)

    missing_provider_keys: list[str] = []
    updated_records: list[dict[str, Any]] = []
    unchanged_with_raw = 0
    raw_payloads_added = 0
    raw_payloads_still_missing = 0
    black_box_records = 0
    strict_key_match_count = 0
    stable_identity_match_count = 0
    for record in records:
        current = copy.deepcopy(record)
        if str(current.get("evaluation_surface", "")).strip() != "black_box_api":
            updated_records.append(current)
            continue
        black_box_records += 1
        if _has_raw_payload(current):
            unchanged_with_raw += 1
            updated_records.append(current)
            continue
        key = _provider_record_key(current)
        source = provider_index.get(key)
        if source:
            strict_key_match_count += 1
        else:
            source = stable_provider_index.get(_stable_record_identity(current))
            if source:
                stable_identity_match_count += 1
        if not source:
            missing_provider_keys.append(key)
            raw_payloads_still_missing += 1
            updated_records.append(current)
            continue
        source_samples = source.get("candidate_samples")
        if not isinstance(source_samples, list) or not _has_raw_payload(source):
            raw_payloads_still_missing += 1
            updated_records.append(current)
            continue
        current["candidate_samples"] = copy.deepcopy(source_samples)
        for field in (
            "raw_payload_hash",
            "raw_provider_transcript_hash",
            "provider_trace_transcript_hash",
            "structured_payload_hash",
        "provider_trace_request_count",
        "provider_request_ids",
            "candidate_payload_capture_complete",
            "candidate_payload_capture_reason",
            "candidate_payload_schema_version",
            "candidate_sample_count",
            "sample_selection_contract_version",
        "selected_sample_index",
        "utility_selected_sample_index",
            "run_checkpoint_key",
        ):
            if field in source:
                current[field] = copy.deepcopy(source[field])
        raw_payloads_added += 1
        updated_records.append(current)

    complete = (
        black_box_records > 0
        and raw_payloads_still_missing == 0
        and not duplicate_keys
        and not stable_duplicate_keys
        and len(provider_records) >= black_box_records
    )
    blockers: list[str] = []
    if black_box_records <= 0:
        blockers.append("canonical_black_box_records_missing")
    if duplicate_keys:
        blockers.append(f"provider_records_duplicate_keys:{len(duplicate_keys)}")
    if stable_duplicate_keys:
        blockers.append(f"provider_records_stable_identity_duplicate_keys:{len(stable_duplicate_keys)}")
    if len(provider_records) < black_box_records:
        blockers.append(f"provider_records_incomplete:{len(provider_records)}/{black_box_records}")
    if missing_provider_keys:
        blockers.append(f"provider_records_missing_canonical_keys:{len(missing_provider_keys)}")
    if raw_payloads_still_missing:
        blockers.append(f"raw_provider_payloads_still_missing:{raw_payloads_still_missing}")

    applied = False
    backup_path = Path()
    if apply and (complete or allow_partial):
        backup_path = full_eval_path.with_suffix(full_eval_path.suffix + f".pre_payload_sync_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.bak")
        backup_path.write_bytes(full_eval_path.read_bytes())
        full_eval["records"] = updated_records
        full_eval.setdefault("operator_state", {})
        if isinstance(full_eval["operator_state"], dict):
            full_eval["operator_state"]["provider_payload_canonical_sync_schema"] = SCHEMA
            full_eval["operator_state"]["provider_payload_canonical_sync_run_id"] = run_id
            full_eval["operator_state"]["provider_payload_canonical_sync_applied_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            full_eval["operator_state"]["provider_payload_source_sha256"] = _sha256_bytes(provider_records_path)
        full_eval_path.write_text(json.dumps(full_eval, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
        applied = True

    report = {
        "schema_version": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "CodeDye",
        "run_id": run_id,
        "status": "pass" if complete else "blocked",
        "apply_requested": apply,
        "applied": applied,
        "allow_partial": allow_partial,
        "full_eval_path": _display(full_eval_path),
        "full_eval_sha256_after": _sha256_bytes(full_eval_path),
        "backup_path": _display(backup_path) if backup_path else "",
        "provider_records_path": _display(provider_records_path),
        "provider_records_sha256": _sha256_bytes(provider_records_path),
        "canonical_black_box_record_count": black_box_records,
        "provider_record_count": len(provider_records),
        "unchanged_with_raw_payload_count": unchanged_with_raw,
        "raw_payloads_added_count": raw_payloads_added,
        "raw_payloads_still_missing_count": raw_payloads_still_missing,
        "duplicate_provider_key_count": len(duplicate_keys),
        "duplicate_stable_identity_key_count": len(stable_duplicate_keys),
        "missing_provider_key_count": len(missing_provider_keys),
        "missing_provider_key_examples": missing_provider_keys[:10],
        "strict_key_match_count": strict_key_match_count,
        "stable_identity_match_count": stable_identity_match_count,
        "claim_policy": "fail_closed: canonical full_eval is updated only when run-scoped provider_records cover every black-box record unless --allow-partial is explicit",
        "blockers": blockers,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize run-scoped raw provider payloads into canonical CodeDye full_eval.")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--full-eval-path", type=Path, default=ARTIFACTS / "full_eval_results.json")
    parser.add_argument("--provider-records-path", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    provider_records_path = args.provider_records_path or (ARTIFACTS / "live_runs" / args.run_id / "provider_records.jsonl")
    report = build_sync_report(
        run_id=args.run_id,
        full_eval_path=args.full_eval_path if args.full_eval_path.is_absolute() else ROOT / args.full_eval_path,
        provider_records_path=provider_records_path if provider_records_path.is_absolute() else ROOT / provider_records_path,
        output_path=args.output if args.output.is_absolute() else ROOT / args.output,
        apply=args.apply,
        allow_partial=args.allow_partial,
    )
    print(json.dumps({"status": report["status"], "applied": report["applied"], "blockers": report["blockers"]}, ensure_ascii=True))
    if args.apply and report["status"] != "pass" and not args.allow_partial:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
