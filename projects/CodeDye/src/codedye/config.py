from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .benchmarks import benchmark_matrix
from .protocol import BackboneConfig


@dataclass(frozen=True, slots=True)
class CodeDyePlan:
    title: str
    objective: str
    embedding_mechanism: str
    verifier_contract: dict[str, str]
    benchmark_matrix: dict[str, object] = field(default_factory=benchmark_matrix)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_plan() -> CodeDyePlan:
    return CodeDyePlan(
        title="CodeDye",
        objective="Benchmark contamination auditing for code models and code APIs.",
        embedding_mechanism=(
            "benchmark-curator dye-pack scheduling over semantic canary variants, "
            "chronology-aware task packs, and low-FPR accusation scoring"
        ),
        verifier_contract={
            "input": "generated code snippets or API responses over protected tasks and canary variants",
            "output": (
                "{contaminated, contamination_score, p_value_or_score, accused_asset_ids, "
                "false_positive_bound, evidence_trace}"
            ),
        },
    )


def load_plan(path: str | Path | None = None) -> CodeDyePlan:
    if path is None:
        return default_plan()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return CodeDyePlan(
        title=str(payload["title"]),
        objective=str(payload["objective"]),
        embedding_mechanism=str(payload["embedding_mechanism"]),
        verifier_contract=dict(payload["verifier_contract"]),
        benchmark_matrix=dict(payload.get("benchmark_matrix", benchmark_matrix())),
    )


def load_backbone_matrix(path: str | Path) -> tuple[BackboneConfig, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(BackboneConfig(**item) for item in payload["backbones"])
