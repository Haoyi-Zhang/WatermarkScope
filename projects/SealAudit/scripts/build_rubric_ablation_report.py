from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Iterable

from _bootstrap import ROOT
from sealaudit.benchmark_v2 import BENCHMARK_NAME, generate_v2_cases, summarize_v2_cases, validate_v2_cases
from sealaudit.canonical_v2 import (
    MARKER_HIDDEN_PROMPT_BLINDING_POLICY,
    MARKER_HIDDEN_PROMPT_RUBRIC_VERSION,
    PROMPT_BLINDING_POLICY,
    PROMPT_RUBRIC_VERSION,
    blind_case_id,
    build_v2_deepseek_prompt,
    build_v2_marker_hidden_deepseek_prompt,
)


SCHEMA_VERSION = "sealaudit_rubric_ablation_report_v1"
DEFAULT_OUTPUT = "artifacts/generated/rubric_ablation_report.json"
MARKER_HIDDEN_EXECUTION_PACKET = ROOT / "artifacts/generated/marker_hidden_ablation_execution_packet.json"
MARKER_HIDDEN_PROVIDER_RECORDS = ROOT / "artifacts/generated/marker_hidden_ablation_provider_records.json"
MARKER_HIDDEN_SUBSET_TASK_FAMILY = "sequence_filter"
MARKER_HIDDEN_FULL_CASE_COUNT = 320

LABEL_HIDDEN_FORBIDDEN_FIELDS: tuple[str, ...] = (
    "case_id",
    "scheme_kind",
    "case_family",
    "expected_verdict",
    "design_oracle_verdict",
    "scheme_label",
    "source_case_id",
    "provider_targets",
    "curation_packet",
    "provenance.source_case_id",
)

MARKER_HIDDEN_ADDITIONAL_FORBIDDEN_FIELDS: tuple[str, ...] = (
    "candidate_contract.marker_requirements",
    "redacted_markers",
    "claimed_signal_markers",
    "trigger_like_markers",
    "unsafe_markers",
    "laundering_markers",
    "spoofing_markers",
    "marker_surface_summary",
    "prompt.audit_surface_descriptor",
    "rubric.decision_precedence.marker_to_verdict_rules",
    "rubric.verdict_rules.marker_token_lists",
)

OUTPUT_VERDICT_LABELS: tuple[str, ...] = (
    "benign",
    "latent_trojan",
    "laundered_review",
    "needs_review",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or check the reviewer-facing rubric ablation and marker-hidden scaffold artifact."
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate that the output file already matches the generated rubric ablation report.",
    )
    return parser.parse_args()


def _resolve_output(path: str) -> Path:
    output = Path(path)
    if not output.is_absolute():
        output = ROOT / output
    return output


def _json_after_marker(text: str, marker: str) -> object:
    if marker not in text:
        raise ValueError(f"prompt is missing marker: {marker}")
    return json.loads(text.split(marker, 1)[1])


def _rubric_json_from_prompt(prompt: str) -> dict[str, object]:
    marker = "Decision rubric JSON:\n"
    if marker not in prompt or "\n\nCase JSON:\n" not in prompt:
        raise ValueError("prompt is missing rubric or case JSON block")
    raw = prompt.split(marker, 1)[1].split("\n\nCase JSON:\n", 1)[0]
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("rubric JSON block must be an object")
    return payload


def _case_json_from_prompt(prompt: str) -> dict[str, object]:
    payload = _json_after_marker(prompt, "Case JSON:\n")
    if not isinstance(payload, dict):
        raise ValueError("case JSON block must be an object")
    return payload


def _has_dotted_path(payload: dict[str, object], dotted: str) -> bool:
    current: object = payload
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def _counter_dict(values: Iterable[object]) -> dict[str, int]:
    return dict(sorted(Counter(str(value) for value in values).items()))


