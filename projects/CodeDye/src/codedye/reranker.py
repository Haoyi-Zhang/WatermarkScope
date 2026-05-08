from __future__ import annotations

import ast
import re
from collections.abc import Iterable

from .protocol import FamilyObservation


_STYLE_PATTERNS: dict[str, dict[int, tuple[re.Pattern[str], ...]]] = {
    "guard_first": {
        0: (re.compile(r"\belse\s*:"), re.compile(r"\breturn\s+result\b")),
        1: (re.compile(r"if\s+.*:\s*\n\s*return\b"), re.compile(r"if\s*\(.*\)\s*\{\s*return\b")),
    },
    "lookup_idiom": {
        0: (re.compile(r"if\s+.*\s+in\s+.*:\s*\n"), re.compile(r"\[[^\]]+\]")),
        1: (re.compile(r"\.get\("), re.compile(r"\.setdefault\(")),
    },
    "iteration_idiom": {
        0: (re.compile(r"for\s+\w+\s+in\s+\w+\s*:"),),
        1: (re.compile(r"enumerate\("), re.compile(r"range\(")),
    },
    "helper_split": {
        0: (re.compile(r"parts\s*=\s*\["), re.compile(r"return\s+\[part\s+for\s+part\s+in\s+parts")),
        1: (re.compile(r"def\s+(?:probe_|trace_|helper_)\w+\("), re.compile(r"\n\ndef\s+\w+\(")),
    },
    "container_choice": {
        0: (re.compile(r"\.append\("), re.compile(r"\[\]")),
        1: (re.compile(r"set\("), re.compile(r"dict\.fromkeys\(")),
    },
    "temporary_variable": {
        0: (re.compile(r"\w+\s*\+=\s*"),),
        1: (re.compile(r"\b(?:tmp|buffer|trace_buffer|probe_buffer)\w*\s*="),),
    },
}


FAMILY_ORDER: tuple[str, ...] = tuple(_STYLE_PATTERNS.keys())


def _build_observation(
    family: str,
    observed_bit: int | None,
    confidence: float,
    matches: tuple[str, ...],
    *,
    evidence_source: str,
    forensic_weight: float,
    stability_score: float,
) -> FamilyObservation:
    return FamilyObservation(
        family=family,
        observed_bit=observed_bit,
        confidence=round(max(0.0, min(confidence, 1.0)), 4),
        evidence_source=evidence_source,
        forensic_weight=round(max(0.0, min(forensic_weight, 1.0)), 4),
        stability_score=round(max(0.0, min(stability_score, 1.0)), 4),
        matches=matches[:3],
    )


def _score_patterns(code: str, patterns: tuple[re.Pattern[str], ...]) -> tuple[float, tuple[str, ...]]:
    hits: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(code):
            hits.append(match.group(0))
    confidence = min(1.0, 0.35 + 0.2 * len(hits)) if hits else 0.0
    return confidence, tuple(hits[:3])


def _parse_python(code: str) -> ast.AST | None:
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


