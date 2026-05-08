from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT


DEFAULT_OUTPUT = ARTIFACTS / "transfer_public_promotion_gate.json"
SCHEMA_VERSION = "probetrace_transfer_public_promotion_gate_v1"

REQUIRED_BASELINE_CONTROL_IDS = {
    "null_owner_abstain",
    "random_owner_seeded_prior",
    "unwrapped_same_provider_task_level",
    "task_level_utility_only_comparator",
}
REQUIRED_OFFICIAL_BASELINE_IDS = {"instructional-fingerprinting"}
REQUIRED_TRANSFER_FAMILIES = {"sft", "lora", "quantized"}
REQUIRED_HARD_DECOY_CLASSES = {
    "near_collision_owner",
    "session_drift_owner",
    "same_style_wrong_owner",
    "rehosted_student_owner",
}
APIS300_CLAIM_ROLE = "claim_bearing_apis300_live_canonical_evidence"
APIS300_EVIDENCE_SCOPE = "claim_bearing_live_apis300_attribution"
MIN_APIS300_RECORDS = 300
MIN_CONTROL_TASKS = 300
MIN_STUDENT_EXAMPLES = 300
MIN_SOURCE_RECORD_HASHES = 300
MIN_CI_N = 300
FORBIDDEN_CONTROL_ACCESS_KEYS = (
    "access_to_ground_truth_label",
    "access_to_hidden_tests",
    "access_to_owner_label",
    "access_to_probe_key",
    "access_to_watermark_key",
    "can_access_ground_truth_label",
    "can_access_hidden_tests",
    "can_access_owner_label",
    "can_access_probe_key",
    "can_access_watermark_key",
)
NONREAL_EVIDENCE_TOKENS = (
    "behavioral_probe_fit",
    "diagnostic",
    "mock",
    "no_provider",
    "not_sft_or_lora_weight_training",
    "not_valid_for_main_claim_promotion",
    "operator_claim_bearing_unverified_by_gate",
    "pilot",
    "posthoc",
    "projection",
    "replay",
    "scaffold",
    "simulated",
    "simulation",
    "unverified",
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)


def _artifact(path: Path, root: Path) -> dict[str, object]:
    return {
        "path": _rel(path, root),
        "exists": path.exists(),
        "sha256": _sha256(path),
    }


def _resolve_artifact_path(root: Path, value: object) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else root / path


def _gate(
    name: str,
    passed: bool,
    *,
    artifacts: list[str],
    blockers: list[str],
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "gate": name,
        "status": "passed" if passed else "blocked",
        "artifacts": artifacts,
        "blockers": [] if passed else blockers,
        "details": details or {},
    }


def _as_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _string_blob(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True).lower()


def _contains_nonreal_evidence_token(value: object) -> bool:
    blob = _string_blob(value)
    return any(token in blob for token in NONREAL_EVIDENCE_TOKENS)


def _artifact_path_from_payload(root: Path, payload: dict[str, Any], key: str) -> Path | None:
    raw = str(payload.get(key, "")).strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    return root / path


def _student_training_families(student: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(student.get(key, ""))
        for key in (
            "training_kind",
            "fit_recipe",
            "adapter_kind",
            "quantization_method",
            "model_artifact",
            "training_run_id",
        )
    ).lower()
    families: set[str] = set()
    if "sft" in text or "supervised_fine" in text or "supervised-fine" in text:
        families.add("sft")
    if "lora" in text or "qlora" in text:
        families.add("lora")
    if "quant" in text or "int4" in text or "int8" in text or "gguf" in text:
        families.add("quantized")
    return families


def _launch_training_families(launch_manifest: dict[str, Any] | None) -> set[str]:
    if not launch_manifest:
        return set()
    families: set[str] = set()
    for item in _as_list(launch_manifest.get("jobs")):
        if isinstance(item, dict):
            family = str(item.get("family", "")).strip().lower()
            if family:
                families.add(family)
    return families


def _has_weight_or_training_artifact(student: dict[str, Any]) -> bool:
    artifact_keys = (
        "adapter_artifact_sha256",
        "checkpoint_sha256",
        "model_artifact_sha256",
        "training_run_sha256",
        "weight_artifact_sha256",
    )
    return any(str(student.get(key, "")).strip() for key in artifact_keys) and bool(
        str(student.get("training_run_id", "")).strip()
    )


def _real_transfer_manifest_ref(payload: dict[str, Any]) -> tuple[str, str, str]:
    manifest_ref = payload.get("real_transfer_manifest", {})
    manifest_ref = manifest_ref if isinstance(manifest_ref, dict) else {}
    path = str(manifest_ref.get("path", "") or payload.get("real_transfer_manifest_path", "")).strip()
    sha256 = str(manifest_ref.get("sha256", "") or payload.get("real_transfer_manifest_sha256", "")).strip()
    schema = str(manifest_ref.get("schema_version", "")).strip()
    return path, sha256, schema


