from __future__ import annotations

import hashlib
import json
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Protocol

from .protocol import ProviderTrace
from .probes import prompt_family_from_text
from .tracing import build_provider_trace


Transport = Callable[[dict[str, Any], "ProviderConfig"], list[str]]

_PLACEHOLDER_KEY_MARKERS = (
    "placeholder",
    "replace-me",
    "replace_me",
    "changeme",
    "change_me",
    "dummy",
    "example",
    "your-",
    "your_",
    "test-key",
    "<api-key>",
)
PLACEHOLDER_BASE_URL = "https" + "://placeholder.invalid"


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    name: str
    api_key_env: str
    base_url: str
    model_name: str
    provider_kind: str = "openai_compatible"
    api_key: str = ""


class ProviderClient(Protocol):
    def generate(self, prompt: str, sample_count: int = 1) -> list[str]:
        ...

    def generate_structured(self, prompt: str, sample_count: int = 1) -> ProviderTrace:
        ...

    def summary(self) -> dict[str, object]:
        ...


_FAMILY_FIXTURES: dict[str, dict[int, str]] = {
    "guard_first": {
        0: "def solve(items):\n    result = []\n    if items:\n        result = list(items)\n    else:\n        result = []\n    return result\n",
        1: "def solve(items):\n    if not items:\n        return []\n    return list(items)\n",
    },
    "lookup_idiom": {
        0: "def solve(mapping, key, default):\n    if key in mapping:\n        return mapping[key]\n    return default\n",
        1: "def solve(mapping, key, default):\n    return mapping.get(key, default)\n",
    },
    "iteration_idiom": {
        0: "def solve(items):\n    total = 0\n    for item in items:\n        total += item\n    return total\n",
        1: "def solve(items):\n    total = 0\n    for index in range(len(items)):\n        total += items[index]\n    return total\n",
    },
    "helper_split": {
        0: "def solve(text):\n    parts = [chunk.strip() for chunk in text.split(',')]\n    return [part for part in parts if part]\n",
        1: "def probe_helper(chunk):\n    return chunk.strip()\n\ndef solve(text):\n    return [probe_helper(chunk) for chunk in text.split(',') if chunk.strip()]\n",
    },
    "container_choice": {
        0: "def solve(items):\n    result = []\n    for item in items:\n        if item not in result:\n            result.append(item)\n    return result\n",
        1: "def solve(items):\n    return list(dict.fromkeys(items))\n",
    },
    "temporary_variable": {
        0: "def solve(items):\n    total = 0\n    for item in items:\n        total += item\n    return total\n",
        1: "def solve(items):\n    probe_buffer = 0\n    for item in items:\n        probe_buffer = probe_buffer + item\n    return probe_buffer\n",
    },
}


def render_family_candidate(family: str, bit: int) -> str:
    return _FAMILY_FIXTURES[family][bit]


def render_prompt_candidate(prompt: str, family: str, bit: int) -> str:
    inferred_family = prompt_family_from_text(prompt)
    if inferred_family == family:
        return render_family_candidate(family, bit)
    if family in _FAMILY_FIXTURES:
        return render_family_candidate(family, bit)
    return render_family_candidate(inferred_family, bit)


def _coerce_provider_config(config_or_name: ProviderConfig | str) -> ProviderConfig:
    if isinstance(config_or_name, ProviderConfig):
        return config_or_name
    return ProviderConfig(
        name=str(config_or_name),
        api_key_env="DUMMY_API_KEY",
        base_url=PLACEHOLDER_BASE_URL,
        model_name=f"{config_or_name}-mock-model",
        provider_kind="openai_compatible",
    )


def provider_prompt_family(prompt: str) -> str:
    lowered = prompt.lower()
    if "counter" in lowered or "nested record" in lowered or "list of counters" in lowered:
        return "temporary_variable"
    if "lowercase word tokens" in lowered or ("tokens" in lowered and "string" in lowered):
        return "helper_split"
    if "diagonal values" in lowered or "rectangular matrix" in lowered or "matrix" in lowered:
        return "iteration_idiom"
    if "json-like records" in lowered or ("value field" in lowered and "records" in lowered):
        return "helper_split"
    if "validates a list of integers" in lowered or "normalized list" in lowered:
        return "guard_first"
    if "mapping" in lowered or "lookup" in lowered or "default fallback" in lowered or "default value" in lowered:
        return "lookup_idiom"
    if "weighted sum" in lowered or "sums a list of integers using a loop" in lowered or "reverses the order of words" in lowered:
        return "iteration_idiom"
    if "comma-separated" in lowered or "record string" in lowered or "tokens" in lowered or "joins path fragments" in lowered:
        return "helper_split"
    if "duplicate" in lowered or "stable order" in lowered or "stable output" in lowered or "index pairs" in lowered:
        return "container_choice"
    if "counter" in lowered or "nested record" in lowered or "nested records" in lowered:
        return "temporary_variable"
    return prompt_family_from_text(prompt)


