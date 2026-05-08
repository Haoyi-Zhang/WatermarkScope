from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import ROOT

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from semcodebook.benchmarks import load_carrier_stressbench
from semcodebook.detector import SemCodebookDetector
from semcodebook.inference import _language_support_materializer_variants, _target_aligned_schedule
from semcodebook.protocol import GenerationRequest, WatermarkSpec
from semcodebook.semantic_validator import validate_semantics
from semcodebook.variant_pool import build_adaptive_carrier_schedule


def _sha256_path(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def _source_hashes() -> dict[str, str]:
    paths = {
        "script": Path(__file__),
        "inference": ROOT / "src" / "semcodebook" / "inference.py",
        "detector": ROOT / "src" / "semcodebook" / "detector.py",
        "semantic_validator": ROOT / "src" / "semcodebook" / "semantic_validator.py",
        "variant_pool": ROOT / "src" / "semcodebook" / "variant_pool.py",
        "tasks": ROOT / "benchmarks" / "carrier_stressbench_tasks.json",
    }
    return {name: _sha256_path(path) for name, path in paths.items()}


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _clean_positive_contract(
    *,
    semantic_ok: bool,
    code_changed: bool,
    detection,
    expected_wm_id: int,
) -> bool:
    return (
        semantic_ok
        and code_changed
        and bool(detection.is_watermarked)
        and detection.wm_id_hat == expected_wm_id
        and int(detection.positive_support_family_count or 0) >= 2
        and int(detection.positive_support_level_count or 0) >= 2
    )


def _negative_control_contract(*, semantic_ok: bool, detection) -> bool:
    return (
        semantic_ok
        and not bool(detection.is_watermarked)
        and detection.wm_id_hat is None
        and detection.decision_status in {"abstain", "reject"}
    )


def _metadata_flag(metadata: dict[str, str], key: str) -> bool:
    return metadata.get(key, "").strip().lower() == "true"


def _is_positive_carrier(metadata: dict[str, str]) -> bool:
    return _metadata_flag(metadata, "positive_carrier") or metadata.get("variant_kind", "").strip().lower() == "positive_carrier"


def _is_negative_control(metadata: dict[str, str]) -> bool:
    return _metadata_flag(metadata, "negative_control") or metadata.get("variant_kind", "").strip().lower() == "negative_control"


def _candidate_tuple(candidate: dict[str, object]) -> tuple[object, ...]:
    return (
        bool(candidate["clean_positive_contract"]),
        bool(candidate["semantic_ok"]),
        bool(candidate["code_changed"]),
        bool(candidate["detected"]),
        int(candidate["positive_support_family_count"]),
        int(candidate["positive_support_level_count"]),
        float(candidate["positive_support_score"]),
        -int(candidate["variant_index"]),
    )


def audit_materializers(
    *,
    languages: set[str],
    positive_only: bool,
    max_tasks_per_language: int,
    wm_id: int,
    carrier_key: str,
    example_limit: int,
) -> dict[str, object]:
    detector = SemCodebookDetector()
    summary: Counter[str] = Counter()
    by_slice: dict[str, Counter[str]] = defaultdict(Counter)
    language_seen: Counter[str] = Counter()
    examples: list[dict[str, object]] = []
    best_failures: list[dict[str, object]] = []

    for task in load_carrier_stressbench(ROOT):
        language = task.language.strip().lower()
        if languages and language not in languages:
            continue
        if max_tasks_per_language > 0 and language_seen[language] >= max_tasks_per_language:
            continue
        metadata = {str(key): str(value) for key, value in task.metadata}
        is_positive_carrier = _is_positive_carrier(metadata)
        is_negative_control = _is_negative_control(metadata)
        if positive_only and not is_positive_carrier:
            continue
        language_seen[language] += 1
        family = metadata.get("carrier_family", "unknown")
        slice_key = f"{language}:{family}"
        summary["task_count"] += 1
        by_slice[slice_key]["task_count"] += 1
        if is_negative_control:
            summary["negative_control_task_count"] += 1
            by_slice[slice_key]["negative_control_task_count"] += 1
        else:
            summary["positive_contract_eligible_task_count"] += 1
            by_slice[slice_key]["positive_contract_eligible_task_count"] += 1

        request = GenerationRequest(
            prompt=task.prompt,
            task_id=task.task_id,
            language=task.language,
            wm_id=wm_id,
            carrier_key=carrier_key,
            model_name="materializer-audit",
        )
        schedule = _target_aligned_schedule(
            task.reference_code,
            request,
            build_adaptive_carrier_schedule(task.reference_code, request.carrier_key, task.language),
        )

        if is_negative_control:
            trace = validate_semantics(
                task.reference_code,
                task.language,
                task.tests,
                task_id=task.task_id,
                metadata=metadata,
            )
            semantic_ok = bool(trace.compile_ok and trace.tests_ok)
            detection = detector.detect(
                task.reference_code,
                WatermarkSpec(
                    wm_id=wm_id,
                    carrier_key=request.carrier_key,
                    carrier_schedule=schedule,
                    implementation_stage="materializer_audit_negative_control",
                ),
                language=task.language,
                negative_control=True,
            )
            candidate = {
                "variant_index": -1,
                "label": "negative_control:reference_code",
                "semantic_ok": semantic_ok,
                "compile_ok": bool(trace.compile_ok),
                "tests_ok": bool(trace.tests_ok),
                "failure_reason": trace.failure_reason or "",
                "code_changed": False,
                "detected": bool(detection.is_watermarked),
                "wm_id_hat": detection.wm_id_hat,
                "decision_status": detection.decision_status,
                "abstain_reason": detection.abstain_reason,
                "negative_control_score": float(detection.negative_control_score or 0.0),
                "positive_support_score": float(detection.positive_support_score or 0.0),
                "positive_support_family_count": int(detection.positive_support_family_count or 0),
                "positive_support_level_count": int(detection.positive_support_level_count or 0),
                "negative_control_contract": _negative_control_contract(
                    semantic_ok=semantic_ok,
                    detection=detection,
                ),
            }
            if candidate["negative_control_contract"]:
                summary["negative_control_contract_task_count"] += 1
                by_slice[slice_key]["negative_control_contract_task_count"] += 1
                summary["contract_pass_task_count"] += 1
                by_slice[slice_key]["contract_pass_task_count"] += 1
            elif semantic_ok:
                summary["negative_control_false_positive_task_count"] += 1
                by_slice[slice_key]["negative_control_false_positive_task_count"] += 1
                best_failures.append({"task_id": task.task_id, "language": language, "family": family, **candidate})
            else:
                summary["semantic_failed_task_count"] += 1
                by_slice[slice_key]["semantic_failed_task_count"] += 1
                best_failures.append({"task_id": task.task_id, "language": language, "family": family, **candidate})
            if len(examples) < example_limit and not candidate["negative_control_contract"]:
                examples.append({"task_id": task.task_id, "language": language, "family": family, "best": candidate})
            continue

        variants = _language_support_materializer_variants(task.reference_code, request, schedule)
        if not variants:
            summary["no_variant_task_count"] += 1
            by_slice[slice_key]["no_variant_task_count"] += 1
            if len(examples) < example_limit:
                examples.append(
                    {
                        "task_id": task.task_id,
                        "language": language,
                        "family": family,
                        "status": "no_variants",
                    }
                )
            continue

        best: dict[str, object] | None = None
        for variant_index, (label, code) in enumerate(variants):
            trace = validate_semantics(
                code,
                task.language,
                task.tests,
                task_id=task.task_id,
                metadata=metadata,
            )
            semantic_ok = bool(trace.compile_ok and trace.tests_ok)
            detection = detector.detect(
                code,
                WatermarkSpec(
                    wm_id=wm_id,
                    carrier_key=request.carrier_key,
                    carrier_schedule=schedule,
                    implementation_stage="materializer_audit",
                ),
                language=task.language,
            )
            candidate = {
                "variant_index": variant_index,
                "label": label,
                "semantic_ok": semantic_ok,
                "compile_ok": bool(trace.compile_ok),
                "tests_ok": bool(trace.tests_ok),
                "failure_reason": trace.failure_reason or "",
                "code_changed": _compact(code) != _compact(task.reference_code),
                "detected": bool(detection.is_watermarked),
                "wm_id_hat": detection.wm_id_hat,
                "decision_status": detection.decision_status,
                "positive_support_score": float(detection.positive_support_score or 0.0),
                "positive_support_family_count": int(detection.positive_support_family_count or 0),
                "positive_support_level_count": int(detection.positive_support_level_count or 0),
                "clean_positive_contract": _clean_positive_contract(
                    semantic_ok=semantic_ok,
                    code_changed=_compact(code) != _compact(task.reference_code),
                    detection=detection,
                    expected_wm_id=wm_id,
                ),
            }
            if best is None or _candidate_tuple(candidate) > _candidate_tuple(best):
                best = candidate
            if candidate["clean_positive_contract"]:
                break

        if best is None:
            summary["no_candidate_task_count"] += 1
            by_slice[slice_key]["no_candidate_task_count"] += 1
            continue
        if best["clean_positive_contract"]:
            summary["clean_positive_contract_task_count"] += 1
            summary["contract_pass_task_count"] += 1
            by_slice[slice_key]["clean_positive_contract_task_count"] += 1
            by_slice[slice_key]["contract_pass_task_count"] += 1
        elif best["semantic_ok"]:
            summary["semantic_but_contract_failed_task_count"] += 1
            by_slice[slice_key]["semantic_but_contract_failed_task_count"] += 1
            best_failures.append({"task_id": task.task_id, "language": language, "family": family, **best})
        else:
            summary["semantic_failed_task_count"] += 1
            by_slice[slice_key]["semantic_failed_task_count"] += 1
            best_failures.append({"task_id": task.task_id, "language": language, "family": family, **best})
        if len(examples) < example_limit and not best["clean_positive_contract"]:
            examples.append({"task_id": task.task_id, "language": language, "family": family, "best": best})

    task_count = int(summary["task_count"])
    clean_count = int(summary["clean_positive_contract_task_count"])
    positive_task_count = int(summary["positive_contract_eligible_task_count"])
    negative_control_count = int(summary["negative_control_task_count"])
    negative_control_pass_count = int(summary["negative_control_contract_task_count"])
    contract_pass_count = int(summary["contract_pass_task_count"])
    return {
        "schema": "semcodebook_carrier_materializer_audit_v1",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "claim_bearing": False,
        "source_hashes": _source_hashes(),
        "task_count": task_count,
        "positive_contract_eligible_task_count": positive_task_count,
        "negative_control_task_count": negative_control_count,
        "clean_positive_contract_task_count": clean_count,
        "clean_positive_contract_rate": round(clean_count / positive_task_count, 4) if positive_task_count else None,
        "negative_control_contract_task_count": negative_control_pass_count,
        "negative_control_contract_rate": round(negative_control_pass_count / negative_control_count, 4) if negative_control_count else None,
        "contract_pass_task_count": contract_pass_count,
        "contract_pass_rate": round(contract_pass_count / task_count, 4) if task_count else None,
        "summary": dict(sorted(summary.items())),
        "language_seen": dict(sorted(language_seen.items())),
        "by_language_family": {
            key: dict(sorted(value.items()))
            for key, value in sorted(by_slice.items())
        },
        "examples": examples,
        "best_failure_count": len(best_failures),
        "best_failures": best_failures[: max(example_limit, 0)],
        "policy": {
            "positive_only": positive_only,
            "provider_mode": "no_provider",
            "wm_id": wm_id,
            "contract": (
                "positive carriers: semantic compile/tests pass, code changed, detected, exact wm_id recovery, "
                "and at least two positive carrier families across two structural levels; "
                "negative controls: reference semantics pass and detector rejects or abstains without wm_id recovery"
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit SemCodebook no-provider carrier materializers.")
    parser.add_argument("--language", action="append", default=[], help="Restrict to a language; may be repeated.")
    parser.add_argument("--include-negative-tasks", action="store_true")
    parser.add_argument("--max-tasks-per-language", type=int, default=0)
    parser.add_argument("--wm-id", type=int, default=13)
    parser.add_argument("--carrier-key", default="carrier-key")
    parser.add_argument("--example-limit", type=int, default=25)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "generated" / "carrier_materializer_audit.json")
    args = parser.parse_args()

    payload = audit_materializers(
        languages={item.strip().lower() for item in args.language if item.strip()},
        positive_only=not args.include_negative_tasks,
        max_tasks_per_language=max(0, args.max_tasks_per_language),
        wm_id=args.wm_id & 0x0F,
        carrier_key=args.carrier_key,
        example_limit=max(0, args.example_limit),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("task_count", "clean_positive_contract_task_count", "clean_positive_contract_rate")}, ensure_ascii=True))


if __name__ == "__main__":
    main()
