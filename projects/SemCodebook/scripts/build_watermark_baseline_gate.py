from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "generated" / "watermark_baseline_gate.json"


@dataclass(frozen=True, slots=True)
class RequiredFile:
    role: str
    path: str


@dataclass(frozen=True, slots=True)
class BaselineGateSpec:
    name: str
    checkout_slug: str
    manifest_slug: str
    entrypoint: str
    support_smoke_command: tuple[str, ...]
    support_smoke_workdir: str
    required_files: tuple[RequiredFile, ...]
    entrypoint_smoke_args: tuple[str, ...] = ("--help",)
    main_table_smoke_command: tuple[str, ...] = ()
    main_table_smoke_workdir: str = "."


BASELINES: tuple[BaselineGateSpec, ...] = (
    BaselineGateSpec(
        name="KGW",
        checkout_slug="kgw-lm-watermarking",
        manifest_slug="kgw-lm-watermarking",
        entrypoint="demo_watermark.py",
        support_smoke_command=(
            "python",
            "-c",
            "from watermark_processor import WatermarkLogitsProcessor; print(WatermarkLogitsProcessor.__name__)",
        ),
        support_smoke_workdir=".",
        required_files=(
            RequiredFile("provenance_manifest", "third_party/upstream/kgw-lm-watermarking.json"),
            RequiredFile("docs", "external_checkout/kgw-lm-watermarking/README.md"),
            RequiredFile("env_spec", "external_checkout/kgw-lm-watermarking/requirements.txt"),
            RequiredFile("entrypoint", "external_checkout/kgw-lm-watermarking/demo_watermark.py"),
            RequiredFile("library_surface", "external_checkout/kgw-lm-watermarking/watermark_processor.py"),
            RequiredFile("task_smoke_adapter", "scripts/run_watermark_baseline_task_smoke.py"),
        ),
        main_table_smoke_command=(
            "python",
            "scripts/run_watermark_baseline_task_smoke.py",
            "--baseline",
            "KGW",
            "--task-id",
            "guard_loop_accumulator_python_positive_s01",
        ),
        main_table_smoke_workdir="../..",
    ),
    BaselineGateSpec(
        name="SWEET",
        checkout_slug="sweet-watermark",
        manifest_slug="sweet-watermark",
        entrypoint="main.py",
        support_smoke_command=("python", "-c", "import sweet; print(sweet.__name__)"),
        support_smoke_workdir=".",
        required_files=(
            RequiredFile("provenance_manifest", "third_party/upstream/sweet-watermark.json"),
            RequiredFile("docs", "external_checkout/sweet-watermark/README.md"),
            RequiredFile("entrypoint", "external_checkout/sweet-watermark/main.py"),
            RequiredFile("library_surface", "external_checkout/sweet-watermark/sweet.py"),
            RequiredFile("metric_entrypoint", "external_checkout/sweet-watermark/calculate_auroc_tpr.py"),
            RequiredFile("pipeline_script", "external_checkout/sweet-watermark/scripts/main/run_sweet_generation.sh"),
            RequiredFile("pipeline_script", "external_checkout/sweet-watermark/scripts/main/run_sweet_detection.sh"),
        ),
        main_table_smoke_command=(
            "python",
            "scripts/run_sweet_ewd_official_carrierstressbench.py",
            "--baseline",
            "SWEET",
            "--limit",
            "1",
        ),
        main_table_smoke_workdir="../..",
    ),
    BaselineGateSpec(
        name="STONE",
        checkout_slug="stone-watermarking",
        manifest_slug="stone-watermarking",
        entrypoint="stone_implementation/run.py",
        support_smoke_command=(
            "python",
            "-c",
            "import sys; sys.path.insert(0, 'stone_implementation'); "
            "from watermark.auto_watermark import STONEAutoWatermark; print(STONEAutoWatermark.__name__)",
        ),
        support_smoke_workdir=".",
        required_files=(
            RequiredFile("provenance_manifest", "third_party/upstream/stone-watermarking.json"),
            RequiredFile("docs", "external_checkout/stone-watermarking/README.md"),
            RequiredFile("env_spec", "external_checkout/stone-watermarking/stone.yaml"),
            RequiredFile("entrypoint", "external_checkout/stone-watermarking/stone_implementation/run.py"),
            RequiredFile("pipeline_script", "external_checkout/stone-watermarking/stone_implementation/run.sh"),
            RequiredFile(
                "correctness_eval",
                "external_checkout/stone-watermarking/stone_implementation/custom_evalplus/evalplus/pass_evaluation.sh",
            ),
            RequiredFile(
                "library_surface",
                "external_checkout/stone-watermarking/stone_implementation/watermark/auto_watermark.py",
            ),
            RequiredFile("task_smoke_adapter", "scripts/run_watermark_baseline_task_smoke.py"),
        ),
        main_table_smoke_command=(
            "python",
            "scripts/run_watermark_baseline_task_smoke.py",
            "--baseline",
            "STONE",
            "--task-id",
            "guard_loop_accumulator_python_positive_s01",
        ),
        main_table_smoke_workdir="../..",
    ),
    BaselineGateSpec(
        name="EWD",
        checkout_slug="ewd",
        manifest_slug="ewd",
        entrypoint="main.py",
        support_smoke_command=("python", "-c", "import watermark; print(watermark.__name__)"),
        support_smoke_workdir=".",
        required_files=(
            RequiredFile("provenance_manifest", "third_party/upstream/ewd.json"),
            RequiredFile("docs", "external_checkout/ewd/README.md"),
            RequiredFile("env_spec", "external_checkout/ewd/requirements.txt"),
            RequiredFile("entrypoint", "external_checkout/ewd/main.py"),
            RequiredFile("library_surface", "external_checkout/ewd/watermark.py"),
            RequiredFile("metric_entrypoint", "external_checkout/ewd/calculate_auroc_tpr.py"),
            RequiredFile("task_level_runner", "scripts/run_sweet_ewd_official_carrierstressbench.py"),
        ),
        main_table_smoke_command=(
            "python",
            "scripts/run_sweet_ewd_official_carrierstressbench.py",
            "--baseline",
            "EWD",
            "--limit",
            "1",
        ),
        main_table_smoke_workdir="../..",
    ),
)


