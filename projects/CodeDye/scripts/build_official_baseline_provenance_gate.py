from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT
from integrations.dyepack_official_adapter import bridge_paths


OFFICIAL_REPO = "https://github.com/chengez/DyePack.git"
OFFICIAL_ENTRYPOINT = "BIG-Bench-Hard/cheatcheck_from_local.py"
OFFICIAL_CORE_FILES = (
    "BIG-Bench-Hard/cheatcheck_from_local.py",
    "BIG-Bench-Hard/evaluate_from_local.py",
    "MMLU_Pro/cheatcheck_from_local.py",
    "MMLU_Pro/evaluate_from_local.py",
    "Alpaca/cheatcheck_from_local.py",
    "model-prompt-templates.json",
)
SECRET_MARKERS = (
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "CLAUDE_API_KEY",
)
SECRET_REGEXES = (
    ("openai_style_secret_key", re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_-]{20,}\b")),
)
QWEN25_CACHE_SLUG = "models--Qwen--Qwen2.5-Coder-7B-Instruct"
QWEN25_CACHE_ROOTS = (
    ("shared_hf_cache", Path("/data/codemark/shared/hf_cache")),
    ("shared_hf_hub", Path("/data/codemark/shared/hf_cache/hub")),
    ("root_hf_hub", Path("/root/.cache/huggingface/hub")),
)