def _validate_real_transfer_manifest_ref(
    *,
    root: Path,
    manifest: dict[str, Any],
    attribution: dict[str, Any],
    blockers: list[str],
) -> dict[str, object]:
    manifest_path_text, manifest_sha, manifest_schema = _real_transfer_manifest_ref(manifest)
    attribution_path_text, attribution_sha, attribution_schema = _real_transfer_manifest_ref(attribution)
    details = {
        "manifest_path": manifest_path_text,
        "attribution_path": attribution_path_text,
        "manifest_sha256_present": bool(manifest_sha),
        "attribution_sha256_present": bool(attribution_sha),
        "manifest_schema_version": manifest_schema,
        "attribution_schema_version": attribution_schema,
    }
    if not manifest_path_text:
        blockers.append("student_transfer_real_manifest_path_missing_from_training_manifest")
    if not attribution_path_text:
        blockers.append("student_transfer_real_manifest_path_missing_from_attribution")
    if manifest_path_text and attribution_path_text and manifest_path_text != attribution_path_text:
        blockers.append("student_transfer_real_manifest_path_mismatch")
    if not manifest_sha:
        blockers.append("student_transfer_real_manifest_sha256_missing_from_training_manifest")
    if not attribution_sha:
        blockers.append("student_transfer_real_manifest_sha256_missing_from_attribution")
    if manifest_sha and attribution_sha and manifest_sha != attribution_sha:
        blockers.append("student_transfer_real_manifest_sha256_mismatch_between_artifacts")
    if manifest_schema and manifest_schema != "probetrace_real_student_transfer_manifest_v1":
        blockers.append("student_transfer_real_manifest_schema_wrong_in_training_manifest_ref")
    if attribution_schema and attribution_schema != "probetrace_real_student_transfer_manifest_v1":
        blockers.append("student_transfer_real_manifest_schema_wrong_in_attribution_ref")

    selected_path_text = manifest_path_text or attribution_path_text
    selected_sha = manifest_sha or attribution_sha
    if selected_path_text:
        path = _resolve_artifact_path(root, selected_path_text)
        details["resolved_manifest_path"] = _rel(path, root) if path is not None else ""
        if path is None or not path.exists():
            blockers.append("student_transfer_real_manifest_artifact_missing")
        elif selected_sha and _sha256(path) != selected_sha:
            blockers.append("student_transfer_real_manifest_sha256_mismatch_with_artifact")
        elif path is not None and path.exists():
            real_manifest = _load_json(path)
            details["resolved_manifest_schema_version"] = str(real_manifest.get("schema_version", ""))
            details["resolved_manifest_claim_role"] = str(real_manifest.get("claim_role", ""))
            details["resolved_manifest_evidence_scope"] = str(real_manifest.get("evidence_scope", ""))
            if real_manifest.get("schema_version") != "probetrace_real_student_transfer_manifest_v1":
                blockers.append("student_transfer_real_manifest_artifact_schema_wrong")
            if real_manifest.get("claim_role") != "claim_bearing_student_transfer_evidence":
                blockers.append("student_transfer_real_manifest_artifact_not_claim_bearing")
            if real_manifest.get("evidence_scope") != "claim_bearing_live_student_transfer":
                blockers.append("student_transfer_real_manifest_artifact_scope_wrong")
            manifest_students = [dict(item) for item in _as_list(manifest.get("students")) if isinstance(item, dict)]
            manifest_results = [dict(item) for item in _as_list(attribution.get("results")) if isinstance(item, dict)]
            real_students = [dict(item) for item in _as_list(real_manifest.get("students")) if isinstance(item, dict)]
            real_results = [dict(item) for item in _as_list(real_manifest.get("results")) if isinstance(item, dict)]
            if _safe_int(real_manifest.get("student_count")) != len(real_students):
                blockers.append("student_transfer_real_manifest_student_count_mismatch")
            if {str(item.get("student_id", "")).strip() for item in real_students} != {
                str(item.get("student_id", "")).strip() for item in manifest_students
            }:
                blockers.append("student_transfer_real_manifest_students_mismatch_training_manifest")
            if {str(item.get("student_id", "")).strip() for item in real_results} != {
                str(item.get("student_id", "")).strip() for item in manifest_results
            }:
                blockers.append("student_transfer_real_manifest_results_mismatch_attribution")
            for result in real_results:
                student_id = str(result.get("student_id", "")).strip() or "<unknown>"
                if _safe_int(result.get("validation_prompt_count")) < MIN_STUDENT_EXAMPLES:
                    blockers.append(f"student_transfer_real_manifest_validation_prompt_count_below_300:{student_id}")
                if not str(result.get("output_record_sha256", "")).strip():
                    blockers.append(f"student_transfer_real_manifest_output_record_sha256_missing:{student_id}")
                if str(result.get("validation_status", "")).strip() not in {
                    "claim_bearing_live_validated",
                    "live_validated",
                    "passed",
                }:
                    blockers.append(f"student_transfer_real_manifest_result_not_live_validated:{student_id}")
    return details


