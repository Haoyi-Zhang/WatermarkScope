from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ProbePrompt:
    prompt_id: str
    text: str
    target_family: str
    target_bit: int
    session_id: str = "session-default"
    tenant_id: str = "public"
    commitment: str = ""
    subset: str = "probe_prompts"
    rationale: str = ""
    selection_weight: float = 1.0
    query_cost: int = 1
    budget_priority: float = 1.0
    trace_anchor: str = ""
    probe_nonce: str = ""
    calibration_bucket: str = "service_style"


@dataclass(frozen=True, slots=True)
class ProviderSampleTrace:
    sample_index: int
    response_text: str
    response_hash: str
    observed_family: str
    observed_bit: int | None
    confidence: float
    request_id: str = ""
    transcript_hash: str = ""


@dataclass(frozen=True, slots=True)
class ProviderTrace:
    provider_name: str
    provider_mode: str
    model_name: str
    prompt_hash: str
    prompt_preview: str
    requested_sample_count: int
    returned_sample_count: int
    latency_ms: float
    model_revision: str = ""
    usage_tokens: int = 0
    request_ids: tuple[str, ...] = field(default_factory=tuple)
    samples: tuple[ProviderSampleTrace, ...] = field(default_factory=tuple)
    transcript_hash: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class FamilyObservation:
    family: str
    observed_bit: int | None
    confidence: float
    evidence_source: str = ""
    forensic_weight: float = 0.0
    stability_score: float = 0.0
    matches: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProbeEvidence:
    prompt_id: str
    target_family: str
    expected_bit: int
    observed_bit: int | None
    confidence: float
    prompt_commitment: str = ""
    response_commitment: str = ""
    trace_commitment: str = ""
    subset: str = ""
    query_index: int = 0
    query_cost: int = 1
    agreement_score: float = 0.0
    trace_score: float = 0.0
    evidence_source: str = ""
    forensic_weight: float = 0.0
    stability_score: float = 0.0
    matches: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AssetScorecard:
    asset_id: str
    score: float
    mean_agreement: float
    mean_forensic_weight: float
    trace_consistency: float
    query_count: int


@dataclass(frozen=True, slots=True)
class WrappedGeneration:
    watermarked_code: str
    asset_id: str
    selected_family: str
    expected_bit: int
    chosen_index: int
    confidence: float
    query_count: int = 0
    latency_ms: float = 0.0
    session_id: str = "session-default"
    commitment: str = ""
    service_commitment_root: str = ""
    selected_candidate_commitment: str = ""
    candidate_commitments: tuple[str, ...] = field(default_factory=tuple)
    candidate_trace_hashes: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ContaminationDecision:
    contaminated: bool
    accused_asset_ids: tuple[str, ...]
    contamination_score: float
    p_value_or_score: float
    false_positive_bound: float
    accusation_eligibility_bound: float
    familywise_test_count: int
    null_sample_size: int
    strongest_null_score: float
    strongest_null_margin: float
    query_count: int
    matched_null_sample_size: int = 0
    null_pool_strategy: str = ""
    null_pool_tier: int = 0
    null_pool_fallback_used: bool = False
    null_calibration_method: str = ""
    strongest_null_task_id: str = ""
    witness_density: float = 0.0
    output_visible_canary_evidence_count: int = 0
    admissible_output_visible_canary_evidence_count: int = 0
    diagnostic_evidence_count: int = 0
    hidden_test_family_diagnostic_only: bool = False
    direct_output_visible_canary_count: int = 0
    semantic_output_visible_canary_count: int = 0
    prompt_context_canary_evidence_count: int = 0
    study_kind: str = "deepseek_live_null_audit"
    latency_ms: float = 0.0
    extra_query_cost: int = 0
    margin: float = 0.0
    query_budget_used: int = 0
    calibrated_threshold: float = 0.0
    canary_coverage: float = 0.0
    trace_consistency: float = 0.0
    familywise_adjusted_p_value: float = 1.0
    familywise_decision_gate_pass: bool = False
    service_commitment_root: str = ""
    commitment_trace_root: str = ""
    probe_evidence: tuple[ProbeEvidence, ...] = field(default_factory=tuple)
    top_asset_scores: tuple[AssetScorecard, ...] = field(default_factory=tuple)
    evidence_trace: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DistillationSimulation:
    student_name: str
    inherited_asset_id: str | None
    inheritance_rate: float
    copied_probe_count: int
    student_recipe_name: str = ""
    learned_families: tuple[str, ...] = field(default_factory=tuple)
    family_preferences: tuple[tuple[str, int], ...] = field(default_factory=tuple)
    distilled_outputs: tuple["DistilledOutput", ...] = field(default_factory=tuple)
    utility_score: float = 0.0
    compile_rate: float = 0.0
    pass_rate: float = 0.0
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class BackboneConfig:
    name: str
    model_name: str
    provider_alias: str
    family: str


@dataclass(frozen=True, slots=True)
class RunManifest:
    run_name: str
    project: str
    stage: str
    backbone_names: tuple[str, ...]
    benchmark_names: tuple[str, ...]
    baseline_names: tuple[str, ...]
    subsets: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class BenchmarkTask:
    benchmark: str
    task_id: str
    prompt: str
    language: str
    reference_code: str
    tests: tuple[str, ...] = ()
    subset: str = "smoke"
    source: str = "project_local"
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class UtilityRecord:
    benchmark: str
    task_id: str
    language: str
    compile_supported: bool
    compile_ok: bool | None
    pass_supported: bool
    pass_ok: bool | None
    source: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExtractionQueryLog:
    provider: str
    mode: str
    sample_count: int
    raw_candidate_count: int
    passing_candidate_count: int
    selected_from_passing_pool: bool
    latency_ms: float
    prompt_hash: str = ""
    transcript_hash: str = ""
    service_commitment_root: str = ""
    selected_candidate_commitment: str = ""
    selected_candidate_trace_hash: str = ""
    candidate_commitments: tuple[str, ...] = field(default_factory=tuple)
    candidate_trace_hashes: tuple[str, ...] = field(default_factory=tuple)
    request_ids: tuple[str, ...] = field(default_factory=tuple)
    candidate_reports: tuple[UtilityRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ExtractionRecord:
    backbone_name: str
    model_name: str
    task: BenchmarkTask
    wrapped_generation: WrappedGeneration
    utility: UtilityRecord
    code: str
    query_log: ExtractionQueryLog


@dataclass(frozen=True, slots=True)
class DistilledOutput:
    task: BenchmarkTask
    code: str
    family: str
    inferred_bit: int
    utility: UtilityRecord
