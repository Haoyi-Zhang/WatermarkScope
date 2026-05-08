from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT


SCHEMA = "semcodebook_method_schema_gate_v1"
DEFAULT_FULL_EVAL = ARTIFACTS / "full_eval_results.json"
DEFAULT_OUTPUT = ARTIFACTS / "method_schema_gate.json"
CLAIM_BEARING_STATUS = "claim_bearing"
STALE_STATUS = "stale_not_claim_bearing"
REQUIRED_RECORD_FIELDS = (
    "decision_status",
    "abstain_reason",
    "positive_support_score",
    "positive_support_family_count",
    "positive_support_level_count",
    "carrier_signal_coverage",
)
NEGATIVE_CONTROL_ALLOWED_DECISIONS = {"reject", "rejected", "abstain"}


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True).encode("utf-8") + b"\n"


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _load_json(path: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"missing_full_eval:{_display_path(path)}"
    except json.JSONDecodeError as exc:
        return None, f"malformed_full_eval_json:{exc.lineno}:{exc.colno}"
    except OSError as exc:
        return None, f"unreadable_full_eval:{exc}"


def _records_from_payload(payload: Any) -> tuple[list[Any], str | None]:
    if isinstance(payload, dict):
        records = payload.get("records")
    else:
        records = payload
    if not isinstance(records, list):
        return [], "full_eval_records_not_list"
    return records, None


def _field_presence(records: list[dict[str, Any]], fields: tuple[str, ...] = REQUIRED_RECORD_FIELDS) -> dict[str, Any]:
    per_field = {
        field: {
            "present_count": sum(1 for record in records if field in record),
            "missing_count": sum(1 for record in records if field not in record),
        }
        for field in fields
    }
    return {
        "required_fields": list(fields),
        "missing_required_fields": [field for field, counts in per_field.items() if counts["missing_count"]],
        "per_field": per_field,
    }


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _negative_control_contract(records: list[dict[str, Any]]) -> dict[str, Any]:
    blockers: list[str] = []
    examples: list[dict[str, Any]] = []
    checked = 0
    for index, record in enumerate(records):
        if not bool(record.get("negative_control") or record.get("is_negative_control")):
            continue
        checked += 1
        task_id = str(record.get("task_id", f"record_{index}"))
        decision_status = str(record.get("decision_status") or "").strip().lower()
        reasons: list[str] = []
        if decision_status not in NEGATIVE_CONTROL_ALLOWED_DECISIONS:
            reasons.append(f"negative_control_decision_not_fail_closed:{decision_status or '<missing>'}")
        if record.get("wm_id_hat") is not None:
            reasons.append("negative_control_exposes_wm_id_hat")
        if record.get("decoded_wm_id_candidate") is not None:
            reasons.append("negative_control_exposes_decoded_candidate")
        if _as_float(record.get("positive_support_score")) > 0.0:
            reasons.append("negative_control_positive_support_score_nonzero")
        if _as_int(record.get("positive_support_family_count")) > 0:
            reasons.append("negative_control_positive_support_family_count_nonzero")
        if _as_int(record.get("positive_support_level_count")) > 0:
            reasons.append("negative_control_positive_support_level_count_nonzero")
        if not str(record.get("abstain_reason") or "").strip():
            reasons.append("negative_control_abstain_reason_missing")
        if bool(record.get("detected") or record.get("is_watermarked") or record.get("watermarked")):
            reasons.append("negative_control_positive_detection_flag")
        if reasons:
            blockers.extend(f"{task_id}:{reason}" for reason in reasons)
            if len(examples) < 20:
                examples.append(
                    {
                        "record_index": index,
                        "task_id": task_id,
                        "decision_status": record.get("decision_status"),
                        "wm_id_hat": record.get("wm_id_hat"),
                        "decoded_wm_id_candidate": record.get("decoded_wm_id_candidate"),
                        "positive_support_score": record.get("positive_support_score"),
                        "positive_support_family_count": record.get("positive_support_family_count"),
                        "positive_support_level_count": record.get("positive_support_level_count"),
                        "reasons": reasons,
                    }
                )
    return {
        "checked_negative_control_record_count": checked,
        "status": "pass" if not blockers else "blocked",
        "blockers": blockers[:100],
        "blocker_count": len(blockers),
        "examples": examples,
        "policy": (
            "Declared negative controls must fail closed before owner/payload exposure: no wm_id_hat, "
            "no decoded candidate, no positive-support counters, and reject/abstain with a reason."
        ),
    }


def _candidate_full_eval_paths(full_eval_path: Path) -> list[Path]:
    generated = full_eval_path.parent
    candidates: list[Path] = []
    if generated.exists():
        candidates.extend(generated.glob("*full_eval_results*.json"))
        candidates.extend((generated / "remote_sync").glob("*full_eval_results*.json"))
    candidates.append(full_eval_path)
    unique: dict[str, Path] = {}
    for path in candidates:
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        unique[key] = path
    return sorted(unique.values(), key=lambda item: _display_path(item))


def _schema_audit_for_path(path: Path) -> dict[str, Any]:
    payload, load_error = _load_json(path)
    if load_error is not None:
        return {
            "path": _display_path(path),
            "exists": path.exists(),
            "record_count": 0,
            "object_record_count": 0,
            "schema_current": False,
            "missing_required_fields": [],
            "blockers": [load_error],
        }
    records, records_error = _records_from_payload(payload)
    if records_error is not None:
        return {
            "path": _display_path(path),
            "exists": path.exists(),
            "record_count": 0,
            "object_record_count": 0,
            "schema_current": False,
            "missing_required_fields": [],
            "blockers": [records_error],
        }
    dict_records = [record for record in records if isinstance(record, dict)]
    non_dict_record_count = len(records) - len(dict_records)
    presence = _field_presence(dict_records)
    negative_contract = _negative_control_contract(dict_records)
    blockers = []
    if non_dict_record_count:
        blockers.append(f"non_object_record_count:{non_dict_record_count}")
    if not records:
        blockers.append("full_eval_records_empty")
    blockers.extend(f"missing_record_field:{field}" for field in presence["missing_required_fields"])
    blockers.extend(f"negative_control_contract:{item}" for item in negative_contract["blockers"][:20])
    return {
        "path": _display_path(path),
        "exists": path.exists(),
        "record_count": len(records),
        "object_record_count": len(dict_records),
        "schema_current": not blockers,
        "missing_required_fields": presence["missing_required_fields"],
        "negative_control_contract": negative_contract,
        "blockers": blockers,
    }


def build_manifest(*, full_eval_path: Path) -> dict[str, Any]:
    payload, load_error = _load_json(full_eval_path)
    blockers: list[str] = []
    records: list[Any] = []
    meta: dict[str, Any] = {}

    if load_error is not None:
        blockers.append(load_error)
    else:
        records, records_error = _records_from_payload(payload)
        if records_error is not None:
            blockers.append(records_error)
        if isinstance(payload, dict) and isinstance(payload.get("meta"), dict):
            meta = payload["meta"]

    dict_records = [record for record in records if isinstance(record, dict)]
    non_dict_record_count = len(records) - len(dict_records)
    if non_dict_record_count:
        blockers.append(f"non_object_record_count:{non_dict_record_count}")
    if not records and load_error is None:
        blockers.append("full_eval_records_empty")

    presence = _field_presence(dict_records, REQUIRED_RECORD_FIELDS)
    negative_contract = _negative_control_contract(dict_records)
    blockers.extend(f"missing_record_field:{field}" for field in presence["missing_required_fields"])
    blockers.extend(f"negative_control_contract:{item}" for item in negative_contract["blockers"][:50])
    candidate_audits = _candidate_full_eval_paths(full_eval_path)
    candidate_schema_audits = [_schema_audit_for_path(path) for path in candidate_audits]
    schema_current_candidates = [
        item for item in candidate_schema_audits if item["schema_current"] and item["record_count"] > 0
    ]
    best_schema_candidate = max(
        schema_current_candidates,
        key=lambda item: (int(item["record_count"]), item["path"]),
        default={},
    )
    canonical_path = _display_path(full_eval_path)
    if blockers and best_schema_candidate and best_schema_candidate.get("path") != canonical_path:
        blockers.append(f"schema_current_support_artifact_not_canonical:{best_schema_candidate['path']}")

    schema_current = not blockers
    status = CLAIM_BEARING_STATUS if schema_current else STALE_STATUS
    return {
        "schema": SCHEMA,
        "status": status,
        "claim_bearing": schema_current,
        "claim_bearing_status": status,
        "detector_schema_status": "current_detector_schema" if schema_current else "stale_detector_schema",
        "source_artifacts": {
            "full_eval": _display_path(full_eval_path),
        },
        "record_count": len(records),
        "object_record_count": len(dict_records),
        "non_object_record_count": non_dict_record_count,
        "required_record_schema": presence,
        "negative_control_fail_closed_contract": negative_contract,
        "observed_record_fields_sample": sorted(dict_records[0].keys()) if dict_records else [],
        "canonical_full_eval_meta": {
            "mode": meta.get("mode"),
            "progress_status": (meta.get("progress") or {}).get("status") if isinstance(meta.get("progress"), dict) else None,
            "full_eval_review_status": (meta.get("contract") or {}).get("full_eval_review_status")
            if isinstance(meta.get("contract"), dict)
            else None,
        },
        "candidate_schema_audit": {
            "canonical_full_eval": canonical_path,
            "schema_current_support_artifact_available": bool(best_schema_candidate),
            "best_schema_current_support_artifact": best_schema_candidate,
            "audited_candidate_count": len(candidate_schema_audits),
            "audited_candidates": candidate_schema_audits,
            "promotion_policy": (
                "Schema-current sidecars are support-only until a fresh canonical full_eval_results.json "
                "with the same scope, provenance hash, and fail-closed detector fields replaces the stale artifact."
            ),
        },
        "blockers": blockers,
        "policy": {
            "latest_detector_schema_required": True,
            "missing_latest_detector_fields_fail_closed": True,
            "stale_artifact_policy": STALE_STATUS,
        },
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the SemCodebook method schema gate manifest.")
    parser.add_argument("--full-eval", type=Path, default=DEFAULT_FULL_EVAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Fail if the manifest is missing, stale, or not claim-bearing.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    manifest = build_manifest(full_eval_path=args.full_eval)
    rendered = _json_bytes(manifest)

    if args.check:
        if not args.output.exists():
            print(f"{args.output} is missing; run build_method_schema_gate.py", file=sys.stderr)
            return 1
        if args.output.read_bytes() != rendered:
            print(f"{args.output} is stale; rerun build_method_schema_gate.py", file=sys.stderr)
            return 1
        if not manifest["claim_bearing"]:
            print(
                json.dumps(
                    {
                        "status": manifest["status"],
                        "path": str(args.output),
                        "blockers": manifest["blockers"],
                    },
                    ensure_ascii=True,
                ),
                file=sys.stderr,
            )
            return 1
        print(json.dumps({"status": "ok", "path": str(args.output), "record_count": manifest["record_count"]}))
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rendered)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "path": str(args.output),
                "record_count": manifest["record_count"],
                "blocker_count": len(manifest["blockers"]),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
