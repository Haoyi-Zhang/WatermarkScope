from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Sequence


DEFAULT_SIGNATURE_BITS = 64
DEFAULT_ASSET_KEY_ENV = "CODEDYE_ASSET_KEY"
DEFAULT_ASSET_KEY_PLACEHOLDER = "codedye-demo-asset-key"
_ASSET_ID_DOMAIN = "codedye-asset-id-v1"
_PROBE_DOMAIN = "codedye-probe-commitment-v1"
_RESPONSE_DOMAIN = "codedye-response-commitment-v1"
_TRACE_DOMAIN = "codedye-trace-commitment-v1"


def load_asset_key() -> str:
    return os.environ.get(DEFAULT_ASSET_KEY_ENV, DEFAULT_ASSET_KEY_PLACEHOLDER)


def _hmac_hex(asset_key: str, *parts: object, length: int | None = None) -> str:
    payload = "::".join(str(part) for part in parts).encode("utf-8")
    digest = hmac.new(asset_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    if length is None:
        return digest
    return digest[:length]


def asset_key_to_asset_id(asset_key: str, bits: int = DEFAULT_SIGNATURE_BITS) -> str:
    if bits <= 0 or bits % 4 != 0:
        raise ValueError("bits must be positive and divisible by 4")
    return _hmac_hex(asset_key, _ASSET_ID_DOMAIN, bits, length=bits // 4)


def asset_key_to_bitstream(asset_key: str, bits: int = DEFAULT_SIGNATURE_BITS) -> tuple[int, ...]:
    asset_id = asset_key_to_asset_id(asset_key, bits=bits)
    packed = "".join(f"{int(nibble, 16):04b}" for nibble in asset_id)
    return tuple(int(bit) for bit in packed[:bits])


def derive_probe_commitment(asset_key: str, tenant_id: str, session_id: str, prompt_id: str) -> str:
    return _hmac_hex(asset_key, _PROBE_DOMAIN, tenant_id, session_id, prompt_id)


def derive_probe_bit(asset_key: str, tenant_id: str, session_id: str, prompt_id: str) -> int:
    return int(derive_probe_commitment(asset_key, tenant_id, session_id, prompt_id)[0], 16) & 1


def derive_probe_nonce(asset_key: str, tenant_id: str, session_id: str, prompt_id: str) -> str:
    return _hmac_hex(asset_key, _PROBE_DOMAIN, "nonce", tenant_id, session_id, prompt_id, length=12)


def derive_session_commitment_root(
    asset_key: str,
    tenant_id: str,
    session_id: str,
    prompt_ids: Sequence[str],
) -> str:
    return _hmac_hex(asset_key, _PROBE_DOMAIN, "session-root", tenant_id, session_id, "|".join(prompt_ids), length=24)


def derive_probe_priority(
    asset_key: str,
    tenant_id: str,
    session_id: str,
    prompt_id: str,
    subset: str,
) -> float:
    raw = int(_hmac_hex(asset_key, _PROBE_DOMAIN, "priority", tenant_id, session_id, prompt_id, subset, length=8), 16)
    return 1.0 + (raw % 41) / 100.0


def derive_candidate_commitment(
    asset_key: str,
    tenant_id: str,
    session_id: str,
    prompt: str,
    candidate_code: str,
    candidate_index: int,
) -> str:
    return _hmac_hex(
        asset_key,
        _RESPONSE_DOMAIN,
        "candidate",
        tenant_id,
        session_id,
        candidate_index,
        prompt,
        candidate_code,
        length=24,
    )


def derive_response_commitment(
    asset_key: str,
    tenant_id: str,
    session_id: str,
    prompt_id: str,
    response_text: str,
) -> str:
    return _hmac_hex(asset_key, _RESPONSE_DOMAIN, tenant_id, session_id, prompt_id, response_text, length=24)


def derive_service_log_commitment(
    asset_key: str,
    tenant_id: str,
    session_id: str,
    prompt: str,
    candidate_commitments: Sequence[str],
    selected_index: int,
) -> str:
    joined = ",".join(candidate_commitments)
    return _hmac_hex(asset_key, _TRACE_DOMAIN, "service-log", tenant_id, session_id, selected_index, prompt, joined, length=24)


def derive_trace_commitment(
    asset_key: str,
    tenant_id: str,
    session_id: str,
    query_index: int,
    prompt_commitment: str,
    response_commitment: str,
    previous_trace_commitment: str = "",
) -> str:
    return _hmac_hex(
        asset_key,
        _TRACE_DOMAIN,
        tenant_id,
        session_id,
        query_index,
        prompt_commitment,
        response_commitment,
        previous_trace_commitment,
        length=24,
    )