def render_prompt_candidate(prompt: str, family: str, bit: int) -> str:
    lowered = prompt.lower()
    if family == "guard_first" and ("validates a list of integers" in lowered or "normalized list" in lowered):
        if bit == 0:
            return (
                "def solve(items):\n"
                "    result = []\n"
                "    if items:\n"
                "        for item in items:\n"
                "            if isinstance(item, int) and item >= 0:\n"
                "                result.append(item)\n"
                "    else:\n"
                "        result = []\n"
                "    return result\n"
            )
        return (
            "def solve(items):\n"
            "    if not items:\n"
            "        return []\n"
            "    return [item for item in items if isinstance(item, int) and item >= 0]\n"
        )
    if family == "lookup_idiom" and ("mapping" in lowered or "lookup" in lowered or "default" in lowered):
        if bit == 0:
            return (
                "def solve(mapping, key, default):\n"
                "    if key in mapping:\n"
                "        return mapping[key]\n"
                "    return default\n"
            )
        return "def solve(mapping, key, default):\n    return mapping.get(key, default)\n"
    if family == "iteration_idiom":
        if "reverses the order of words" in lowered:
            if bit == 0:
                return (
                    "def solve(text):\n"
                    "    words = text.split()\n"
                    "    words.reverse()\n"
                    "    return ' '.join(words)\n"
                )
            return (
                "def solve(text):\n"
                "    return ' '.join(reversed(text.split()))\n"
            )
        if "weighted sum" in lowered:
            if bit == 0:
                return (
                    "def solve(items):\n"
                    "    total = 0\n"
                    "    for index, item in enumerate(items):\n"
                    "        total += index * item\n"
                    "    return total\n"
                )
            return (
                "def solve(items):\n"
                "    total = 0\n"
                "    for index in range(len(items)):\n"
                "        total += index * items[index]\n"
                "    return total\n"
            )
        if "sum" in lowered and ("list" in lowered or "sequence" in lowered):
            if bit == 0:
                return (
                    "def solve(items):\n"
                    "    total = 0\n"
                    "    for item in items:\n"
                    "        total += item\n"
                    "    return total\n"
                )
            return (
                "def solve(items):\n"
                "    total = 0\n"
                "    for index in range(len(items)):\n"
                "        total += items[index]\n"
                "    return total\n"
            )
    if family == "helper_split" and ("comma-separated" in lowered or "record string" in lowered or "tokens" in lowered):
        if bit == 0:
            if "lowercase word tokens" in lowered:
                return (
                    "import re\n\n"
                    "def solve(text):\n"
                    "    return re.findall(r'[a-z]+', text.lower())\n"
                )
            return (
                "def solve(text):\n"
                "    return [chunk.strip() for chunk in text.split(',') if chunk.strip()]\n"
            )
        if "lowercase word tokens" in lowered:
            return (
                "import re\n\n"
                "def probe_helper(text):\n"
                "    return text.lower()\n\n"
                "def solve(text):\n"
                "    return re.findall(r'[a-z]+', probe_helper(text))\n"
            )
        return (
            "def probe_helper(chunk):\n"
            "    return chunk.strip()\n\n"
            "def solve(text):\n"
            "    return [probe_helper(chunk) for chunk in text.split(',') if probe_helper(chunk)]\n"
        )
    if family == "helper_split" and ("json-like records" in lowered or ("value field" in lowered and "records" in lowered)):
        if bit == 0:
            return (
                "def solve(records):\n"
                "    return [record['value'] for record in records if 'value' in record]\n"
            )
        return (
            "def probe_helper(record):\n"
            "    return record.get('value')\n\n"
            "def solve(records):\n"
            "    return [probe_helper(record) for record in records if 'value' in record]\n"
        )
    if family == "iteration_idiom" and ("diagonal values" in lowered or "rectangular matrix" in lowered or "matrix" in lowered):
        if bit == 0:
            return (
                "def solve(rows):\n"
                "    width = min(len(rows), len(rows[0]) if rows else 0)\n"
                "    diagonal = []\n"
                "    for index in range(width):\n"
                "        diagonal.append(rows[index][index])\n"
                "    return diagonal\n"
            )
        return (
            "def solve(rows):\n"
            "    diagonal = []\n"
            "    for index, row in enumerate(rows):\n"
            "        if index >= len(row):\n"
                "            break\n"
            "        diagonal.append(row[index])\n"
            "    return diagonal\n"
        )
    if family == "helper_split" and "joins path fragments" in lowered:
        if bit == 0:
            return (
                "import os\n\n"
                "def solve(parts):\n"
                "    return os.path.normpath(os.path.join(*parts)).replace('\\\\', '/')\n"
            )
        return (
            "import os\n\n"
            "def probe_helper(part):\n"
            "    return part.strip('/\\\\')\n\n"
            "def solve(parts):\n"
            "    cleaned = [probe_helper(part) for part in parts]\n"
            "    return os.path.normpath(os.path.join(*cleaned)).replace('\\\\', '/')\n"
        )
    if family == "container_choice" and ("duplicate" in lowered or "stable order" in lowered or "stable output" in lowered):
        if bit == 0:
            return (
                "def solve(items):\n"
                "    result = []\n"
                "    for item in items:\n"
                "        if item not in result:\n"
                "            result.append(item)\n"
                "    return result\n"
            )
        return "def solve(items):\n    return list(dict.fromkeys(items))\n"
    if family == "container_choice" and "index pairs" in lowered:
        if bit == 0:
            return (
                "def solve(values, target):\n"
                "    pairs = []\n"
                "    for i, left in enumerate(values):\n"
                "        for j in range(i + 1, len(values)):\n"
                "            if left + values[j] == target:\n"
                "                pairs.append((i, j))\n"
                "    return pairs\n"
            )
        return (
            "def solve(values, target):\n"
            "    pairs = []\n"
            "    for i in range(len(values)):\n"
            "        for j in range(i + 1, len(values)):\n"
            "            if values[i] + values[j] == target:\n"
            "                pairs.append((i, j))\n"
            "    return pairs\n"
        )
    if family == "temporary_variable" and ("counter" in lowered or "nested record" in lowered or "nested records" in lowered):
        if "list of counters" in lowered:
            if bit == 0:
                return (
                    "def solve(counters):\n"
                    "    total = 0\n"
                    "    for counter in counters:\n"
                    "        total += counter.get('value', 0)\n"
                    "    return total\n"
                )
            return (
                "def solve(counters):\n"
                "    total = 0\n"
                "    for counter in counters:\n"
                "        probe_buffer = counter.get('value', 0)\n"
                "        total += probe_buffer\n"
                "    return total\n"
            )
        if bit == 0:
            return (
                "def solve(records):\n"
                "    total = {}\n"
                "    for record in records:\n"
                "        for key, value in record.items():\n"
                "            total[key] = total.get(key, 0) + value\n"
                "    return total\n"
            )
        return (
            "def solve(records):\n"
            "    total = {}\n"
            "    for record in records:\n"
            "        for key, value in record.items():\n"
            "            probe_buffer = total.get(key, 0) + value\n"
            "            total[key] = probe_buffer\n"
            "    return total\n"
        )
    return render_family_candidate(family, bit)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_mode(prefer_mock: bool, prefer_replay: bool) -> str:
    if prefer_replay:
        return "replay"
    if prefer_mock:
        return "mock"
    return "live"