def _current_prompt_field_audit(cases: list[dict[str, object]]) -> dict[str, object]:
    field_failures: list[dict[str, object]] = []
    marker_requirement_exposure_count = 0
    scheme_descriptor_exposure_count = 0
    rubric_marker_rule_exposure_count = 0

    for case in cases:
        prompt = build_v2_deepseek_prompt(case)
        case_json = _case_json_from_prompt(prompt)
        rubric_json = _rubric_json_from_prompt(prompt)
        present = sorted(field for field in LABEL_HIDDEN_FORBIDDEN_FIELDS if _has_dotted_path(case_json, field))
        if present:
            field_failures.append(
                {
                    "blind_case_id": blind_case_id(case),
                    "present_forbidden_fields": present,
                }
            )

        candidate_contract = case_json.get("candidate_contract", {})
        if isinstance(candidate_contract, dict) and candidate_contract.get("marker_requirements"):
            marker_requirement_exposure_count += 1

        scheme_descriptor = str(case.get("scheme_kind", "")).replace("_", " ").lower()
        if scheme_descriptor and scheme_descriptor in prompt.lower():
            scheme_descriptor_exposure_count += 1

        rubric_text = json.dumps(rubric_json, sort_keys=True, ensure_ascii=True)
        marker_requirements = case.get("candidate_contract", {})
        marker_values = []
        if isinstance(marker_requirements, dict):
            marker_values = [str(item) for item in marker_requirements.get("marker_requirements", [])]
        if marker_values and any(marker in rubric_text for marker in marker_values):
            rubric_marker_rule_exposure_count += 1

    marker_hidden_gate_pass = (
        marker_requirement_exposure_count == 0
        and scheme_descriptor_exposure_count == 0
        and rubric_marker_rule_exposure_count == 0
    )
    return {
        "prompt_builder": "sealaudit.canonical_v2.build_v2_deepseek_prompt",
        "prompt_count": len(cases),
        "label_hidden_policy": PROMPT_BLINDING_POLICY,
        "prompt_rubric_version": PROMPT_RUBRIC_VERSION,
        "label_hidden_case_json_forbidden_fields": list(LABEL_HIDDEN_FORBIDDEN_FIELDS),
        "label_hidden_case_json_failure_count": len(field_failures),
        "label_hidden_case_json_failures_sample": field_failures[:8],
        "label_hidden_case_json_gate_pass": len(field_failures) == 0,
        "current_marker_requirement_exposure_count": marker_requirement_exposure_count,
        "current_scheme_descriptor_exposure_count": scheme_descriptor_exposure_count,
        "current_rubric_marker_rule_exposure_count": rubric_marker_rule_exposure_count,
        "current_marker_hidden_prompt_gate_pass": marker_hidden_gate_pass,
        "interpretation": (
            "The current v3 prompt passes a field-level label-hidden Case JSON check, "
            "but it is not marker-hidden and does not by itself prove absence of leakage."
        ),
    }


def _case_marker_values(case: dict[str, object]) -> list[str]:
    contract = case.get("candidate_contract", {})
    if not isinstance(contract, dict):
        return []
    return [str(item) for item in contract.get("marker_requirements", [])]


