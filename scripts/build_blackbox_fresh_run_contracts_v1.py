from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
GENERATED = "artifacts/generated"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_json(path: str) -> dict[str, Any]:
    payload = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(path)
    return payload


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact_ref(path: str) -> dict[str, Any]:
    full = ROOT / path
    return {
        "path": path,
        "exists": full.exists(),
        "bytes": full.stat().st_size if full.exists() else None,
        "sha256": sha256_file(full) if full.exists() and full.is_file() else None,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command_has_secret(command: str) -> bool:
    lower = command.lower()
    suspicious = ("ghp_", "github_pat_", "sk-", "bearer ", "authorization:", "api_key=", "apikey=")
    return any(item in lower for item in suspicious)


def code_dye_contract() -> dict[str, Any]:
    readiness_path = f"results/CodeDye/{GENERATED}/codedye_v3_run_readiness_classifier_v1_{DATE}.json"
    postrun_path = f"results/CodeDye/{GENERATED}/codedye_v3_postrun_promotion_gate_v1_{DATE}.json"
    readiness = load_json(readiness_path)
    postrun = load_json(postrun_path)
    output = f"results/CodeDye/{GENERATED}/codedye_v3_live_results_{DATE}.json"
    progress = f"results/CodeDye/{GENERATED}/codedye_v3_live_progress_{DATE}.json"
    run_id = f"codedye_v3_{DATE}"
    command = (
        "python projects/CodeDye/scripts/run_attack_matrix_live_support.py "
        "--provider deepseek --claim-bearing-canonical "
        "--target-records 300 "
        f"--run-id {run_id} "
        f"--output {output} "
        f"--progress-output {progress}"
    )
    prerequisites = [
        readiness_path,
        postrun_path,
        f"results/CodeDye/{GENERATED}/codedye_v3_protocol_freeze_gate_{DATE}.json",
        f"results/CodeDye/{GENERATED}/codedye_v3_positive_negative_control_gate_{DATE}.json",
        f"results/CodeDye/{GENERATED}/codedye_v3_support_exclusion_gate_{DATE}.json",
        f"results/CodeDye/{GENERATED}/codedye_negative_control_row_hash_manifest_v2_{DATE}.json",
    ]
    blockers: list[str] = []
    if readiness.get("gate_pass") is not True or readiness.get("deepseek_v3_rerun_allowed") is not True:
        blockers.append("codedye_v3_readiness_classifier_not_ready")
    if postrun.get("formal_v3_live_claim_allowed") is not False:
        blockers.append("codedye_postrun_gate_promotes_before_fresh_run")
    if output not in set(postrun.get("checked_candidate_paths", [])):
        blockers.append("codedye_output_path_not_bound_to_postrun_gate")
    if command_has_secret(command):
        blockers.append("codedye_launch_command_contains_secret_like_text")
    missing = [path for path in prerequisites if not (ROOT / path).exists()]
    blockers.extend(f"missing_prerequisite:{path}" for path in missing)
    return {
        "schema_version": "codedye_v3_fresh_run_preflight_contract_v1",
        "generated_at_utc": utc_now(),
        "project": "CodeDye",
        "claim_bearing": False,
        "gate_pass": not blockers,
        "execution_contract_ready": not blockers,
        "formal_v3_live_claim_allowed": False,
        "formal_high_recall_detection_claim_allowed": False,
        "provider": "deepseek",
        "provider_mode_required": "live",
        "run_id": run_id,
        "canonical_output": output,
        "progress_output": progress,
        "expected_record_count": 300,
        "expected_claim_denominator_record_count": 300,
        "support_only_attack_conditions_excluded_from_main_denominator": ["query_budget_drop"],
        "expected_result_schema_version": "codedye_attack_matrix_live_canonical_v1",
        "required_payload_fields": postrun.get("required_live_result_schema", {}).get("payload", []),
        "required_record_fields": postrun.get("required_live_result_schema", {}).get("records", []),
        "prerequisite_artifacts": [artifact_ref(path) for path in prerequisites],
        "launch_command_redacted": command,
        "secret_values_recorded": False,
        "postrun_promotion_gate": postrun_path,
        "promotion_policy": (
            "This contract permits only a fresh DeepSeek v3 execution attempt. "
            "A paper claim upgrade remains blocked until the postrun promotion gate passes."
        ),
        "blockers": blockers,
    }


def probe_trace_contract() -> dict[str, Any]:
    package_path = f"results/ProbeTrace/{GENERATED}/probetrace_multi_owner_deepseek_canonical_input_package_{DATE}.json"
    postrun_path = f"results/ProbeTrace/{GENERATED}/probetrace_multi_owner_postrun_promotion_gate_v1_{DATE}.json"
    package = load_json(package_path)
    postrun = load_json(postrun_path)
    input_rows = str(package.get("input_rows", f"results/ProbeTrace/{GENERATED}/probetrace_multi_owner_deepseek_canonical_input_rows_{DATE}.jsonl"))
    output = f"results/ProbeTrace/{GENERATED}/probetrace_multi_owner_deepseek_live_score_vectors_{DATE}.jsonl"
    run_id = f"probetrace_multi_owner_{DATE}"
    command = (
        "python projects/ProbeTrace/scripts/run_multi_owner_deepseek_live.py "
        "--provider deepseek --claim-bearing-canonical "
        f"--run-id {run_id} "
        f"--input {input_rows} "
        f"--output {output} "
        f"--progress-output results/ProbeTrace/{GENERATED}/probetrace_multi_owner_deepseek_live_progress_{DATE}.json"
    )
    prerequisites = [
        package_path,
        input_rows,
        f"results/ProbeTrace/{GENERATED}/probetrace_multi_owner_deepseek_prerun_gate_{DATE}.json",
        str(package.get("registry", "")),
        str(package.get("rerun_manifest", "")),
        postrun_path,
    ]
    prerequisites = [path for path in prerequisites if path]
    blockers: list[str] = []
    if package.get("gate_pass") is not True:
        blockers.append("probetrace_multi_owner_input_package_not_ready")
    if package.get("row_count") != 6000:
        blockers.append("probetrace_input_row_count_not_6000")
    if int(package.get("owner_count", 0) or 0) < 5:
        blockers.append("probetrace_owner_count_below_5")
    if int(package.get("language_count", 0) or 0) < 3:
        blockers.append("probetrace_language_count_below_3")
    if output not in set(postrun.get("checked_candidate_paths", [])):
        blockers.append("probetrace_output_path_not_bound_to_postrun_gate")
    if postrun.get("formal_multi_owner_claim_allowed") is not False:
        blockers.append("probetrace_postrun_gate_promotes_before_fresh_run")
    if command_has_secret(command):
        blockers.append("probetrace_launch_command_contains_secret_like_text")
    missing = [path for path in prerequisites if not (ROOT / path).exists()]
    blockers.extend(f"missing_prerequisite:{path}" for path in missing)
    return {
        "schema_version": "probetrace_multi_owner_fresh_run_preflight_contract_v1",
        "generated_at_utc": utc_now(),
        "project": "ProbeTrace",
        "claim_bearing": False,
        "gate_pass": not blockers,
        "execution_contract_ready": not blockers,
        "formal_multi_owner_claim_allowed": False,
        "formal_provider_general_claim_allowed": False,
        "provider": "deepseek",
        "provider_mode_required": "live",
        "run_id": run_id,
        "canonical_input_rows": input_rows,
        "canonical_output": output,
        "expected_record_count": 6000,
        "expected_owner_count_minimum": 5,
        "expected_language_count_minimum": 3,
        "required_record_fields": postrun.get("required_row_schema", []),
        "required_aggregate_gates": postrun.get("required_aggregate_gates", []),
        "prerequisite_artifacts": [artifact_ref(path) for path in prerequisites],
        "launch_command_redacted": command,
        "secret_values_recorded": False,
        "postrun_promotion_gate": postrun_path,
        "promotion_policy": (
            "The input package and support receipt are not claim evidence. "
            "Only the fresh score-vector JSONL can be evaluated by the postrun promotion gate."
        ),
        "blockers": blockers,
    }


def seal_audit_contract() -> dict[str, Any]:
    readiness_path = f"results/SealAudit/{GENERATED}/sealaudit_v5_final_evidence_readiness_gate_{DATE}.json"
    postrun_path = f"results/SealAudit/{GENERATED}/sealaudit_v5_postrun_promotion_gate_v1_{DATE}.json"
    readiness = load_json(readiness_path)
    postrun = load_json(postrun_path)
    evidence = f"results/SealAudit/{GENERATED}/sealaudit_v5_final_claim_evidence_rows_{DATE}.json"
    receipt = f"results/SealAudit/{GENERATED}/sealaudit_second_stage_v5_results_sealaudit_v5_{DATE}.json"
    frontier = f"results/SealAudit/{GENERATED}/sealaudit_v5_coverage_risk_frontier_{DATE}.json"
    visible = f"results/SealAudit/{GENERATED}/sealaudit_v5_visible_marker_diagnostic_boundary_{DATE}.json"
    threshold = f"results/SealAudit/{GENERATED}/sealaudit_v5_threshold_sensitivity_{DATE}.json"
    run_id = f"sealaudit_v5_{DATE}"
    command = (
        "python projects/SealAudit/scripts/run_second_stage_v5_conjunction.py "
        "--provider deepseek "
        f"--run-id {run_id} "
        f"--v5-evidence {evidence} "
        f"--output {receipt}"
    )
    prerequisites = [
        readiness_path,
        postrun_path,
        f"results/SealAudit/{GENERATED}/sealaudit_second_stage_support_import_gate_v1_{DATE}.json",
        f"results/SealAudit/{GENERATED}/canonical_claim_surface_results.json",
        f"results/SealAudit/{GENERATED}/sealaudit_needs_review_row_taxonomy_v2_{DATE}.jsonl",
        f"results/SealAudit/{GENERATED}/sealaudit_claim_wording_lock_v1_{DATE}.json",
    ]
    blockers: list[str] = []
    if readiness.get("support_ready") is not True:
        blockers.append("sealaudit_support_package_not_ready")
    if postrun.get("formal_v5_claim_allowed") is not False:
        blockers.append("sealaudit_postrun_gate_promotes_before_fresh_run")
    expected_sources = postrun.get("source_artifacts", {})
    if expected_sources.get("runner_receipt") != receipt:
        blockers.append("sealaudit_runner_receipt_path_not_bound_to_postrun_gate")
    if expected_sources.get("coverage_risk_frontier") != frontier:
        blockers.append("sealaudit_frontier_path_not_bound_to_postrun_gate")
    if expected_sources.get("visible_marker_diagnostic_boundary") != visible:
        blockers.append("sealaudit_visible_boundary_path_not_bound_to_postrun_gate")
    if expected_sources.get("threshold_sensitivity") != threshold:
        blockers.append("sealaudit_threshold_path_not_bound_to_postrun_gate")
    if command_has_secret(command):
        blockers.append("sealaudit_launch_command_contains_secret_like_text")
    missing = [path for path in prerequisites if not (ROOT / path).exists()]
    blockers.extend(f"missing_prerequisite:{path}" for path in missing)
    return {
        "schema_version": "sealaudit_v5_fresh_run_preflight_contract_v1",
        "generated_at_utc": utc_now(),
        "project": "SealAudit",
        "claim_bearing": False,
        "gate_pass": not blockers,
        "execution_contract_ready": not blockers,
        "formal_v5_claim_allowed": False,
        "formal_security_certificate_claim_allowed": False,
        "formal_harmlessness_claim_allowed": False,
        "provider": "deepseek",
        "provider_mode_required": "live",
        "run_id": run_id,
        "canonical_v5_evidence_input": evidence,
        "runner_receipt_output": receipt,
        "coverage_risk_frontier_output": frontier,
        "visible_marker_boundary_output": visible,
        "threshold_sensitivity_output": threshold,
        "expected_marker_hidden_claim_rows": 960,
        "expected_visible_marker_diagnostic_rows": 320,
        "required_record_fields": readiness.get("required_row_schema_for_final_v5", []),
        "required_promotion_gates": readiness.get("required_promotion_gates", []),
        "prerequisite_artifacts": [artifact_ref(path) for path in prerequisites],
        "launch_command_redacted": command,
        "secret_values_recorded": False,
        "postrun_promotion_gate": postrun_path,
        "promotion_policy": (
            "The v5 input evidence path is fixed here, but the current claim remains the v3 selective triage surface "
            "until the v5 postrun promotion gate admits row-level evidence."
        ),
        "blockers": blockers,
    }


def main() -> int:
    contracts = {
        "CodeDye": code_dye_contract(),
        "ProbeTrace": probe_trace_contract(),
        "SealAudit": seal_audit_contract(),
    }
    outputs = {
        "CodeDye": ROOT / f"results/CodeDye/{GENERATED}/codedye_v3_fresh_run_preflight_contract_v1_{DATE}.json",
        "ProbeTrace": ROOT / f"results/ProbeTrace/{GENERATED}/probetrace_multi_owner_fresh_run_preflight_contract_v1_{DATE}.json",
        "SealAudit": ROOT / f"results/SealAudit/{GENERATED}/sealaudit_v5_fresh_run_preflight_contract_v1_{DATE}.json",
    }
    for project, payload in contracts.items():
        write_json(outputs[project], payload)
    project_refs = {
        project: {
            "path": rel(path),
            "gate_pass": contracts[project]["gate_pass"],
            "blockers": contracts[project]["blockers"],
            "canonical_output": contracts[project].get("canonical_output", contracts[project].get("runner_receipt_output")),
        }
        for project, path in outputs.items()
    }
    all_blockers = [f"{project}:{item}" for project, contract in contracts.items() for item in contract["blockers"]]
    portfolio = {
        "schema_version": "blackbox_fresh_run_preflight_contracts_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": not all_blockers,
        "formal_blackbox_upgrade_claims_allowed": False,
        "project_contracts": project_refs,
        "provider": "deepseek",
        "secret_values_recorded": False,
        "blockers": all_blockers,
        "policy": "These contracts make provider execution auditable. They do not promote any black-box paper claim.",
    }
    portfolio_path = ROOT / f"results/blackbox_fresh_run_preflight_contracts_v1_{DATE}.json"
    write_json(portfolio_path, portfolio)
    print(f"[OK] Wrote {rel(portfolio_path)}")
    return 0 if not all_blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
