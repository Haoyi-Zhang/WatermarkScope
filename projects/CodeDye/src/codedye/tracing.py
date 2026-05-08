from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from typing import Any

from .protocol import ProviderSampleTrace, ProviderTrace
from .reranker import FAMILY_ORDER, observe_family
from .response_normalization import normalize_code_response


def hash_text(text: str, *, width: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:width]


def trace_request_id(provider_name: str, prompt: str, sample_index: int) -> str:
    seed = f"{provider_name}|{sample_index}|{prompt}"
    return f"req_{hash_text(seed, width=12)}"


def prompt_preview(prompt: str, *, width: int = 96) -> str:
    normalized = " ".join(prompt.split())
    if len(normalized) <= width:
        return normalized
    return normalized[: width - 3] + "..."


def infer_dominant_family(code: str) -> tuple[str, int | None, float]:
    best_family = FAMILY_ORDER[0]
    best_bit: int | None = None
    best_confidence = -1.0
    for family in FAMILY_ORDER:
        observation = observe_family(code, family)
        if observation.confidence > best_confidence:
            best_family = family
            best_bit = observation.observed_bit
            best_confidence = observation.confidence
    return best_family, best_bit, max(best_confidence, 0.0)


def trace_samples(
    provider_name: str,
    prompt: str,
    responses: list[str],
) -> tuple[ProviderSampleTrace, ...]:
    samples: list[ProviderSampleTrace] = []
    for index, response in enumerate(responses):
        normalized_response = normalize_code_response(response)
        family, observed_bit, confidence = infer_dominant_family(normalized_response)
        response_hash = hash_text(normalized_response, width=24)
        request_id = trace_request_id(provider_name, prompt, index)
        transcript_hash = hash_text(f"{request_id}|{response_hash}|{family}|{observed_bit}", width=24)
        samples.append(
            ProviderSampleTrace(
                sample_index=index,
                response_text=response,
                response_hash=response_hash,
                observed_family=family,
                observed_bit=observed_bit,
                confidence=round(confidence, 4),
                request_id=request_id,
                transcript_hash=transcript_hash,
            )
        )
    return tuple(samples)


def build_provider_trace(
    provider_name: str,
    provider_mode: str,
    model_name: str,
    prompt: str,
    responses: list[str],
    *,
    latency_ms: float,
    model_revision: str = "",
    usage_tokens: int = 0,
    notes: tuple[str, ...] = (),
) -> ProviderTrace:
    samples = trace_samples(provider_name, prompt, responses)
    request_ids = tuple(sample.request_id for sample in samples)
    joined_hashes = ",".join(sample.response_hash for sample in samples)
    trace_hash = hash_text(f"{provider_name}|{provider_mode}|{prompt}|{joined_hashes}|{latency_ms}", width=24)
    return ProviderTrace(
        provider_name=provider_name,
        provider_mode=provider_mode,
        model_name=model_name,
        prompt_hash=hash_text(prompt, width=24),
        prompt_preview=prompt_preview(prompt),
        requested_sample_count=len(responses),
        returned_sample_count=len(samples),
        latency_ms=round(latency_ms, 4),
        model_revision=model_revision,
        usage_tokens=usage_tokens,
        request_ids=request_ids,
        samples=samples,
        transcript_hash=trace_hash,
        notes=notes,
    )


def replay_cassette_payload(trace: ProviderTrace) -> dict[str, Any]:
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "provider_name": trace.provider_name,
        "provider_mode": trace.provider_mode,
        "model_name": trace.model_name,
        "model_revision": trace.model_revision,
        "prompt_hash": trace.prompt_hash,
        "prompt_preview": trace.prompt_preview,
        "requested_sample_count": trace.requested_sample_count,
        "returned_sample_count": trace.returned_sample_count,
        "latency_ms": trace.latency_ms,
        "usage_tokens": trace.usage_tokens,
        "request_ids": list(trace.request_ids),
        "transcript_hash": trace.transcript_hash,
        "created_at_utc": created_at,
        "responses": [sample.response_text for sample in trace.samples],
        "samples": [asdict(sample) for sample in trace.samples],
        "notes": list(trace.notes),
    }


def commitment_audit_payload(
    trace: ProviderTrace,
    candidate_commitments: tuple[str, ...],
    selected_index: int,
    service_commitment_root: str,
) -> dict[str, Any]:
    selected_hash = trace.samples[selected_index].response_hash if trace.samples and 0 <= selected_index < len(trace.samples) else ""
    return {
        "provider_name": trace.provider_name,
        "provider_mode": trace.provider_mode,
        "prompt_hash": trace.prompt_hash,
        "transcript_hash": trace.transcript_hash,
        "request_ids": list(trace.request_ids),
        "candidate_commitments": list(candidate_commitments),
        "selected_index": selected_index,
        "selected_response_hash": selected_hash,
        "service_commitment_root": service_commitment_root,
    }


def provider_trace_to_dict(trace: ProviderTrace) -> dict[str, Any]:
    return asdict(trace)


def provider_trace_from_payload(payload: dict[str, Any]) -> ProviderTrace:
    samples = tuple(
        ProviderSampleTrace(
            sample_index=int(item["sample_index"]),
            response_text=str(item["response_text"]),
            response_hash=str(item["response_hash"]),
            observed_family=str(item["observed_family"]),
            observed_bit=None if item.get("observed_bit") is None else int(item["observed_bit"]),
            confidence=float(item["confidence"]),
            request_id=str(item.get("request_id", "")),
            transcript_hash=str(item.get("transcript_hash", "")),
        )
        for item in payload.get("samples", [])
    )
    return ProviderTrace(
        provider_name=str(payload["provider_name"]),
        provider_mode=str(payload["provider_mode"]),
        model_name=str(payload["model_name"]),
        prompt_hash=str(payload["prompt_hash"]),
        prompt_preview=str(payload["prompt_preview"]),
        requested_sample_count=int(payload["requested_sample_count"]),
        returned_sample_count=int(payload["returned_sample_count"]),
        latency_ms=float(payload["latency_ms"]),
        model_revision=str(payload.get("model_revision", "")),
        usage_tokens=int(payload.get("usage_tokens", 0)),
        request_ids=tuple(str(item) for item in payload.get("request_ids", [])),
        samples=samples,
        transcript_hash=str(payload.get("transcript_hash", "")),
        notes=tuple(str(item) for item in payload.get("notes", [])),
    )


def write_replay_cassette(path: str, trace: ProviderTrace) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(replay_cassette_payload(trace), handle, indent=2, ensure_ascii=True)
