from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from _bootstrap import ROOT
from codedye.benchmarks import evaluate_task, load_code_dyebench_tasks, task_metadata
from codedye.providers import generate_provider_trace, provider_summary, resolve_provider_config_path
from codedye.response_normalization import normalize_code_response
from codedye.statistics import build_contamination_decision
from run_attack_matrix_ci_scaffold import (
    PLACEHOLDER_TRANSFORM_KINDS,
    REQUIRED_ATTACK_IDS,
    SUPPORT_REQUIRED_ATTACK_IDS,
    _metadata_hash,
    _read_json,
    _sha256_text as _attack_sha256_text,
    _transform_code,
    _utility_preservation,
)
from run_attack_matrix_live_support import (
    MIN_ADMISSIBLE_RATE,
    MIN_ADMISSIBLE_RECORDS_PER_ATTACK,
    _candidate_samples,
    _decision_payload,
    _load_env_file,
    _record_claim_admissible,
    _record_hash,
    _select_sample,
    _sha256_json,
    _sha256_text,
    _task_hash,
    _utility_score,
    build_attack_prompt,
    summarize_records,
)


DEFAULT_ENV_FILE = Path("/root/.codemark_secrets/deepseek.env")
DEFAULT_ATTACK_MATRIX = ROOT / "configs" / "attack_matrix.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Top up a blocked CodeDye v3 canonical run using utility-only repairs.")
    parser.add_argument("--input", required=True, help="Blocked canonical candidate with retained utility failures.")
    parser.add_argument("--output", required=True, help="Additive repaired canonical candidate output.")
    parser.add_argument("--progress-output", default="")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--attack-matrix", default=str(DEFAULT_ATTACK_MATRIX))
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sample-count", type=int, default=2)
    parser.add_argument("--target-records", type=int, default=300)
    parser.add_argument("--require-live", action="store_true", default=True)
    return parser.parse_args()


