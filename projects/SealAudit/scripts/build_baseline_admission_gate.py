from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT


DEFAULT_OUTPUT = ARTIFACTS / "baseline_admission_gate.json"
INSTRUCTIONAL_BASELINE = "Instructional Fingerprinting"
OFFICIAL_POSTMARK_BASELINE = "PostMark Official Detector"
MIN_OFFICIAL_TASK_RECORDS = 320


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _add(blockers: list[str], blocker: str) -> None:
    if blocker and blocker not in blockers:
        blockers.append(blocker)


def _baseline_support_artifact(root: Path) -> dict[str, Any]:
    path = root / "artifacts" / "generated" / "baselines" / "instructional_fingerprinting_task_records.json"
    payload = _load_json(path)
    summary = payload.get("summary", {})
    summary = summary if isinstance(summary, dict) else {}
    records = _list(payload.get("records"))
    claim_role = str(payload.get("claim_role", "")).strip()
    official_trained_output = (
        bool(payload.get("official_trained_output", False))
        or "official_trained_output" in claim_role
        and "not_official_trained_output" not in claim_role
    )
    return {
        "path": "artifacts/generated/baselines/instructional_fingerprinting_task_records.json",
        "present": path.exists(),
        "baseline": str(payload.get("baseline", INSTRUCTIONAL_BASELINE)).strip() or INSTRUCTIONAL_BASELINE,
        "claim_role": claim_role,
        "task_truth_scope": str(payload.get("task_truth_scope", "")).strip(),
        "task_execution_mode": str(payload.get("task_execution_mode", "")).strip(),
        "record_count": len(records) or _as_int(summary.get("task_level_record_count")),
        "task_target_count": _as_int(summary.get("task_level_task_target_count")),
        "task_level_evidence_ready": bool(summary.get("task_level_evidence_ready", False)),
        "official_trained_output": official_trained_output,
        "main_table_admissible": False,
        "admission_role": "support_control_only_not_official_main_table_baseline",
    }


def _official_task_level_baseline_artifacts(root: Path) -> list[dict[str, Any]]:
    baselines_dir = root / "artifacts" / "generated" / "baselines"
    if not baselines_dir.exists():
        return []
    admitted: list[dict[str, Any]] = []
    for path in sorted(baselines_dir.glob("*_task_records.json")):
        payload = _load_json(path)
        summary = payload.get("summary", {})
        summary = summary if isinstance(summary, dict) else {}
        records = _list(payload.get("records"))
        official = bool(payload.get("official_baseline", False))
        task_output = bool(payload.get("official_task_level_output", False))
        main_table = bool(payload.get("main_table_admissible", False))
        official_resource_verified = bool(payload.get("official_resource_provenance_verified", False))
        record_count = len(records) or _as_int(summary.get("task_level_record_count"))
        target_count = _as_int(summary.get("task_level_task_target_count")) or record_count
        if not (official and task_output and main_table and official_resource_verified):
            continue
        if record_count <= 0 or record_count < target_count:
            continue
        admitted.append(
            {
                "baseline": str(payload.get("baseline", path.stem)).strip() or path.stem,
                "path": str(path.relative_to(root)).replace("\\", "/"),
                "record_count": record_count,
                "task_target_count": target_count,
                "official_repo_url": str(payload.get("official_repo_url", "")),
                "official_entrypoint": str(payload.get("official_entrypoint", "")),
                "official_resource_provenance_verified": official_resource_verified,
                "scope": str(payload.get("task_truth_scope", "")),
            }
        )
    return admitted


def _artifact_backed_control_artifacts(root: Path) -> list[dict[str, Any]]:
    baselines_dir = root / "artifacts" / "generated" / "baselines"
    if not baselines_dir.exists():
        return []
    admitted: list[dict[str, Any]] = []
    for path in sorted(baselines_dir.glob("*_task_records.json")):
        payload = _load_json(path)
        summary = payload.get("summary", {})
        summary = summary if isinstance(summary, dict) else {}
        records = _list(payload.get("records"))
        claim_role = str(payload.get("claim_role", "")).strip()
        official = bool(payload.get("official_baseline", False))
        task_ready = bool(summary.get("task_level_evidence_ready", False))
        control_role = "control" in claim_role and "not_official" in claim_role
        record_count = len(records) or _as_int(summary.get("task_level_record_count"))
        target_count = _as_int(summary.get("task_level_task_target_count")) or record_count
        if official or not control_role or not task_ready:
            continue
        if record_count <= 0 or record_count < target_count:
            continue
        admitted.append(
            {
                "control": str(payload.get("baseline", path.stem)).strip() or path.stem,
                "path": str(path.relative_to(root)).replace("\\", "/"),
                "record_count": record_count,
                "task_target_count": target_count,
                "claim_role": claim_role,
                "scope": str(payload.get("task_truth_scope", "")),
                "task_execution_mode": str(payload.get("task_execution_mode", "")),
                "admission_role": "artifact_backed_control_not_official_baseline",
            }
        )
    return admitted