def _marker_hidden_prompt_surface_audit(cases: list[dict[str, object]]) -> dict[str, object]:
    field_failures: list[dict[str, object]] = []
    marker_value_leaks: list[dict[str, object]] = []
    scheme_descriptor_leaks: list[dict[str, object]] = []
    audit_surface_phrase_count = 0

    forbidden_fields = LABEL_HIDDEN_FORBIDDEN_FIELDS + MARKER_HIDDEN_ADDITIONAL_FORBIDDEN_FIELDS
    for case in cases:
        prompt = build_v2_marker_hidden_deepseek_prompt(case)
        case_json = _case_json_from_prompt(prompt)
        rubric_json = _rubric_json_from_prompt(prompt)
        present = sorted(field for field in forbidden_fields if _has_dotted_path(case_json, field))
        if present:
            field_failures.append(
                {
                    "blind_case_id": blind_case_id(case),
                    "present_forbidden_fields": present,
                }
            )

        prompt_text = prompt.lower()
        if "audit surface:" in prompt_text:
            audit_surface_phrase_count += 1
        leaked_markers = [marker for marker in _case_marker_values(case) if marker.lower() in prompt_text]
        if leaked_markers:
            marker_value_leaks.append(
                {
                    "blind_case_id": blind_case_id(case),
                    "leaked_marker_values": leaked_markers,
                }
            )

        scheme_kind = str(case.get("scheme_kind", "")).replace("_", " ").lower()
        raw_scheme_kind = str(case.get("scheme_kind", "")).lower()
        case_family = str(case.get("case_family", "")).replace("_", " ").lower()
        leaked_scheme_tokens = [
            token
            for token in (scheme_kind, raw_scheme_kind, case_family)
            if token and token not in OUTPUT_VERDICT_LABELS and token in prompt_text
        ]
        if leaked_scheme_tokens:
            scheme_descriptor_leaks.append(
                {
                    "blind_case_id": blind_case_id(case),
                    "leaked_scheme_descriptors": sorted(set(leaked_scheme_tokens)),
                }
            )

        rubric_text = json.dumps(rubric_json, sort_keys=True, ensure_ascii=True).lower()
        rubric_marker_leaks = [marker for marker in _case_marker_values(case) if marker.lower() in rubric_text]
        if rubric_marker_leaks:
            marker_value_leaks.append(
                {
                    "blind_case_id": blind_case_id(case),
                    "leaked_marker_values": rubric_marker_leaks,
                    "surface": "rubric",
                }
            )

    gate_pass = (
        not field_failures
        and not marker_value_leaks
        and not scheme_descriptor_leaks
        and audit_surface_phrase_count == 0
    )
    return {
        "prompt_builder": "sealaudit.canonical_v2.build_v2_marker_hidden_deepseek_prompt",
        "prompt_count": len(cases),
        "prompt_blinding_policy": MARKER_HIDDEN_PROMPT_BLINDING_POLICY,
        "prompt_rubric_version": MARKER_HIDDEN_PROMPT_RUBRIC_VERSION,
        "marker_hidden_forbidden_fields": list(forbidden_fields),
        "case_json_forbidden_field_failure_count": len(field_failures),
        "case_json_forbidden_field_failures_sample": field_failures[:8],
        "marker_value_leak_count": len(marker_value_leaks),
        "marker_value_leaks_sample": marker_value_leaks[:8],
        "scheme_descriptor_leak_count": len(scheme_descriptor_leaks),
        "scheme_descriptor_leaks_sample": scheme_descriptor_leaks[:8],
        "audit_surface_phrase_count": audit_surface_phrase_count,
        "marker_hidden_prompt_gate_pass": gate_pass,
        "claim_boundary": (
            "This gate proves only prompt-surface hiding for the marker-hidden variant; "
            "provider execution, adjudication, executable conjunction, and statistics remain separate gates."
        ),
    }


def _marker_hidden_subset(cases: list[dict[str, object]]) -> dict[str, object]:
    subset = list(cases)
    entries = [
        {
            "blind_case_id": blind_case_id(case),
            "case_index": case["case_index"],
            "language": case["language"],
            "task_family": case["task_family"],
            "split": case["split"],
            "threshold_fit_allowed": bool(case["threshold_fit_allowed"]),
            "case_commitment": case["provenance"]["commitment"],
        }
        for case in subset
    ]
    return {
        "status": "prompt_surface_ready_not_executed",
        "subset_rule": (
            "Use the full WatermarkBackdoorBench-v2 inventory. Earlier 32-case sequence_filter packets are retained "
            "only as smoke/support history and are not sufficient for the best-paper marker-hidden gate."
        ),
        "case_count": len(subset),
        "entries_are_prompt_safe": True,
        "per_case_hidden_fields_omitted": [
            "case_id",
            "scheme_kind",
            "case_family",
            "expected_verdict",
            "candidate_contract.marker_requirements",
        ],
        "entries": entries,
        "balance_summary": {
            "language_counts": _counter_dict(case["language"] for case in subset),
            "task_family_counts": _counter_dict(case["task_family"] for case in subset),
            "split_counts": _counter_dict(case["split"] for case in subset),
            "ambiguity_tier_counts": _counter_dict(case["ambiguity_tier"] for case in subset),
            "hidden_scheme_kind_counts": _counter_dict(case["scheme_kind"] for case in subset),
            "hidden_expected_verdict_counts": _counter_dict(case["expected_verdict"] for case in subset),
        },
    }


