from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from _bootstrap import ROOT


ARTIFACTS = ROOT / "artifacts" / "generated"
OUTPUT_PATH = ARTIFACTS / "sample_selection_rerun_audit.json"
CURRENT_SAMPLE_SELECTION_STATUSES = {
    "pre_registered_utility_selection",
    "utility_preselection_no_contamination_winner_selection",
}
SAMPLE_SELECTION_CONTRACT_VERSIONS = {
    "codedye_sample_selection_contract_v1",
}
RAW_TRANSCRIPT_FIELDS = (
    "raw_response_text",
    "provider_response_text",
    "response_text",
    "raw_text",
    "raw_response",
    "raw_responses",
    "responses",
    "generated_samples",
    "raw_candidates",
    "samples",
)
STRUCTURED_SAMPLE_FIELDS = (
    "candidate_samples",
)
_SELECTED_RE = re.compile(r"^selected_sample_index:(\d+)$")
_UTILITY_SELECTED_RE = re.compile(r"^utility_selected_sample_index:(\d+)$")
_REQUEST_IDS_RE = re.compile(r"^provider_trace_request_ids:(\d+)$")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit CodeDye sample-selection rematerialization readiness.")
    parser.add_argument(
        "--run-id",
        default="",
        help="Optional run id to audit under artifacts/generated/live_runs/<run_id>/ without touching the canonical audit path.",
    )
    parser.add_argument(
        "--full-eval-path",
        default="",
        help="Optional full-eval artifact path. Relative paths are resolved from the project root.",
    )
    parser.add_argument(
        "--provider-records-path",
        default="",
        help="Optional provider_records.jsonl path. Relative paths are resolved from the project root.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path for the audit payload. Relative paths are resolved from the project root.",
    )
    return parser.parse_args()


def _resolve_cli_path(value: str) -> Path | None:
    text = value.strip()
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else ROOT / path


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _resolve_audit_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, str]:
    run_id = str(args.run_id).strip()
    full_eval_override = _resolve_cli_path(str(args.full_eval_path))
    provider_records_override = _resolve_cli_path(str(args.provider_records_path))
    output_override = _resolve_cli_path(str(args.output))
    if run_id:
        run_root = ARTIFACTS / "live_runs" / run_id
        full_eval_path = full_eval_override or (run_root / "full_eval_results.json")
        provider_records_path = provider_records_override or (run_root / "provider_records.jsonl")
        output_path = output_override or (run_root / "sample_selection_rerun_audit.json")
        return full_eval_path, provider_records_path, output_path, "run_scoped_artifact"
    return (
        full_eval_override or (ARTIFACTS / "full_eval_results.json"),
        provider_records_override,
        output_override or OUTPUT_PATH,
        "canonical_artifact",
    )


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _extract_indices(notes: list[object]) -> tuple[int | None, int | None, int | None]:
    selected: int | None = None
    utility_selected: int | None = None
    request_count: int | None = None
    for note in notes:
        text = str(note)
        match = _SELECTED_RE.match(text)
        if match:
            selected = int(match.group(1))
            continue
        match = _UTILITY_SELECTED_RE.match(text)
        if match:
            utility_selected = int(match.group(1))
            continue
        match = _REQUEST_IDS_RE.match(text)
        if match:
            request_count = int(match.group(1))
    return selected, utility_selected, request_count


def _safe_optional_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_selection_contract(record: dict[str, object]) -> tuple[int | None, int | None, int | None, bool]:
    selected = _safe_optional_int(record.get("selected_sample_index"))
    utility_selected = _safe_optional_int(record.get("utility_selected_sample_index"))
    request_count = _safe_optional_int(record.get("provider_trace_request_count"))
    structured = selected is not None and utility_selected is not None
    if request_count is None:
        request_ids = record.get("provider_trace_request_ids")
        if isinstance(request_ids, list):
            request_count = len(request_ids)
    if structured and request_count is not None:
        return selected, utility_selected, request_count, True
    notes = record.get("notes", [])
    notes = notes if isinstance(notes, list) else []
    note_selected, note_utility_selected, note_request_count = _extract_indices(notes)
    return (
        selected if selected is not None else note_selected,
        utility_selected if utility_selected is not None else note_utility_selected,
        request_count if request_count is not None else note_request_count,
        structured,
    )


