from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260508"
GENERATED = "artifacts/generated"
OUT = ROOT / f"results/CodeDye/{GENERATED}/codedye_v4_query_budget_support_protocol_v1_{DATE}.json"


PREREQUISITES = [
    "projects/CodeDye/scripts/run_attack_matrix_live_support.py",
    "projects/CodeDye/configs/attack_matrix.json",
    "projects/CodeDye/configs/providers.example.json",
    "results/CodeDye/artifacts/generated/codedye_v3_live_results_20260507_topup_v5.json",
    "results/CodeDye/artifacts/generated/codedye_v3_postrun_promotion_gate_v1_20260507_deepseek300_topup_v5_postrun.json",
    "results/CodeDye/artifacts/generated/codedye_final_claim_lock_v2_20260507.json",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact_ref(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    return {
        "path": rel,
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else None,
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
    }


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def main() -> int:
    blockers: list[str] = []
    missing = [rel for rel in PREREQUISITES if not (ROOT / rel).exists()]
    blockers.extend(f"missing_prerequisite:{rel}" for rel in missing)

    if not missing:
        attack_matrix = load_json("projects/CodeDye/configs/attack_matrix.json")
        attack_ids = {
            str(item.get("attack_id", "")).strip()
            for item in attack_matrix.get("attacks", [])
            if isinstance(item, dict)
        }
        if "query_budget_drop" not in attack_ids:
            blockers.append("query_budget_drop_attack_not_declared")
        lock = load_json("results/CodeDye/artifacts/generated/codedye_final_claim_lock_v2_20260507.json")
        if lock.get("gate_pass") is not True:
            blockers.append("codedye_v3_final_claim_lock_not_passed")
        if lock.get("formal_high_recall_detection_claim_allowed") is not False:
            blockers.append("high_recall_claim_boundary_not_fail_closed")

    output = f"results/CodeDye/{GENERATED}/codedye_v4_query_budget_support_results_{DATE}.json"
    progress = f"results/CodeDye/{GENERATED}/codedye_v4_query_budget_support_progress_{DATE}.json"
    run_id = f"codedye_v4_query_budget_support_{DATE}"
    command = (
        "python projects/CodeDye/scripts/run_attack_matrix_live_support.py "
        "--provider deepseek "
        "--attack-id query_budget_drop "
        "--rows-per-attack 20 "
        "--sample-count 1 "
        f"--run-id {run_id} "
        f"--output {output} "
        f"--progress-output {progress}"
    )
    payload = {
        "schema_version": "codedye_v4_query_budget_support_protocol_v1",
        "date": DATE,
        "project": "CodeDye",
        "claim_bearing": False,
        "frozen": True,
        "gate_pass": not blockers,
        "execution_allowed": not blockers,
        "experiment_role": "support_only_deepseek_query_budget_sensitivity",
        "provider": "deepseek",
        "provider_mode_required": "live",
        "run_id": run_id,
        "attack_id": "query_budget_drop",
        "minimum_live_records": 20,
        "sample_count": 1,
        "canonical_output": output,
        "progress_output": progress,
        "launch_command_redacted": command,
        "secret_values_recorded": False,
        "main_claim_policy": {
            "v3_main_denominator_preserved": True,
            "v4_rows_enter_main_denominator": False,
            "formal_high_recall_detection_claim_allowed": False,
            "formal_contamination_prevalence_claim_allowed": False,
            "threshold_adjustment_allowed": False,
        },
        "why_this_experiment_matters": (
            "The locked v3 main table has a clean 300-row DeepSeek denominator, but reviewers can still ask "
            "whether sparse audit decisions are stable under a one-query budget. This v4 support run tests that "
            "operator-budget axis with live provider rows while keeping all rows outside the main denominator."
        ),
        "prerequisite_artifacts": [artifact_ref(rel) for rel in PREREQUISITES],
        "postrun_gate": f"results/CodeDye/{GENERATED}/codedye_v4_query_budget_support_postrun_gate_v1_{DATE}.json",
        "blockers": blockers,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"gate_pass": payload["gate_pass"], "output": str(OUT.relative_to(ROOT)), "blockers": blockers}, ensure_ascii=True))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
