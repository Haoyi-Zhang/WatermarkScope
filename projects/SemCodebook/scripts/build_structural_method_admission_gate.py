from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from _bootstrap import ARTIFACTS, ROOT


SCHEMA = "semcodebook_structural_method_admission_gate_v1"
DEFAULT_OUTPUT = ARTIFACTS / "structural_method_admission_gate.json"
EXPECTED_LANGUAGES = ("python", "javascript", "java", "go", "cpp")
EXPECTED_CARRIERSTRESS_FAMILIES = (
    "guard_loop_accumulator",
    "guard_helper_accumulator",
    "container_helper",
    "multilingual_equivalence",
    "cfg_branch_normalization",
    "ssa_phi_liveness",
)
EXPECTED_STRUCTURAL_LEVELS = ("ast", "cfg", "ssa")
PROXY_MARKERS = ("proxy", "regex")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _as_bool(value: Any) -> bool:
    return bool(value) and str(value).strip().lower() not in {"0", "false", "no", "none", "null", ""}


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _display_path(path: Path, *, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return str(path)


def _unique(items: Iterable[str]) -> list[str]:
    return sorted(dict.fromkeys(item for item in items if item))


def _variant_records(payload: Any) -> list[dict[str, Any]]:
    records = _as_list(_as_dict(payload).get("records"))
    return [dict(item) for item in records if isinstance(item, dict)]


def _notes(record: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(item) for item in _as_list(record.get("notes")) if str(item).strip())


def _validation_notes(record: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(item) for item in _as_list(record.get("validation_notes")) if str(item).strip())


def _code_changed(record: dict[str, Any]) -> bool:
    reference = str(record.get("reference_code", ""))
    transformed = str(record.get("transformed_code", ""))
    if reference and transformed and reference != transformed:
        return True
    notes = _notes(record)
    return not any(note == "no_rewrite_required_reference_variant" for note in notes) and bool(record.get("transformed_code_hash"))


def _has_compile_test_witness(record: dict[str, Any]) -> bool:
    validation_notes = set(_validation_notes(record))
    notes = set(_notes(record))
    return (
        _as_bool(record.get("validation_passed"))
        and "compile_test_validated" in validation_notes
        and bool({"rewrite_certificate_valid", "witness_preserved"} & (validation_notes | notes))
    )


def _is_proxy_record(record: dict[str, Any]) -> bool:
    text = " ".join((*_notes(record), *_validation_notes(record))).lower()
    return any(marker in text for marker in PROXY_MARKERS)


def _variant_pool_gate(root: Path, artifacts: Path) -> dict[str, Any]:
    variant_pool_path = artifacts / "variant_pool.json"
    manifest_path = artifacts / "variant_dataset_manifest.json"
    payload = _load_json(variant_pool_path)
    manifest = _as_dict(_load_json(manifest_path))
    records = _variant_records(payload)
    changed_witness_records = [
        record for record in records if _code_changed(record) and _has_compile_test_witness(record)
    ]
    changed_by_language = Counter(str(record.get("language", "")).lower() for record in changed_witness_records)
    changed_by_level = Counter(str(record.get("structural_level", "")).lower() for record in changed_witness_records)
    changed_by_language_level = Counter(
        f"{str(record.get('language', '')).lower()}:{str(record.get('structural_level', '')).lower()}"
        for record in changed_witness_records
    )
    proxy_by_language = Counter(str(record.get("language", "")).lower() for record in records if _is_proxy_record(record))
    training_languages = tuple(str(item).lower() for item in _as_list(manifest.get("training_languages")) if str(item).strip()) or EXPECTED_LANGUAGES
    blockers: list[str] = []
    if not records:
        blockers.append("variant_pool_records_missing")
    for language in EXPECTED_LANGUAGES:
        if language not in training_languages:
            blockers.append(f"training_language_missing:{language}")
        if changed_by_language.get(language, 0) <= 0:
            blockers.append(f"changed_compile_test_witness_missing_for_language:{language}")
    for level in EXPECTED_STRUCTURAL_LEVELS:
        if changed_by_level.get(level, 0) <= 0:
            blockers.append(f"changed_compile_test_witness_missing_for_structural_level:{level}")
    proxy_only_languages = [
        language
        for language in EXPECTED_LANGUAGES
        if proxy_by_language.get(language, 0) > 0 and changed_by_language.get(language, 0) <= 0
    ]
    return {
        "status": "pass" if not blockers else "blocked",
        "source_artifacts": {
            "variant_pool": _display_path(variant_pool_path, root=root),
            "variant_dataset_manifest": _display_path(manifest_path, root=root),
        },
        "record_count": len(records),
        "changed_compile_test_witness_record_count": len(changed_witness_records),
        "changed_by_language": dict(sorted(changed_by_language.items())),
        "changed_by_structural_level": dict(sorted(changed_by_level.items())),
        "changed_by_language_level": dict(sorted(changed_by_language_level.items())),
        "proxy_by_language": dict(sorted(proxy_by_language.items())),
        "proxy_only_languages": proxy_only_languages,
        "training_languages": list(training_languages),
        "blockers": blockers,
        "claim_policy": (
            "Reference-profile or proxy-only variants are support evidence. A language contributes to the "
            "main method claim only after changed code, compile/test validation, and rewrite/witness evidence."
        ),
    }


def _audit_paths(artifacts: Path) -> list[Path]:
    candidates = list(artifacts.glob("carrier_materializer_audit*.json"))
    candidates.extend((artifacts / "materializer_audits").glob("carrier_materializer_audit*.json"))
    unique: dict[str, Path] = {}
    for path in candidates:
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        unique[key] = path
    return sorted(unique.values(), key=lambda item: str(item))


def _materializer_gate(root: Path, artifacts: Path) -> dict[str, Any]:
    audits: list[dict[str, Any]] = []
    pair_status: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []
    for path in _audit_paths(artifacts):
        payload = _as_dict(_load_json(path))
        by_pair = _as_dict(payload.get("by_language_family"))
        audits.append(
            {
                "path": _display_path(path, root=root),
                "schema": payload.get("schema"),
                "task_count": _as_int(payload.get("task_count")),
                "clean_positive_contract_task_count": _as_int(payload.get("clean_positive_contract_task_count")),
                "negative_control_contract_task_count": _as_int(payload.get("negative_control_contract_task_count")),
                "contract_pass_task_count": _as_int(payload.get("contract_pass_task_count")),
                "positive_only": _as_bool(_as_dict(payload.get("policy")).get("positive_only")),
            }
        )
        for key, value in by_pair.items():
            current = pair_status.setdefault(
                str(key),
                {
                    "task_count": 0,
                    "clean_positive_contract_task_count": 0,
                    "negative_control_contract_task_count": 0,
                    "contract_pass_task_count": 0,
                    "semantic_failed_task_count": 0,
                    "source_paths": [],
                },
            )
            item = _as_dict(value)
            current["task_count"] = max(_as_int(current.get("task_count")), _as_int(item.get("task_count")))
            current["clean_positive_contract_task_count"] = max(
                _as_int(current.get("clean_positive_contract_task_count")),
                _as_int(item.get("clean_positive_contract_task_count")),
            )
            current["negative_control_contract_task_count"] = max(
                _as_int(current.get("negative_control_contract_task_count")),
                _as_int(item.get("negative_control_contract_task_count")),
            )
            current["contract_pass_task_count"] = max(
                _as_int(current.get("contract_pass_task_count")),
                _as_int(item.get("contract_pass_task_count")),
            )
            current["semantic_failed_task_count"] = max(
                _as_int(current.get("semantic_failed_task_count")),
                _as_int(item.get("semantic_failed_task_count")),
            )
            current["source_paths"].append(_display_path(path, root=root))

    if not audits:
        blockers.append("carrier_materializer_audit_missing")
    for language in EXPECTED_LANGUAGES:
        for family in EXPECTED_CARRIERSTRESS_FAMILIES:
            key = f"{language}:{family}"
            item = pair_status.get(key, {})
            clean_positive = _as_int(item.get("clean_positive_contract_task_count"))
            clean_negative = _as_int(item.get("negative_control_contract_task_count"))
            if clean_positive <= 0:
                blockers.append(f"materializer_positive_contract_missing:{key}")
            if clean_negative <= 0:
                blockers.append(f"materializer_negative_contract_missing:{key}")
    return {
        "status": "pass" if not blockers else "blocked",
        "audit_count": len(audits),
        "audits": audits,
        "pair_status": pair_status,
        "blockers": blockers,
        "claim_policy": (
            "Helper closure and multilingual carrier claims require clean positive and matched negative "
            "materializer contracts for every CarrierStressBench language-family pair."
        ),
    }


def _method_schema_gate(artifacts: Path) -> dict[str, Any]:
    gate = _as_dict(_load_json(artifacts / "method_schema_gate.json"))
    claim_bearing = gate.get("schema") == "semcodebook_method_schema_gate_v1" and _as_bool(gate.get("claim_bearing"))
    blockers = [] if claim_bearing else [f"method_schema_not_claim_bearing:{gate.get('status', 'missing')}"]
    blockers.extend(str(item) for item in _as_list(gate.get("blockers")) if str(item).strip())
    return {
        "status": "pass" if claim_bearing else "blocked",
        "claim_bearing": claim_bearing,
        "source_status": gate.get("status", "missing"),
        "record_count": gate.get("record_count", 0),
        "blockers": blockers,
        "claim_policy": "Fresh canonical full_eval schema is required before fail-closed detector evidence can be claim-bearing.",
    }


def _ecc_fail_closed_gate(artifacts: Path) -> dict[str, Any]:
    payload = _as_dict(_load_json(artifacts / "full_eval_results.json"))
    records = [dict(item) for item in _as_list(payload.get("records")) if isinstance(item, dict)]
    schema_current_records = [record for record in records if "decision_status" in record]
    leaks = []
    for record in schema_current_records:
        decision = str(record.get("decision_status", "")).lower()
        if decision in {"abstain", "reject", "rejected"} and record.get("wm_id_hat") is not None:
            leaks.append(
                {
                    "task_id": record.get("task_id", ""),
                    "decision_status": record.get("decision_status"),
                    "wm_id_hat": record.get("wm_id_hat"),
                }
            )
        if record.get("negative_control") and record.get("wm_id_hat") is not None:
            leaks.append(
                {
                    "task_id": record.get("task_id", ""),
                    "decision_status": record.get("decision_status", ""),
                    "wm_id_hat": record.get("wm_id_hat"),
                    "reason": "negative_control_wm_id_exposed",
                }
            )
    blockers = []
    if not schema_current_records:
        blockers.append("ecc_fail_closed_schema_current_records_missing")
    if leaks:
        blockers.append(f"wm_id_hat_exposed_on_fail_closed_records:{len(leaks)}")
    return {
        "status": "pass" if not blockers else "blocked",
        "schema_current_record_count": len(schema_current_records),
        "leak_count": len(leaks),
        "leak_examples": leaks[:10],
        "blockers": blockers,
        "claim_policy": "Uncorrectable, abstain, reject, or negative-control decisions must not expose wm_id_hat.",
    }


def _keyed_schedule_gate(artifacts: Path) -> dict[str, Any]:
    plan = _as_dict(_load_json(artifacts / "semcodebook_stats_ablation_plan.json"))
    ablation = _as_dict(plan.get("ablation_plan"))
    keyed = _as_dict(ablation.get("keyed_schedule_ablation"))
    units = _as_list(keyed.get("units"))
    preregistered = plan.get("schema_version") == "semcodebook_stats_ablation_prereg_v1" and len(units) > 0
    blockers = [] if preregistered else ["keyed_schedule_ablation_prereg_missing"]
    return {
        "status": "pass" if preregistered else "blocked",
        "preregistered": preregistered,
        "unit_count": len(units),
        "blockers": blockers,
        "claim_policy": (
            "A keyed schedule mechanism can be described as implemented/preregistered, but its security "
            "or robustness contribution remains support-only until fresh canonical ablation results land."
        ),
    }


def build_payload(*, root: Path = ROOT, artifacts: Path = ARTIFACTS) -> dict[str, Any]:
    variant_gate = _variant_pool_gate(root, artifacts)
    materializer_gate = _materializer_gate(root, artifacts)
    schema_gate = _method_schema_gate(artifacts)
    ecc_gate = _ecc_fail_closed_gate(artifacts)
    keyed_gate = _keyed_schedule_gate(artifacts)
    dimensions = {
        "variant_pool": variant_gate,
        "materializer_contract": materializer_gate,
        "method_schema": schema_gate,
        "ecc_fail_closed": ecc_gate,
        "keyed_schedule": keyed_gate,
    }
    blockers: list[str] = []
    for name, item in dimensions.items():
        if item.get("status") != "pass":
            blockers.extend(f"{name}:{blocker}" for blocker in _as_list(item.get("blockers")))
    admission_allowed = all(item.get("status") == "pass" for item in dimensions.values())
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "SemCodebook",
        "artifact_role": "structural_method_admission_gate_not_claim_bearing",
        "status": "pass" if admission_allowed else "blocked",
        "admission_allowed": admission_allowed,
        "claim_bearing": admission_allowed,
        "claim_boundary": "structured_code_provenance_watermark_after_multilingual_structural_admission",
        "dimensions": dimensions,
        "blockers": _unique(blockers),
        "next_action": _unique(blockers)[0] if blockers else "refresh_best_paper_gate_and_generate_pre_run_report",
        "policy": {
            "support_only_until_pass": True,
            "no_proxy_ir_as_main_claim": True,
            "no_support_sidecar_promotion": True,
            "no_threshold_relaxation_or_sample_removal": True,
        },
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the SemCodebook structural method admission gate.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_payload()
    rendered = json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True).encode("utf-8") + b"\n"
    if args.check:
        if not args.output.exists():
            print(f"{args.output} missing; run build_structural_method_admission_gate.py", file=sys.stderr)
            return 1
        if args.output.read_bytes() != rendered:
            print(f"{args.output} stale; rerun build_structural_method_admission_gate.py", file=sys.stderr)
            return 1
        if not payload["admission_allowed"]:
            print(
                json.dumps(
                    {
                        "status": payload["status"],
                        "blockers": payload["blockers"][:40],
                        "blocker_count": len(payload["blockers"]),
                    },
                    ensure_ascii=True,
                ),
                file=sys.stderr,
            )
            return 1
        print(json.dumps({"status": "ok", "path": str(args.output)}, ensure_ascii=True))
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rendered)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "path": str(args.output),
                "admission_allowed": payload["admission_allowed"],
                "blocker_count": len(payload["blockers"]),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
