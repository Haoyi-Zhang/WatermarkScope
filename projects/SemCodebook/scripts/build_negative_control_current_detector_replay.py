from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from _bootstrap import ARTIFACTS, ROOT
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal sync copies.
    ROOT = Path(__file__).resolve().parents[1]
    ARTIFACTS = ROOT / "artifacts" / "generated"

import sys

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from semcodebook.detector import SemCodebookDetector
from semcodebook.protocol import WatermarkSpec


SCHEMA = "semcodebook_negative_control_current_detector_replay_v1"
DEFAULT_FULL_EVAL = ARTIFACTS / "full_eval_results.json"
DEFAULT_OUTPUT = ARTIFACTS / "negative_control_current_detector_replay.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256_json(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _truthy_detection(record: dict[str, Any]) -> bool:
    status = str(record.get("decision_status") or "").strip().lower()
    return (
        bool(record.get("detected"))
        or bool(record.get("is_watermarked"))
        or bool(record.get("watermarked"))
        or status in {"accept", "accepted", "detected", "verified", "watermarked"}
        or record.get("wm_id_hat") is not None
    )


def _negative_hit(record: dict[str, Any]) -> bool:
    return bool(record.get("negative_control") or record.get("is_negative_control")) and _truthy_detection(record)


def _record_id(record: dict[str, Any]) -> str:
    material = {
        key: record.get(key)
        for key in (
            "model_name",
            "benchmark",
            "task_id",
            "language",
            "attack_name",
            "attack_category",
        )
    }
    return _sha256_json(material)[:16]


