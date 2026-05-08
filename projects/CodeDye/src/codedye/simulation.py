from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from .benchmarks import evaluate_task, summarize_utility, task_target_family
from .protocol import BenchmarkTask, DistillationSimulation, DistilledOutput, ProbePrompt
from .providers import render_family_candidate, render_prompt_candidate
from .probes import collect_probe_set, select_probe_subset
from .reranker import FAMILY_ORDER, observe_family
from .signature import asset_key_to_asset_id


def _learn_family_preferences(api_outputs: Sequence[str]) -> dict[str, int]:
    votes: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for code in api_outputs:
        for family in FAMILY_ORDER:
            observation = observe_family(code, family)
            if observation.observed_bit is not None and observation.confidence > 0.0:
                votes[family].append((observation.confidence, observation.observed_bit))
    preferences: dict[str, int] = {}
    for family, family_votes in votes.items():
        score_zero = sum(conf for conf, bit in family_votes if bit == 0)
        score_one = sum(conf for conf, bit in family_votes if bit == 1)
        preferences[family] = 1 if score_one >= score_zero else 0
    return preferences


def render_student_probe_responses(
    prompts: Sequence[ProbePrompt],
    family_preferences: Mapping[str, int],
) -> dict[str, str]:
    return {
        str(prompt.text): render_family_candidate(str(prompt.target_family), int(family_preferences.get(prompt.target_family, 0)))
        for prompt in prompts
    }


def _distill_task_outputs(
    benchmark_tasks: Sequence[BenchmarkTask],
    family_preferences: Mapping[str, int],
) -> tuple[DistilledOutput, ...]:
    outputs: list[DistilledOutput] = []
    for task in benchmark_tasks:
        family = task_target_family(task)
        inferred_bit = int(family_preferences.get(family, 0))
        code = render_prompt_candidate(task.prompt, family, inferred_bit)
        utility = evaluate_task(task, code)
        outputs.append(
            DistilledOutput(
                task=task,
                code=code,
                family=family,
                inferred_bit=inferred_bit,
                utility=utility,
            )
        )
    return tuple(outputs)


def simulate_extraction(
    api_outputs: Sequence[str],
    student_recipe: Mapping[str, object],
    *,
    benchmark_tasks: Sequence[BenchmarkTask] = (),
) -> DistillationSimulation:
    student_name = str(student_recipe.get("student_name", "distilled-student"))
    student_recipe_name = str(student_recipe.get("recipe_name", "behavioral_fit_v1"))
    asset_key = str(student_recipe.get("asset_key", ""))
    query_budget = int(student_recipe.get("query_budget", 8))
    tenant_id = str(student_recipe.get("tenant_id", "public"))
    learned_preferences = _learn_family_preferences(api_outputs)
    held_out = select_probe_subset(
        collect_probe_set(asset_key, count=max(query_budget, len(FAMILY_ORDER)), tenant_id=tenant_id, session_id="student-holdout"),
        query_budget,
    )
    matched = 0
    counted = 0
    for prompt in held_out:
        if prompt.target_family not in learned_preferences:
            continue
        counted += 1
        if learned_preferences[prompt.target_family] == prompt.target_bit:
            matched += 1
    inheritance_rate = matched / counted if counted else 0.0
    inherited_asset_id = asset_key_to_asset_id(asset_key) if asset_key and inheritance_rate >= 0.5 else None
    distilled_outputs = _distill_task_outputs(benchmark_tasks, learned_preferences)
    utility_summary = summarize_utility([item.utility for item in distilled_outputs]) if distilled_outputs else {
        "utility_score": 0.0,
        "compile_rate": 0.0,
        "pass_rate": 0.0,
    }
    return DistillationSimulation(
        student_name=student_name,
        inherited_asset_id=inherited_asset_id,
        inheritance_rate=round(inheritance_rate, 4),
        copied_probe_count=len(api_outputs),
        student_recipe_name=student_recipe_name,
        learned_families=tuple(sorted(learned_preferences)),
        family_preferences=tuple(sorted((family, bit) for family, bit in learned_preferences.items())),
        distilled_outputs=distilled_outputs,
        utility_score=float(utility_summary["utility_score"]),
        compile_rate=float(utility_summary["compile_rate"]),
        pass_rate=float(utility_summary["pass_rate"]),
        notes=(
            "behavioral_student_fit_from_extracted_outputs",
            "student_outputs_are_rendered_from_learned_family_preferences",
            "held_out_probe_subset_is_query_budget_aware",
            "held_out_probe_evaluation_without_model_weight_access",
        ),
    )