def _sibling_project_markers() -> tuple[str, ...]:
    repo_prefix = "codemark_"
    names = ("sem" + "codebook", "probe" + "trace", "seal" + "audit")
    display_names = ("Sem" + "Codebook", "Probe" + "Trace", "Seal" + "Audit")
    return tuple(repo_prefix + name for name in names) + tuple(
        wrapper + display_name + wrapper for display_name in display_names for wrapper in ("/", "\\")
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the CodeDye official-baseline provenance gate.")
    parser.add_argument("--output", type=Path, default=ARTIFACTS / "official_baseline_provenance_gate.json")
    parser.add_argument("--minimum-records", type=int, default=300)
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _git_value(checkout: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(checkout), *args],
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


def _probe_command(command: tuple[str, ...], *, timeout: int = 20) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return {
            "command": " ".join(command),
            "ok": False,
            "returncode": None,
            "status": "missing_executable",
            "detail": str(exc.filename or ""),
        }
    except subprocess.TimeoutExpired:
        return {
            "command": " ".join(command),
            "ok": False,
            "returncode": None,
            "status": "timeout",
            "detail": f"timeout_after_seconds:{timeout}",
        }
    detail = (completed.stdout.strip() or completed.stderr.strip()).splitlines()
    return {
        "command": " ".join(command),
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "detail": "; ".join(line[:180] for line in detail[:4]),
    }


def _qwen25_cache_state() -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    snapshot_present = False
    for label, root in QWEN25_CACHE_ROOTS:
        candidate = root / QWEN25_CACHE_SLUG
        refs_main = candidate / "refs" / "main"
        snapshots = candidate / "snapshots"
        has_snapshot = False
        if refs_main.exists():
            revision = refs_main.read_text(encoding="utf-8").strip()
            has_snapshot = bool(revision and (snapshots / revision).exists())
        if not has_snapshot and snapshots.exists():
            has_snapshot = any(path.is_dir() for path in snapshots.iterdir())
        if not has_snapshot and (candidate / "config.json").exists():
            has_snapshot = True
        snapshot_present = snapshot_present or has_snapshot
        roots.append(
            {
                "root_label": label,
                "cache_dir_exists": candidate.exists(),
                "snapshot_present": has_snapshot,
            }
        )
    return {
        "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "cache_slug": QWEN25_CACHE_SLUG,
        "snapshot_present": snapshot_present,
        "roots": roots,
    }


def _official_execution_resource_preflight() -> dict[str, Any]:
    gpu = _probe_command(("nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"))
    vllm = _probe_command(("python3", "-c", "import vllm; print(getattr(vllm, '__version__', 'unknown'))"))
    model_cache = _qwen25_cache_state()
    blockers: list[str] = []
    if not gpu["ok"]:
        blockers.append("dyepack_official_gpu_unavailable")
    if not vllm["ok"]:
        blockers.append("dyepack_official_vllm_import_failed")
    if not model_cache["snapshot_present"]:
        blockers.append("dyepack_official_qwen25_model_cache_missing")
    return {
        "schema_version": "codedye_dyepack_official_execution_resource_preflight_v1",
        "admission_scope": "official DyePack vLLM local entrypoint only; API providers and comparators do not satisfy this gate",
        "gpu": gpu,
        "vllm": vllm,
        "model_cache": model_cache,
        "blockers": blockers,
        "ready_for_official_task_output_run": not blockers,
    }


def _official_run_contract(*, minimum_records: int, outputs_path: Path, resource_preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "official_baseline": "DyePack",
        "official_repo": OFFICIAL_REPO,
        "official_entrypoint": OFFICIAL_ENTRYPOINT,
        "command": (
            "python3 scripts/run_dyepack_official_task_outputs.py "
            "--selected-subjects codedye_bridge --pat rand --num-pattern 4 --poison-rate 0.1"
        ),
        "expected_output": _relative(outputs_path, ROOT),
        "required_record_count": minimum_records,
        "requires_unmodified_official_core_files": list(OFFICIAL_CORE_FILES),
        "requires_bridge_alignment_with_current_codedyebench": True,
        "requires_raw_response_and_hash_per_task": True,
        "requires_provider_required_false": True,
        "api_provider_or_comparator_can_satisfy_gate": False,
        "resource_blockers": list(resource_preflight.get("blockers", [])),
        "next_action": (
            "Resolve resource blockers, run the official command, then rebuild "
            "build_official_baseline_provenance_gate.py and verify_baseline_admission.py. "
            "Do not promote lexical/embedding/AST/nearest-neighbor controls as official baselines."
        ),
    }


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def _dirty_status_summary(checkout: Path, allowed_bridge_paths: set[str]) -> dict[str, Any]:
    raw = _git_value(checkout, "status", "--porcelain")
    lines = [line for line in raw.splitlines() if line.strip()]
    unexpected: list[str] = []
    for line in lines:
        path = line[3:].strip() if len(line) >= 4 else line.strip()
        status = line[:2]
        allowed = status == "??" and any(path == allowed_path or path.startswith(f"{allowed_path}/") for allowed_path in allowed_bridge_paths)
        if not allowed:
            unexpected.append(line)
    core_diff = _git_value(checkout, "diff", "--name-only", "HEAD", "--", *OFFICIAL_CORE_FILES)
    core_diff_files = [line.strip() for line in core_diff.splitlines() if line.strip()]
    return {
        "dirty_status": lines,
        "allowed_bridge_dirty_paths": sorted(allowed_bridge_paths),
        "unexpected_dirty_status": unexpected,
        "official_core_diff_files": core_diff_files,
        "official_core_unmodified": not core_diff_files,
        "dirty_status_allowed": not unexpected,
    }


def _record_contract(
    *,
    outputs: dict[str, Any],
    task_map: list[dict[str, Any]],
    bridge_dataset_sha256: str,
    minimum_records: int,
) -> dict[str, Any]:
    records = outputs.get("records", [])
    records = records if isinstance(records, list) else []
    task_by_index = {int(item.get("dyepack_index", -1)): item for item in task_map if isinstance(item, dict)}
    task_ids = [str(item.get("task_id", "")).strip() for item in records if isinstance(item, dict)]
    duplicate_task_ids = sorted(task_id for task_id, count in Counter(task_ids).items() if task_id and count > 1)
    blockers: list[str] = []
    missing_required: dict[str, int] = {}
    raw_hash_mismatch = 0
    prompt_hash_missing = 0
    bridge_hash_mismatch = 0
    task_map_mismatch = 0
    non_dyepack_records = 0
    comparator_promotion_rows = 0
    upstream_modified_rows = 0
    provider_required_rows = 0
    non_claim_rows = 0
    empty_raw_response_rows = 0
    required_fields = (
        "baseline_name",
        "official_repo",
        "official_entrypoint",
        "official_main_table_baseline",
        "claim_bearing",
        "dyepack_index",
        "task_id",
        "language",
        "family",
        "pattern",
        "target_answer",
        "raw_response",
        "raw_response_sha256",
        "prompt_sha256",
        "bridge_dataset_sha256",
        "provider_required",
        "upstream_core_logic_modified",
    )
    for record in records:
        if not isinstance(record, dict):
            blockers.append("official_output_record_not_object")
            continue
        for field in required_fields:
            if field not in record:
                missing_required[field] = missing_required.get(field, 0) + 1
        raw_response = str(record.get("raw_response", ""))
        if not raw_response.strip():
            empty_raw_response_rows += 1
        if str(record.get("raw_response_sha256", "")) != _sha256_text(raw_response):
            raw_hash_mismatch += 1
        if not str(record.get("prompt_sha256", "")).strip():
            prompt_hash_missing += 1
        if str(record.get("bridge_dataset_sha256", "")) != bridge_dataset_sha256:
            bridge_hash_mismatch += 1
        if str(record.get("baseline_name", "")) != "DyePack":
            non_dyepack_records += 1
        if not bool(record.get("official_main_table_baseline", False)):
            comparator_promotion_rows += 1
        if bool(record.get("upstream_core_logic_modified", True)):
            upstream_modified_rows += 1
        if bool(record.get("provider_required", True)):
            provider_required_rows += 1
        if not bool(record.get("claim_bearing", False)):
            non_claim_rows += 1
        try:
            dyepack_index = int(record.get("dyepack_index", -1))
        except (TypeError, ValueError):
            dyepack_index = -1
        mapped = task_by_index.get(dyepack_index, {})
        if not mapped:
            task_map_mismatch += 1
        else:
            for key in ("task_id", "language", "family", "pattern", "target_answer"):
                if str(record.get(key, "")) != str(mapped.get(key, "")):
                    task_map_mismatch += 1
                    break

    declared_count = int(outputs.get("record_count", 0) or 0)
    target_count = int(outputs.get("target_record_count", 0) or 0)
    if declared_count != len(records):
        blockers.append("official_output_record_count_mismatch")
    if len(records) < minimum_records:
        blockers.append(f"official_output_record_count_below_{minimum_records}:{len(records)}")
    if target_count < minimum_records:
        blockers.append(f"official_output_target_count_below_{minimum_records}:{target_count}")
    if not bool(outputs.get("claim_bearing", False)):
        blockers.append("official_output_not_claim_bearing")
    if missing_required:
        blockers.append("official_output_required_fields_missing")
    if duplicate_task_ids:
        blockers.append("official_output_duplicate_task_ids")
    if raw_hash_mismatch:
        blockers.append("official_output_raw_response_hash_mismatch")
    if prompt_hash_missing:
        blockers.append("official_output_prompt_hash_missing")
    if bridge_hash_mismatch:
        blockers.append("official_output_bridge_dataset_hash_mismatch")
    if task_map_mismatch:
        blockers.append("official_output_task_map_mismatch")
    if non_dyepack_records:
        blockers.append("official_output_non_dyepack_records")
    if comparator_promotion_rows:
        blockers.append("official_output_comparator_promoted_as_official")
    if upstream_modified_rows:
        blockers.append("official_output_upstream_core_modified")
    if provider_required_rows:
        blockers.append("official_output_provider_required")
    if non_claim_rows:
        blockers.append("official_output_non_claim_rows")
    if empty_raw_response_rows:
        blockers.append("official_output_empty_raw_response")

    return {
        "gate_pass": not blockers,
        "record_count": len(records),
        "declared_record_count": declared_count,
        "target_record_count": target_count,
        "minimum_record_count": minimum_records,
        "duplicate_task_ids": duplicate_task_ids[:20],
        "missing_required_field_counts": dict(sorted(missing_required.items())),
        "raw_response_hash_mismatch_count": raw_hash_mismatch,
        "prompt_hash_missing_count": prompt_hash_missing,
        "bridge_dataset_hash_mismatch_count": bridge_hash_mismatch,
        "task_map_mismatch_count": task_map_mismatch,
        "non_dyepack_record_count": non_dyepack_records,
        "comparator_promotion_row_count": comparator_promotion_rows,
        "upstream_modified_row_count": upstream_modified_rows,
        "provider_required_row_count": provider_required_rows,
        "non_claim_row_count": non_claim_rows,
        "empty_raw_response_count": empty_raw_response_rows,
        "language_counts": dict(sorted(Counter(str(item.get("language", "")) for item in records if isinstance(item, dict)).items())),
        "family_counts": dict(sorted(Counter(str(item.get("family", "")) for item in records if isinstance(item, dict)).items())),
        "blockers": blockers,
    }


def _marker_hits(payloads: list[dict[str, Any]], markers: tuple[str, ...]) -> list[str]:
    text = "\n".join(json.dumps(payload, sort_keys=True, ensure_ascii=True) for payload in payloads)
    return sorted(marker for marker in markers if marker in text)


def _secret_hits(payloads: list[dict[str, Any]]) -> list[str]:
    text = "\n".join(json.dumps(payload, sort_keys=True, ensure_ascii=True) for payload in payloads)
    hits = [marker for marker in SECRET_MARKERS if marker in text]
    hits.extend(name for name, pattern in SECRET_REGEXES if pattern.search(text))
    return sorted(hits)


def build_gate(root: Path = ROOT, *, minimum_records: int = 300) -> dict[str, Any]:
    artifacts = root / "artifacts" / "generated"
    outputs_path = artifacts / "dyepack_official_task_outputs.json"
    bridge_manifest_path = artifacts / "dyepack_official_bridge_manifest.json"
    baseline_admission_path = artifacts / "baseline_admission_verification.json"
    outputs = _read_json(outputs_path)
    bridge_manifest = _read_json(bridge_manifest_path)
    baseline_admission = _read_json(baseline_admission_path)
    paths = bridge_paths(root, selected_subjects="codedye_bridge", pat="rand", num_pattern=4, poison_rate="0.1")
    checkout = paths.checkout
    task_map = []
    if paths.task_id_map.exists():
        try:
            loaded = json.loads(paths.task_id_map.read_text(encoding="utf-8"))
            task_map = loaded if isinstance(loaded, list) else []
        except (OSError, json.JSONDecodeError):
            task_map = []

    bridge_dataset_sha256 = _sha256_file(paths.bbh_dataset)
    allowed_bridge_paths = {
        "BIG-Bench-Hard/bbh/codedye_bridge.json",
        "BIG-Bench-Hard/data/codedye_bridge_rand_B4_pr0.1",
    }
    dirty = _dirty_status_summary(checkout, allowed_bridge_paths) if checkout.exists() else {
        "dirty_status": [],
        "allowed_bridge_dirty_paths": sorted(allowed_bridge_paths),
        "unexpected_dirty_status": [],
        "official_core_diff_files": [],
        "official_core_unmodified": False,
        "dirty_status_allowed": False,
    }
    record_contract = _record_contract(
        outputs=outputs,
        task_map=task_map,
        bridge_dataset_sha256=bridge_dataset_sha256,
        minimum_records=minimum_records,
    )
    resource_preflight = _official_execution_resource_preflight()
    official_repo_url = _git_value(checkout, "remote", "get-url", "origin") if checkout.exists() else ""
    checkout_head = _git_value(checkout, "rev-parse", "HEAD") if checkout.exists() else ""
    entrypoint_path = checkout / OFFICIAL_ENTRYPOINT
    bridge_files = {
        "bbh_dataset": paths.bbh_dataset,
        "task_id_map": paths.task_id_map,
        "poisoned_ans_dict": paths.metadata_dir / "poisoned_ans_dict.npy",
        "poisoned_pat_dict": paths.metadata_dir / "poisoned_pat_dict.npy",
        "pattern2ans": paths.metadata_dir / "pattern2ans.npy",
    }
    bridge_file_state = {
        name: {
            "path": _relative(path, root),
            "exists": path.exists(),
            "sha256": _sha256_file(path) if path.exists() else "",
        }
        for name, path in bridge_files.items()
    }
    blockers: list[str] = []
    if not bool(baseline_admission.get("official_baseline_gate_pass", False)):
        blockers.append("baseline_admission_official_gate_not_passed")
    if "DyePack" not in [str(item) for item in baseline_admission.get("official_runnable_baselines", [])]:
        blockers.append("dyepack_not_in_official_runnable_baselines")
    if not checkout.exists():
        blockers.append("dyepack_checkout_missing")
    if official_repo_url != OFFICIAL_REPO:
        blockers.append("dyepack_official_origin_mismatch")
    if not checkout_head:
        blockers.append("dyepack_checkout_head_missing")
    if not entrypoint_path.exists():
        blockers.append("dyepack_official_entrypoint_missing")
    if not dirty["official_core_unmodified"]:
        blockers.append("dyepack_official_core_diff_detected")
    if not dirty["dirty_status_allowed"]:
        blockers.append("dyepack_unexpected_dirty_status")
    missing_bridge_files = [name for name, state in bridge_file_state.items() if not state["exists"]]
    if missing_bridge_files:
        blockers.append("dyepack_bridge_files_missing")
    if int(bridge_manifest.get("task_count", 0) or 0) < minimum_records:
        blockers.append(f"dyepack_bridge_task_count_below_{minimum_records}")
    if bool(bridge_manifest.get("claim_bearing", True)):
        blockers.append("dyepack_bridge_manifest_should_be_support_only")
    if len(task_map) < minimum_records:
        blockers.append(f"dyepack_task_map_count_below_{minimum_records}:{len(task_map)}")
    blockers.extend(f"record_contract:{item}" for item in record_contract["blockers"])
    blockers.extend(f"resource_preflight:{item}" for item in resource_preflight["blockers"])
    secret_hits = _secret_hits([outputs, bridge_manifest, baseline_admission])
    sibling_hits = _marker_hits([outputs, bridge_manifest, baseline_admission], _sibling_project_markers())
    if secret_hits:
        blockers.append("official_baseline_secret_marker_detected")
    if sibling_hits:
        blockers.append("official_baseline_sibling_project_reference_detected")

    payload = {
        "schema_version": "codedye_official_baseline_provenance_gate_v1",
        "gate_name": "official_dyepack_baseline_provenance_and_independence",
        "status": "passed" if not blockers else "failed",
        "gate_pass": not blockers,
        "provider_policy": "no_provider_no_live_api",
        "official_baseline_name": "DyePack",
        "official_repo": OFFICIAL_REPO,
        "official_entrypoint": OFFICIAL_ENTRYPOINT,
        "minimum_record_count": minimum_records,
        "baseline_admission": {
            "path": "artifacts/generated/baseline_admission_verification.json",
            "official_baseline_gate_pass": bool(baseline_admission.get("official_baseline_gate_pass", False)),
            "official_runnable_baselines": [
                str(item) for item in baseline_admission.get("official_runnable_baselines", []) if str(item).strip()
            ] if isinstance(baseline_admission.get("official_runnable_baselines", []), list) else [],
            "main_table_comparator_controls": [
                str(item) for item in baseline_admission.get("main_table_comparator_controls", []) if str(item).strip()
            ] if isinstance(baseline_admission.get("main_table_comparator_controls", []), list) else [],
            "comparator_controls_are_not_official_baselines": bool(
                baseline_admission.get("official_baseline_failure_audit", {}).get(
                    "comparator_controls_are_not_official_baselines",
                    True,
                )
            )
            if isinstance(baseline_admission.get("official_baseline_failure_audit", {}), dict)
            else True,
        },
        "checkout_provenance": {
            "path": _relative(checkout, root),
            "exists": checkout.exists(),
            "origin_url": official_repo_url,
            "head_commit": checkout_head,
            "entrypoint_exists": entrypoint_path.exists(),
            "entrypoint_sha256": _sha256_file(entrypoint_path),
            "official_core_files": {
                item: _sha256_file(checkout / item) for item in OFFICIAL_CORE_FILES if (checkout / item).exists()
            },
            **dirty,
        },
        "bridge_provenance": {
            "manifest_path": "artifacts/generated/dyepack_official_bridge_manifest.json",
            "manifest_sha256": _sha256_file(bridge_manifest_path),
            "manifest_task_count": int(bridge_manifest.get("task_count", 0) or 0),
            "manifest_target_task_count": int(bridge_manifest.get("target_task_count", 0) or 0),
            "manifest_claim_bearing": bool(bridge_manifest.get("claim_bearing", True)),
            "task_map_count": len(task_map),
            "bridge_dataset_sha256": bridge_dataset_sha256,
            "bridge_files": bridge_file_state,
        },
        "official_output_provenance": {
            "path": "artifacts/generated/dyepack_official_task_outputs.json",
            "sha256": _sha256_file(outputs_path),
            "schema_version": str(outputs.get("schema_version", "")),
            "claim_bearing": bool(outputs.get("claim_bearing", False)),
            "activation_rate": float(outputs.get("activation_rate", 0.0) or 0.0),
            "model_path_hash": _sha256_text(str(outputs.get("model_path", ""))),
            "model_path_redacted": "<local_model_path_present>" if str(outputs.get("model_path", "")).strip() else "",
            "record_contract": record_contract,
        },
        "official_run_contract": _official_run_contract(
            minimum_records=minimum_records,
            outputs_path=outputs_path,
            resource_preflight=resource_preflight,
        ),
        "official_execution_resource_preflight": resource_preflight,
        "independence_and_leakage": {
            "secret_marker_hits": secret_hits,
            "sibling_project_marker_hits": sibling_hits,
            "comparator_controls_promoted_as_official": not bool(
                baseline_admission.get("official_baseline_failure_audit", {}).get(
                    "comparator_controls_are_not_official_baselines",
                    True,
                )
            )
            if isinstance(baseline_admission.get("official_baseline_failure_audit", {}), dict)
            else False,
        },
        "blockers": sorted(dict.fromkeys(blockers)),
    }
    return payload


def main() -> None:
    args = _parse_args()
    payload = build_gate(ROOT, minimum_records=args.minimum_records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("schema_version", "status", "gate_pass", "blockers")}, indent=2))
    if payload["blockers"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