def _classify_api_key_value(value: str, env_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        return "missing"
    lowered = normalized.lower()
    env_lower = env_name.lower()
    if lowered in {env_lower, f"${env_lower}", f"${{{env_lower}}}"}:
        return "placeholder"
    if any(marker in lowered for marker in _PLACEHOLDER_KEY_MARKERS):
        return "placeholder"
    return "configured"


def _configured_api_key(config: ProviderConfig) -> str:
    local_key = config.api_key.strip()
    if _classify_api_key_value(local_key, config.api_key_env) == "configured":
        return local_key
    env_value = os.getenv(config.api_key_env, "").strip()
    if _classify_api_key_value(env_value, config.api_key_env) == "configured":
        return env_value
    return ""


def provider_api_key_state(config: ProviderConfig) -> str:
    if _configured_api_key(config):
        return "configured"
    return _classify_api_key_value(os.getenv(config.api_key_env, ""), config.api_key_env)


def resolve_provider_config_path(root: str | Path) -> Path:
    config_root = Path(root)
    if config_root.is_file():
        return config_root
    local_path = config_root / "configs" / "providers.local.json"
    if local_path.exists():
        return local_path
    return config_root / "configs" / "providers.example.json"


def _resolve_mode(config: ProviderConfig, requested_mode: str) -> tuple[str, tuple[str, ...]]:
    key_state = provider_api_key_state(config)
    if requested_mode == "replay":
        return "replay", ("replay_mode_never_calls_live_provider",)
    if requested_mode == "mock":
        return "mock", ("mock_mode_uses_local_family_fixtures",)
    if key_state == "configured":
        return "live", ("live_mode_enabled",)
    return "blocked", (f"live_mode_blocked_due_to_api_key_state:{key_state}",)


def _provider_summary(
    config: ProviderConfig,
    *,
    requested_mode: str,
    resolved_mode: str,
    replay_path: str | None,
    replay_payload_available: bool,
    notes: tuple[str, ...],
) -> dict[str, object]:
    _key_state = provider_api_key_state(config)
    return {
        "provider": config.name,
        "model_name": config.model_name,
        "base_url": config.base_url,
        "provider_kind": config.provider_kind,
        "credential_state": "redacted_runtime_config",
        "api_key_env": config.api_key_env,
        "api_key_source": "redacted",
        "api_key_state": "redacted",
        "requested_mode": requested_mode,
        "resolved_mode": resolved_mode,
        "replay_path": replay_path or "",
        "replay_payload_available": replay_payload_available,
        "available_modes": ("mock", "replay", "live"),
        "notes": notes,
    }


def _normalize_response_texts(entries: object) -> list[str]:
    if not isinstance(entries, list):
        return []
    texts: list[str] = []
    for item in entries:
        if isinstance(item, dict):
            if "response_text" in item:
                texts.append(str(item["response_text"]))
            elif "text" in item:
                texts.append(str(item["text"]))
            elif "response" in item:
                texts.append(str(item["response"]))
        else:
            texts.append(str(item))
    return texts


def _code_only_system_prompt() -> str:
    return (
        "You are a coding model. Return only executable code in the programming language "
        "specified by the user task. Do not include Markdown fences, prose, analysis, or "
        "surrounding explanation."
    )


class _BaseProviderClient:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        requested_mode: str,
        resolved_mode: str,
        replay_path: str | None = None,
        replay_payload_available: bool = False,
        notes: tuple[str, ...] = (),
    ) -> None:
        self._config = config
        self._requested_mode = requested_mode
        self._resolved_mode = resolved_mode
        self._replay_path = replay_path or ""
        self._replay_payload_available = replay_payload_available
        self._notes = notes

    def _build_trace(
        self,
        prompt: str,
        responses: list[str],
        *,
        latency_ms: float,
        notes: tuple[str, ...] = (),
        model_revision: str | None = None,
    ) -> ProviderTrace:
        return build_provider_trace(
            provider_name=self._config.name,
            provider_mode=self._resolved_mode,
            model_name=self._config.model_name,
            prompt=prompt,
            responses=responses,
            latency_ms=latency_ms,
            model_revision=model_revision or self._config.model_name,
            usage_tokens=sum(max(len(item.split()), 1) for item in responses),
            notes=self._notes + notes,
        )

    def generate(self, prompt: str, sample_count: int = 1) -> list[str]:
        trace = self.generate_structured(prompt, sample_count=sample_count)
        return [sample.response_text for sample in trace.samples]

    def summary(self) -> dict[str, object]:
        return _provider_summary(
            self._config,
            requested_mode=self._requested_mode,
            resolved_mode=self._resolved_mode,
            replay_path=self._replay_path,
            replay_payload_available=self._replay_payload_available,
            notes=self._notes,
        )