def _ast_observe_family(tree: ast.AST, family: str) -> FamilyObservation | None:
    if family == "guard_first":
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.body:
                first_stmt = node.body[0]
                if isinstance(first_stmt, ast.If) and any(isinstance(item, ast.Return) for item in first_stmt.body):
                    return _build_observation(
                        family,
                        1,
                        0.92,
                        ("ast:early_return_guard",),
                        evidence_source="ast",
                        forensic_weight=0.95,
                        stability_score=0.9,
                    )
                if any(isinstance(item, ast.If) and item.orelse for item in node.body):
                    return _build_observation(
                        family,
                        0,
                        0.84,
                        ("ast:if_else_result_path",),
                        evidence_source="ast",
                        forensic_weight=0.88,
                        stability_score=0.82,
                    )
    elif family == "lookup_idiom":
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"get", "setdefault"}:
                return _build_observation(
                    family,
                    1,
                    0.91,
                    (f"ast:{node.func.attr}",),
                    evidence_source="ast",
                    forensic_weight=0.93,
                    stability_score=0.88,
                )
            if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
                return _build_observation(
                    family,
                    0,
                    0.82,
                    ("ast:membership_branch",),
                    evidence_source="ast",
                    forensic_weight=0.87,
                    stability_score=0.8,
                )
    elif family == "iteration_idiom":
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                iterator = ast.unparse(node.iter) if hasattr(ast, "unparse") else ""
                if "range(" in iterator or "enumerate(" in iterator:
                    return _build_observation(
                        family,
                        1,
                        0.9,
                        (iterator,),
                        evidence_source="ast",
                        forensic_weight=0.92,
                        stability_score=0.86,
                    )
                return _build_observation(
                    family,
                    0,
                    0.86,
                    (iterator,),
                    evidence_source="ast",
                    forensic_weight=0.89,
                    stability_score=0.83,
                )
    elif family == "helper_split":
        functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        if len(functions) > 1:
            return _build_observation(
                family,
                1,
                0.9,
                tuple(node.name for node in functions[:3]),
                evidence_source="ast",
                forensic_weight=0.94,
                stability_score=0.88,
            )
        if functions:
            return _build_observation(
                family,
                0,
                0.74,
                (functions[0].name,),
                evidence_source="ast",
                forensic_weight=0.8,
                stability_score=0.72,
            )
    elif family == "container_choice":
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "fromkeys":
                return _build_observation(
                    family,
                    1,
                    0.92,
                    ("ast:dict.fromkeys",),
                    evidence_source="ast",
                    forensic_weight=0.95,
                    stability_score=0.89,
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "set":
                return _build_observation(
                    family,
                    1,
                    0.82,
                    ("ast:set",),
                    evidence_source="ast",
                    forensic_weight=0.84,
                    stability_score=0.78,
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "append":
                return _build_observation(
                    family,
                    0,
                    0.82,
                    ("ast:append",),
                    evidence_source="ast",
                    forensic_weight=0.84,
                    stability_score=0.78,
                )
    elif family == "temporary_variable":
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = [ast.unparse(target) for target in node.targets if hasattr(ast, "unparse")]
                if any(name.endswith("buffer") or name.startswith("tmp") or name.startswith("trace_") for name in targets):
                    return _build_observation(
                        family,
                        1,
                        0.9,
                        tuple(targets[:3]),
                        evidence_source="ast",
                        forensic_weight=0.93,
                        stability_score=0.87,
                    )
            if isinstance(node, ast.AugAssign):
                return _build_observation(
                    family,
                    0,
                    0.77,
                    ("ast:augassign",),
                    evidence_source="ast",
                    forensic_weight=0.82,
                    stability_score=0.76,
                )
    return None


def observe_family(code: str, family: str) -> FamilyObservation:
    tree = _parse_python(code)
    if tree is not None:
        ast_observation = _ast_observe_family(tree, family)
        if ast_observation is not None:
            return ast_observation
    scored: list[tuple[float, int | None, tuple[str, ...]]] = []
    for bit, patterns in _STYLE_PATTERNS[family].items():
        confidence, hits = _score_patterns(code, patterns)
        scored.append((confidence, bit if confidence > 0 else None, hits))
    confidence, observed_bit, hits = max(scored, key=lambda item: item[0])
    if confidence <= 0.0:
        return _build_observation(
            family,
            None,
            0.0,
            (),
            evidence_source="none",
            forensic_weight=0.0,
            stability_score=0.0,
        )
    hit_count = len(hits)
    return _build_observation(
        family,
        observed_bit,
        confidence,
        hits,
        evidence_source="regex",
        forensic_weight=min(0.78, 0.34 + 0.08 * hit_count),
        stability_score=min(0.76, 0.28 + 0.14 * hit_count),
    )


def score_family_alignment(observation: FamilyObservation, target_bit: int) -> float:
    if observation.observed_bit is None:
        return 0.0
    if observation.observed_bit != target_bit:
        return 0.0
    gates = (
        observation.confidence >= 0.74,
        observation.evidence_source == "ast",
        observation.forensic_weight >= 0.84,
        observation.stability_score >= 0.76,
    )
    return round(sum(1.0 for gate in gates if gate) / len(gates), 4)


def extract_probe_evidence(code_batch: Iterable[str]) -> tuple[FamilyObservation, ...]:
    evidence: list[FamilyObservation] = []
    for code in code_batch:
        for family in FAMILY_ORDER:
            evidence.append(observe_family(code, family))
    return tuple(evidence)


def rank_candidates(candidates: Iterable[str], target_family: str, target_bit: int) -> tuple[int, FamilyObservation, float]:
    best_index = 0
    best_observation = _build_observation(
        target_family,
        None,
        0.0,
        (),
        evidence_source="none",
            forensic_weight=0.0,
            stability_score=0.0,
        )
    best_score = -1.0
    best_rank: tuple[float | int, ...] = (-1.0,)
    for index, candidate in enumerate(candidates):
        observation = observe_family(candidate, target_family)
        agreement = score_family_alignment(observation, target_bit)
        rank = (
            1 if observation.observed_bit == target_bit else 0,
            1 if observation.confidence >= 0.74 else 0,
            1 if observation.evidence_source == "ast" else 0,
            1 if observation.forensic_weight >= 0.84 else 0,
            1 if observation.stability_score >= 0.76 else 0,
            observation.confidence,
            observation.forensic_weight,
            observation.stability_score,
            -index,
        )
        if rank > best_rank:
            best_index = index
            best_observation = observation
            best_score = agreement
            best_rank = rank
    return best_index, best_observation, max(best_score, 0.0)
