from __future__ import annotations

import hashlib

from .protocol import ProbePrompt
from .signature import (
    derive_probe_bit,
    derive_probe_commitment,
    derive_probe_nonce,
    derive_probe_priority,
    derive_session_commitment_root,
)


_PROMPT_TEMPLATES: tuple[dict[str, str], ...] = (
    {
        "family": "guard_first",
        "stem": "Write a Python function that validates a list of integers and returns a normalized list.",
        "rationale": "Underdetermined validation logic leaves room for guard ordering choices.",
        "subset": "probe_prompts",
        "calibration_bucket": "service_style",
    },
    {
        "family": "lookup_idiom",
        "stem": "Write a Python function that looks up a key in a mapping and falls back to a default value.",
        "rationale": "Dictionary access can be written with explicit membership checks or idiomatic lookup methods.",
        "subset": "probe_prompts",
        "calibration_bucket": "service_style",
    },
    {
        "family": "iteration_idiom",
        "stem": "Write a Python function that computes a weighted sum over a sequence.",
        "rationale": "The task can use direct iteration or index-aware loops without changing semantics.",
        "subset": "query_budget",
        "calibration_bucket": "budget_sentinel",
    },
    {
        "family": "helper_split",
        "stem": "Write a Python function that parses and normalizes a comma-separated record string.",
        "rationale": "The solution may inline logic or extract a helper function.",
        "subset": "protected_asset_echo",
        "calibration_bucket": "service_trace",
    },
    {
        "family": "container_choice",
        "stem": "Write a Python function that removes duplicates while preserving a stable output policy.",
        "rationale": "The implementation can emphasize list accumulation or container-oriented idioms.",
        "subset": "wrapper_stripping",
        "calibration_bucket": "service_trace",
    },
    {
        "family": "temporary_variable",
        "stem": "Write a Python function that merges counters from nested records.",
        "rationale": "The implementation can use direct accumulation or explicit buffer variables.",
        "subset": "neutralization_after_distillation",
        "calibration_bucket": "distillation_probe",
    },
)

_SUBSET_WEIGHTS: dict[str, float] = {
    "probe_prompts": 1.0,
    "query_budget": 1.15,
    "protected_asset_echo": 1.05,
    "wrapper_stripping": 0.95,
    "neutralization_after_distillation": 0.9,
}


def prompt_family_from_text(prompt: str) -> str:
    lowered = prompt.lower()
    if "reverses the order of words" in lowered or "reverse words" in lowered:
        return "helper_split"
    if "title-cases every word" in lowered or "title case" in lowered:
        return "helper_split"
    if "joins nonempty" in lowered or "dash-separated segment" in lowered or "value field" in lowered:
        return "helper_split"
    if "replaces every digit" in lowered or "common suffix" in lowered or "common prefix" in lowered:
        return "helper_split"
    if "comma-separated" in lowered or "record string" in lowered or "projects the value field" in lowered:
        return "helper_split"
    if "filters a list down to truthy values" in lowered or "unique lowercase words" in lowered or "swaps keys and values" in lowered or "sorts records" in lowered:
        return "container_choice"
    if "adjacent pairs" in lowered or "two-item tuples" in lowered or "fixed-size chunk" in lowered or "prefix sums" in lowered or "merges overlapping" in lowered or "absolute difference" in lowered or "even positions" in lowered:
        return "iteration_idiom"
    if "looks up a key in a mapping" in lowered or "falls back to a default value" in lowered or "nested key path" in lowered or "falls back to a default when any level is missing" in lowered:
        return "lookup_idiom"
    if "counter" in lowered or "nested record" in lowered or "weighted sum" in lowered:
        return "iteration_idiom"
    if "duplicate" in lowered or "stable output" in lowered or "index pairs" in lowered:
        return "container_choice"
    return "guard_first"

def _default_session_id(asset_key: str, tenant_id: str) -> str:
    digest = hashlib.sha256(f"{tenant_id}|{asset_key}".encode("utf-8")).hexdigest()
    return digest[:12]


def _scheduled_templates(asset_key: str, tenant_id: str, session_id: str, cycle: int) -> tuple[dict[str, str], ...]:
    ranked = sorted(
        _PROMPT_TEMPLATES,
        key=lambda template: derive_probe_commitment(
            asset_key,
            tenant_id,
            session_id,
            f"template::{cycle}::{template['family']}::{template['subset']}",
        ),
    )
    return tuple(ranked)