class MockProviderClient(_BaseProviderClient):
    def __init__(
        self,
        config: ProviderConfig | str,
        *,
        requested_mode: str = "mock",
        resolved_mode: str = "mock",
        replay_path: str | None = None,
        latency_ms: float = 0.0,
        notes: tuple[str, ...] = (),
    ) -> None:
        resolved_config = _coerce_provider_config(config)
        super().__init__(
            resolved_config,
            requested_mode=requested_mode,
            resolved_mode=resolved_mode,
            replay_path=replay_path,
            notes=notes,
        )
        self._latency_ms = latency_ms

    def generate_structured(self, prompt: str, sample_count: int = 1) -> ProviderTrace:
        started = perf_counter()
        if self._latency_ms > 0:
            time.sleep(self._latency_ms / 1000.0)
        family = provider_prompt_family(prompt)
        distractor_families = [item for item in _FAMILY_FIXTURES if item != family]
        candidate_pool = [
            render_prompt_candidate(prompt, family, 0),
            render_prompt_candidate(prompt, family, 1),
            render_family_candidate(distractor_families[0], 0),
            render_family_candidate(distractor_families[1], 1),
        ]
        responses = [candidate_pool[index % len(candidate_pool)] for index in range(sample_count)]
        return self._build_trace(
            prompt,
            responses,
            latency_ms=(perf_counter() - started) * 1000.0,
            notes=("deterministic_fixture_candidates",),
        )