def _control_records(control_artifact: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("records", "task_records", "control_records"):
        rows = [dict(item) for item in _as_list(control_artifact.get(key)) if isinstance(item, dict)]
        if rows:
            return rows
    return []


def _validate_control_artifact(
    *,
    control_id: str,
    control: dict[str, Any],
    control_artifact: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if control_artifact.get("control_id") not in {"", None, control_id}:
        blockers.append(f"baseline_control_artifact_control_id_mismatch:{control_id}")
    if control_artifact.get("claim_role") != "claim_bearing_control_evidence":
        blockers.append(f"baseline_control_artifact_not_claim_bearing:{control_id}")
    artifact_status = str(control_artifact.get("execution_status", "")).strip().lower()
    verifier_status = str(control_artifact.get("verifier_execution_status", "")).strip().lower()
    if "executed" not in artifact_status:
        blockers.append(f"baseline_control_artifact_not_executed:{control_id}")
    if "executed" not in verifier_status:
        blockers.append(f"baseline_control_verifier_not_executed:{control_id}")
    if _contains_nonreal_evidence_token(
        {
            "execution_status": control_artifact.get("execution_status"),
            "verifier_execution_status": control_artifact.get("verifier_execution_status"),
            "notes": control_artifact.get("notes"),
        }
    ):
        blockers.append(f"baseline_control_artifact_nonreal_or_scaffold:{control_id}")
    rows = _control_records(control_artifact)
    if len(rows) < MIN_CONTROL_TASKS:
        blockers.append(f"baseline_control_artifact_record_count_below_300:{control_id}")
    if _safe_int(control_artifact.get("task_count")) < MIN_CONTROL_TASKS:
        blockers.append(f"baseline_control_artifact_task_count_below_300:{control_id}")
    false_attributions = 0
    owner_emissions = 0
    missing_hashes = 0
    for row in rows:
        if bool(row.get("false_attribution", False)) or str(row.get("verification_status", "")).strip() == "accepted":
            false_attributions += 1
        if str(row.get("owner_id_hat", row.get("attributed_owner_id", ""))).strip():
            owner_emissions += 1
        if not str(row.get("output_record_sha256", row.get("response_hash", row.get("structured_payload_hash", "")))).strip():
            missing_hashes += 1
    if false_attributions:
        blockers.append(f"baseline_control_artifact_false_attribution_nonzero:{control_id}:{false_attributions}")
    if owner_emissions:
        blockers.append(f"baseline_control_artifact_owner_id_emission_nonzero:{control_id}:{owner_emissions}")
    if missing_hashes:
        blockers.append(f"baseline_control_artifact_output_hash_missing:{control_id}:{missing_hashes}")
    if control_id == "unwrapped_same_provider_task_level":
        live_rows = [
            row
            for row in rows
            if str(row.get("provider_mode", "")).strip().lower() == "live"
            and str(row.get("provider_name", row.get("provider", ""))).strip().lower() == "deepseek"
        ]
        if len(live_rows) < MIN_CONTROL_TASKS:
            blockers.append(f"baseline_control_unwrapped_same_provider_live_rows_below_300:{len(live_rows)}")
    if control_id == "task_level_utility_only_comparator":
        utility_rows = [
            row
            for row in rows
            if "compile_ok" in row
            and ("pass_ok" in row or "pass_supported" in row)
            and not str(row.get("owner_id_hat", "")).strip()
        ]
        if len(utility_rows) < MIN_CONTROL_TASKS:
            blockers.append(f"baseline_control_task_level_utility_rows_below_300:{len(utility_rows)}")
    return blockers


def _build_student_transfer_gate(
    root: Path,
    manifest: dict[str, Any],
    attribution: dict[str, Any],
    launch_manifest: dict[str, Any] | None = None,
) -> tuple[bool, list[str], dict[str, object]]:
    blockers: list[str] = []
    if manifest.get("schema_version") != "student_transfer_artifacts_v1":
        blockers.append("student_training_manifest_schema_missing_or_wrong")
    if attribution.get("schema_version") != "student_transfer_artifacts_v1":
        blockers.append("student_transfer_attribution_schema_missing_or_wrong")
    if manifest.get("artifact_type") != "student_training_corpus_manifest":
        blockers.append("student_training_manifest_artifact_type_wrong")
    if attribution.get("artifact_type") != "student_transfer_attribution_results":
        blockers.append("student_transfer_attribution_artifact_type_wrong")
    if manifest.get("claim_role") != "claim_bearing_student_transfer_evidence":
        blockers.append("student_training_manifest_not_claim_bearing")
    if attribution.get("claim_role") != "claim_bearing_student_transfer_evidence":
        blockers.append("student_transfer_attribution_not_claim_bearing")
    if manifest.get("evidence_scope") != "claim_bearing_live_student_transfer":
        blockers.append("student_training_manifest_not_live_transfer_scope")
    if attribution.get("evidence_scope") != "claim_bearing_live_student_transfer":
        blockers.append("student_transfer_attribution_not_live_transfer_scope")

    manifest_live = (
        manifest.get("claim_role") == "claim_bearing_student_transfer_evidence"
        and manifest.get("evidence_scope") == "claim_bearing_live_student_transfer"
    )
    attribution_live = (
        attribution.get("claim_role") == "claim_bearing_student_transfer_evidence"
        and attribution.get("evidence_scope") == "claim_bearing_live_student_transfer"
    )
    launch_families = _launch_training_families(launch_manifest)
    if not (manifest_live and attribution_live):
        if launch_families:
            for family in sorted(REQUIRED_TRANSFER_FAMILIES):
                if family in launch_families:
                    blockers.append(f"student_transfer_training_receipt_missing:{family}")
                else:
                    blockers.append(f"student_transfer_family_missing:{family}")
        else:
            missing_families = sorted(REQUIRED_TRANSFER_FAMILIES.difference(launch_families))
            blockers.extend(f"student_transfer_family_missing:{family}" for family in missing_families)
        details = {
            "observed_transfer_families": [],
            "observed_training_launch_families": sorted(launch_families),
            "required_transfer_families": sorted(REQUIRED_TRANSFER_FAMILIES),
            "student_count": _safe_int(manifest.get("student_count")),
            "result_count": _safe_int(attribution.get("student_count")),
            "legacy_or_support_only_artifacts": True,
            "admission_policy": "legacy pilot details are not inspected for main-claim evidence; real receipts and live validation are required",
        }
        return False, list(dict.fromkeys(blockers)), details

    students = [dict(item) for item in _as_list(manifest.get("students")) if isinstance(item, dict)]
    results = [dict(item) for item in _as_list(attribution.get("results")) if isinstance(item, dict)]
    if not students:
        blockers.append("student_training_entries_missing")
    if not results:
        blockers.append("student_transfer_results_missing")
    if _safe_int(manifest.get("student_count")) != len(students) or _safe_int(attribution.get("student_count")) != len(results):
        blockers.append("student_count_does_not_match_entries")

    families: set[str] = set()
    nonreal_student_ids: list[str] = []
    missing_weight_artifacts: list[str] = []
    for student in students:
        student_id = str(student.get("student_id", "")).strip() or "<unknown>"
        families.update(_student_training_families(student))
        if _contains_nonreal_evidence_token(
            {
                "training_kind": student.get("training_kind"),
                "fit_recipe": student.get("fit_recipe"),
                "notes": student.get("notes"),
                "validation_status": student.get("validation_status"),
            }
        ):
            nonreal_student_ids.append(student_id)
        if not _has_weight_or_training_artifact(student):
            missing_weight_artifacts.append(student_id)
        if _safe_int(student.get("example_count")) < MIN_STUDENT_EXAMPLES:
            blockers.append(f"student_training_example_count_below_{MIN_STUDENT_EXAMPLES}:{student_id}")
        if len(_as_list(student.get("source_record_hashes"))) < MIN_SOURCE_RECORD_HASHES:
            blockers.append(f"student_source_record_hashes_below_{MIN_SOURCE_RECORD_HASHES}:{student_id}")
        if not _as_list(student.get("provider_names")):
            blockers.append(f"student_provider_names_missing:{student_id}")

    missing_families = sorted(REQUIRED_TRANSFER_FAMILIES.difference(families))
    blockers.extend(f"student_transfer_family_missing:{family}" for family in missing_families)
    blockers.extend(f"student_transfer_missing_weight_or_training_artifact:{student_id}" for student_id in missing_weight_artifacts)
    blockers.extend(f"simulated_or_nonreal_student_transfer_evidence:{student_id}" for student_id in nonreal_student_ids)

    result_by_id = {str(item.get("student_id", "")).strip(): item for item in results}
    student_ids = {str(item.get("student_id", "")).strip() for item in students}
    if student_ids and student_ids != set(result_by_id):
        blockers.append("student_training_and_attribution_student_ids_mismatch")
    for student_id, result in result_by_id.items():
        if _contains_nonreal_evidence_token(
            {
                "validation_status": result.get("validation_status"),
                "evidence_trace": result.get("evidence_trace"),
            }
        ):
            blockers.append(f"student_transfer_result_nonreal_or_unverified:{student_id or '<unknown>'}")
        if str(result.get("validation_status", "")).strip() not in {
            "claim_bearing_live_validated",
            "live_validated",
            "passed",
        }:
            blockers.append(f"student_transfer_result_not_live_validated:{student_id or '<unknown>'}")
        if not str(result.get("attributed_owner_id", "")).strip():
            blockers.append(f"student_transfer_result_attributed_owner_missing:{student_id or '<unknown>'}")
        if _safe_float(result.get("coverage")) < 1.0:
            blockers.append(f"student_transfer_result_coverage_below_one:{student_id or '<unknown>'}")
        if _safe_float(result.get("confidence")) <= 0.0:
            blockers.append(f"student_transfer_result_confidence_missing:{student_id or '<unknown>'}")
        if _safe_float(result.get("inheritance_rate")) <= 0.0:
            blockers.append(f"student_transfer_result_inheritance_rate_missing:{student_id or '<unknown>'}")
        if _safe_float(result.get("margin")) <= 0.0:
            blockers.append(f"student_transfer_result_margin_missing:{student_id or '<unknown>'}")
        if not _as_list(result.get("evidence_trace")):
            blockers.append(f"student_transfer_result_evidence_trace_missing:{student_id or '<unknown>'}")

    manifest_ref_details = _validate_real_transfer_manifest_ref(
        root=root,
        manifest=manifest,
        attribution=attribution,
        blockers=blockers,
    )

    details = {
        "observed_transfer_families": sorted(families),
        "observed_training_launch_families": sorted(launch_families),
        "required_transfer_families": sorted(REQUIRED_TRANSFER_FAMILIES),
        "student_count": len(students),
        "result_count": len(results),
        "real_transfer_manifest_ref": manifest_ref_details,
    }
    return not blockers, blockers, details


def _build_apis300_gate(
    root: Path,
    support: dict[str, Any],
    provenance: dict[str, Any],
) -> tuple[bool, list[str], dict[str, object]]:
    blockers: list[str] = []
    source_path = _artifact_path_from_payload(root, support, "source_artifact")
    source_sha = _sha256(source_path) if source_path is not None else ""
    support_promoters = _as_list(support.get("promotion_blockers"))
    blockers.extend(f"apis300_support_promotion_blocker:{item}" for item in support_promoters)
    if support.get("schema_version") != "probetrace_apis300_support_materialization_v1":
        blockers.append("apis300_support_schema_missing_or_wrong")
    if support.get("support_status") != "materialized":
        blockers.append("apis300_support_not_materialized")
    if support.get("claim_role") != APIS300_CLAIM_ROLE:
        blockers.append("apis300_support_not_claim_bearing_live_canonical")
    if support.get("evidence_scope") != APIS300_EVIDENCE_SCOPE:
        blockers.append("apis300_support_evidence_scope_not_live_apis300")
    if support.get("formal_claim_allowed") is not True:
        blockers.append("apis300_support_formal_claim_not_allowed")
    if _safe_int(support.get("local_task_count")) < 300 or _safe_int(support.get("local_task_target")) < 300:
        blockers.append("apis300_local_task_count_or_target_below_300")
    if _safe_float(support.get("local_task_coverage_rate")) < 1.0:
        blockers.append("apis300_local_task_coverage_below_one")
    if _safe_int(support.get("public_task_target")) <= 0 or _safe_int(support.get("public_task_count")) < _safe_int(
        support.get("public_task_target")
    ):
        blockers.append("apis300_public_support_not_complete")
    if _safe_int(support.get("baseline_task_evidence_count")) < 300:
        blockers.append("apis300_baseline_task_evidence_below_300")
    if not bool(support.get("budget_feasible_attribution_pass", False)):
        blockers.append("apis300_budget_feasible_attribution_false")
    if _safe_int(support.get("canonical_anchor_record_count")) < 300:
        blockers.append("apis300_canonical_anchor_record_count_below_300")
    if _safe_int(support.get("record_count")) < MIN_APIS300_RECORDS:
        blockers.append(f"apis300_record_count_below_{MIN_APIS300_RECORDS}")
    if "live" not in str(support.get("source_mode", "")).lower():
        blockers.append("apis300_source_mode_not_live")
    if source_path is None or not source_path.exists():
        blockers.append("apis300_source_artifact_missing")
    if source_sha and str(support.get("source_sha256", "")).strip() and source_sha != str(support.get("source_sha256", "")).strip():
        blockers.append("apis300_source_sha256_mismatch")

    source_run_id = str(support.get("source_run_id", "")).strip()
    canonical_run_id = str(support.get("canonical_anchor_source_run_id", "")).strip()
    provenance_run_id = str(provenance.get("canonical_source_run_id", "")).strip()
    if not source_run_id:
        blockers.append("apis300_source_run_id_missing")
    if source_run_id and canonical_run_id and source_run_id != canonical_run_id:
        blockers.append("apis300_support_source_run_not_canonical_anchor")
    if source_run_id and provenance_run_id and source_run_id != provenance_run_id:
        blockers.append("apis300_support_source_run_not_canonical_provenance")
    provenance_schema = str(provenance.get("schema_version", ""))
    if provenance_schema not in {
        "probetrace_canonical_run_provenance_v1",
        "probetrace_apis300_live_attribution_provenance_v1",
    }:
        blockers.append("canonical_run_provenance_schema_missing_or_wrong")
    if not bool(provenance.get("canonical_eligible", False)):
        blockers.append("canonical_run_provenance_not_eligible")
    if str(provenance.get("provider_mode") or provenance.get("source_mode") or "").strip() != "live":
        blockers.append("canonical_run_provenance_not_live")

    provenance_artifact = str(provenance.get("canonical_artifact", "")).strip()
    if source_path is not None and provenance_artifact:
        expected = _rel(source_path, root)
        if provenance_artifact != expected:
            blockers.append("canonical_provenance_artifact_not_apis300_source")
    if source_sha and str(provenance.get("canonical_artifact_sha256", "")).strip() and source_sha != str(
        provenance.get("canonical_artifact_sha256", "")
    ).strip():
        blockers.append("canonical_provenance_sha256_mismatch")

    gate_rates = provenance.get("gate_rates", {})
    gate_rates = gate_rates if isinstance(gate_rates, dict) else {}
    if not bool(gate_rates.get("coverage_gate_pass", False)):
        blockers.append("canonical_provenance_coverage_gate_false")
    for key in (
        "support_count_gate_pass_rate",
        "support_family_diversity_gate_pass_rate",
        "support_bucket_diversity_gate_pass_rate",
        "winner_support_conjunction_pass_rate",
    ):
        if _safe_float(gate_rates.get(key)) < 1.0:
            blockers.append(f"canonical_provenance_{key}_below_one")

    if _contains_nonreal_evidence_token(
        {
            "claim_role": support.get("claim_role"),
            "source_mode": support.get("source_mode"),
            "source_artifact": support.get("source_artifact"),
        }
    ):
        blockers.append("apis300_support_contains_nonreal_or_diagnostic_scope")

    details = {
        "source_run_id": source_run_id,
        "canonical_anchor_source_run_id": canonical_run_id,
        "local_task_count": _safe_int(support.get("local_task_count")),
        "local_task_target": _safe_int(support.get("local_task_target")),
        "public_task_count": _safe_int(support.get("public_task_count")),
        "public_task_target": _safe_int(support.get("public_task_target")),
    }
    return not blockers, blockers, details


def _final_survivor_count(class_row: dict[str, Any]) -> int:
    if "survivor_count" in class_row:
        return _safe_int(class_row.get("survivor_count"))
    if "projected_survivor_count" in class_row:
        return _safe_int(class_row.get("projected_survivor_count"))
    checkpoints = [dict(item) for item in _as_list(class_row.get("checkpoints")) if isinstance(item, dict)]
    if not checkpoints:
        return 1
    final = max(checkpoints, key=lambda item: _safe_int(item.get("query_index")))
    return _safe_int(final.get("survivor_count"))


def _build_hard_decoy_gate(
    registry: dict[str, Any],
    survival: dict[str, Any],
) -> tuple[bool, list[str], dict[str, object]]:
    blockers: list[str] = []
    class_counts = registry.get("materialized_decoy_class_counts", {})
    class_counts = class_counts if isinstance(class_counts, dict) else {}
    registry_classes = {str(item) for item in _as_list(registry.get("decoy_class_order"))} or set(class_counts)
    if registry_classes != REQUIRED_HARD_DECOY_CLASSES:
        blockers.append("hard_decoy_96_class_inventory_mismatch")
    if _safe_int(registry.get("target_registry_count")) != 96:
        blockers.append("hard_decoy_96_target_registry_count_wrong")
    if _safe_int(registry.get("target_per_class")) != 24:
        blockers.append("hard_decoy_96_target_per_class_wrong")
    if _safe_int(registry.get("slot_count")) != 96 or _safe_int(registry.get("materialized_slot_count")) != 96:
        blockers.append("hard_decoy_96_slots_not_fully_materialized")
    if _safe_int(registry.get("unique_materialized_owner_count")) != 96:
        blockers.append("hard_decoy_96_unique_owner_count_wrong")
    if _safe_int(registry.get("unmaterialized_slot_count")) != 0:
        blockers.append("hard_decoy_96_unmaterialized_slots_present")
    if not bool(registry.get("expansion_ready", False)):
        blockers.append("hard_decoy_96_registry_not_ready")
    blockers.extend(f"hard_decoy_96_registry_promotion_blocker:{item}" for item in _as_list(registry.get("promotion_blockers")))
    for decoy_class in sorted(REQUIRED_HARD_DECOY_CLASSES):
        if _safe_int(class_counts.get(decoy_class)) != 24:
            blockers.append(f"hard_decoy_96_class_count_not_24:{decoy_class}")

    if _safe_int(survival.get("target_registry_count")) != 96:
        blockers.append("hard_decoy_96_survival_target_count_wrong")
    if survival.get("claim_role") != "claim_bearing_hard_decoy_96_live_survival_evidence":
        blockers.append("hard_decoy_96_survival_not_claim_bearing_live_evidence")
    if "live" not in str(survival.get("run_mode", "")).lower():
        blockers.append("hard_decoy_96_survival_run_mode_not_live")
    if _safe_int(survival.get("provider_calls_made")) < 96:
        blockers.append("hard_decoy_96_survival_has_no_live_provider_calls")
    if not bool(survival.get("live_probe_rescoring_performed", False)):
        blockers.append("hard_decoy_96_per_class_live_rescoring_missing")
    if _contains_nonreal_evidence_token(
        {
            "claim_role": survival.get("claim_role"),
            "run_mode": survival.get("run_mode"),
            "notes": survival.get("notes"),
            "status": survival.get("status"),
        }
    ):
        blockers.append("hard_decoy_96_survival_is_diagnostic_or_projected")

    attack_curves = [dict(item) for item in _as_list(survival.get("attack_curves")) if isinstance(item, dict)]
    if not attack_curves:
        blockers.append("hard_decoy_96_attack_curves_missing")
    observed_classes: set[str] = set()
    for attack in attack_curves:
        attack_name = str(attack.get("attack", "")).strip() or "<unknown>"
        class_rows = [dict(item) for item in _as_list(attack.get("classes")) if isinstance(item, dict)]
        class_by_name = {str(item.get("decoy_class", "")).strip(): item for item in class_rows}
        missing_classes = sorted(REQUIRED_HARD_DECOY_CLASSES.difference(class_by_name))
        blockers.extend(f"hard_decoy_96_survival_class_missing:{attack_name}:{item}" for item in missing_classes)
        for decoy_class, row in class_by_name.items():
            observed_classes.add(decoy_class)
            if _safe_int(row.get("registry_count")) != 24:
                blockers.append(f"hard_decoy_96_survival_class_registry_count_wrong:{attack_name}:{decoy_class}")
            if _safe_int(row.get("provider_call_count")) < _safe_int(row.get("registry_count")):
                blockers.append(f"hard_decoy_96_survival_class_provider_calls_below_registry:{attack_name}:{decoy_class}")
            if _final_survivor_count(row) != 0:
                blockers.append(f"hard_decoy_96_survival_class_survivors_nonzero:{attack_name}:{decoy_class}")
            if _contains_nonreal_evidence_token(row):
                blockers.append(f"hard_decoy_96_survival_class_nonreal_source:{attack_name}:{decoy_class}")
            checkpoints = [dict(item) for item in _as_list(row.get("checkpoints")) if isinstance(item, dict)]
            if not checkpoints:
                blockers.append(f"hard_decoy_96_survival_class_checkpoints_missing:{attack_name}:{decoy_class}")
            elif any(str(item.get("source", "")).strip() != "live_rescoring" for item in checkpoints):
                blockers.append(f"hard_decoy_96_survival_class_checkpoint_source_not_live:{attack_name}:{decoy_class}")

    details = {
        "registry_classes": sorted(registry_classes),
        "observed_survival_classes": sorted(observed_classes),
        "attack_curve_count": len(attack_curves),
    }
    return not blockers, blockers, details


def _build_baseline_control_gate(
    root: Path,
    controls_payload: dict[str, Any],
    activation: dict[str, Any],
) -> tuple[bool, list[str], dict[str, object]]:
    controls = [dict(item) for item in _as_list(controls_payload.get("controls")) if isinstance(item, dict)]
    control_by_id = {str(item.get("control_id", "")).strip(): item for item in controls}
    control_ids = set(control_by_id)
    blockers = [f"baseline_control_missing:{item}" for item in sorted(REQUIRED_BASELINE_CONTROL_IDS.difference(control_ids))]
    execution_status = str(controls_payload.get("execution_status", "")).strip().lower()
    claim_role = str(controls_payload.get("claim_role", "")).strip().lower()
    if _contains_nonreal_evidence_token({"execution_status": execution_status, "claim_role": claim_role}):
        blockers.append("baseline_controls_not_executed_or_scaffold")
    if activation.get("overall_status") != "passed":
        blockers.append("baseline_activation_checks_not_passed")
    blockers.extend(str(item) for item in _as_list(activation.get("blockers")))
    if _as_list(activation.get("missing_control_ids")):
        blockers.extend(f"baseline_activation_missing_control:{item}" for item in _as_list(activation.get("missing_control_ids")))
    if _safe_int(controls_payload.get("control_count")) < len(REQUIRED_BASELINE_CONTROL_IDS):
        blockers.append("baseline_control_count_below_required")
    if not activation.get("source_artifact"):
        blockers.append("baseline_activation_source_artifact_missing")
    for control_id in sorted(REQUIRED_BASELINE_CONTROL_IDS.intersection(control_ids)):
        control = control_by_id[control_id]
        status_blob = {
            "execution_status": control.get("execution_status"),
            "claim_role": control.get("claim_role"),
            "notes": control.get("notes"),
        }
        if _contains_nonreal_evidence_token(status_blob):
            blockers.append(f"baseline_control_not_claim_bearing_executed:{control_id}")
        task_count = max(
            _safe_int(control.get("task_count")),
            _safe_int(control.get("record_count")),
            _safe_int(control.get("task_record_count")),
        )
        if task_count < 300:
            blockers.append(f"baseline_control_task_count_below_300:{control_id}")
        artifact = str(control.get("artifact", control.get("source_artifact", ""))).strip()
        artifact_sha = str(control.get("artifact_sha256", control.get("source_sha256", ""))).strip()
        if not artifact:
            blockers.append(f"baseline_control_artifact_missing:{control_id}")
        if not artifact_sha:
            blockers.append(f"baseline_control_artifact_sha256_missing:{control_id}")
        artifact_path = _resolve_artifact_path(root, artifact)
        if artifact_path is None or not artifact_path.exists():
            blockers.append(f"baseline_control_artifact_not_found:{control_id}")
        elif artifact_sha and _sha256(artifact_path) != artifact_sha:
            blockers.append(f"baseline_control_artifact_sha256_mismatch:{control_id}")
        elif artifact_path is not None and artifact_path.exists():
            blockers.extend(
                _validate_control_artifact(
                    control_id=control_id,
                    control=control,
                    control_artifact=_load_json(artifact_path),
                )
            )
        if bool(control.get("can_emit_owner_id_hat", False)):
            blockers.append(f"baseline_control_can_emit_owner_id_hat:{control_id}")
        if _safe_int(control.get("false_attribution_count")) != 0:
            blockers.append(f"baseline_control_false_attribution_nonzero:{control_id}")
        if _safe_int(control.get("owner_id_hat_emission_count")) != 0:
            blockers.append(f"baseline_control_owner_id_hat_emission_nonzero:{control_id}")
        for key in FORBIDDEN_CONTROL_ACCESS_KEYS:
            if bool(control.get(key, False)):
                blockers.append(f"baseline_control_forbidden_access:{control_id}:{key}")
    details = {
        "observed_control_ids": sorted(control_ids),
        "required_control_ids": sorted(REQUIRED_BASELINE_CONTROL_IDS),
        "execution_status": execution_status,
        "baseline_activation_status": str(activation.get("overall_status", "")),
    }
    return not blockers, blockers, details


def _build_official_baseline_gate(admission: dict[str, Any]) -> tuple[bool, list[str], dict[str, object]]:
    blockers: list[str] = []
    if admission.get("schema_version") != "probetrace_instructional_fingerprinting_official_admission_gate_v1":
        blockers.append("official_if_admission_schema_missing_or_wrong")
    if admission.get("status") != "passed":
        blockers.append("official_if_admission_gate_not_passed")
    blockers.extend(f"official_if_admission_blocker:{item}" for item in _as_list(admission.get("blockers")))
    if str(admission.get("baseline_id", "")).strip() not in REQUIRED_OFFICIAL_BASELINE_IDS:
        blockers.append("official_if_baseline_id_missing_or_wrong")
    if not bool(admission.get("official_core_unmodified", False)):
        blockers.append("official_if_core_modified")
    if not bool(admission.get("official_main_table_admissible", False)):
        blockers.append("official_if_not_main_table_admissible")
    contract = admission.get("task_evidence_contract", {})
    contract = contract if isinstance(contract, dict) else {}
    if _safe_int(contract.get("task_record_count")) < 60:
        blockers.append("official_if_task_records_below_60")
    if str(contract.get("status", "")) != "passed":
        blockers.append("official_if_task_evidence_contract_not_passed")
    details = {
        "required_official_baselines": sorted(REQUIRED_OFFICIAL_BASELINE_IDS),
        "baseline": admission.get("baseline"),
        "baseline_id": admission.get("baseline_id"),
        "official_commit": admission.get("official_commit"),
        "task_record_count": _safe_int(contract.get("task_record_count")),
        "activation_count": _safe_int(contract.get("activation_count")),
        "activation_rate": _safe_float(contract.get("activation_rate")),
        "policy": (
            "Official IF admission is separate from null/control comparators. Low activation is reported as "
            "a baseline result and cannot satisfy or replace the student-transfer gate."
        ),
    }
    return not blockers, blockers, details


def _metric_from_payload(payload: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    metrics = payload.get("metrics", {})
    metrics = metrics if isinstance(metrics, dict) else {}
    for name in names:
        value = metrics.get(name, payload.get(name))
        if isinstance(value, dict):
            return dict(value)
    return {}


def _ci_metric_pass(metric: dict[str, Any], *, direction: str, default_threshold: float | None) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if not metric:
        return False, ["ci_metric_missing"]
    if _safe_int(metric.get("n")) < MIN_CI_N:
        blockers.append(f"ci_metric_n_below_{MIN_CI_N}")
    ci_method = str(metric.get("ci_method", "")).lower()
    if any(token in ci_method for token in ("descriptive_only", "unavailable", "scaffold")):
        blockers.append("ci_metric_not_preregistered_interval")
    low = metric.get("ci95_low")
    high = metric.get("ci95_high")
    if not isinstance(low, (int, float)) or isinstance(low, bool):
        blockers.append("ci95_low_missing")
    if not isinstance(high, (int, float)) or isinstance(high, bool):
        blockers.append("ci95_high_missing")
    if bool(metric.get("gate_pass", False)):
        return not blockers, blockers

    threshold = metric.get("threshold", metric.get("max_allowed", metric.get("min_required", default_threshold)))
    if threshold is None:
        return not blockers, blockers
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        blockers.append("ci_metric_threshold_missing")
        return False, blockers
    if direction == "lower_bound" and isinstance(low, (int, float)) and float(low) < float(threshold):
        blockers.append("ci95_low_below_threshold")
    if direction == "upper_bound" and isinstance(high, (int, float)) and float(high) > float(threshold):
        blockers.append("ci95_high_above_threshold")
    return not blockers, blockers


def _build_ci_gate(payload: dict[str, Any]) -> tuple[bool, list[str], dict[str, object]]:
    blockers: list[str] = []
    if _safe_int(payload.get("record_count")) < MIN_CI_N:
        blockers.append(f"ci_record_count_below_{MIN_CI_N}")
    if _safe_float(payload.get("budget_feasible_rate")) < 1.0:
        blockers.append("budget_feasible_rate_below_one")
    if str(payload.get("claim_role", "")).strip() != "claim_bearing_statistics_report":
        blockers.append("statistics_report_not_claim_bearing")
    effective_gate = payload.get("effective_n_independence_gate", {})
    effective_gate = dict(effective_gate) if isinstance(effective_gate, dict) else {}
    if not bool(effective_gate.get("gate_pass", False)):
        blockers.append("effective_n_independence_gate_failed")
    if _safe_int(effective_gate.get("positive_effective_n")) < MIN_CI_N:
        blockers.append(f"positive_effective_n_below_{MIN_CI_N}")
    if _safe_int(effective_gate.get("negative_effective_n")) < MIN_CI_N:
        blockers.append(f"negative_effective_n_below_{MIN_CI_N}")
    if _safe_int(effective_gate.get("task_joined_run_level_record_count")) > 0:
        blockers.append("run_level_decision_joined_to_task_records_not_independent")

    metric_specs = {
        "tpr": (_metric_from_payload(payload, ("tpr", "true_positive_rate", "tpr_ci")), "lower_bound", 0.8),
        "fpr": (_metric_from_payload(payload, ("fpr", "false_positive_rate", "fpr_ci")), "upper_bound", 0.05),
        "latency": (
            _metric_from_payload(payload, ("latency_overhead", "latency_per_provider_call", "latency_ms", "latency_ci")),
            "upper_bound",
            None,
        ),
    }
    metric_details: dict[str, object] = {}
    for name, (metric, direction, threshold) in metric_specs.items():
        metric_pass, metric_blockers = _ci_metric_pass(metric, direction=direction, default_threshold=threshold)
        metric_details[name] = {
            "n": _safe_int(metric.get("n")),
            "ci95_low": metric.get("ci95_low"),
            "ci95_high": metric.get("ci95_high"),
            "gate_pass": bool(metric.get("gate_pass", False)),
        }
        if not metric_pass:
            blockers.extend(f"{name}_{blocker}" for blocker in metric_blockers)
    return not blockers, blockers, metric_details


def _build_expanded_gate(expanded: dict[str, Any]) -> tuple[bool, list[str], dict[str, object]]:
    blockers: list[str] = []
    if expanded.get("gate_version") != "probetrace_expanded_evidence_gate_v1":
        blockers.append("expanded_evidence_gate_schema_missing_or_wrong")
    gates = _as_list(expanded.get("gates"))
    blocking_gate_names = {
        "apis_300_executable_materialized_manifest",
        "hard_decoy_96_expansion_registry_materialized",
        "hard_decoy_96_manifest",
        "hard_decoy_96_survival_curve_scaffold_run",
        "baseline_activation_and_comparator_controls",
        "apis300_support_materialization",
        "student_transfer_preflight_and_deepseek_canary",
        "budget_latency_ci",
        "review_ready_v6_anchor_preserved",
    }
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        name = str(gate.get("gate", "")).strip()
        if name not in blocking_gate_names:
            continue
        if str(gate.get("status", "")).strip() != "passed":
            gate_blockers = [str(item) for item in _as_list(gate.get("blockers")) if str(item).strip()]
            if gate_blockers:
                blockers.extend(f"expanded_evidence_gate:{name}:{item}" for item in gate_blockers)
            else:
                blockers.append(f"expanded_evidence_gate:{name}:not_passed")
    if not gates:
        if not bool(expanded.get("live_promotion_gate_pass", False)):
            blockers.append("expanded_evidence_live_promotion_gate_false")
        if str(expanded.get("overall_status", "")) != "passed":
            blockers.append("expanded_evidence_overall_status_not_passed")
        blockers.extend(f"expanded_evidence_remaining_blocker:{item}" for item in _as_list(expanded.get("remaining_blockers")))
    details = {
        "live_promotion_gate_pass": bool(expanded.get("live_promotion_gate_pass", False)),
        "overall_status": str(expanded.get("overall_status", "")),
        "student_transfer_artifact_gate_deferred": True,
        "policy": "student transfer is checked by student_transfer_real_training_evidence; expanded evidence gate only blocks non-transfer APIS/control/statistics scaffolds here.",
    }
    return not blockers, blockers, details


def build_gate(root: Path = ROOT) -> dict[str, Any]:
    paths = {
        "apis300_support": root / "artifacts" / "generated" / "probetrace_apis300_support_materialization.json",
        "apis300_live_attribution_provenance": root / "artifacts" / "generated" / "apis300_live_attribution_provenance.json",
        "expanded_evidence_gate": root / "artifacts" / "generated" / "expanded_evidence_gate.json",
        "hard_decoy_96_registry": root / "artifacts" / "generated" / "hard_decoy_96_expansion_registry.json",
        "hard_decoy_96_survival": root / "artifacts" / "generated" / "hard_decoy_96_survival_curves.json",
        "baseline_controls": root / "artifacts" / "generated" / "baseline_control_manifest.json",
        "baseline_activation": root / "artifacts" / "generated" / "baseline_activation_checks.json",
        "instructional_fingerprinting_official_admission": root
        / "artifacts"
        / "generated"
        / "instructional_fingerprinting_official_admission_gate.json",
        "canonical_run_provenance": root / "artifacts" / "generated" / "canonical_run_provenance.json",
        "budget_latency_ci": root / "artifacts" / "generated" / "budget_latency_ci_summary.json",
        "student_training_manifest": root / "artifacts" / "generated" / "student_training_corpus_manifest.json",
        "student_transfer_training_launch": root / "artifacts" / "generated" / "student_transfer_training_launch_manifest.json",
        "student_transfer_attribution": root / "artifacts" / "generated" / "student_transfer_attribution_results.json",
    }
    payloads = {name: _load_json(path) for name, path in paths.items()}
    apis300_provenance = (
        payloads["apis300_live_attribution_provenance"]
        if payloads["apis300_live_attribution_provenance"]
        else payloads["canonical_run_provenance"]
    )
    apis300_provenance_path = (
        paths["apis300_live_attribution_provenance"]
        if payloads["apis300_live_attribution_provenance"]
        else paths["canonical_run_provenance"]
    )

    gate_specs = [
        (
            "expanded_evidence_gate_promoted",
            _build_expanded_gate(payloads["expanded_evidence_gate"]),
            [paths["expanded_evidence_gate"]],
        ),
        (
            "apis300_live_canonical_support",
            _build_apis300_gate(root, payloads["apis300_support"], apis300_provenance),
            [paths["apis300_support"], apis300_provenance_path],
        ),
        (
            "student_transfer_real_training_evidence",
            _build_student_transfer_gate(
                root,
                payloads["student_training_manifest"],
                payloads["student_transfer_attribution"],
                payloads["student_transfer_training_launch"],
            ),
            [paths["student_training_manifest"], paths["student_transfer_training_launch"], paths["student_transfer_attribution"]],
        ),
        (
            "hard_decoy_96_per_class_live_survival",
            _build_hard_decoy_gate(payloads["hard_decoy_96_registry"], payloads["hard_decoy_96_survival"]),
            [paths["hard_decoy_96_registry"], paths["hard_decoy_96_survival"]],
        ),
        (
            "baseline_activation_and_required_controls",
            _build_baseline_control_gate(root, payloads["baseline_controls"], payloads["baseline_activation"]),
            [paths["baseline_controls"], paths["baseline_activation"]],
        ),
        (
            "official_instructional_fingerprinting_baseline_admitted",
            _build_official_baseline_gate(payloads["instructional_fingerprinting_official_admission"]),
            [paths["instructional_fingerprinting_official_admission"]],
        ),
        (
            "tpr_fpr_latency_ci",
            _build_ci_gate(payloads["budget_latency_ci"]),
            [paths["budget_latency_ci"]],
        ),
    ]

    gates = [
        _gate(
            name,
            passed,
            artifacts=[_rel(path, root) for path in artifact_paths],
            blockers=blockers,
            details=details,
        )
        for name, (passed, blockers, details), artifact_paths in gate_specs
    ]
    remaining_blockers = [
        f"{gate['gate']}:{blocker}"
        for gate in gates
        for blocker in _as_list(gate.get("blockers"))
    ]
    main_claim_allowed = all(gate["status"] == "passed" for gate in gates)
    apis_support = payloads["apis300_support"]
    student_manifest = payloads["student_training_manifest"]
    student_attribution = payloads["student_transfer_attribution"]
    return {
        "schema_version": SCHEMA_VERSION,
        "claim_role": "transfer_public_support_promotion_gate_not_evidence",
        "claim_boundary": "main_claim_requires_real_transfer_public_support_and_live_controls",
        "main_claim_allowed": main_claim_allowed,
        "overall_status": "passed" if main_claim_allowed else "blocked",
        "decision": "allow_main_claim" if main_claim_allowed else "block_main_claim",
        "gates": gates,
        "remaining_blockers": remaining_blockers,
        "promotion_contract": {
            "blocks_simulated_diagnostic_transfer_claims": True,
            "requires_transfer_families": sorted(REQUIRED_TRANSFER_FAMILIES),
            "requires_apis300_live_canonical": True,
            "requires_hard_decoy_96_per_class_live_survival": True,
            "requires_official_instructional_fingerprinting_baseline": True,
            "requires_baseline_null_owner_unwrapped_task_controls": sorted(REQUIRED_BASELINE_CONTROL_IDS),
            "requires_tpr_fpr_latency_ci": True,
        },
        "summaries": {
            "apis300_support": {
                "support_status": str(apis_support.get("support_status", "")),
                "source_run_id": str(apis_support.get("source_run_id", "")),
                "local_task_count": _safe_int(apis_support.get("local_task_count")),
                "local_task_target": _safe_int(apis_support.get("local_task_target")),
                "public_task_count": _safe_int(apis_support.get("public_task_count")),
                "public_task_target": _safe_int(apis_support.get("public_task_target")),
            },
            "student_transfer": {
                "manifest_claim_role": str(student_manifest.get("claim_role", "")),
                "attribution_claim_role": str(student_attribution.get("claim_role", "")),
                "manifest_evidence_scope": str(student_manifest.get("evidence_scope", "")),
                "attribution_evidence_scope": str(student_attribution.get("evidence_scope", "")),
                "training_launch_ready": bool(payloads["student_transfer_training_launch"].get("launch_ready", False)),
                "training_launch_families": sorted(_launch_training_families(payloads["student_transfer_training_launch"])),
            },
        },
        "artifacts": {name: _artifact(path, root) for name, path in paths.items()},
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the transfer/public-support promotion gate.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = build_gate(ROOT)
    if args.check:
        if not args.output.exists():
            raise SystemExit(f"missing transfer/public promotion gate: {args.output}")
        observed = json.loads(args.output.read_text(encoding="utf-8"))
        if observed != payload:
            raise SystemExit(f"stale transfer/public promotion gate: {args.output}")
        print(f"transfer/public promotion gate check passed: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
