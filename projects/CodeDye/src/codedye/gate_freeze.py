from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_accusation_gate_freeze() -> dict[str, object]:
    path = Path(__file__).resolve().parents[2] / "configs" / "accusation_gate_freeze.json"
    return json.loads(path.read_text(encoding="utf-8"))


def frozen_accusation_threshold() -> float:
    payload = load_accusation_gate_freeze()
    return float(payload["threshold_value"])


def frozen_accusation_threshold_version() -> str:
    payload = load_accusation_gate_freeze()
    return str(payload["schema_version"])