class ReplayProviderClient(_BaseProviderClient):
    def __init__(
        self,
        config: ProviderConfig,
        replay_payload: dict[str, object],
        *,
        requested_mode: str = "replay",
        replay_path: str | None = None,
    ) -> None:
        super().__init__(
            config,
            requested_mode=requested_mode,
            resolved_mode="replay",
            replay_path=replay_path,
            replay_payload_available=bool(replay_payload),
            notes=("replay_mode_uses_local_payload_only",),
        )
        self._replay_payload = replay_payload

    def _lookup_responses(self, prompt: str) -> tuple[list[str], tuple[str, ...], str]:
        prompt_hash = _sha256_text(prompt)
        prompt_family = provider_prompt_family(prompt)
        top_level_prompt_hash = str(self._replay_payload.get("prompt_hash", ""))
        if top_level_prompt_hash and top_level_prompt_hash == prompt_hash:
            direct_responses = _normalize_response_texts(self._replay_payload.get("samples", []))
            if not direct_responses:
                direct_responses = _normalize_response_texts(self._replay_payload.get("responses", []))
            if direct_responses:
                return direct_responses, ("replay_top_level_prompt_hash_match",), "top_level_prompt_hash"
        records = self._replay_payload.get("records", [])
        if isinstance(records, list):
            for index, item in enumerate(records):
                if not isinstance(item, dict):
                    continue
                record_hash = str(item.get("prompt_sha256", ""))
                if not record_hash and item.get("prompt"):
                    record_hash = _sha256_text(str(item["prompt"]))
                if record_hash and record_hash == prompt_hash:
                    responses = _normalize_response_texts(item.get("responses", []))
                    if responses:
                        return responses, ("replay_exact_prompt_match",), str(item.get("record_id", f"record_{index:02d}"))
            for index, item in enumerate(records):
                if not isinstance(item, dict):
                    continue
                if str(item.get("prompt_family", "")) == prompt_family:
                    responses = _normalize_response_texts(item.get("responses", []))
                    if responses:
                        return responses, ("replay_family_match",), str(item.get("record_id", f"family_{index:02d}"))
        sample_payloads = self._replay_payload.get("samples", [])
        sample_responses = _normalize_response_texts(sample_payloads)
        if sample_responses:
            return sample_responses, ("replay_sample_payload",), "sample_payload"
        legacy_responses = _normalize_response_texts(self._replay_payload.get("responses", []))
        if legacy_responses:
            return legacy_responses, ("replay_legacy_payload",), "legacy_payload"
        return (
            [render_prompt_candidate(prompt, prompt_family, 0), render_prompt_candidate(prompt, prompt_family, 1)],
            ("replay_missing_payload_fell_back_to_fixtures",),
            "fixture_fallback",
        )

    def generate_structured(self, prompt: str, sample_count: int = 1) -> ProviderTrace:
        started = perf_counter()
        responses, replay_notes, replay_source = self._lookup_responses(prompt)
        resolved_responses = [responses[index % len(responses)] for index in range(sample_count)]
        return self._build_trace(
            prompt,
            resolved_responses,
            latency_ms=(perf_counter() - started) * 1000.0,
            notes=replay_notes + (f"replay_source:{replay_source}",),
            model_revision=f"replay:{replay_source}",
        )


