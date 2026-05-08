from __future__ import annotations

import os
import json
from dataclasses import asdict
from pathlib import Path

from .adaptive_ecc import oracle_post_correction_bit_error_rate
from .attacks import run_attack
from .detector import SemCodebookDetector
from .protocol import BenchmarkTask, EvaluationRecord, WatermarkSpec
from .semantic_validator import validate_semantics


def _semantic_status(
    compile_supported: bool,
    pass_supported: bool,
    compile_ok: bool | None,
    pass_ok: bool | None,
) -> bool | None:
    if not compile_supported:
        return None
    return pass_ok if pass_supported else compile_ok


def evaluate_task(
    task: BenchmarkTask,
    code: str,
    spec: WatermarkSpec,
    model_name: str,
    method_name: str = "SemCodebook",
    attack_name: str | None = None,
    negative_control: bool = False,
) -> EvaluationRecord:
    detector = SemCodebookDetector()
    attack_record = run_attack(attack_name, code, task.language) if attack_name else None
    evaluated_code = attack_record.attacked_code if attack_record else code
    task_metadata = {str(key): str(value) for key, value in task.metadata}
    result = detector.detect(
        evaluated_code,
        spec,
        language=task.language,
        negative_control=negative_control,
    )

    compile_supported = task.language.lower() in {"python", "javascript", "java", "go", "cpp"}
    pass_supported = compile_supported and bool(task.tests)
    compile_ok: bool | None = None
    pass_ok: bool | None = None
    executed_tests: tuple[str, ...] = ()
    failure_reason: str | None = None
    clean_compile_ok: bool | None = None
    clean_pass_ok: bool | None = None
    if compile_supported:
        clean_trace = validate_semantics(
            code,
            task.language,
            task.tests,
            task_id=task.task_id,
            metadata=task_metadata,
        )
        trace = validate_semantics(
            evaluated_code,
            task.language,
            task.tests,
            task_id=task.task_id,
            metadata=task_metadata,
        )
        clean_compile_ok = clean_trace.compile_ok
        clean_pass_ok = clean_trace.tests_ok
        compile_ok = trace.compile_ok
        pass_ok = trace.tests_ok
        executed_tests = trace.executed_tests
        failure_reason = trace.failure_reason
    semantic_ok = _semantic_status(compile_supported, pass_supported, compile_ok, pass_ok)
    clean_semantic_ok = _semantic_status(compile_supported, pass_supported, clean_compile_ok, clean_pass_ok)
    compile_pass_preserved: bool | None = None
    if attack_record and attack_record.applicable and attack_record.changed and clean_semantic_ok is not None:
        compile_pass_preserved = bool(clean_semantic_ok and semantic_ok)
    bit_error_count = None
    bit_error_rate = None
    if not negative_control and result.wm_id_hat is not None:
        bit_error_rate = oracle_post_correction_bit_error_rate(result.wm_id_hat, spec.wm_id, spec.payload_bits)
        bit_error_count = int(round(bit_error_rate * spec.payload_bits))
    carrier_signal_coverage = 0.0
    if result.carrier_evidence:
        carrier_signal_coverage = round(
            sum(1.0 for item in result.carrier_evidence if item.confidence > 0.0) / len(result.carrier_evidence),
            4,
        )
    carrier_coverage = result.support_ratio
    coverage_notes = (
        "carrier_coverage_semantics:scheduled_support_ratio",
        f"carrier_signal_coverage:{carrier_signal_coverage:.4f}",
    )
    return EvaluationRecord(
        project="SemCodebook",
        method_name=method_name,
        model_name=model_name,
        benchmark=task.benchmark,
        task_id=task.task_id,
        split=task.split,
        source=task.source,
        language=task.language,
        attack_name=attack_name,
        attack_category=attack_record.attack_category if attack_record else None,
        attack_applicable=attack_record.applicable if attack_record else True,
        compile_supported=compile_supported,
        compile_ok=compile_ok,
        pass_supported=pass_supported,
        pass_ok=pass_ok,
        semantic_ok=semantic_ok,
        compile_pass_preserved=compile_pass_preserved,
        negative_control=negative_control,
        detected=result.is_watermarked,
        wm_id_expected=spec.wm_id,
        wm_id_hat=result.wm_id_hat,
        payload_bits=spec.payload_bits,
        ecc_scheme=spec.ecc_scheme,
        exact_recovery=(not negative_control) and result.wm_id_hat == spec.wm_id if result.wm_id_hat is not None else False,
        bit_error_count=bit_error_count,
        bit_error_rate=bit_error_rate,
        corrected_bits=result.corrected_bits,
        decoder_status=result.decoder_status,
        erasure_count=result.erasure_count,
        raw_bit_error_count=result.raw_bit_error_count,
        support_count=result.support_count,
        support_ratio=result.support_ratio,
        carrier_signal_coverage=carrier_signal_coverage,
        negative_control_score=result.negative_control_score,
        ber_numerator=None if negative_control else bit_error_count,
        ber_denominator=0 if negative_control else spec.payload_bits,
        confidence=result.confidence,
        code_changed=attack_record.changed if attack_record else False,
        carrier_coverage=carrier_coverage,
        executed_tests=executed_tests,
        failure_reason=failure_reason,
        carrier_evidence=tuple(f"{item.family}:{item.option}:{item.confidence:.2f}" for item in result.carrier_trace),
        notes=((attack_record.notes if attack_record else ()) + (("negative_control",) if negative_control else ()) + result.notes + coverage_notes),
        decision_status=result.decision_status,
        abstain_reason=result.abstain_reason,
        positive_support_score=result.positive_support_score,
        positive_support_family_count=result.positive_support_family_count,
        positive_support_level_count=result.positive_support_level_count,
    )


def save_evaluation(records: list[EvaluationRecord], path: str | Path) -> None:
    save_evaluation_with_meta(records, path)


def save_evaluation_with_meta(
    records: list[EvaluationRecord],
    path: str | Path,
    meta: dict[str, object] | None = None,
) -> None:
    serialized_records = []
    for item in records:
        if hasattr(item, "__dataclass_fields__"):
            serialized_records.append(asdict(item))
        elif isinstance(item, dict):
            serialized_records.append(dict(item))
        else:
            raise TypeError(f"unsupported evaluation record type: {type(item)!r}")
    payload: dict[str, object] = {"records": serialized_records, "record_count": len(serialized_records)}
    if meta:
        payload["meta"] = meta
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f"{output_path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    os.replace(temp_path, output_path)