def _sample_has_raw_transcript(sample: dict[str, object]) -> tuple[bool, list[str]]:
    present: list[str] = []
    for field in RAW_TRANSCRIPT_FIELDS:
        value = sample.get(field)
        if isinstance(value, str) and value.strip():
            present.append(f"candidate_samples.{field}")
        elif isinstance(value, list) and value:
            present.append(f"candidate_samples.{field}")
        elif isinstance(value, dict) and value:
            present.append(f"candidate_samples.{field}")
    return bool(present), present


def _candidate_payload_present(record: dict[str, object]) -> tuple[bool, list[str], bool]:
    raw_present: list[str] = []
    structured_complete = False
    for field in RAW_TRANSCRIPT_FIELDS:
        if field not in record:
            continue
        value = record[field]
        if isinstance(value, list) and value:
            raw_present.append(field)
        elif isinstance(value, dict) and value:
            raw_present.append(field)
        elif isinstance(value, str) and value.strip():
            raw_present.append(field)
    for field in STRUCTURED_SAMPLE_FIELDS:
        value = record.get(field)
        if not isinstance(value, list) or not value:
            continue
        if field == "candidate_samples":
            structured_complete = all(
                isinstance(item, dict)
                and "sample_index" in item
                and str(item.get("normalized_code", "")).strip()
                and str(item.get("normalized_code_sha256", "")).strip()
                for item in value
            )
            sample_raw_fields: list[str] = []
            raw_sample_count = 0
            for item in value:
                if not isinstance(item, dict):
                    continue
                sample_has_raw, fields = _sample_has_raw_transcript(item)
                if sample_has_raw:
                    raw_sample_count += 1
                    sample_raw_fields.extend(fields)
            if raw_sample_count == len(value):
                raw_present.extend(sorted(set(sample_raw_fields)))
    if bool(record.get("candidate_payload_capture_complete")) and isinstance(record.get("candidate_samples"), list):
        structured_complete = structured_complete or bool(record.get("candidate_samples"))
    return bool(raw_present), sorted(set(raw_present)), structured_complete


def _provider_record_key(record: dict[str, object]) -> str:
    existing = str(record.get("run_checkpoint_key", "")).strip()
    if existing:
        return existing
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