class OpenAICompatibleProviderClient(_BaseProviderClient):
    def __init__(
        self,
        config: ProviderConfig,
        *,
        requested_mode: str = "live",
        transport: Transport | None = None,
        timeout_s: int = 45,
        max_retries: int = 2,
    ) -> None:
        super().__init__(
            config,
            requested_mode=requested_mode,
            resolved_mode="live",
            notes=("openai_compatible_live_transport",),
        )
        self._transport = transport
        self._timeout_s = timeout_s
        self._max_retries = max_retries

    def _headers(self) -> dict[str, str]:
        api_key = _configured_api_key(self._config)
        if provider_api_key_state(self._config) != "configured":
            raise RuntimeError(f"missing_or_placeholder_api_key:{self._config.api_key_env}")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, prompt: str) -> dict[str, Any]:
        return {
            "model": self._config.model_name,
            "messages": [
                {"role": "system", "content": _code_only_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }

    def _single(self, prompt: str) -> str:
        payload = self._payload(prompt)
        if self._transport is not None:
            samples = self._transport({"prompt": prompt, "sample_count": 1, "payload": payload}, self._config)
            if not samples:
                raise RuntimeError("provider_transport_returned_no_samples")
            return str(samples[0])
        request = urllib.request.Request(
            url=f"{self._config.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                    body = json.loads(response.read().decode("utf-8"))
                return str(body["choices"][0]["message"]["content"])
            except (TimeoutError, socket.timeout, urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(min(0.5 * (2**attempt), 4.0))
        raise RuntimeError(f"provider_request_failed:{last_error}")

    def generate_structured(self, prompt: str, sample_count: int = 1) -> ProviderTrace:
        started = perf_counter()
        if self._transport is not None:
            payload = self._payload(prompt)
            responses = [str(item) for item in self._transport({"prompt": prompt, "sample_count": sample_count, "payload": payload}, self._config)]
        else:
            responses = [self._single(prompt) for _ in range(sample_count)]
        if not responses:
            raise RuntimeError("provider_transport_returned_no_samples")
        return self._build_trace(
            prompt,
            responses,
            latency_ms=(perf_counter() - started) * 1000.0,
            notes=("live_request_completed",),
        )


class ClaudeProviderClient(_BaseProviderClient):
    def __init__(
        self,
        config: ProviderConfig,
        *,
        requested_mode: str = "live",
        transport: Transport | None = None,
        timeout_s: int = 45,
        max_retries: int = 2,
    ) -> None:
        super().__init__(
            config,
            requested_mode=requested_mode,
            resolved_mode="live",
            notes=("claude_live_transport",),
        )
        self._transport = transport
        self._timeout_s = timeout_s
        self._max_retries = max_retries

    def _headers(self) -> dict[str, str]:
        api_key = _configured_api_key(self._config)
        if provider_api_key_state(self._config) != "configured":
            raise RuntimeError(f"missing_or_placeholder_api_key:{self._config.api_key_env}")
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _payload(self, prompt: str) -> dict[str, Any]:
        return {
            "model": self._config.model_name,
            "max_tokens": 512,
            "messages": [{"role": "user", "content": prompt}],
            "system": _code_only_system_prompt(),
        }

    def _single(self, prompt: str) -> str:
        payload = self._payload(prompt)
        if self._transport is not None:
            samples = self._transport({"prompt": prompt, "sample_count": 1, "payload": payload}, self._config)
            if not samples:
                raise RuntimeError("provider_transport_returned_no_samples")
            return str(samples[0])
        request = urllib.request.Request(
            url=f"{self._config.base_url.rstrip('/')}/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                    body = json.loads(response.read().decode("utf-8"))
                return str(body["content"][0]["text"])
            except (TimeoutError, socket.timeout, urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(min(0.5 * (2**attempt), 4.0))
        raise RuntimeError(f"provider_request_failed:{last_error}")

    def generate_structured(self, prompt: str, sample_count: int = 1) -> ProviderTrace:
        started = perf_counter()
        if self._transport is not None:
            payload = self._payload(prompt)
            responses = [str(item) for item in self._transport({"prompt": prompt, "sample_count": sample_count, "payload": payload}, self._config)]
        else:
            responses = [self._single(prompt) for _ in range(sample_count)]
        if not responses:
            raise RuntimeError("provider_transport_returned_no_samples")
        return self._build_trace(
            prompt,
            responses,
            latency_ms=(perf_counter() - started) * 1000.0,
            notes=("live_request_completed",),
        )


def load_provider_configs(path: str) -> dict[str, ProviderConfig]:
    payload = json.loads(resolve_provider_config_path(path).read_text(encoding="utf-8"))
    configs = {}
    for name, spec in payload.items():
        configs[name] = ProviderConfig(
            name=name,
            api_key_env=str(spec["api_key_env"]),
            base_url=str(spec["base_url"]),
            model_name=str(spec.get("model_name", f"{name}-placeholder-model")),
            provider_kind=str(spec.get("provider_kind", "claude" if name == "claude" else "openai_compatible")),
            api_key=str(spec.get("api_key", "")),
        )
    return configs


def load_replay_payload(path: str | None) -> dict[str, dict[str, object]]:
    if not path:
        return {}
    replay_path = Path(path)
    if not replay_path.exists():
        return {}
    payload = json.loads(replay_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "provider_name" in payload and ("responses" in payload or "samples" in payload):
        return {str(payload["provider_name"]): dict(payload)}
    return {str(name): dict(spec) for name, spec in payload.items()}


def provider_is_configured(config: ProviderConfig) -> bool:
    return provider_api_key_state(config) == "configured"


def build_provider_client(
    provider_name: str,
    config_path: str,
    *,
    prefer_mock: bool = False,
    prefer_replay: bool = False,
    replay_path: str | None = None,
    transport: Transport | None = None,
    timeout_s: int = 45,
    max_retries: int = 2,
) -> ProviderClient:
    configs = load_provider_configs(config_path)
    if provider_name not in configs:
        raise KeyError(f"unknown_provider:{provider_name}")
    config = configs[provider_name]
    requested_mode = _normalize_mode(prefer_mock=prefer_mock, prefer_replay=prefer_replay)
    resolved_mode, notes = _resolve_mode(config, requested_mode)
    replay_payload = load_replay_payload(replay_path).get(provider_name, {})
    if requested_mode == "replay":
        return ReplayProviderClient(
            config,
            replay_payload,
            requested_mode=requested_mode,
            replay_path=replay_path,
        )
    if resolved_mode == "blocked":
        raise RuntimeError(f"live_provider_preflight_blocked:{provider_name}:{notes[0]}")
    if resolved_mode == "mock":
        return MockProviderClient(
            config,
            requested_mode=requested_mode,
            resolved_mode=resolved_mode,
            replay_path=replay_path,
            notes=notes,
        )
    if config.provider_kind == "claude":
        return ClaudeProviderClient(
            config,
            requested_mode=requested_mode,
            transport=transport,
            timeout_s=timeout_s,
            max_retries=max_retries,
        )
    return OpenAICompatibleProviderClient(
        config,
        requested_mode=requested_mode,
        transport=transport,
        timeout_s=timeout_s,
        max_retries=max_retries,
    )


def provider_summary(
    provider_name: str,
    config_path: str,
    *,
    prefer_mock: bool = False,
    prefer_replay: bool = False,
    replay_path: str | None = None,
) -> dict[str, object]:
    configs = load_provider_configs(config_path)
    if provider_name not in configs:
        raise KeyError(f"unknown_provider:{provider_name}")
    config = configs[provider_name]
    requested_mode = _normalize_mode(prefer_mock=prefer_mock, prefer_replay=prefer_replay)
    resolved_mode, notes = _resolve_mode(config, requested_mode)
    replay_payload_available = bool(load_replay_payload(replay_path).get(provider_name, {}))
    return _provider_summary(
        config,
        requested_mode=requested_mode,
        resolved_mode=resolved_mode,
        replay_path=replay_path,
        replay_payload_available=replay_payload_available,
        notes=notes,
    )


def generate_provider_trace(
    provider_name: str,
    prompt: str,
    sample_count: int,
    config_path: str,
    *,
    prefer_mock: bool = False,
    prefer_replay: bool = False,
    replay_path: str | None = None,
    transport: Transport | None = None,
    timeout_s: int = 45,
    max_retries: int = 2,
) -> ProviderTrace:
    client = build_provider_client(
        provider_name,
        config_path,
        prefer_mock=prefer_mock,
        prefer_replay=prefer_replay,
        replay_path=replay_path,
        transport=transport,
        timeout_s=timeout_s,
        max_retries=max_retries,
    )
    return client.generate_structured(prompt, sample_count=sample_count)