def _prompt_policy() -> dict[str, object]:
    return {
        "policy_name": PROMPT_BLINDING_POLICY,
        "prompt_rubric_version": PROMPT_RUBRIC_VERSION,
        "marker_hidden_prompt_rubric_version": MARKER_HIDDEN_PROMPT_RUBRIC_VERSION,
        "marker_hidden_prompt_blinding_policy": MARKER_HIDDEN_PROMPT_BLINDING_POLICY,
        "scope": "WatermarkBackdoorBench-v2 canonical DeepSeek prompt and planned ablations",
        "output_verdict_labels_visible_by_design": list(OUTPUT_VERDICT_LABELS),
        "label_hidden_forbidden_fields": list(LABEL_HIDDEN_FORBIDDEN_FIELDS),
        "marker_hidden_ablation_additional_forbidden_fields": list(MARKER_HIDDEN_ADDITIONAL_FORBIDDEN_FIELDS),
        "allowed_public_case_fields_for_current_label_hidden_prompt": [
            "blind_case_id",
            "benchmark",
            "language",
            "task_family",
            "prompt",
            "candidate_contract",
            "test_contract",
            "provenance_commitment",
        ],
        "allowed_public_case_fields_for_marker_hidden_ablation": [
            "blind_case_id",
            "benchmark",
            "language",
            "task_family",
            "task_prompt_without_audit_surface",
            "candidate_contract_without_marker_requirements",
            "test_contract",
            "provenance_commitment",
        ],
        "supported_claims": [
            "The current artifact can check that forbidden label fields are absent from the Case JSON block.",
            "The marker-hidden prompt variant can be constructed and scanned without marker requirements, scheme descriptors, or marker-to-verdict rules.",
            "The marker-hidden subset is defined with prompt-safe per-case entries and aggregate hidden-axis balance.",
        ],
        "unsupported_claims": [
            "does_not_prove_absence_of_leakage",
            "does_not_prove_marker_independent_reasoning",
            "does_not_establish_provider_performance_without_executed_ablation_records",
        ],
    }


def _rubric_ablation_plan() -> dict[str, object]:
    return {
        "status": "planned_not_executed",
        "reviewer_attack_point": (
            "v3 rubric performance could be explained by a direct marker-to-label mapping rather than "
            "generalizable scheme-audit reasoning."
        ),
        "variants": [
            {
                "id": "v3_label_hidden_marker_visible",
                "role": "current_reference_prompt",
                "label_hidden": True,
                "marker_requirements_visible": True,
                "decision_precedence_marker_rules_visible": True,
                "claim_bearing_without_ablation": False,
            },
            {
                "id": "v3_label_hidden_no_precedence",
                "role": "rubric_precedence_ablation",
                "label_hidden": True,
                "marker_requirements_visible": True,
                "decision_precedence_marker_rules_visible": False,
                "claim_bearing_without_ablation": False,
            },
            {
                "id": "marker_hidden_neutral_rubric",
                "role": "primary_marker_hidden_ablation",
                "label_hidden": True,
                "marker_requirements_visible": False,
                "decision_precedence_marker_rules_visible": False,
                "claim_bearing_without_ablation": False,
            },
            {
                "id": "marker_hidden_schema_only",
                "role": "minimal_prompt_control",
                "label_hidden": True,
                "marker_requirements_visible": False,
                "decision_precedence_marker_rules_visible": False,
                "claim_bearing_without_ablation": False,
            },
        ],
        "required_result_fields": [
            "prompt_variant_id",
            "blind_case_id",
            "provider_response_parsed",
            "raw_provider_response",
            "structured_provider_payload",
            "provider_verdict",
            "provider_positive_score",
            "posthoc_expected_verdict_alignment",
        ],
        "metrics_to_report_after_execution": [
            "provider_json_parse_rate_by_variant",
            "expected_verdict_alignment_rate_by_variant",
            "delta_vs_v3_label_hidden_marker_visible",
            "confusion_matrix_by_variant",
            "bootstrap_interval_for_alignment_delta",
            "threshold_sensitivity_on_threshold_fit_subset",
        ],
        "interpretation_rules": [
            "Treat the scaffold as non-claim-bearing until every variant has retained prompts and raw provider payloads.",
            "Only discuss marker-hidden robustness if the marker-hidden variants have executed records.",
            "Do not state that leakage is absent; at most state what the executed artifact directly checks.",
        ],
    }