def _analyze_provider_records(
    records: list[dict[str, object]],
    *,
    current_status: str,
) -> dict[str, object]:
    record_count = 0
    records_with_selection_notes = 0
    records_with_selection_contract = 0
    records_with_structured_selection_contract = 0
    records_with_request_id_notes = 0
    records_with_request_id_contract = 0
    records_with_raw_candidate_payloads = 0
    records_with_structured_candidate_payloads = 0
    records_with_contract_version = 0
    raw_candidate_payload_fields: set[str] = set()
    mismatches: list[dict[str, object]] = []

    for record in records:
        record_count += 1
        contract_version = str(record.get("sample_selection_contract_version", "")).strip()
        if contract_version in SAMPLE_SELECTION_CONTRACT_VERSIONS:
            records_with_contract_version += 1
        notes = record.get("notes", [])
        notes = notes if isinstance(notes, list) else []
        note_selected, note_utility_selected, note_request_count = _extract_indices(notes)
        if note_selected is not None and note_utility_selected is not None:
            records_with_selection_notes += 1
        selected, utility_selected, request_count, structured_selection = _extract_selection_contract(record)
        if selected is not None and utility_selected is not None:
            records_with_selection_contract += 1
            if selected != utility_selected:
                mismatches.append(
                    {
                        "task_id": str(record.get("task_id", "")),
                        "benchmark": str(record.get("benchmark", "")),
                        "attack": str(record.get("attack", "")),
                        "provider_name": str(record.get("provider_name", "")),
                        "provider_mode_resolved": str(record.get("provider_mode_resolved", "")),
                        "selected_sample_index": selected,
                        "utility_selected_sample_index": utility_selected,
                    }
                )
        if structured_selection:
            records_with_structured_selection_contract += 1
        if note_request_count is not None:
            records_with_request_id_notes += 1
        if request_count is not None:
            records_with_request_id_contract += 1
        has_payload, fields, structured_payload = _candidate_payload_present(record)
        if has_payload:
            records_with_raw_candidate_payloads += 1
            raw_candidate_payload_fields.update(fields)
        if structured_payload:
            records_with_structured_candidate_payloads += 1

    rerun_free_rematerialization_possible = False
    rerun_required = False
    rerun_required_reason = ""
    future_run_contract_ready = False
    current_status_valid = current_status in CURRENT_SAMPLE_SELECTION_STATUSES
    if current_status_valid:
        if record_count <= 0:
            rerun_required = True
            rerun_required_reason = "pre-registered utility-selection status is declared but no provider records are materialized"
        elif records_with_selection_contract != record_count:
            rerun_required = True
            rerun_required_reason = "pre-registered utility-selection run does not preserve structured selected and utility-selected indices for every provider record"
        elif records_with_request_id_contract != record_count:
            rerun_required = True
            rerun_required_reason = "pre-registered utility-selection run does not preserve provider trace request counts for every provider record"
        elif records_with_structured_candidate_payloads != record_count:
            rerun_required = True
            rerun_required_reason = "pre-registered utility-selection run does not preserve structured candidate sample payloads for every provider record"
        elif records_with_raw_candidate_payloads != record_count:
            rerun_required = True
            rerun_required_reason = "pre-registered utility-selection run does not preserve raw provider response payloads for every provider record"
        elif records_with_contract_version != record_count:
            rerun_required = True
            rerun_required_reason = "pre-registered utility-selection run does not preserve a machine-verifiable sample-selection contract version for every provider record"
        else:
            future_run_contract_ready = True
            rerun_free_rematerialization_possible = True
    elif record_count <= 0:
        rerun_required = True
        rerun_required_reason = "provider_records.jsonl is present but contains no rematerializable task records"
    elif records_with_selection_notes != record_count:
        rerun_required = True
        rerun_required_reason = "provider_records.jsonl does not preserve both selected and utility-selected sample notes for every record"
    elif not mismatches:
        rerun_free_rematerialization_possible = True
    elif records_with_raw_candidate_payloads < len(mismatches):
        rerun_required = True
        rerun_required_reason = (
            "run-scoped provider records preserve only selection notes and request-id counts for utility-selection mismatches; "
            "they do not retain raw candidate sample payloads needed for truthful rematerialization"
        )
    else:
        rerun_required = True
        rerun_required_reason = "canonical sample-selection mismatch requires a fresh utility-first rerun under the current contract"

    return {
        "provider_record_count": record_count,
        "records_with_selection_notes": records_with_selection_notes,
        "records_with_selection_contract": records_with_selection_contract,
        "records_with_structured_selection_contract": records_with_structured_selection_contract,
        "records_with_request_id_notes": records_with_request_id_notes,
        "records_with_request_id_contract": records_with_request_id_contract,
        "records_with_raw_candidate_payloads": records_with_raw_candidate_payloads,
        "records_with_structured_candidate_payloads": records_with_structured_candidate_payloads,
        "records_with_contract_version": records_with_contract_version,
        "raw_candidate_payload_fields": sorted(raw_candidate_payload_fields),
        "utility_selection_mismatch_records": mismatches,
        "rerun_free_rematerialization_possible": rerun_free_rematerialization_possible,
        "rerun_required": rerun_required,
        "rerun_required_reason": rerun_required_reason,
        "future_run_contract_ready": future_run_contract_ready,
    }