def _relative(root: Path, path: Path) -> str:
    for base in (root, root.parent):
        try:
            return path.relative_to(base).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def _sanitize_detail(root: Path, text: str, *, limit: int = 700) -> str:
    cleaned = text.replace(str(root), "<repo>").replace(str(root).replace("\\", "/"), "<repo>")
    cleaned = cleaned.replace("\\", "/")
    return cleaned.strip()[:limit]


def _failure_audit_from_detail(detail: str) -> dict[str, object]:
    missing_modules = sorted(set(re.findall(r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]", detail)))
    syntax_errors = sorted(set(re.findall(r"SyntaxError: ([^\n]+)", detail)))
    if missing_modules:
        failure_kind = "missing_python_dependency"
        stable_summary = "missing_python_module:" + ",".join(missing_modules)
    elif syntax_errors:
        failure_kind = "python_syntax_error"
        stable_summary = "syntax_error:" + ";".join(syntax_errors)
    elif detail:
        failure_kind = "runtime_failure"
        stable_summary = detail.splitlines()[-1].strip()[:180]
    else:
        failure_kind = "no_failure_detail"
        stable_summary = ""
    return {
        "failure_kind": failure_kind,
        "stable_summary": stable_summary,
        "missing_python_modules": missing_modules,
        "syntax_errors": syntax_errors,
        "raw_detail_sha256": hashlib.sha256(detail.encode("utf-8")).hexdigest() if detail else "",
    }


def _json_dumps(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=True) + "\n"


def _syntax_check(path: Path) -> tuple[bool, str]:
    if not path.exists() or path.suffix != ".py":
        return path.exists(), "" if path.exists() else "entrypoint_missing"
    try:
        ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return False, f"syntax_error:{exc.msg}"
    return True, ""


def _format_command(command: tuple[str, ...]) -> str:
    return subprocess.list2cmdline(list(command))


def _smoke_status(
    root: Path,
    command: tuple[str, ...],
    *,
    cwd: Path,
    execute: bool,
    timeout_seconds: int,
    scope: str,
) -> dict[str, object]:
    cwd = cwd.resolve()
    payload: dict[str, object] = {
        "scope": scope,
        "command": _format_command(command) if command else "",
        "cwd": _relative(root, cwd),
        "executed": bool(execute and command),
        "ok": False,
        "status": "not_configured" if not command else "not_executed",
        "returncode": None,
        "detail": "",
    }
    if not command:
        return payload
    if not execute:
        return payload
    if not cwd.exists():
        payload.update({"status": "cwd_missing", "detail": _relative(root, cwd)})
        return payload
    resolved = tuple(sys.executable if item == "python" else item for item in command)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("PYTHONPYCACHEPREFIX", str(root / "artifacts" / "generated" / ".pycache_smoke"))
    try:
        completed = subprocess.run(
            resolved,
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        payload.update({"status": "missing_executable", "detail": str(exc.filename)})
        return payload
    except subprocess.TimeoutExpired:
        payload.update({"status": "timeout", "detail": f"timeout_after_seconds:{timeout_seconds}"})
        return payload

    raw_detail = completed.stderr.strip() or completed.stdout.strip()
    failure_audit = _failure_audit_from_detail(raw_detail) if completed.returncode != 0 else {
        "failure_kind": "",
        "stable_summary": "",
        "missing_python_modules": [],
        "syntax_errors": [],
        "raw_detail_sha256": hashlib.sha256(raw_detail.encode("utf-8")).hexdigest() if raw_detail else "",
    }
    payload.update(
        {
            "ok": completed.returncode == 0,
            "status": "passed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "detail": str(failure_audit["stable_summary"]) if completed.returncode != 0 else _sanitize_detail(root, raw_detail),
            "failure_audit": failure_audit,
        }
    )
    if completed.returncode == 0 and raw_detail:
        try:
            parsed = json.loads(raw_detail)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            payload["structured_evidence"] = parsed
    return payload


def _load_manifest(root: Path, spec: BaselineGateSpec) -> dict[str, object]:
    manifest_path = root / "third_party" / "upstream" / f"{spec.manifest_slug}.json"
    if not manifest_path.exists():
        return {"exists": False}
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "exists": True,
        "repo_url": str(payload.get("repo_url", "")),
        "pinned_commit": str(payload.get("pinned_commit", "")),
        "license_status": str(payload.get("license_status", "")),
        "redistributable": bool(payload.get("redistributable", False)),
        "integration_mode": str(payload.get("integration_mode", "")),
    }


def _stone_task_output_record_audit(payload: dict[str, object], summary: dict[str, object]) -> dict[str, object]:
    records = payload.get("records", [])
    if not isinstance(records, list):
        return {
            "record_schema_ok": False,
            "record_schema_blockers": ["records_not_list"],
            "unsupported_language_fail_closed_ok": False,
            "unsupported_language_count": 0,
            "fail_closed_record_count": 0,
            "official_pipeline_record_count": 0,
        }

    blockers: list[str] = []
    unsupported_count = 0
    fail_closed_count = 0
    official_pipeline_count = 0
    denominator_count = 0
    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, dict):
            blockers.append(f"record_{index}:not_object")
            continue
        task_id = str(raw_record.get("task_id", f"index_{index}"))
        pipeline_scope = str(raw_record.get("pipeline_scope", ""))
        official_supported = bool(raw_record.get("official_language_supported", False))
        unsupported = bool(raw_record.get("unsupported_language", False))
        fail_closed = bool(raw_record.get("fail_closed", False))
        denominator_included = bool(raw_record.get("main_table_denominator_included", False))
        decision = bool(raw_record.get("decision", False))
        uses_generation = bool(raw_record.get("uses_model_generation", False))
        abstain_reason = str(raw_record.get("abstain_reason", ""))
        decision_status = str(raw_record.get("decision_status", ""))

        if denominator_included:
            denominator_count += 1
        if fail_closed:
            fail_closed_count += 1
        if unsupported:
            unsupported_count += 1
        if bool(raw_record.get("official_pipeline_end_to_end", False)):
            official_pipeline_count += 1

        if not denominator_included:
            blockers.append(f"{task_id}:missing_main_table_denominator_included")
        if unsupported:
            expected_fail_closed = all(
                (
                    not official_supported,
                    fail_closed,
                    not decision,
                    not uses_generation,
                    pipeline_scope == "official_pipeline_fail_closed_unsupported_language",
                    decision_status == "fail_closed_unsupported_language",
                    bool(abstain_reason),
                )
            )
            if not expected_fail_closed:
                blockers.append(f"{task_id}:unsupported_language_not_fail_closed")
        elif fail_closed:
            expected_runtime_failure = all(
                (
                    official_supported,
                    not decision,
                    pipeline_scope == "official_pipeline_fail_closed_runtime_failure",
                    decision_status == "fail_closed_runtime_failure",
                    bool(abstain_reason),
                )
            )
            if not expected_runtime_failure:
                blockers.append(f"{task_id}:runtime_failure_not_fail_closed")
        else:
            expected_supported_pipeline = all(
                (
                    official_supported,
                    bool(raw_record.get("official_pipeline_end_to_end", False)),
                    uses_generation,
                    pipeline_scope == "official_generation_detection_pipeline",
                    decision_status in {"detected", "not_detected"},
                )
            )
            if not expected_supported_pipeline:
                blockers.append(f"{task_id}:supported_pipeline_schema_incomplete")
        if len(blockers) >= 20:
            blockers.append("record_schema_blocker_limit_reached")
            break

    summary_unsupported = int(summary.get("unsupported_language_count", -1) or 0)
    summary_fail_closed = int(summary.get("fail_closed_record_count", -1) or 0)
    if summary_unsupported != unsupported_count:
        blockers.append("summary_unsupported_language_count_mismatch")
    if summary_fail_closed != fail_closed_count:
        blockers.append("summary_fail_closed_record_count_mismatch")
    if denominator_count != len(records):
        blockers.append("not_all_records_included_in_main_table_denominator")

    return {
        "record_schema_ok": not blockers,
        "record_schema_blockers": blockers,
        "unsupported_language_fail_closed_ok": not any("unsupported_language_not_fail_closed" in item for item in blockers),
        "unsupported_language_count": unsupported_count,
        "fail_closed_record_count": fail_closed_count,
        "official_pipeline_record_count": official_pipeline_count,
        "main_table_denominator_count": denominator_count,
    }


def _official_task_output_record_audit(spec: BaselineGateSpec, payload: dict[str, object], summary: dict[str, object]) -> dict[str, object]:
    if spec.name == "STONE":
        return _stone_task_output_record_audit(payload, summary)
    records = payload.get("records", [])
    if not isinstance(records, list):
        return {
            "record_schema_ok": False,
            "record_schema_blockers": ["records_not_list"],
            "unsupported_language_fail_closed_ok": False,
            "unsupported_language_count": 0,
            "fail_closed_record_count": 0,
            "official_pipeline_record_count": 0,
            "main_table_denominator_count": 0,
        }
    blockers: list[str] = []
    official_pipeline_count = 0
    denominator_count = 0
    fail_closed_count = 0
    unsupported_count = 0
    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, dict):
            blockers.append(f"record_{index}:not_object")
            continue
        task_id = str(raw_record.get("task_id", f"index_{index}"))
        decision_status = str(raw_record.get("decision_status", ""))
        denominator_included = bool(raw_record.get("main_table_denominator_included", False))
        fail_closed = bool(raw_record.get("fail_closed", False))
        unsupported = bool(raw_record.get("unsupported_language", False))
        if bool(raw_record.get("official_pipeline_end_to_end", False)):
            official_pipeline_count += 1
        if denominator_included:
            denominator_count += 1
        if fail_closed:
            fail_closed_count += 1
        if unsupported:
            unsupported_count += 1
        if not bool(raw_record.get("official_baseline", False)):
            blockers.append(f"{task_id}:official_baseline_missing")
        if not bool(raw_record.get("official_task_level_output", False)):
            blockers.append(f"{task_id}:official_task_level_output_missing")
        if not denominator_included:
            blockers.append(f"{task_id}:missing_main_table_denominator_included")
        if fail_closed:
            if not str(raw_record.get("abstain_reason", "")):
                blockers.append(f"{task_id}:fail_closed_without_abstain_reason")
            if bool(raw_record.get("decision", False)):
                blockers.append(f"{task_id}:fail_closed_record_detected")
        elif decision_status not in {"detected", "not_detected"}:
            blockers.append(f"{task_id}:decision_status_missing_or_invalid")
        if str(raw_record.get("pipeline_scope", "")) != "official_generation_detection_pipeline":
            blockers.append(f"{task_id}:pipeline_scope_not_official_generation_detection")
        if len(blockers) >= 20:
            blockers.append("record_schema_blocker_limit_reached")
            break
    return {
        "record_schema_ok": not blockers,
        "record_schema_blockers": blockers,
        "unsupported_language_fail_closed_ok": not any("unsupported" in item and "fail_closed" in item for item in blockers),
        "unsupported_language_count": unsupported_count,
        "fail_closed_record_count": fail_closed_count,
        "official_pipeline_record_count": official_pipeline_count,
        "main_table_denominator_count": denominator_count,
    }


