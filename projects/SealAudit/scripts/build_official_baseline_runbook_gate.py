from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT


SCHEMA_VERSION = "sealaudit_official_baseline_runbook_gate_v1"
DEFAULT_OUTPUT = ARTIFACTS / "official_baseline_runbook_gate.json"
REQUIRED_BASELINES = ("PostMark", "DuFFin", "Instructional Fingerprinting")
REQUIRED_CASE_COUNT = 320
OFFICIAL_OUTPUT_FILENAMES = {
    "PostMark": "postmark_official_task_records.json",
    "DuFFin": "duffin_official_task_records.json",
    "Instructional Fingerprinting": "instructional_fingerprinting_official_task_records.json",
}
OFFICIAL_RUN_COMMANDS = {
    "PostMark": (
        "python scripts/run_postmark_official_task_records.py "
        "--case-manifest benchmarks/watermark_backdoorbench_v2_cases.json "
        "--output artifacts/generated/official_baseline_outputs/postmark_official_task_records.json"
    ),
    "DuFFin": (
        "python scripts/run_duffin_official_task_records.py "
        "--case-manifest benchmarks/watermark_backdoorbench_v2_cases.json "
        "--output artifacts/generated/official_baseline_outputs/duffin_official_task_records.json"
    ),
    "Instructional Fingerprinting": (
        "python scripts/run_instructional_fingerprinting_official_task_records.py "
        "--case-manifest benchmarks/watermark_backdoorbench_v2_cases.json "
        "--output artifacts/generated/official_baseline_outputs/"
        "instructional_fingerprinting_official_task_records.json"
    ),
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _probe(command: list[str], *, timeout: int = 20) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        return {"ok": False, "status": "missing_executable", "command": " ".join(command), "detail": str(exc.filename or "")}
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "timeout", "command": " ".join(command), "detail": f"timeout_after_seconds:{timeout}"}
    detail = (completed.stdout.strip() or completed.stderr.strip()).splitlines()
    return {
        "ok": completed.returncode == 0,
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "command": " ".join(command),
        "detail": "; ".join(line[:180] for line in detail[:4]),
    }