def build_audit(
    *,
    full_eval_path: Path,
    provider_records_path: Path | None = None,
    output_path: Path = OUTPUT_PATH,
    requested_run_id: str = "",
    audit_scope: str = "canonical_artifact",
) -> dict[str, object]:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    full_eval = _read_json(full_eval_path)
    source_full_eval_sha256 = hashlib.sha256(full_eval_path.read_bytes()).hexdigest() if full_eval_path.exists() else ""
    operator_state = full_eval.get("operator_state", {})
    operator_state = dict(operator_state) if isinstance(operator_state, dict) else {}
    canonical_source_run_id = str(
        operator_state.get("canonical_source_run_id")
        or operator_state.get("run_id")
        or full_eval.get("run_id")
        or ""
    ).strip()
    canonical_provider_keys = {
        _provider_record_key(record)
        for record in full_eval.get("records", [])
        if isinstance(record, dict) and str(record.get("evaluation_surface", "")).strip() == "black_box_api"
    }
    if provider_records_path is None:
        provider_records_path = (
            ARTIFACTS / "live_runs" / canonical_source_run_id / "provider_records.jsonl"
            if canonical_source_run_id
            else ARTIFACTS / "__missing_provider_records__.jsonl"
        )
    current_status = str(full_eval.get("sample_selection_adjustment_status", "legacy_or_unknown"))
    future_policy = str(full_eval.get("future_sample_selection_policy", "pre_registered_utility_before_contamination_scoring"))

    analysis = {
        "provider_record_count": 0,
        "records_with_selection_notes": 0,
        "records_with_selection_contract": 0,
        "records_with_structured_selection_contract": 0,
        "records_with_request_id_notes": 0,
        "records_with_request_id_contract": 0,
        "records_with_raw_candidate_payloads": 0,
        "records_with_structured_candidate_payloads": 0,
        "records_with_contract_version": 0,
        "raw_candidate_payload_fields": [],
        "utility_selection_mismatch_records": [],
        "rerun_free_rematerialization_possible": False,
        "rerun_required": False,
        "rerun_required_reason": "",
        "future_run_contract_ready": False,
    }
    provider_record_source = "run_scoped_provider_records_jsonl" if provider_records_path.exists() else ""

    if provider_records_path.exists():
        provider_records: list[dict[str, object]] = []
        unmatched_provider_records = 0
        duplicate_provider_record_keys: set[str] = set()
        observed_provider_record_keys: set[str] = set()
        for line in provider_records_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                continue
            key = _provider_record_key(record)
            if key in observed_provider_record_keys:
                duplicate_provider_record_keys.add(key)
            observed_provider_record_keys.add(key)
            if key in canonical_provider_keys:
                provider_records.append(record)
            else:
                unmatched_provider_records += 1
        analysis = _analyze_provider_records(provider_records, current_status=current_status)
        analysis["matched_provider_record_count"] = len(provider_records)
        analysis["expected_canonical_provider_record_count"] = len(canonical_provider_keys)
        analysis["unmatched_provider_record_count"] = unmatched_provider_records
        analysis["duplicate_provider_record_key_count"] = len(duplicate_provider_record_keys)
        if canonical_provider_keys and len(provider_records) != len(canonical_provider_keys):
            analysis["rerun_free_rematerialization_possible"] = False
            analysis["rerun_required"] = True
            analysis["rerun_required_reason"] = (
                "provider_records.jsonl does not match the canonical black-box record set for the current full_eval_results.json"
            )
        if duplicate_provider_record_keys and not analysis["rerun_required"]:
            analysis["rerun_free_rematerialization_possible"] = False
            analysis["rerun_required"] = True
            analysis["rerun_required_reason"] = "provider_records.jsonl contains duplicate canonical record keys"
    else:
        embedded_provider_records = [
            record
            for record in full_eval.get("records", [])
            if isinstance(record, dict)
            and str(record.get("evaluation_surface", "")).strip() == "black_box_api"
            and _provider_record_key(record) in canonical_provider_keys
        ]
        if embedded_provider_records:
            analysis = _analyze_provider_records(embedded_provider_records, current_status=current_status)
            analysis["matched_provider_record_count"] = len(embedded_provider_records)
            analysis["expected_canonical_provider_record_count"] = len(canonical_provider_keys)
            analysis["unmatched_provider_record_count"] = 0
            analysis["duplicate_provider_record_key_count"] = 0
            provider_record_source = "embedded_full_eval_candidate_payloads"

    rerun_free_rematerialization_possible = bool(analysis["rerun_free_rematerialization_possible"])
    rerun_required = bool(analysis["rerun_required"])
    rerun_required_reason = str(analysis["rerun_required_reason"])
    provider_records_materialized = provider_records_path.exists() or provider_record_source == "embedded_full_eval_candidate_payloads"
    if current_status in CURRENT_SAMPLE_SELECTION_STATUSES and not provider_records_materialized:
        rerun_required = True
        rerun_free_rematerialization_possible = False
        rerun_required_reason = "pre-registered utility-selection status is declared but no run-scoped provider_records.jsonl artifact exists"
    elif not provider_records_materialized:
        rerun_required = True
        rerun_required_reason = "canonical live run does not retain a run-scoped provider_records.jsonl artifact"

    payload = {
        "schema_version": "codedye_sample_selection_rerun_audit_v2",
        "audit_scope": audit_scope,
        "requested_run_id": requested_run_id,
        "audited_run_id": requested_run_id or canonical_source_run_id,
        "source_full_eval_path": _display_path(full_eval_path) if full_eval_path.exists() else "",
        "source_full_eval_sha256": source_full_eval_sha256,
        "canonical_source_run_id": canonical_source_run_id,
        "provider_records_path": _display_path(provider_records_path) if provider_records_path.exists() else "",
        "provider_records_present": provider_records_path.exists(),
        "provider_record_source": provider_record_source,
        "provider_records_sha256": hashlib.sha256(provider_records_path.read_bytes()).hexdigest() if provider_records_path.exists() else "",
        "provider_record_count": analysis["provider_record_count"],
        "expected_reference_provider_record_count": int(analysis.get("expected_canonical_provider_record_count", 0) or 0),
        "expected_canonical_provider_record_count": int(analysis.get("expected_canonical_provider_record_count", 0) or 0),
        "matched_provider_record_count": int(analysis.get("matched_provider_record_count", 0) or 0),
        "unmatched_provider_record_count": int(analysis.get("unmatched_provider_record_count", 0) or 0),
        "duplicate_provider_record_key_count": int(analysis.get("duplicate_provider_record_key_count", 0) or 0),
        "current_canonical_status": current_status,
        "future_run_policy": future_policy,
        "records_with_selection_notes": analysis["records_with_selection_notes"],
        "records_with_selection_contract": analysis["records_with_selection_contract"],
        "records_with_structured_selection_contract": analysis["records_with_structured_selection_contract"],
        "records_with_request_id_notes": analysis["records_with_request_id_notes"],
        "records_with_request_id_contract": analysis["records_with_request_id_contract"],
        "utility_selection_mismatch_record_count": len(analysis["utility_selection_mismatch_records"]),
        "utility_selection_mismatch_records": analysis["utility_selection_mismatch_records"],
        "raw_candidate_payload_record_count": analysis["records_with_raw_candidate_payloads"],
        "structured_candidate_payload_record_count": analysis["records_with_structured_candidate_payloads"],
        "raw_candidate_payload_fields": analysis["raw_candidate_payload_fields"],
        "contract_version_record_count": analysis["records_with_contract_version"],
        "future_run_contract_ready": analysis["future_run_contract_ready"],
        "rerun_free_rematerialization_possible": rerun_free_rematerialization_possible,
        "rerun_required": rerun_required,
        "closure_blocker": "" if rerun_free_rematerialization_possible else "legacy_sample_selection_requires_rerun",
        "rerun_required_reason": rerun_required_reason,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return payload


def main() -> None:
    args = _parse_args()
    full_eval_path, provider_records_path, output_path, audit_scope = _resolve_audit_paths(args)
    payload = build_audit(
        full_eval_path=full_eval_path,
        provider_records_path=provider_records_path,
        output_path=output_path,
        requested_run_id=str(args.run_id).strip(),
        audit_scope=audit_scope,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