def _official_task_output(root: Path, spec: BaselineGateSpec) -> dict[str, object]:
    slug = spec.name.lower()
    path = root / "artifacts" / "generated" / "baselines" / f"{slug}_official_carrierstressbench_task_records.json"
    if not path.exists():
        return {"present": False, "path": _relative(root, path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"present": True, "path": _relative(root, path), "ready": False, "blocker": "invalid_json"}
    summary = payload.get("summary", {})
    summary = summary if isinstance(summary, dict) else {}
    record_count = int(summary.get("record_count", 0) or 0)
    target_count = int(summary.get("target_record_count", 0) or 0)
    record_audit = _official_task_output_record_audit(spec, payload, summary)
    ready = all(
        (
            str(payload.get("baseline", "")) == spec.name,
            bool(payload.get("official_baseline", False)),
            bool(payload.get("official_task_level_output", False)),
            bool(payload.get("official_generation_detection_pipeline", False)),
            not bool(payload.get("upstream_core_logic_modified", True)),
            record_count >= target_count,
            target_count >= 600,
            bool(record_audit.get("record_schema_ok", False)),
        )
    )
    return {
        "present": True,
        "path": _relative(root, path),
        "ready": ready,
        "record_count": record_count,
        "target_record_count": target_count,
        "task_pass_count": int(summary.get("task_pass_count", 0) or 0),
        "detection_count": int(summary.get("detection_count", 0) or 0),
        "unsupported_language_count": int(record_audit.get("unsupported_language_count", 0) or 0),
        "fail_closed_record_count": int(record_audit.get("fail_closed_record_count", 0) or 0),
        "official_pipeline_record_count": int(record_audit.get("official_pipeline_record_count", 0) or 0),
        "main_table_denominator_count": int(record_audit.get("main_table_denominator_count", record_count) or 0),
        "record_schema_ok": bool(record_audit.get("record_schema_ok", False)),
        "unsupported_language_fail_closed_ok": bool(record_audit.get("unsupported_language_fail_closed_ok", False)),
        "record_schema_blockers": list(record_audit.get("record_schema_blockers", [])),
        "generation_model": str(payload.get("generation_model", "")),
        "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "blocker": ""
        if ready
        else "official_task_output_not_complete_or_not_pipeline_or_fail_closed_schema",
    }


def _main_table_smoke_evidence_ok(spec: BaselineGateSpec, smoke: dict[str, object]) -> bool:
    if not bool(smoke.get("ok", False)):
        return False
    evidence = smoke.get("structured_evidence")
    if not isinstance(evidence, dict):
        return False
    if str(evidence.get("schema_version", "")) != "semcodebook_baseline_task_smoke_v1":
        return False
    return all(
        (
            str(evidence.get("baseline", "")) == spec.name,
            str(evidence.get("official_checkout_slug", "")) == spec.checkout_slug,
            bool(evidence.get("task_level_end_to_end", False)),
            bool(evidence.get("official_pipeline_end_to_end", False)),
            str(evidence.get("pipeline_scope", "")) == "official_generation_detection_pipeline",
            bool(evidence.get("task_tests_passed", False)),
            not bool(evidence.get("negative_control", True)),
            not bool(evidence.get("claim_bearing", True)),
            not bool(evidence.get("uses_provider", True)),
            bool(evidence.get("uses_model_generation", False)),
            not bool(evidence.get("official_core_logic_modified", True)),
            bool(evidence.get("decision", False)),
        )
    )


def _required_file_payload(root: Path, spec: BaselineGateSpec) -> list[dict[str, object]]:
    return [
        {
            "role": item.role,
            "path": item.path,
            "exists": (root / item.path).exists(),
        }
        for item in spec.required_files
    ]


def _status_for_record(
    *,
    spec: BaselineGateSpec,
    required_ok: bool,
    entrypoint_exists: bool,
    entrypoint_parse_ok: bool,
    main_table_smoke: dict[str, object],
) -> tuple[str, str, bool]:
    if (
        required_ok
        and entrypoint_exists
        and entrypoint_parse_ok
        and _main_table_smoke_evidence_ok(spec, main_table_smoke)
    ):
        return "main_table_runnable", "task_level_main_table_smoke_passed", True
    if not required_ok:
        return "citation_or_support_only", "missing_required_files", False
    if not entrypoint_exists:
        return "citation_or_support_only", "entrypoint_missing", False
    if not entrypoint_parse_ok:
        return "citation_or_support_only", "entrypoint_parse_failed", False
    if not main_table_smoke.get("command"):
        return "citation_or_support_only", "no_task_level_main_table_smoke_configured", False
    if main_table_smoke.get("ok") and not _main_table_smoke_evidence_ok(spec, main_table_smoke):
        return "citation_or_support_only", "task_level_main_table_smoke_missing_required_evidence", False
    return "citation_or_support_only", "task_level_main_table_smoke_failed", False


def _baseline_payload(
    root: Path,
    spec: BaselineGateSpec,
    *,
    execute_smoke: bool,
    timeout_seconds: int,
) -> dict[str, object]:
    checkout = root / "external_checkout" / spec.checkout_slug
    entrypoint = checkout / spec.entrypoint
    required_files = _required_file_payload(root, spec)
    missing_required_files = [str(item["path"]) for item in required_files if not bool(item["exists"])]
    entrypoint_parse_ok, parse_detail = _syntax_check(entrypoint)
    entrypoint_smoke_command = ("python", spec.entrypoint, *spec.entrypoint_smoke_args)
    entrypoint_smoke = _smoke_status(
        root,
        entrypoint_smoke_command,
        cwd=checkout,
        execute=execute_smoke,
        timeout_seconds=timeout_seconds,
        scope="official_entrypoint_launch",
    )
    support_smoke = _smoke_status(
        root,
        spec.support_smoke_command,
        cwd=checkout / spec.support_smoke_workdir,
        execute=execute_smoke,
        timeout_seconds=timeout_seconds,
        scope="support_library_surface",
    )
    main_table_smoke = _smoke_status(
        root,
        spec.main_table_smoke_command,
        cwd=checkout / spec.main_table_smoke_workdir,
        execute=execute_smoke,
        timeout_seconds=timeout_seconds,
        scope="task_level_end_to_end",
    )
    status, reason, main_table_admissible = _status_for_record(
        spec=spec,
        required_ok=not missing_required_files,
        entrypoint_exists=entrypoint.exists(),
        entrypoint_parse_ok=entrypoint_parse_ok,
        main_table_smoke=main_table_smoke,
    )
    official_task_output = _official_task_output(root, spec)
    if (
        not missing_required_files
        and entrypoint.exists()
        and entrypoint_parse_ok
        and bool(official_task_output.get("ready", False))
    ):
        status = "main_table_runnable"
        reason = "official_carrierstressbench_task_output_passed"
        main_table_admissible = True
    dependency_blockers = sorted(
        {
            str(module)
            for smoke in (entrypoint_smoke, support_smoke, main_table_smoke)
            for module in (
                smoke.get("failure_audit", {}).get("missing_python_modules", [])
                if isinstance(smoke.get("failure_audit"), dict)
                else []
            )
        }
    )
    main_table_smoke_evidence_ok = _main_table_smoke_evidence_ok(spec, main_table_smoke)
    official_task_output_ready = bool(official_task_output.get("ready", False))
    failure_audit = {
        "admission_tier": "main_table" if main_table_admissible else "support_or_citation_only",
        "demotion_reason": "" if main_table_admissible else reason,
        "dependency_blockers": dependency_blockers,
        "required_file_blockers": missing_required_files,
        "task_level_surface_present": bool(spec.main_table_smoke_command),
        "task_level_smoke_status": main_table_smoke.get("status"),
        "task_level_smoke_evidence_ok": main_table_smoke_evidence_ok,
        "official_task_output_ready": official_task_output_ready,
        "official_task_output_schema_ok": bool(official_task_output.get("record_schema_ok", False)),
        "admission_evidence_ok": bool(main_table_smoke_evidence_ok or official_task_output_ready),
        "official_entrypoint_launch_status": entrypoint_smoke.get("status"),
        "support_library_surface_status": support_smoke.get("status"),
        "upstream_core_logic_modified": False,
        "comparator_or_official": "official_baseline_candidate",
        "claim_policy": (
            "This row is support/citation only until a task-level end-to-end smoke over the SemCodebook "
            "canonical task contract passes without editing upstream core logic."
        )
        if not main_table_admissible
        else "This row is eligible for main-table smoke expansion over the frozen canonical task scope.",
    }
    return {
        "baseline": spec.name,
        "checkout_slug": spec.checkout_slug,
        "manifest": _load_manifest(root, spec),
        "required_files": required_files,
        "missing_required_files": missing_required_files,
        "entrypoint": {
            "path": _relative(root, entrypoint),
            "exists": entrypoint.exists(),
            "parse_ok": entrypoint_parse_ok,
            "parse_detail": parse_detail,
        },
        "smoke": {
            "entrypoint": entrypoint_smoke,
            "support": support_smoke,
            "main_table": main_table_smoke,
        },
        "official_task_output": official_task_output,
        "status": status,
        "status_reason": reason,
        "main_table_admissible": main_table_admissible,
        "failure_audit": failure_audit,
    }


def build_payload(
    root: str | Path = ROOT,
    *,
    execute_smoke: bool = True,
    timeout_seconds: int = 60,
) -> dict[str, object]:
    root_path = Path(root).resolve()
    baselines = [
        _baseline_payload(root_path, spec, execute_smoke=execute_smoke, timeout_seconds=timeout_seconds)
        for spec in BASELINES
    ]
    main_table_admissible = [item["baseline"] for item in baselines if bool(item["main_table_admissible"])]
    return {
        "schema_version": "semcodebook_watermark_baseline_gate_v1",
        "artifact_role": "watermark_baseline_runnability_gate",
        "generated_by": "scripts/build_watermark_baseline_gate.py",
        "policy": (
            "A baseline is main-table admissible only when required files and the official entrypoint are present "
            "and a task-level end-to-end smoke passes. Entrypoint launch or library-surface smoke is citation/support "
            "evidence only."
        ),
        "smoke_executed": bool(execute_smoke),
        "baseline_order": [spec.name for spec in BASELINES],
        "baselines": baselines,
        "summary": {
            "baseline_count": len(baselines),
            "main_table_admissible_count": len(main_table_admissible),
            "main_table_admissible_baselines": main_table_admissible,
            "citation_or_support_only_count": sum(
                1 for item in baselines if str(item["status"]) == "citation_or_support_only"
            ),
            "entrypoint_smoke_pass_count": sum(1 for item in baselines if bool(item["smoke"]["entrypoint"]["ok"])),
            "support_smoke_pass_count": sum(1 for item in baselines if bool(item["smoke"]["support"]["ok"])),
            "missing_required_file_count": sum(len(item["missing_required_files"]) for item in baselines),
        },
    }


def write_payload(payload: dict[str, object], output: str | Path = ARTIFACT) -> Path:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_json_dumps(payload), encoding="utf-8")
    return output_path


