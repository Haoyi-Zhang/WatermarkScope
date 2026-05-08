from __future__ import annotations

from collections.abc import Callable, Sequence
from time import perf_counter

from .probes import prompt_commitment_target
from .protocol import ProviderTrace, WrappedGeneration
from .reranker import rank_candidates
from .response_normalization import normalize_code_response
from .signature import (
    derive_candidate_commitment,
    derive_service_log_commitment,
    asset_key_to_asset_id,
)
from .tracing import commitment_audit_payload

Sampler = Callable[[str, int], Sequence[object]]


def _candidate_text(candidate: object) -> str:
    if isinstance(candidate, str):
        return normalize_code_response(candidate)
    if isinstance(candidate, dict) and "response_text" in candidate:
        return normalize_code_response(str(candidate["response_text"]))
    if isinstance(candidate, dict) and "text" in candidate:
        return normalize_code_response(str(candidate["text"]))
    if hasattr(candidate, "response_text"):
        return normalize_code_response(str(getattr(candidate, "response_text")))
    if hasattr(candidate, "text"):
        return normalize_code_response(str(getattr(candidate, "text")))
    return normalize_code_response(str(candidate))


class CodeDyeWrapper:
    """Black-box release wrapper that selects contamination-aligned samples under a session commitment."""

    def __init__(self, sampler: Sampler, sample_count: int = 4) -> None:
        self._sampler = sampler
        self._sample_count = sample_count

    def wrap_candidates(
        self,
        prompt: str,
        asset_key: str,
        candidates: Sequence[object],
        user_tag: str | None = None,
    ) -> WrappedGeneration:
        target_family, target_bit, session_id, commitment = prompt_commitment_target(
            asset_key,
            prompt,
            user_tag=user_tag,
        )
        tenant_id = "public"
        normalized_candidates = tuple(_candidate_text(candidate) for candidate in candidates)
        if not normalized_candidates:
            raise ValueError("sampler returned no candidates")
        chosen_index, observation, score = rank_candidates(
            normalized_candidates,
            target_family=target_family,
            target_bit=target_bit,
        )
        candidate_commitments = tuple(
            derive_candidate_commitment(asset_key, tenant_id, session_id, prompt, candidate, index)
            for index, candidate in enumerate(normalized_candidates)
        )
        service_commitment_root = derive_service_log_commitment(
            asset_key,
            tenant_id,
            session_id,
            prompt,
            candidate_commitments,
            chosen_index,
        )
        candidate_trace_hashes = tuple(f"candidate:{index}:{commitment}" for index, commitment in enumerate(candidate_commitments))
        return WrappedGeneration(
            watermarked_code=normalized_candidates[chosen_index],
            asset_id=asset_key_to_asset_id(asset_key),
            selected_family=target_family,
            expected_bit=target_bit,
            chosen_index=chosen_index,
            confidence=round(score, 4),
            query_count=len(normalized_candidates),
            latency_ms=0.0,
            session_id=session_id,
            commitment=commitment,
            service_commitment_root=service_commitment_root,
            selected_candidate_commitment=candidate_commitments[chosen_index],
            candidate_commitments=candidate_commitments,
            candidate_trace_hashes=candidate_trace_hashes,
            notes=(
                "black_box_wrapper",
                "auditable_service_commitment",
                "selection_uses_candidate_reranking_only",
                "no_model_weight_or_logit_access",
                "candidate_inputs_normalized_to_text",
            ),
        )

    def wrap_trace(self, prompt: str, asset_key: str, trace: ProviderTrace, user_tag: str | None = None) -> WrappedGeneration:
        wrapped = self.wrap_candidates(prompt, asset_key, tuple(sample.response_text for sample in trace.samples), user_tag=user_tag)
        audit_payload = commitment_audit_payload(
            trace,
            wrapped.candidate_commitments,
            wrapped.chosen_index,
            wrapped.service_commitment_root,
        )
        notes = wrapped.notes + (
            f"provider_mode:{trace.provider_mode}",
            f"transcript_hash:{trace.transcript_hash}",
            f"selected_response_hash:{audit_payload['selected_response_hash']}",
        )
        return WrappedGeneration(
            watermarked_code=wrapped.watermarked_code,
            asset_id=wrapped.asset_id,
            selected_family=wrapped.selected_family,
            expected_bit=wrapped.expected_bit,
            chosen_index=wrapped.chosen_index,
            confidence=wrapped.confidence,
            query_count=wrapped.query_count,
            latency_ms=trace.latency_ms,
            session_id=wrapped.session_id,
            commitment=wrapped.commitment,
            service_commitment_root=wrapped.service_commitment_root,
            selected_candidate_commitment=wrapped.selected_candidate_commitment,
            candidate_commitments=wrapped.candidate_commitments,
            candidate_trace_hashes=tuple(
                f"{trace.samples[index].transcript_hash}:{commitment}"
                for index, commitment in enumerate(wrapped.candidate_commitments)
            ),
            notes=notes,
        )

    def wrap_generate(self, prompt: str, asset_key: str, user_tag: str | None = None) -> WrappedGeneration:
        started = perf_counter()
        candidates = tuple(self._sampler(prompt, self._sample_count))
        elapsed_ms = round((perf_counter() - started) * 1000.0, 4)
        wrapped = self.wrap_candidates(prompt, asset_key, candidates, user_tag=user_tag)
        return WrappedGeneration(
            watermarked_code=wrapped.watermarked_code,
            asset_id=wrapped.asset_id,
            selected_family=wrapped.selected_family,
            expected_bit=wrapped.expected_bit,
            chosen_index=wrapped.chosen_index,
            confidence=wrapped.confidence,
            query_count=wrapped.query_count,
            latency_ms=elapsed_ms,
            session_id=wrapped.session_id,
            commitment=wrapped.commitment,
            service_commitment_root=wrapped.service_commitment_root,
            selected_candidate_commitment=wrapped.selected_candidate_commitment,
            candidate_commitments=wrapped.candidate_commitments,
            candidate_trace_hashes=wrapped.candidate_trace_hashes,
            notes=wrapped.notes,
        )


def wrap_generate(
    prompt: str,
    asset_key: str,
    user_tag: str | None = None,
    sampler: Sampler | None = None,
    sample_count: int = 4,
) -> str:
    if sampler is None:
        raise ValueError("sampler is required for the scaffold")
    wrapper = CodeDyeWrapper(sampler=sampler, sample_count=sample_count)
    return wrapper.wrap_generate(prompt, asset_key, user_tag=user_tag).watermarked_code