def _result_scaffold() -> dict[str, object]:
    packet: dict[str, object] = {}
    if MARKER_HIDDEN_EXECUTION_PACKET.exists():
        try:
            loaded = json.loads(MARKER_HIDDEN_EXECUTION_PACKET.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                packet = loaded
        except (OSError, json.JSONDecodeError):
            packet = {}
    packet_ready = (
        packet.get("schema_version") == "sealaudit_marker_hidden_ablation_execution_packet_v1"
        and int(packet.get("case_count", 0) or 0) >= MARKER_HIDDEN_FULL_CASE_COUNT
        and int(packet.get("record_count", 0) or 0) == int(packet.get("expected_record_count", 0) or 0)
        and int(packet.get("record_count", 0) or 0) >= MARKER_HIDDEN_FULL_CASE_COUNT * 4
        and bool(packet.get("marker_hidden_prompt_leak_gate_pass", False))
        and str(packet.get("exact_prompt_retention_status", "")) == "passed"
        and int(packet.get("provider_calls_made", -1)) == 0
    )
    executed: dict[str, object] = {}
    if MARKER_HIDDEN_PROVIDER_RECORDS.exists():
        try:
            loaded = json.loads(MARKER_HIDDEN_PROVIDER_RECORDS.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                executed = loaded
        except (OSError, json.JSONDecodeError):
            executed = {}
    executed_records = executed.get("records", [])
    executed_records = executed_records if isinstance(executed_records, list) else []
    executed_complete = (
        executed.get("schema_version") == "sealaudit_marker_hidden_ablation_provider_execution_v1"
        and str(executed.get("status", "")) == "executed"
        and bool(executed.get("claim_bearing", False))
        and int(executed.get("record_count", 0) or 0) == int(executed.get("expected_record_count", 0) or 0)
        and int(executed.get("record_count", 0) or 0) >= MARKER_HIDDEN_FULL_CASE_COUNT * 4
        and int(executed.get("provider_call_count", 0) or 0) == int(executed.get("record_count", 0) or 0)
        and int(executed.get("executed_variant_count", 0) or 0) >= 4
    )
    if executed_complete:
        return {
            "status": "executed",
            "claim_bearing": True,
            "claim_bearing_scope": "marker_hidden_ablation_only_not_final_safety_claim",
            "provider_execution_artifact": MARKER_HIDDEN_PROVIDER_RECORDS.relative_to(ROOT).as_posix(),
            "prompt_packet_materialized": packet_ready,
            "prompt_packet_artifact": (
                MARKER_HIDDEN_EXECUTION_PACKET.relative_to(ROOT).as_posix()
                if MARKER_HIDDEN_EXECUTION_PACKET.exists()
                else ""
            ),
            "prompt_packet_record_count": int(packet.get("record_count", 0) or 0),
            "prompt_packet_variant_count": int(packet.get("variant_count", 0) or 0),
            "prompt_packet_case_count": int(packet.get("case_count", 0) or 0),
            "prompt_packet_marker_hidden_leak_gate_pass": bool(packet.get("marker_hidden_prompt_leak_gate_pass", False)),
            "executed_variant_count": int(executed.get("executed_variant_count", 0) or 0),
            "executed_record_count": int(executed.get("record_count", 0) or 0),
            "provider_call_count": int(executed.get("provider_call_count", 0) or 0),
            "records": executed_records,
            "metrics": executed.get("metrics", {}),
            "blocked_claims": [
                "final_safety_claim_without_adjudication",
                "final_security_certificate_without_executable_conjunction",
                "threshold_claim_without_claim_bearing_320_case_statistics",
            ],
            "evidence_required_to_unblock": [
                "dual-curator labels and adjudicator decisions for all v2 cases",
                "claim-bearing threshold sensitivity joined to final provider/adjudication records",
                "final executable conjunction and promotion gate",
            ],
            "claim_boundary": executed.get("claim_boundary", ""),
        }
    return {
        "status": "prompt_packet_materialized_not_provider_executed" if packet_ready else "not_executed",
        "claim_bearing": False,
        "prompt_packet_materialized": packet_ready,
        "provider_execution_artifact": (
            MARKER_HIDDEN_PROVIDER_RECORDS.relative_to(ROOT).as_posix()
            if MARKER_HIDDEN_PROVIDER_RECORDS.exists()
            else ""
        ),
        "prompt_packet_artifact": (
            MARKER_HIDDEN_EXECUTION_PACKET.relative_to(ROOT).as_posix()
            if MARKER_HIDDEN_EXECUTION_PACKET.exists()
            else ""
        ),
        "prompt_packet_record_count": int(packet.get("record_count", 0) or 0),
        "prompt_packet_variant_count": int(packet.get("variant_count", 0) or 0),
        "prompt_packet_case_count": int(packet.get("case_count", 0) or 0),
        "prompt_packet_marker_hidden_leak_gate_pass": bool(packet.get("marker_hidden_prompt_leak_gate_pass", False)),
        "executed_variant_count": 0,
        "executed_record_count": 0,
        "records": [],
        "metrics": {
            "provider_json_parse_rate_by_variant": None,
            "expected_verdict_alignment_rate_by_variant": None,
            "delta_vs_v3_label_hidden_marker_visible": None,
            "confusion_matrix_by_variant": None,
            "bootstrap_interval_for_alignment_delta": None,
            "threshold_sensitivity_on_threshold_fit_subset": None,
        },
        "blocked_claims": [
            "no_leakage_proven",
            "marker_independent_reasoning_established",
            "rubric_v3_attack_resolved",
            "provider_marker_hidden_ablation_executed",
        ],
        "evidence_required_to_unblock": [
            "retained exact prompts for every ablation variant",
            "raw and structured provider payloads for every completed record",
            "posthoc join to hidden expected verdicts outside the prompt path",
            "prompt scanner passing label-hidden and marker-hidden forbidden-field checks",
            "variant-level metric deltas with uncertainty intervals",
        ],
    }


def build_report() -> dict[str, object]:
    cases = generate_v2_cases()
    issues = validate_v2_cases(cases)
    if issues:
        raise ValueError("v2 inventory validation failed: " + "; ".join(issues))
    results = _result_scaffold()
    marker_hidden_claim_bearing = bool(results.get("claim_bearing", False))
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": (
            "rubric_ablation_marker_hidden_executed_leakage_probe"
            if marker_hidden_claim_bearing
            else "rubric_ablation_marker_hidden_scaffold"
        ),
        "claim_role": (
            "claim_bearing_marker_hidden_leakage_probe_not_final_safety_claim"
            if marker_hidden_claim_bearing
            else "review_response_scaffold_not_leakage_proof"
        ),
        "claim_bearing": marker_hidden_claim_bearing,
        "claim_bearing_scope": (
            "marker_hidden_visible-marker-to-label-mapping_attack_only"
            if marker_hidden_claim_bearing
            else "none"
        ),
        "final_safety_claim_allowed": False,
        "benchmark": BENCHMARK_NAME,
        "source_case_count": len(cases),
        "source_inventory_summary": summarize_v2_cases(cases),
        "artifact_limitations": (
            [
                "Executed marker-hidden provider records support only the visible-marker-to-label-mapping red-team response.",
                "They do not promote the final safety/security claim without completed adjudication, executable conjunction, threshold sensitivity, and official baseline gates.",
                "They must be joined by artifact hash to v2_adjudication_promotion_gate before use in any main claim table.",
            ]
            if marker_hidden_claim_bearing
            else [
                "This artifact documents policy, prompt-surface checks, and a planned ablation scaffold.",
                "It does not prove absence of leakage.",
                "It does not contain executed marker-hidden provider results.",
            ]
        ),
        "prompt_policy": _prompt_policy(),
        "current_prompt_field_audit": _current_prompt_field_audit(cases),
        "marker_hidden_prompt_surface_audit": _marker_hidden_prompt_surface_audit(cases),
        "marker_hidden_subset": _marker_hidden_subset(cases),
        "rubric_ablation_plan": _rubric_ablation_plan(),
        "rubric_ablation_results": results,
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main() -> None:
    args = _parse_args()
    output = _resolve_output(args.output)
    payload = build_report()
    if args.check:
        if not output.exists():
            print(json.dumps({"path": _relative(output), "check": "failed", "reason": "missing"}, indent=2, ensure_ascii=True))
            raise SystemExit(1)
        current = json.loads(output.read_text(encoding="utf-8"))
        if current != payload:
            print(json.dumps({"path": _relative(output), "check": "failed", "reason": "content_drift"}, indent=2, ensure_ascii=True))
            raise SystemExit(1)
        print(json.dumps({"path": _relative(output), "check": "passed"}, indent=2, ensure_ascii=True))
        return

    _write_json(output, payload)
    print(
        json.dumps(
            {
                "path": _relative(output),
                "schema_version": SCHEMA_VERSION,
                "check_command": f"python scripts/build_rubric_ablation_report.py --check --output {_relative(output)}",
            },
            indent=2,
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
