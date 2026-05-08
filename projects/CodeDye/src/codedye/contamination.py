from __future__ import annotations

from dataclasses import dataclass

from .benchmarks import (
    task_canary_split,
    task_chronology_split,
    task_hidden_test_family,
    task_metadata,
    task_release_window,
    task_review_status,
    task_target_family,
)
from .canaries import measure_canary_evidence
from .protocol import BenchmarkTask
from .reranker import observe_family
from .response_normalization import normalize_code_response


@dataclass(frozen=True, slots=True)
class ContaminationAssessment:
    task_id: str
    contaminated: bool
    suspicion_score: float
    canary_coverage: float
    accused_asset_ids: tuple[str, ...]
    false_positive_bound: float
    evidence_trace: tuple[str, ...]
    evidence_stage: int = 0
    gate_vector: tuple[int, ...] = ()
    canary_evidence_count: int = 0
    semantic_witness_count: int = 0
    witness_density: float = 0.0
    output_visible_canary_evidence_count: int = 0
    admissible_output_visible_canary_evidence_count: int = 0
    diagnostic_evidence_count: int = 0
    hidden_test_family_diagnostic_only: bool = False
    direct_output_visible_canary_count: int = 0
    semantic_output_visible_canary_count: int = 0
    prompt_context_canary_evidence_count: int = 0
    study_kind: str = "deepseek_live_null_audit"


def _witness_density(canary_evidence: tuple[str, ...]) -> float:
    # Only admissible output-visible evidence contributes to the headline witness density.
    categories = (
        any(item.startswith("canary_hit:") for item in canary_evidence),
        any(item.startswith("semantic_canary_hit:") for item in canary_evidence),
    )
    return round(sum(1 for flag in categories if flag) / len(categories), 4)


def _evidence_stage(
    gate_signals: dict[str, bool],
    *,
    semantic_witness_present: bool,
    canary_coverage: float,
    witness_density: float,
    canary_evidence_count: int,
) -> int:
    family_supported = gate_signals["family_observed"]
    structural_supported = gate_signals["ast_or_stable_witness"]
    contextual_supported = gate_signals["heldout_or_rewrite_context"]
    weak_canary_supported = gate_signals["weak_canary"]
    strong_canary_supported = gate_signals["direct_canary"] or semantic_witness_present

    if not family_supported:
        return 0
    if not (structural_supported or contextual_supported):
        return 1
    if strong_canary_supported and structural_supported and (contextual_supported or canary_evidence_count >= 2) and witness_density >= 0.25:
        return 4
    if strong_canary_supported and structural_supported and canary_evidence_count >= 1:
        return 3
    if not weak_canary_supported:
        return 2
    return 2 if canary_coverage >= 0.5 else 1