def build_gate(root: Path = ROOT) -> dict[str, Any]:
    artifacts = root / "artifacts" / "generated"
    aggregate = _load_json(artifacts / "aggregate_results.json")
    executable = _load_json(artifacts / "executable_adapter_conjunction.json")
    blockers: list[str] = []

    baseline_promotion = aggregate.get("baseline_promotion", {})
    baseline_promotion = baseline_promotion if isinstance(baseline_promotion, dict) else {}
    aggregate_main_table = [str(item).strip() for item in _list(baseline_promotion.get("main_table")) if str(item).strip()]
    support_controls = [
        str(item).strip() for item in _list(baseline_promotion.get("support_controls")) if str(item).strip()
    ]
    citation_only = [str(item).strip() for item in _list(baseline_promotion.get("citation_only")) if str(item).strip()]

    baseline_artifact = _baseline_support_artifact(root)
    official_artifacts = _official_task_level_baseline_artifacts(root)
    control_artifacts = _artifact_backed_control_artifacts(root)
    artifact_task_evidence_count = sum(_as_int(item.get("record_count")) for item in official_artifacts)
    official_main_table_count = len(official_artifacts)
    main_table_baseline_count = len(official_artifacts)
    baseline_task_evidence_count = artifact_task_evidence_count
    artifact_control_count = len(control_artifacts)
    artifact_control_task_evidence_count = sum(_as_int(item.get("record_count")) for item in control_artifacts)
    aggregate_control_count = _as_int(aggregate.get("main_table_control_count"))
    main_table_control_count = max(aggregate_control_count, artifact_control_count)
    artifact_main_table = [str(item["baseline"]) for item in official_artifacts]
    main_table = list(dict.fromkeys(artifact_main_table))
    aggregate_unbacked_main_table = [name for name in aggregate_main_table if name not in artifact_main_table]

    if official_main_table_count <= 0 or main_table_baseline_count <= 0 or not main_table:
        _add(blockers, "official_main_table_runnable_baseline_missing")
    if baseline_task_evidence_count <= 0:
        _add(blockers, "main_table_baseline_task_evidence_missing")
    if 0 < baseline_task_evidence_count < MIN_OFFICIAL_TASK_RECORDS:
        _add(blockers, f"main_table_baseline_task_evidence_below_{MIN_OFFICIAL_TASK_RECORDS}")
    if official_main_table_count <= 0 and baseline_artifact["present"] and not baseline_artifact["official_trained_output"]:
        _add(blockers, "instructional_fingerprinting_support_only_no_official_trained_output")
    if official_main_table_count <= 0 and support_controls:
        _add(blockers, "support_controls_do_not_clear_official_baseline_gate")
    for name in aggregate_unbacked_main_table:
        _add(blockers, f"aggregate_main_table_baseline_not_artifact_backed:{name}")
    if main_table_control_count < 3:
        _add(blockers, "artifact_backed_control_count_below_3")

    executable_controls = {}
    controls = executable.get("baseline_controls", {})
    if isinstance(controls, dict):
        executable_controls = {
            "control_count": _as_int(controls.get("control_count")),
            "claim_boundary": "deterministic_controls_are_controls_not_official_baselines",
        }

    return {
        "schema_version": "sealaudit_baseline_admission_gate_v1",
        "project": "SealAudit",
        "status": "passed" if not blockers else "blocked",
        "claim_role": "baseline_admission_audit_not_claim_bearing",
        "main_table_baseline_admission_allowed": not blockers,
        "official_main_table_baseline_count": official_main_table_count,
        "main_table_baseline_count": main_table_baseline_count,
        "baseline_task_evidence_count": baseline_task_evidence_count,
        "minimum_official_task_records": MIN_OFFICIAL_TASK_RECORDS,
        "main_table_control_count": main_table_control_count,
        "artifact_backed_control_count": artifact_control_count,
        "artifact_backed_control_task_evidence_count": artifact_control_task_evidence_count,
        "main_table_baselines": main_table,
        "aggregate_main_table_baselines": aggregate_main_table,
        "aggregate_unbacked_main_table_baselines": aggregate_unbacked_main_table,
        "official_task_level_baseline_artifacts": official_artifacts,
        "artifact_backed_control_artifacts": control_artifacts,
        "support_controls": support_controls,
        "citation_only": citation_only,
        "instructional_fingerprinting": baseline_artifact,
        "executable_controls": executable_controls,
        "policy": (
            "Only official end-to-end trained/inference baselines with task-level provenance may enter "
            "the main table. Template adapters and deterministic local controls remain support/control rows."
        ),
        "blockers": blockers,
        "first_blocker": blockers[0] if blockers else "",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    payload = build_gate(root)
    if args.check and output.exists():
        current = _load_json(output)
        if current != payload:
            raise SystemExit(f"stale baseline admission gate: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "blockers": payload["blockers"], "gate": str(output)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