def _first_present(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _spec_from_record(record: dict[str, Any]) -> WatermarkSpec:
    return WatermarkSpec(
        wm_id=_as_int(_first_present(record, ("wm_id_expected", "wm_id", "expected_wm_id")), 13),
        payload_bits=_as_int(record.get("payload_bits"), 4),
        ecc_scheme=str(record.get("ecc_scheme") or "soft_secded84_adaptive_v1"),
        detector_threshold=_as_float(record.get("detector_threshold"), 0.5),
        carrier_key=str(record.get("carrier_key") or "semcodebook-demo-key"),
        implementation_stage=str(record.get("implementation_stage") or "negative_control_current_detector_replay"),
    )


def _code_from_record(record: dict[str, Any]) -> str | None:
    value = _first_present(
        record,
        (
            "evaluated_code",
            "attacked_code",
            "watermarked_code",
            "generated_code",
            "code",
            "source_code",
        ),
    )
    return value if isinstance(value, str) and value.strip() else None


def _detector_contract_passes(detection: Any) -> bool:
    status = str(getattr(detection, "decision_status", "") or "").strip().lower()
    return (
        status in {"reject", "rejected", "abstain"}
        and not bool(getattr(detection, "is_watermarked", False))
        and getattr(detection, "wm_id_hat", None) is None
        and getattr(detection, "decoded_wm_id_candidate", None) is None
        and float(getattr(detection, "positive_support_score", 0.0) or 0.0) == 0.0
        and int(getattr(detection, "positive_support_family_count", 0) or 0) == 0
        and int(getattr(detection, "positive_support_level_count", 0) or 0) == 0
        and bool(str(getattr(detection, "abstain_reason", "") or "").strip())
    )


def _detector_replay(record: dict[str, Any]) -> dict[str, Any]:
    original = {
        "detected": bool(record.get("detected")),
        "decision_status": record.get("decision_status"),
        "wm_id_hat": record.get("wm_id_hat"),
        "confidence": record.get("confidence"),
        "support_ratio": record.get("support_ratio"),
        "support_count": record.get("support_count"),
    }
    code = _code_from_record(record)
    replay: dict[str, Any]
    remaining_detected = True
    rerun_status = "missing_rerunnable_code"
    if code is None:
        replay = {
            "rerun_status": rerun_status,
            "missing_reason": "source_code_field_missing",
            "contract_passed": False,
        }
    else:
        detection = SemCodebookDetector().detect(
            code,
            _spec_from_record(record),
            language=str(record.get("language") or "python"),
            negative_control=True,
        )
        contract_passed = _detector_contract_passes(detection)
        remaining_detected = not contract_passed
        rerun_status = "detector_rerun_complete"
        replay = {
            "rerun_status": rerun_status,
            "detected": bool(detection.is_watermarked),
            "decision_status": detection.decision_status,
            "abstain_reason": detection.abstain_reason,
            "wm_id_hat": detection.wm_id_hat,
            "decoded_wm_id_candidate": detection.decoded_wm_id_candidate,
            "payload_exposure_blocked": detection.wm_id_hat is None and detection.decoded_wm_id_candidate is None,
            "positive_support_score": detection.positive_support_score,
            "positive_support_family_count": detection.positive_support_family_count,
            "positive_support_level_count": detection.positive_support_level_count,
            "decoder_status": detection.decoder_status,
            "notes": list(detection.notes),
            "contract_passed": contract_passed,
        }
    return {
        "candidate_id": _record_id(record),
        "task_id": record.get("task_id"),
        "benchmark": record.get("benchmark"),
        "language": record.get("language"),
        "family": record.get("family"),
        "attack_name": record.get("attack_name") or "clean_reference",
        "attack_category": record.get("attack_category") or "clean_control",
        "negative_control": True,
        "source_record_sha256": _sha256_json(record),
        "old_detector": original,
        "current_detector_contract": replay,
        "rerun_status": rerun_status,
        "remaining_detected_after_contract": remaining_detected,
    }


def build_payload(full_eval_path: Path) -> dict[str, Any]:
    payload = _load_json(full_eval_path)
    records = payload.get("records", []) if isinstance(payload, dict) else []
    if not isinstance(records, list):
        raise ValueError("full_eval records must be a list")
    hits = [_detector_replay(dict(record)) for record in records if isinstance(record, dict) and _negative_hit(record)]
    by_language = Counter(str(item.get("language") or "unknown") for item in hits)
    by_attack = Counter(str(item.get("attack_name") or "clean_reference") for item in hits)
    remaining = [item for item in hits if item["remaining_detected_after_contract"]]
    missing = [item for item in hits if item["rerun_status"] != "detector_rerun_complete"]
    return {
        "schema": SCHEMA,
        "artifact_role": "current_detector_negative_control_rerun",
        "claim_bearing": False,
        "canonical_replacement_allowed": False,
        "formal_experiment_allowed": False,
        "source_artifact": full_eval_path.relative_to(ROOT).as_posix()
        if full_eval_path.is_relative_to(ROOT)
        else str(full_eval_path),
        "source_artifact_sha256": hashlib.sha256(full_eval_path.read_bytes()).hexdigest(),
        "policy": (
            "This artifact reruns the current detector on stale canonical negative-control hits when "
            "the full_eval record contains enough source material. Missing rerunnable code remains a "
            "blocker; this artifact cannot clear the canonical negative-control gate until a fresh "
            "full_eval rerun is clean."
        ),
        "old_negative_hit_count": len(hits),
        "replay_record_count": len(hits),
        "remaining_detected_count": len(remaining),
        "missing_task_count": len(missing),
        "detector_rerun_count": len(hits) - len(missing),
        "by_language": dict(sorted(by_language.items())),
        "by_attack_name": dict(sorted(by_attack.items())),
        "records": hits,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build support-only replay of current negative-control fail-closed contract.")
    parser.add_argument("--full-eval", type=Path, default=DEFAULT_FULL_EVAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build_payload(args.full_eval)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": args.output.relative_to(ROOT).as_posix() if args.output.is_relative_to(ROOT) else str(args.output),
                "old_negative_hit_count": payload["old_negative_hit_count"],
                "remaining_detected_count": payload["remaining_detected_count"],
                "claim_bearing": payload["claim_bearing"],
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