def evaluate_contamination(
    task: BenchmarkTask,
    code: str | None = None,
    *,
    observed_prompt: str | None = None,
) -> ContaminationAssessment:
    metadata = task_metadata(task)
    protected_asset_id = metadata.get("protected_asset_id", task.task_id)
    chronology_tag = metadata.get("chronology_tag", "")
    chronology_split = task_chronology_split(task)
    release_window = task_release_window(task)
    canary_split = task_canary_split(task)
    hidden_test_family = task_hidden_test_family(task)
    review_status = task_review_status(task)
    candidate_code = normalize_code_response(task.reference_code if code is None else code)
    family = task_target_family(task)
    observation = observe_family(candidate_code, family)
    canary_report = measure_canary_evidence(
        task,
        candidate_code,
        observed_prompt=task.prompt if observed_prompt is None else observed_prompt,
    )
    canary_coverage = canary_report.coverage
    canary_evidence = canary_report.evidence
    output_visible_canary_evidence = canary_report.output_visible_evidence
    diagnostic_evidence = canary_report.diagnostic_evidence
    prompt_context_canary_evidence = canary_report.prompt_context_evidence
    canary_evidence_present = bool(output_visible_canary_evidence)
    semantic_witness_count = canary_report.semantic_output_visible_canary_count
    hidden_evidence_present = canary_report.hidden_test_family_diagnostic_only
    semantic_witness_present = semantic_witness_count > 0
    witness_density = _witness_density(output_visible_canary_evidence)
    gate_signals = {
        "family_observed": observation.observed_bit is not None and observation.confidence >= 0.74,
        "ast_or_stable_witness": (
            observation.evidence_source == "ast" and observation.stability_score >= 0.76
        )
        or (semantic_witness_present and observation.forensic_weight >= 0.84),
        "direct_canary": canary_report.direct_output_visible_canary_count > 0,
        "weak_canary": canary_evidence_present,
        "heldout_or_rewrite_context": chronology_split == "post_release_holdout"
        or canary_split in {"hidden_test_family", "rewrite_marker"}
        or task.subset in {"cross_language_variants", "canary_preserving_rewrites"},
    }
    passed_gates = tuple(name for name, passed in gate_signals.items() if passed)
    evidence_stage = _evidence_stage(
        gate_signals,
        semantic_witness_present=semantic_witness_present,
        canary_coverage=canary_coverage,
        witness_density=witness_density,
        canary_evidence_count=len(output_visible_canary_evidence),
    )
    gate_order = (
        "family_observed",
        "ast_or_stable_witness",
        "direct_canary",
        "weak_canary",
        "heldout_or_rewrite_context",
    )
    gate_vector = tuple(1 if gate_signals[name] else 0 for name in gate_order)
    suspicion_score = round(evidence_stage / 4, 4)
    contaminated = evidence_stage == 4
    heuristic_stage_bound = (
        0.01
        if evidence_stage == 4
        else 0.05
        if evidence_stage == 2
        else 0.05
        if evidence_stage == 3
        else 0.2
        if evidence_stage == 1
        else 0.5
    )
    evidence_trace = (
        f"family:{family}",
        f"observed_bit:{observation.observed_bit}",
        f"family_confidence:{observation.confidence:.4f}",
        f"canary_coverage:{canary_coverage:.4f}",
        f"canary_evidence_count:{len(output_visible_canary_evidence)}",
        f"admissible_output_visible_canary_evidence_count:{len(output_visible_canary_evidence)}",
        f"diagnostic_evidence_count:{len(diagnostic_evidence)}",
        f"prompt_context_canary_evidence_count:{len(prompt_context_canary_evidence)}",
        f"direct_output_visible_canary_count:{canary_report.direct_output_visible_canary_count}",
        f"semantic_output_visible_canary_count:{semantic_witness_count}",
        f"hidden_test_family_diagnostic_only:{int(hidden_evidence_present)}",
        f"witness_density:{witness_density:.4f}",
        f"chronology_tag:{chronology_tag or 'none'}",
        f"chronology_split:{chronology_split}",
        f"release_window:{release_window}",
        f"canary_split:{canary_split}",
        f"hidden_test_family:{hidden_test_family}",
        f"review_status:{review_status}",
        f"subset:{task.subset}",
        f"decision_rule:non_weighted_gate_familywise",
        "contamination_score_source:evidence_stage_ratio",
        "headline_evidence_rule:admissible_output_visible_evidence_only",
        "hidden_test_family_rule:diagnostic_only_not_headline",
        f"evidence_stage:{evidence_stage}/4",
        f"heuristic_stage_bound:{heuristic_stage_bound:.4f}",
        f"passed_gate_count:{len(passed_gates)}",
        f"passed_gates:{'|'.join(passed_gates) if passed_gates else 'none'}",
        f"gate_family_observed:{int(gate_signals['family_observed'])}",
        f"gate_ast_or_stable_witness:{int(gate_signals['ast_or_stable_witness'])}",
        f"gate_direct_canary:{int(gate_signals['direct_canary'])}",
        f"gate_weak_canary:{int(gate_signals['weak_canary'])}",
        f"gate_contextual_holdout:{int(gate_signals['heldout_or_rewrite_context'])}",
        f"semantic_witness_present:{int(semantic_witness_present)}",
    ) + canary_evidence
    return ContaminationAssessment(
        task_id=task.task_id,
        contaminated=contaminated,
        suspicion_score=suspicion_score,
        canary_coverage=round(canary_coverage, 4),
        accused_asset_ids=(protected_asset_id,) if contaminated else (),
        false_positive_bound=heuristic_stage_bound,
        evidence_trace=evidence_trace,
        evidence_stage=evidence_stage,
        gate_vector=gate_vector,
        canary_evidence_count=len(output_visible_canary_evidence),
        semantic_witness_count=semantic_witness_count,
        witness_density=witness_density,
        output_visible_canary_evidence_count=len(output_visible_canary_evidence),
        admissible_output_visible_canary_evidence_count=len(output_visible_canary_evidence),
        diagnostic_evidence_count=len(diagnostic_evidence),
        hidden_test_family_diagnostic_only=hidden_evidence_present,
        direct_output_visible_canary_count=canary_report.direct_output_visible_canary_count,
        semantic_output_visible_canary_count=canary_report.semantic_output_visible_canary_count,
        prompt_context_canary_evidence_count=len(prompt_context_canary_evidence),
    )
