from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT


SCHEMA = "codedye_canonical_evidence_sync_gate_v1"
DEFAULT_OUTPUT = ARTIFACTS / "canonical_evidence_sync_gate.json"
CURRENT_SAMPLE_SELECTION_STATUSES = {
    "pre_registered_utility_selection",
    "utility_preselection_no_contamination_winner_selection",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("records", [])
    return [dict(item) for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _task_items() -> list[dict[str, Any]]:
    payload = _read_json(ROOT / "benchmarks" / "code_dyebench_tasks.json")
    tasks = payload.get("tasks", [])
    return [dict(item) for item in tasks if isinstance(item, dict)] if isinstance(tasks, list) else []


def _source_identity(full_eval_path: Path, full_eval: dict[str, Any]) -> dict[str, str]:
    operator_state = full_eval.get("operator_state", {})
    operator_state = dict(operator_state) if isinstance(operator_state, dict) else {}
    return {
        "canonical_source_run_id": str(
            operator_state.get("canonical_source_run_id")
            or operator_state.get("run_id")
            or full_eval.get("run_id")
            or ""
        ).strip(),
        "source_full_eval_sha256": _sha256(full_eval_path),
        "canonical_source_artifact": str(operator_state.get("canonical_source_artifact", "")).strip(),
    }


def _candidate_payload_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    normalized_count = 0
    raw_provider_response_count = 0
    incomplete_raw_provider_response_count = 0
    for record in records:
        samples = record.get("candidate_samples", [])
        if not isinstance(samples, list):
            continue
        if samples:
            normalized_count += 1
        has_raw_provider_response = any(
            isinstance(sample, dict)
            and any(str(sample.get(field, "")).strip() for field in ("raw_response_text", "response_text", "provider_response_text"))
            for sample in samples
        )
        if has_raw_provider_response:
            raw_provider_response_count += 1
        else:
            incomplete_raw_provider_response_count += 1
    return {
        "normalized_candidate_payload_record_count": normalized_count,
        "raw_provider_response_payload_record_count": raw_provider_response_count,
        "raw_provider_response_payload_missing_record_count": incomplete_raw_provider_response_count,
    }


def _text_state() -> dict[str, Any]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="ignore") if (ROOT / "README.md").exists() else ""
    manifest = _read_json(ROOT / "benchmark_manifest.json")
    return {
        "readme_mentions_50_task_legacy_state": bool(re.search(r"\b50/50\b|\b50-task\b|\b50 tasks\b", readme, re.IGNORECASE)),
        "readme_mentions_300_task_state": bool(re.search(r"\b300\b", readme)),
        "benchmark_manifest_task_count": int(dict(manifest.get("private_benchmark", {})).get("task_count", 0) or 0) if manifest else 0,
        "benchmark_manifest_ready_task_count": int(dict(manifest.get("private_benchmark", {})).get("ready_task_count", 0) or 0) if manifest else 0,
        "benchmark_manifest_canonical_source_run_id": str(manifest.get("canonical_source_run_id", "")) if manifest else "",
    }


def build_gate() -> dict[str, Any]:
    full_eval_path = ARTIFACTS / "full_eval_results.json"
    full_eval = _read_json(full_eval_path)
    aggregate = _read_json(ARTIFACTS / "aggregate_results.json")
    snapshot = _read_json(ARTIFACTS / "project_snapshot.json")
    review_gate = _read_json(ARTIFACTS / "review_ready_gate.json")
    sample_audit = _read_json(ARTIFACTS / "sample_selection_rerun_audit.json")
    baseline_scope = _read_json(ARTIFACTS / "baseline_scope_decision.json")
    tasks = _task_items()
    records = _records(full_eval)
    local_records = [record for record in records if str(record.get("task_source", record.get("source", ""))) == "project_local"]
    source_identity = _source_identity(full_eval_path, full_eval)
    payload_counts = _candidate_payload_counts(records)
    text_state = _text_state()
    source_artifact = source_identity["canonical_source_artifact"]
    source_artifact_path = ROOT / source_artifact if source_artifact and not Path(source_artifact).is_absolute() else Path(source_artifact) if source_artifact else Path()

    blockers: list[str] = []
    if len(tasks) != 300:
        blockers.append(f"codedyebench_task_count_not_300:{len(tasks)}")
    if len(local_records) < len(tasks):
        blockers.append(f"canonical_local_records_below_task_count:{len(local_records)}/{len(tasks)}")
    for artifact_name, artifact in (
        ("aggregate", aggregate),
        ("project_snapshot", snapshot),
        ("review_ready_gate", review_gate),
        ("sample_selection_rerun_audit", sample_audit),
    ):
        if artifact and str(artifact.get("canonical_source_run_id", "")).strip() != source_identity["canonical_source_run_id"]:
            blockers.append(f"{artifact_name}_canonical_source_run_id_mismatch")
        if artifact and str(artifact.get("source_full_eval_sha256", artifact.get("source_artifact_hashes", {}).get("full_eval_results", ""))).strip() not in {
            "",
            source_identity["source_full_eval_sha256"],
        }:
            blockers.append(f"{artifact_name}_source_full_eval_sha256_mismatch")
    if sample_audit:
        if str(sample_audit.get("current_canonical_status", "")).strip() not in CURRENT_SAMPLE_SELECTION_STATUSES:
            blockers.append("sample_selection_status_not_current")
        if bool(sample_audit.get("rerun_required", True)):
            blockers.append("sample_selection_rerun_required")
    if not source_artifact or not source_artifact_path.exists():
        blockers.append("canonical_source_artifact_missing")
    if text_state["readme_mentions_50_task_legacy_state"]:
        blockers.append("readme_mentions_legacy_50_task_state")
    if text_state["benchmark_manifest_task_count"] != 300 or text_state["benchmark_manifest_ready_task_count"] != 300:
        blockers.append("benchmark_manifest_not_300_task_current")
    if payload_counts["normalized_candidate_payload_record_count"] > 0 and payload_counts["raw_provider_response_payload_record_count"] == 0:
        blockers.append("raw_provider_response_payloads_missing_normalized_payloads_only")
    elif payload_counts["raw_provider_response_payload_record_count"] < payload_counts["normalized_candidate_payload_record_count"]:
        blockers.append("raw_provider_response_payloads_incomplete")
    raw_response_complete = (
        payload_counts["normalized_candidate_payload_record_count"] > 0
        and payload_counts["raw_provider_response_payload_record_count"] == payload_counts["normalized_candidate_payload_record_count"]
    )
    return {
        "schema_version": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "CodeDye",
        "status": "pass" if not blockers else "blocked",
        "sync_gate_pass": not blockers,
        "source_identity": source_identity,
        "task_count": len(tasks),
        "canonical_local_record_count": len(local_records),
        "total_record_count": len(records),
        "sample_selection_status": str(sample_audit.get("current_canonical_status", "")),
        "sample_selection_rerun_required": bool(sample_audit.get("rerun_required", True)),
        "baseline_scope_decision": str(baseline_scope.get("decision", "")),
        "candidate_payload_boundary": {
            **payload_counts,
            "claim_boundary": (
                "normalized_candidate_payloads_and_raw_provider_response_text_are_preserved"
                if raw_response_complete
                else "normalized_candidate_payloads_are_preserved; raw provider response text is incomplete"
            ),
            "raw_provider_response_required_for_main_claim": True,
            "raw_provider_response_complete_for_current_records": raw_response_complete,
        },
        "text_state": text_state,
        "hidden_test_boundary": {
            "hidden_tests_are_in_public_task_file": any(bool(item.get("hidden_tests")) for item in tasks),
            "claim_boundary": "public held-out/diagnostic tests, not a private hidden split, unless exported separately",
        },
        "blockers": sorted(dict.fromkeys(blockers)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CodeDye canonical evidence sync gate.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = build_gate()
    rendered = json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    if args.check:
        if not args.output.exists():
            raise SystemExit(f"missing canonical evidence sync gate: {args.output}")
        if args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"stale canonical evidence sync gate: {args.output}")
        if not payload["sync_gate_pass"]:
            raise SystemExit(json.dumps({"status": payload["status"], "blockers": payload["blockers"]}, ensure_ascii=True))
        print(f"canonical evidence sync gate check passed: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps({"status": payload["status"], "blocker_count": len(payload["blockers"])}, ensure_ascii=True))


if __name__ == "__main__":
    main()