def _bridge_by_baseline(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    bridges = manifest.get("bridges", [])
    return {
        str(item.get("baseline", "")).strip(): dict(item)
        for item in bridges
        if isinstance(item, dict) and str(item.get("baseline", "")).strip()
    } if isinstance(bridges, list) else {}


def _official_output_summary(root: Path, baseline: str) -> dict[str, Any]:
    output_dir = root / "artifacts" / "generated" / "official_baseline_outputs"
    candidates = sorted(output_dir.glob(f"{baseline.lower().replace(' ', '_')}*.json*")) if output_dir.exists() else []
    records = 0
    claim_bearing = False
    official_core_unmodified = False
    artifact_paths: list[str] = []
    for path in candidates:
        artifact_paths.append(_rel(path))
        if path.suffix == ".jsonl":
            try:
                records += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
            except OSError:
                pass
            continue
        payload = _load_json(path)
        rows = payload.get("records", [])
        if isinstance(rows, list):
            records += len(rows)
        claim_bearing = claim_bearing or bool(payload.get("claim_bearing", False)) or payload.get("claim_role") == "official_baseline_task_level_evidence"
        official_core_unmodified = official_core_unmodified or bool(payload.get("official_core_unmodified", False))
    return {
        "expected_artifact": _rel(output_dir / OFFICIAL_OUTPUT_FILENAMES.get(baseline, f"{baseline.lower()}_official_task_records.json")),
        "artifact_count": len(candidates),
        "artifacts": artifact_paths,
        "record_count": records,
        "claim_bearing": claim_bearing,
        "official_core_unmodified": official_core_unmodified,
        "admissible": records >= REQUIRED_CASE_COUNT and claim_bearing and official_core_unmodified,
    }


def _run_contract(baseline: str, bridge: dict[str, Any], output: dict[str, Any], resource_blockers: list[str]) -> dict[str, Any]:
    return {
        "baseline": baseline,
        "official_command": OFFICIAL_RUN_COMMANDS.get(baseline, ""),
        "official_run_template_from_bridge": str(bridge.get("official_run_template", "")),
        "expected_output_artifact": output.get("expected_artifact"),
        "required_case_count": REQUIRED_CASE_COUNT,
        "requires_unmodified_official_core": True,
        "requires_task_level_case_id_join": True,
        "requires_raw_or_structured_official_output_hash": True,
        "requires_claim_role": "official_baseline_task_level_evidence",
        "comparators_or_controls_clear_this_gate": False,
        "current_resource_blockers": resource_blockers,
        "next_action": (
            "Resolve listed resources and run the official command; then rebuild "
            "build_baseline_admission_gate.py and build_official_baseline_runbook_gate.py."
        ),
    }


def build_gate(root: Path = ROOT) -> dict[str, Any]:
    manifest_path = ARTIFACTS / "official_baseline_bridge_manifest.json"
    baseline_gate_path = ARTIFACTS / "baseline_admission_gate.json"
    manifest = _load_json(manifest_path)
    baseline_gate = _load_json(baseline_gate_path)
    bridge_index = _bridge_by_baseline(manifest)
    python_probe = _probe(["python3", "-c", "import sys; print(sys.version.split()[0])"])
    cuda_probe = _probe(["python3", "-c", "import torch; print('cuda_available=' + str(torch.cuda.is_available()))"])
    gpu_probe = _probe(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
    blockers: list[str] = []
    baseline_rows: list[dict[str, Any]] = []
    for baseline in REQUIRED_BASELINES:
        bridge = bridge_index.get(baseline, {})
        entry_status = bridge.get("official_entrypoint_status", [])
        entry_status = entry_status if isinstance(entry_status, list) else []
        entrypoints_ok = bool(entry_status) and all(bool(item.get("exists")) for item in entry_status if isinstance(item, dict))
        output = _official_output_summary(root, baseline)
        row_blockers: list[str] = []
        if not bridge:
            row_blockers.append("official_bridge_missing")
        if int(bridge.get("case_count", 0) or 0) < REQUIRED_CASE_COUNT:
            row_blockers.append(f"bridge_case_count_below_{REQUIRED_CASE_COUNT}")
        if not entrypoints_ok:
            row_blockers.append("official_entrypoint_missing")
        if not output["admissible"]:
            row_blockers.append("official_task_level_output_missing_or_not_admissible")
        resource_blockers: list[str] = []
        if baseline in {"DuFFin", "Instructional Fingerprinting"} and not gpu_probe["ok"]:
            resource_blockers.append("gpu_or_local_model_resource_missing")
        if baseline == "PostMark":
            resource_blockers.append("provider_or_embedder_output_missing")
        row_blockers.extend(resource_blockers)
        baseline_rows.append(
            {
                "baseline": baseline,
                "bridge_path": str(bridge.get("bridge_path", "")),
                "case_count": int(bridge.get("case_count", 0) or 0),
                "official_entrypoints_ok": entrypoints_ok,
                "official_entrypoint_status": entry_status,
                "official_run_template": str(bridge.get("official_run_template", "")),
                "official_output_contract": {
                    "required_record_count": REQUIRED_CASE_COUNT,
                    "requires_claim_bearing": True,
                    "requires_official_core_unmodified": True,
                    "requires_task_level_case_id_join": True,
                    "comparators_do_not_satisfy": True,
                },
                "output": output,
                "official_run_contract": _run_contract(baseline, bridge, output, resource_blockers),
                "status": "ready" if not row_blockers else "blocked",
                "blockers": row_blockers,
            }
        )
        blockers.extend(f"{baseline}:{item}" for item in row_blockers)
    admitted_count = sum(1 for row in baseline_rows if not row["blockers"])
    if admitted_count <= 0:
        blockers.append("official_main_table_baseline_count_zero")
    return {
        "schema_version": SCHEMA_VERSION,
        "project": "SealAudit",
        "status": "passed" if not blockers else "blocked",
        "claim_role": "official_baseline_runbook_not_claim_bearing",
        "bridge_manifest": {"path": _rel(manifest_path), "present": manifest_path.exists(), "case_count": manifest.get("case_count")},
        "baseline_admission_gate": {
            "path": _rel(baseline_gate_path),
            "present": baseline_gate_path.exists(),
            "status": baseline_gate.get("status", ""),
            "blockers": baseline_gate.get("blockers", []),
        },
        "resource_preflight": {
            "python": python_probe,
            "gpu": gpu_probe,
            "torch_cuda": cuda_probe,
        },
        "required_baselines": list(REQUIRED_BASELINES),
        "admitted_official_baseline_count": admitted_count,
        "baselines": baseline_rows,
        "policy": "Official baselines are not downgraded: bridge inputs are necessary but not sufficient; only unmodified official-core task-level outputs with 320-case provenance can enter the main table.",
        "blockers": sorted(dict.fromkeys(blockers)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SealAudit official baseline runbook/admission preflight gate.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build_gate(ROOT)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "admitted_official_baseline_count": payload["admitted_official_baseline_count"], "blocker_count": len(payload["blockers"])}, ensure_ascii=True))


if __name__ == "__main__":
    main()