def write_json(path: Path, payload: object) -> None:
    if path.exists():
        raise FileExistsError(f"refusing_to_overwrite:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_progress(path_text: str, payload: object) -> None:
    if not path_text:
        return
    path = Path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def applicable(task, attack: dict[str, object], tasks, *, enforce_subset: bool = True) -> bool:
    attack_id = str(attack.get("attack_id", ""))
    if not attack_id or attack_id in SUPPORT_REQUIRED_ATTACK_IDS:
        return False
    if attack_id == "cross_language_reexpression" and str(task.language).strip().lower() == "python":
        return False
    subsets = attack.get("applies_to_subsets", [])
    subset_set = {str(item) for item in subsets if str(item).strip()} if isinstance(subsets, list) else set()
    if enforce_subset and subset_set and task.subset not in subset_set:
        return False
    transformed, _, _ = _transform_code(task, attack_id, tasks=tasks)
    return _attack_sha256_text(transformed) != _attack_sha256_text(task.reference_code) or attack_id in {
        "comment_whitespace_normalize",
        "chronology_shuffle",
        "cross_language_reexpression",
    }


def materialize_attack_row(task, attack: dict[str, object], tasks) -> dict[str, object]:
    attack_id = str(attack["attack_id"])
    metadata = task_metadata(task)
    transformed_code, transform_kind, transform_metadata = _transform_code(task, attack_id, tasks=tasks)
    utility = _utility_preservation(
        task,
        transformed_code,
        attack_id,
        str(attack.get("utility_preservation_check", "")),
    )
    canary_preserved = all(
        str(metadata.get(key, "")).strip()
        for key in ("canary_split", "canary_pack_id", "hidden_test_family")
    )
    source_hash = _attack_sha256_text(task.reference_code)
    transformed_hash = _attack_sha256_text(transformed_code)
    return {
        "attack_id": attack_id,
        "attack_family": str(attack.get("family", "")),
        "task_id": task.task_id,
        "benchmark": task.benchmark,
        "subset": task.subset,
        "language": task.language,
        "target_family": metadata.get("target_family", ""),
        "chronology_split": metadata.get("chronology_split", ""),
        "canary_split": metadata.get("canary_split", ""),
        "hidden_test_family": metadata.get("hidden_test_family", ""),
        "source_code_sha256": source_hash,
        "transformed_code_sha256": transformed_hash,
        "code_changed": transformed_hash != source_hash,
        "transform_kind": transform_kind,
        "transform_metadata_hash": _metadata_hash(transform_metadata),
        "transform_metadata": transform_metadata,
        "placeholder_transform": transform_kind in PLACEHOLDER_TRANSFORM_KINDS,
        "support_only_not_claim_bearing": False,
        "claim_bearing_attack_evidence": True,
        "utility_preservation_check": str(attack.get("utility_preservation_check", "")),
        "canary_preservation_result": "metadata_preserved" if canary_preserved else "metadata_missing",
        "canary_preserved": canary_preserved,
        "null_control_summary": {
            "method": "task_metadata_matched_null_control",
            "subset": task.subset,
            "no_outcome_selection": True,
        },
        **utility,
    }


def build_live_record(
    *,
    task,
    row: dict[str, object],
    provider: str,
    config_path: Path,
    run_id: str,
    sample_count: int,
    topup_source: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    attack_id = str(row.get("attack_id", ""))
    prompt = build_attack_prompt(task, row)
    trace = generate_provider_trace(provider, prompt, 1 if attack_id == "query_budget_drop" else max(sample_count, 1), str(config_path))
    raw_samples = [sample.response_text for sample in trace.samples]
    normalized_samples = [normalize_code_response(sample, language=task.language) for sample in raw_samples]
    utilities = [evaluate_task(task, sample) for sample in normalized_samples]
    selected_index = _select_sample(utilities)
    selected_code = normalized_samples[selected_index] if normalized_samples else ""
    selected_utility = utilities[selected_index] if utilities else evaluate_task(task, selected_code)
    selected_utility_score = _utility_score(selected_utility)
    decision = build_contamination_decision(
        task,
        selected_code,
        load_code_dyebench_tasks(ROOT),
        query_count=trace.returned_sample_count,
        latency_ms=trace.latency_ms,
        extra_query_cost=max(trace.returned_sample_count - 1, 0),
    )
    samples = _candidate_samples(raw_samples, normalized_samples, utilities, selected_index)
    provenance_hash = _sha256_json(
        {
            "run_id": run_id,
            "attack_id": attack_id,
            "task_id": task.task_id,
            "prompt_hash": trace.prompt_hash,
            "transcript_hash": trace.transcript_hash,
            "request_ids": list(trace.request_ids),
            "attack_transform_metadata_hash": row.get("transform_metadata_hash", ""),
            "topup_source": topup_source,
        }
    )
    record_claim_bearing = selected_utility_score >= 1.0
    support_only_reason = "" if record_claim_bearing else "topup_selected_candidate_failed_utility_validation_retained_in_attempt_ledger"
    record = {
        "schema_version": "codedye_attack_matrix_live_canonical_record_v1",
        "project": "CodeDye",
        "record_kind": "attack_matrix_live_canonical",
        "claim_bearing": record_claim_bearing,
        "claim_bearing_attack_evidence": record_claim_bearing,
        "support_only_not_claim_bearing": not record_claim_bearing,
        "claim_role": (
            "claim_bearing_canonical_attack_matrix_live_evidence"
            if record_claim_bearing
            else "utility_inadmissible_failure_boundary_not_main_claim"
        ),
        "utility_admissible_for_attack_claim": selected_utility_score >= 1.0,
        "admissibility_reason": "selected_candidate_passed_utility_validation" if record_claim_bearing else support_only_reason,
        "row_claim_eligible_for_attack_claim": True,
        "row_claim_eligibility_reason": "eligible",
        "run_id": run_id,
        "attack_id": attack_id,
        "attack_condition": attack_id,
        "attack_family": row.get("attack_family", ""),
        "task_id": task.task_id,
        "benchmark": task.benchmark,
        "subset": task.subset,
        "language": task.language,
        "target_family": row.get("target_family", ""),
        "provider_name": trace.provider_name,
        "provider_mode_resolved": trace.provider_mode,
        "provider_or_backbone": trace.model_name or trace.provider_name,
        "model_name": trace.model_name,
        "prompt_hash": trace.prompt_hash,
        "attack_prompt_hash": _sha256_text(prompt),
        "raw_payload_hash": trace.transcript_hash,
        "raw_provider_transcript_hash": trace.transcript_hash,
        "structured_payload_hash": _sha256_json(samples),
        "task_hash": _task_hash(task),
        "provenance_hash": provenance_hash,
        "task_provenance_hash": _sha256_json({"task_hash": _task_hash(task), "provenance_hash": provenance_hash}),
        "provider_request_ids": list(trace.request_ids),
        "provider_trace_request_count": len(trace.request_ids),
        "candidate_sample_count": len(samples),
        "candidate_samples": samples,
        "selected_sample_index": selected_index,
        "selected_utility": asdict(selected_utility),
        "selected_utility_score": selected_utility_score,
        "attack_transform_kind": row.get("transform_kind", ""),
        "transform_kind": row.get("transform_kind", ""),
        "attack_transform_metadata_hash": row.get("transform_metadata_hash", ""),
        "transform_metadata_hash": row.get("transform_metadata_hash", ""),
        "transform_metadata": row.get("transform_metadata", {}),
        "attack_row_source_code_sha256": row.get("source_code_sha256", ""),
        "source_code_sha256": row.get("source_code_sha256", ""),
        "attack_row_transformed_code_sha256": row.get("transformed_code_sha256", ""),
        "transformed_code_sha256": row.get("transformed_code_sha256", ""),
        "attack_row_code_changed": row.get("code_changed", False),
        "code_changed": row.get("code_changed", False),
        "placeholder_transform": row.get("placeholder_transform", False),
        "utility_preserved": selected_utility_score >= 1.0,
        "canary_preserved": row.get("canary_preserved", False),
        "canary_preservation_result": row.get("canary_preservation_result", ""),
        "attack_prompt_policy": "task_semantics_only_no_expected_canary_or_label_leakage",
        "sample_selection_policy": "utility_only_topup_no_contamination_winner_selection",
        "topup_source": topup_source,
        "baseline_or_control_name": "codedye_attack_matrix_live_deepseek",
        "is_negative_control": False,
        "threshold_version": "codedye_null_audit_threshold_v1",
        **_decision_payload(decision),
    }
    record["record_hash"] = _record_hash(record)
    ledger = {
        "task_id": task.task_id,
        "attack_id": attack_id,
        "provider_mode_resolved": trace.provider_mode,
        "raw_provider_transcript_hash": trace.transcript_hash,
        "structured_payload_hash": _sha256_json(samples),
        "selected_utility_score": selected_utility_score,
        "utility_admissible": record_claim_bearing,
        "record_hash": record["record_hash"],
        "topup_source": topup_source,
    }
    return record, ledger


def main() -> None:
    args = parse_args()
    env_state = _load_env_file(Path(args.env_file))
    source_path = Path(args.input)
    output_path = Path(args.output)
    if output_path.exists():
        raise SystemExit(f"refusing_to_overwrite:{output_path}")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source_records = [row for row in source.get("records", []) if isinstance(row, dict)]
    claim_records = [row for row in source_records if _record_claim_admissible(row)]
    failures = [row for row in source_records if not _record_claim_admissible(row)]
    if len(claim_records) >= args.target_records:
        raise SystemExit("topup_not_needed_or_source_already_has_target_records")
    tasks = load_code_dyebench_tasks(ROOT)
    tasks_by_id = {task.task_id: task for task in tasks}
    attack_matrix = _read_json(Path(args.attack_matrix))
    declared_attack_ids = {
        str(item.get("attack_id", "")).strip()
        for item in attack_matrix.get("attacks", [])
        if isinstance(item, dict) and str(item.get("attack_id", "")).strip()
    }
    attacks = [
        dict(item)
        for item in attack_matrix.get("attacks", [])
        if isinstance(item, dict) and str(item.get("attack_id", "")).strip()
    ]
    config_path = resolve_provider_config_path(ROOT)
    provider_meta = provider_summary(args.provider, str(config_path))
    if args.require_live and str(provider_meta.get("resolved_mode", "")).strip().lower() != "live":
        raise SystemExit(f"provider_resolved_not_live:{provider_meta.get('resolved_mode')}")

    repaired: list[dict[str, object]] = []
    attempt_ledger: list[dict[str, object]] = []
    started_at = time.time()
    for failure_index, failed in enumerate(failures, start=1):
        if len(claim_records) + len(repaired) >= args.target_records:
            break
        task_id = str(failed.get("task_id", ""))
        task = tasks_by_id.get(task_id)
        if task is None:
            attempt_ledger.append({"task_id": task_id, "repair_status": "task_missing", "source_record_hash": failed.get("record_hash")})
            continue
        applicable_attacks = [attack for attack in attacks if applicable(task, attack, tasks)]
        if not applicable_attacks:
            applicable_attacks = [attack for attack in attacks if applicable(task, attack, tasks, enforce_subset=False)]
        original_attack = str(failed.get("attack_id", ""))
        applicable_attacks = sorted(
            applicable_attacks,
            key=lambda attack: (str(attack.get("attack_id")) != original_attack, str(attack.get("attack_id"))),
        )
        for attempt_index, attack in enumerate(applicable_attacks, start=1):
            attack_row = materialize_attack_row(task, attack, tasks)
            topup_source = {
                "source_artifact": str(source_path),
                "source_run_id": source.get("run_id"),
                "source_record_hash": failed.get("record_hash"),
                "source_attack_id": original_attack,
                "repair_failure_index": failure_index,
                "repair_attempt_index": attempt_index,
                "repair_selection_policy": "utility_only_no_contamination_score_selection",
            }
            record, ledger = build_live_record(
                task=task,
                row=attack_row,
                provider=args.provider,
                config_path=config_path,
                run_id=args.run_id,
                sample_count=args.sample_count,
                topup_source=topup_source,
            )
            if args.require_live and str(record.get("provider_mode_resolved", "")).lower() != "live":
                raise SystemExit(f"topup_record_resolved_not_live:{task_id}:{record.get('provider_mode_resolved')}")
            attempt_ledger.append(ledger)
            if record.get("utility_admissible_for_attack_claim") is True:
                repaired.append(record)
                break
        write_progress(
            args.progress_output,
            {
                "schema_version": "codedye_v3_canonical_topup_progress_v1",
                "status": "running",
                "source_claim_records": len(claim_records),
                "repaired_records": len(repaired),
                "target_records": args.target_records,
                "attempts": len(attempt_ledger),
            },
        )

    final_records = claim_records + repaired
    final_records = final_records[: args.target_records]
    declared_claim_attack_ids = declared_attack_ids - SUPPORT_REQUIRED_ATTACK_IDS
    summary = summarize_records(final_records, declared_claim_attack_ids)
    blockers = list(summary.get("blockers", []))
    if len(final_records) != args.target_records:
        blockers.append(f"topup_target_record_count_not_met:{len(final_records)}/{args.target_records}")
    if len({row.get("task_id") for row in final_records}) != args.target_records:
        blockers.append("topup_unique_task_count_not_target")
    if any(not _record_claim_admissible(row) for row in final_records):
        blockers.append("topup_output_contains_inadmissible_claim_row")
    payload_status = "passed" if not blockers else "blocked"
    payload = {
        "schema_version": "codedye_attack_matrix_live_canonical_v1" if not blockers else "codedye_attack_matrix_live_support_v1",
        "status": payload_status,
        "claim_bearing": not blockers,
        "claim_role": (
            "claim_bearing_canonical_live_attack_matrix_with_utility_only_topup"
            if not blockers
            else "support_only_topup_attempt_not_canonical_claim"
        ),
        "formal_claim_allowed": not blockers,
        "run_id": args.run_id,
        "source_blocked_artifact": str(source_path),
        "source_blocked_run_id": source.get("run_id"),
        "utility_topup_policy": {
            "enabled": True,
            "selection_signal": "utility_validation_only",
            "contamination_score_used_for_selection": False,
            "failed_attempts_retained": True,
            "failed_attempts_enter_main_denominator": False,
            "target_records": args.target_records,
            "source_claim_records": len(claim_records),
            "source_failure_records": len(failures),
            "repaired_claim_records": len(repaired),
        },
        "env": env_state,
        "provider": {
            **provider_meta,
            "base_url": f"{args.provider}_placeholder_endpoint",
            "api_key_serialized": False,
        },
        "elapsed_seconds": round(time.time() - started_at, 3),
        "summary": summary,
        "blockers": blockers,
        "utility_failure_attempt_ledger": attempt_ledger,
        "records": final_records,
        "record_count_by_attack": dict(sorted(Counter(str(row.get("attack_id", "")) for row in final_records).items())),
    }
    write_json(output_path, payload)
    write_progress(
        args.progress_output,
        {
            "schema_version": "codedye_v3_canonical_topup_progress_v1",
            "status": payload_status,
            "completed": len(final_records),
            "target_records": args.target_records,
            "output": str(output_path),
            "claim_bearing": not blockers,
            "blockers": blockers,
        },
    )
    print(json.dumps({"status": payload_status, "summary": summary, "blockers": blockers}, indent=2, ensure_ascii=True))
    if blockers:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