def collect_probe_set(
    asset_key: str,
    count: int = 16,
    *,
    tenant_id: str = "public",
    session_id: str | None = None,
) -> tuple[ProbePrompt, ...]:
    active_session = session_id or _default_session_id(asset_key, tenant_id)
    prompt_ids = tuple(f"probe_{index:02d}" for index in range(count))
    trace_anchor = derive_session_commitment_root(asset_key, tenant_id, active_session, prompt_ids)
    prompts: list[ProbePrompt] = []
    for index in range(count):
        cycle = index // len(_PROMPT_TEMPLATES)
        template_schedule = _scheduled_templates(asset_key, tenant_id, active_session, cycle)
        template = template_schedule[index % len(_PROMPT_TEMPLATES)]
        prompt_id = prompt_ids[index]
        commitment = derive_probe_commitment(asset_key, tenant_id, active_session, prompt_id)
        probe_nonce = derive_probe_nonce(asset_key, tenant_id, active_session, prompt_id)
        budget_priority = _SUBSET_WEIGHTS.get(template["subset"], 1.0) * derive_probe_priority(
            asset_key,
            tenant_id,
            active_session,
            prompt_id,
            template["subset"],
        )
        text = (
            f"{template['stem']}\n"
            f"Keep the solution executable and concise.\n"
            f"Probe nonce: {probe_nonce}.\n"
            f"Session anchor: {active_session}.\n"
            f"Trace anchor: {trace_anchor}."
        )
        prompts.append(
            ProbePrompt(
                prompt_id=prompt_id,
                text=text,
                target_family=template["family"],
                target_bit=derive_probe_bit(asset_key, tenant_id, active_session, prompt_id),
                session_id=active_session,
                tenant_id=tenant_id,
                commitment=commitment[:16],
                subset=template["subset"],
                rationale=template["rationale"],
                selection_weight=_SUBSET_WEIGHTS.get(template["subset"], 1.0),
                query_cost=1,
                budget_priority=round(budget_priority, 4),
                trace_anchor=trace_anchor,
                probe_nonce=probe_nonce,
                calibration_bucket=template.get("calibration_bucket", "service_style"),
            )
        )
    return tuple(prompts)


def select_probe_subset(prompts: tuple[ProbePrompt, ...], query_budget: int) -> tuple[ProbePrompt, ...]:
    if query_budget <= 0:
        return ()
    if sum(prompt.query_cost for prompt in prompts) <= query_budget:
        return prompts
    selected: list[ProbePrompt] = []
    covered_families: set[str] = set()
    covered_buckets: set[str] = set()
    remaining_budget = query_budget
    remaining = list(prompts)
    while remaining and remaining_budget > 0:
        affordable = [prompt for prompt in remaining if prompt.query_cost <= remaining_budget]
        if not affordable:
            break
        best_prompt = max(
            affordable,
            key=lambda item: (
                item.budget_priority
                + item.selection_weight
                + (0.45 if item.target_family not in covered_families else 0.0)
                + (0.2 if item.calibration_bucket not in covered_buckets else 0.0)
                - 0.05 * max(item.query_cost - 1, 0),
                item.prompt_id,
            ),
        )
        selected.append(best_prompt)
        covered_families.add(best_prompt.target_family)
        covered_buckets.add(best_prompt.calibration_bucket)
        remaining_budget -= best_prompt.query_cost
        remaining.remove(best_prompt)
    return tuple(selected)


def prompt_commitment_target(
    asset_key: str,
    prompt: str,
    *,
    user_tag: str | None = None,
    tenant_id: str = "public",
) -> tuple[str, int, str, str]:
    family = prompt_family_from_text(prompt)
    session_seed = hashlib.sha256(f"{prompt}|{user_tag or 'anonymous'}".encode("utf-8")).hexdigest()
    session_id = session_seed[:12]
    prompt_id = hashlib.sha256(f"{family}|{prompt}|{user_tag or ''}".encode("utf-8")).hexdigest()[:12]
    target_bit = derive_probe_bit(asset_key, tenant_id, session_id, prompt_id)
    commitment = derive_probe_commitment(asset_key, tenant_id, session_id, prompt_id)[:16]
    return family, target_bit, session_id, commitment


def prompt_signature_target(
    asset_key: str,
    prompt: str,
    user_tag: str | None = None,
) -> tuple[str, int]:
    family, target_bit, _, _ = prompt_commitment_target(asset_key, prompt, user_tag=user_tag)
    return family, target_bit
