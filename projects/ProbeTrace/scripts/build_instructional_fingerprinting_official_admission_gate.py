from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT


SCHEMA_VERSION = "probetrace_instructional_fingerprinting_official_admission_gate_v1"
DEFAULT_OUTPUT = ARTIFACTS / "instructional_fingerprinting_official_admission_gate.json"
CHECKOUT = ROOT / "external_checkout" / "instructional-fingerprinting"
PUBLISH_TRUTH = ARTIFACTS / "baselines" / "instructional_fingerprinting_publish_truth.json"
TASK_EVIDENCE = ARTIFACTS / "baselines" / "instructional_fingerprinting_task_evidence.json"
TASK_LIVE = ARTIFACTS / "baselines" / "instructional_fingerprinting_task_live.json"
REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "templates/barebone.json",
    "pipeline_adapter.py",
    "inference.py",
    "report_eval.py",
)
MIN_TASK_RECORDS = 60


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return str(path)


def _git_value(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(CHECKOUT), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


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


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("records", [])
    return [dict(item) for item in rows if isinstance(item, dict)] if isinstance(rows, list) else []


def _task_evidence_contract(evidence: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    records = _records(evidence)
    live_records = _records(live)
    task_record_count = max(
        _safe_int(evidence.get("task_record_count")),
        _safe_int(evidence.get("task_level_record_count")),
        len(records),
    )
    live_record_count = max(_safe_int(live.get("task_record_count")), _safe_int(live.get("task_level_record_count")), len(live_records))
    if task_record_count < MIN_TASK_RECORDS:
        blockers.append(f"if_task_records_below_{MIN_TASK_RECORDS}:{task_record_count}")
    if live_record_count < MIN_TASK_RECORDS:
        blockers.append(f"if_live_task_records_below_{MIN_TASK_RECORDS}:{live_record_count}")
    if str(evidence.get("provider_mode", "")).strip().lower() != "live":
        blockers.append("if_task_evidence_provider_mode_not_live")
    if str(evidence.get("task_level_execution_mode", "")).strip() != "official_template_black_box_task_adapter":
        blockers.append("if_task_evidence_not_official_template_adapter")
    if not bool(evidence.get("task_level_evidence_ready", False)):
        blockers.append("if_task_evidence_ready_false")
    if _safe_float(evidence.get("task_level_task_coverage_rate")) < 1.0:
        blockers.append("if_task_coverage_below_one")
    if _safe_int(evidence.get("task_level_nonempty_response_count")) < MIN_TASK_RECORDS:
        blockers.append("if_nonempty_response_count_below_minimum")
    if _safe_int(evidence.get("task_level_compile_ok_count")) < MIN_TASK_RECORDS:
        blockers.append("if_compile_ok_count_below_minimum")
    if _safe_int(evidence.get("task_level_pass_ok_count")) < MIN_TASK_RECORDS:
        blockers.append("if_pass_ok_count_below_minimum")
    missing_hash_rows = [
        str(item.get("task_id") or index)
        for index, item in enumerate(records[:MIN_TASK_RECORDS])
        if not str(item.get("raw_code_hash") or item.get("normalized_code_hash") or item.get("output_hash") or "").strip()
    ]
    if missing_hash_rows:
        blockers.append(f"if_task_rows_missing_output_hash:{len(missing_hash_rows)}")
    return {
        "status": "passed" if not blockers else "blocked",
        "blockers": blockers,
        "task_record_count": task_record_count,
        "live_record_count": live_record_count,
        "activation_count": _safe_int(evidence.get("task_level_activated_count")),
        "activation_rate": _safe_float(evidence.get("task_level_activation_rate")),
        "compile_ok_rate": _safe_float(evidence.get("task_level_compile_ok_rate")),
        "pass_ok_rate": _safe_float(evidence.get("task_level_pass_ok_rate")),
        "policy": (
            "Instructional Fingerprinting is admitted as an official runnable baseline only for its "
            "official-template task adapter surface. Low activation is a result, not grounds for demotion "
            "or threshold relaxation."
        ),
    }


def build_gate(root: Path = ROOT) -> dict[str, Any]:
    publish = _load_json(PUBLISH_TRUTH)
    evidence = _load_json(TASK_EVIDENCE)
    live = _load_json(TASK_LIVE)
    required_files = [
        {"path": f"external_checkout/instructional-fingerprinting/{item}", "exists": (CHECKOUT / item).exists()}
        for item in REQUIRED_FILES
    ]
    missing_files = [item["path"] for item in required_files if not item["exists"]]
    dirty_status = _git_value("status", "--porcelain")
    dirty_lines = [line for line in dirty_status.splitlines() if line.strip()]
    core_diff = _git_value("diff", "--name-only", "HEAD", "--", *REQUIRED_FILES)
    core_diff_files = [line.strip() for line in core_diff.splitlines() if line.strip()]
    evidence_contract = _task_evidence_contract(evidence, live)

    blockers: list[str] = []
    if not CHECKOUT.exists():
        blockers.append("if_official_checkout_missing")
    blockers.extend(f"if_required_file_missing:{item}" for item in missing_files)
    if core_diff_files:
        blockers.append("if_official_core_logic_modified")
    if publish.get("status") != "runnable":
        blockers.append("if_publish_truth_not_runnable")
    if str(publish.get("provider_mode", "")).strip().lower() != "live":
        blockers.append("if_publish_truth_provider_mode_not_live")
    if not bool(publish.get("main_table_admissible", False)):
        blockers.append("if_publish_truth_not_main_table_admissible")
    if _safe_int(publish.get("task_record_count")) < MIN_TASK_RECORDS:
        blockers.append("if_publish_truth_task_record_count_below_minimum")
    blockers.extend(evidence_contract["blockers"])

    admitted = not blockers
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "official_baseline_admission_gate_not_task_result",
        "baseline": "Instructional Fingerprinting",
        "baseline_id": "instructional-fingerprinting",
        "official_checkout": _rel(CHECKOUT),
        "official_commit": _git_value("rev-parse", "HEAD"),
        "official_core_unmodified": not core_diff_files,
        "dirty_status_allowed": not dirty_lines,
        "dirty_status": dirty_lines[:40],
        "official_core_diff_files": core_diff_files,
        "required_files": required_files,
        "source_artifacts": {
            "publish_truth": {"path": _rel(PUBLISH_TRUTH), "exists": PUBLISH_TRUTH.exists(), "sha256": _sha256(PUBLISH_TRUTH)},
            "task_evidence": {"path": _rel(TASK_EVIDENCE), "exists": TASK_EVIDENCE.exists(), "sha256": _sha256(TASK_EVIDENCE)},
            "task_live": {"path": _rel(TASK_LIVE), "exists": TASK_LIVE.exists(), "sha256": _sha256(TASK_LIVE)},
        },
        "task_evidence_contract": evidence_contract,
        "official_main_table_admissible": admitted,
        "status": "passed" if admitted else "blocked",
        "blockers": blockers,
        "claim_policy": (
            "This gate admits the official baseline implementation surface only. It does not convert weak "
            "activation into a strong comparator, and it never satisfies student-transfer evidence."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = build_gate(ROOT)
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if args.check:
        if not args.output.exists():
            raise SystemExit(f"missing official IF admission gate: {args.output}")
        if args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"stale official IF admission gate: {args.output}")
        if payload["status"] != "passed":
            raise SystemExit(json.dumps({"status": payload["status"], "blockers": payload["blockers"]}, ensure_ascii=True))
        print(f"official IF admission gate check passed: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