def check_payload(payload: dict[str, object], output: str | Path = ARTIFACT) -> None:
    output_path = Path(output)
    expected = _json_dumps(payload)
    if not output_path.exists():
        raise SystemExit(f"missing artifact: {output_path}")
    observed = output_path.read_text(encoding="utf-8")
    if observed != expected:
        raise SystemExit(f"stale artifact: {output_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="SemCodebook repository root.")
    parser.add_argument(
        "--output",
        default="",
        help="Output JSON path. Defaults to workspace artifacts/generated/watermark_baseline_gate.json.",
    )
    parser.add_argument("--check", action="store_true", help="Validate that the output artifact matches the freshly built payload.")
    parser.add_argument("--no-smoke", action="store_true", help="Skip smoke command execution.")
    parser.add_argument("--timeout-seconds", type=int, default=60, help="Per-smoke timeout.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    output = Path(args.output) if args.output else root / "artifacts" / "generated" / "watermark_baseline_gate.json"
    payload = build_payload(root, execute_smoke=not args.no_smoke, timeout_seconds=args.timeout_seconds)
    if args.check:
        check_payload(payload, output)
        print(json.dumps({"status": "passed", "artifact": _relative(root, output)}, indent=2, ensure_ascii=True))
        return
    written = write_payload(payload, output)
    print(_json_dumps(payload), end="")
    print(json.dumps({"wrote": _relative(root, written)}, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
