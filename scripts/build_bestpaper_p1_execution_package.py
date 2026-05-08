from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(rel: str, payload: Any) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def build() -> dict[str, Any]:
    sem_raw_rel = "results/SemCodebook/artifacts/generated/semcodebook_generation_changing_ablation_full_eval_results_20260505.json"
    sem_large_manifest = json.loads((ROOT / "results/SemCodebook/LARGE_ARTIFACTS_MANIFEST.json").read_text(encoding="utf-8"))
    sem_large = sem_large_manifest["large_artifacts"][0]
    package = {
        "schema_version": "bestpaper_p1_execution_package_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "preservation_policy": "Do not edit preserved artifacts. Every run writes versioned outputs.",
        "formal_experiment_allowed": False,
        "projects": {
            "SemCodebook": {
                "p1": "row-level positive-miss attribution from raw full-eval rows",
                "local_ready": exists(sem_raw_rel),
                "missing_local_inputs": [] if exists(sem_raw_rel) else [sem_raw_rel],
                "remote_source_hint": sem_large,
                "runner_contract": {
                    "input": sem_raw_rel,
                    "output": f"results/SemCodebook/artifacts/generated/semcodebook_row_level_miss_attribution_v1_{DATE}.json",
                    "required_group_keys": ["model", "family", "scale_group", "language", "attack_condition", "carrier_family"],
                    "promotion_condition": "Every positive miss maps to exactly one primary failure bucket; per-bucket Wilson CI exists; no threshold or denominator changes.",
                },
                "command": f"python scripts/run_semcodebook_p1_miss_attribution.py --input {sem_raw_rel} --output results/SemCodebook/artifacts/generated/semcodebook_row_level_miss_attribution_v1_{DATE}.json",
            },
            "CodeDye": {
                "p1": "v3 controls/rerun to improve or explain positive-control sensitivity",
                "local_ready": False,
                "missing_local_inputs": ["DeepSeek live/API environment", "row-level positive-control result bundle"],
                "runner_contract": {
                    "pre_run_gate": f"results/CodeDye/artifacts/generated/codedye_v3_protocol_freeze_gate_{DATE}.json",
                    "outputs": [
                        f"results/CodeDye/artifacts/generated/codedye_v3_positive_negative_control_gate_{DATE}.json",
                        f"results/CodeDye/artifacts/generated/codedye_v3_live_claim_boundary_gate_{DATE}.json",
                        f"results/CodeDye/artifacts/generated/codedye_v3_support_exclusion_gate_{DATE}.json",
                    ],
                    "promotion_condition": "Threshold frozen before rerun; positive and negative controls pass; support rows excluded; raw/structured hashes complete.",
                },
                "command": "python projects/CodeDye/scripts/run_attack_matrix_live_support.py --provider deepseek --claim-bearing-canonical --run-id codedye_v3_20260507",
            },
            "ProbeTrace": {
                "p1": "fresh multi-owner score-vector run",
                "local_ready": False,
                "missing_local_inputs": ["5 active owner registry", "live provider/API access or prepared remote run outputs"],
                "runner_contract": {
                    "pre_run_gate": f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_support_gate_v1_{DATE}.json",
                    "outputs": [
                        f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_score_vectors_{DATE}.jsonl",
                        f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_promotion_gate_{DATE}.json",
                    ],
                    "promotion_condition": "Owner-heldout and task-heldout splits pass; wrong/null/random controls >= 4x positives; per-owner TPR/FPR CI and margin/AUC present.",
                },
                "command": "python projects/ProbeTrace/scripts/run_multi_owner_support.py --owners 5 --claim-bearing false --run-id probetrace_multi_owner_20260507",
            },
            "SealAudit": {
                "p1": "fresh v5 claim-bearing second-stage run",
                "local_ready": exists("results/SealAudit/artifacts/generated/canonical_claim_surface_results.json"),
                "missing_local_inputs": ["DeepSeek/API v5 rerun environment"] if not exists("results/SealAudit/artifacts/generated/canonical_claim_surface_results.json") else ["DeepSeek/API v5 rerun environment"],
                "runner_contract": {
                    "pre_run_gate": f"results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_conjunction_gate_{DATE}.json",
                    "outputs": [
                        f"results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_{DATE}.json",
                        f"results/SealAudit/artifacts/generated/sealaudit_v5_coverage_risk_frontier_{DATE}.json",
                    ],
                    "promotion_condition": "Coverage improves over 8.44%; unsafe-pass count remains 0 or is bounded and disclosed; visible-marker rows remain diagnostic-only.",
                },
                "command": "python projects/SealAudit/scripts/run_second_stage_v5_conjunction.py --provider deepseek --run-id sealaudit_v5_20260507",
            },
        },
        "portfolio_start_condition": [
            "python scripts/check_preserved_results.py passes",
            "python scripts/check_bestpaper_closure.py passes",
            "python scripts/check_bestpaper_second_pass.py passes",
            "Project-specific local_ready or remote/API requirements satisfied",
        ],
        "portfolio_stop_condition": "Do not mark bestpaper_ready until all four P1 promotion gates pass.",
    }
    write_json(f"results/bestpaper_p1_execution_package_v1_{DATE}.json", package)
    return package


def main() -> int:
    package = build()
    ready = {name: spec["local_ready"] for name, spec in package["projects"].items()}
    print("[OK] Wrote best-paper P1 execution package.")
    print("[OK] Local readiness: " + ", ".join(f"{name}={value}" for name, value in ready.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
