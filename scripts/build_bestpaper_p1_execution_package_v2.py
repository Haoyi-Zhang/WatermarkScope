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


def main() -> int:
    package = {
        "schema_version": "bestpaper_p1_execution_package_v2",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "formal_experiment_allowed": False,
        "role": "additive_v2_execution_contract_not_replacing_locked_v1",
        "preservation_policy": "Do not overwrite locked v1 receipts or previous results; all reruns write versioned outputs.",
        "projects": {
            "SemCodebook": {
                "status": "causal contribution gate now passed; no no-retry claim",
                "pre_run_gate": "results/SemCodebook/artifacts/generated/semcodebook_causal_contribution_gate_v2_20260507.json",
                "local_ready": exists("results/SemCodebook/artifacts/generated/semcodebook_causal_contribution_gate_v2_20260507.json"),
                "next_action": "Paper/table integration and failure-boundary wording; no formal rerun needed for causal table.",
            },
            "CodeDye": {
                "status": "v3 protocol frozen; live promotion still blocked",
                "pre_run_gate": "results/CodeDye/artifacts/generated/codedye_v3_protocol_freeze_gate_20260507.json",
                "readiness_gates": [
                    "results/CodeDye/artifacts/generated/codedye_v3_live_claim_boundary_gate_20260507.json",
                    "results/CodeDye/artifacts/generated/codedye_v3_support_exclusion_gate_20260507.json",
                    "results/CodeDye/artifacts/generated/codedye_v3_reused_control_bridge_20260507.json",
                ],
                "missing_for_stronger_claim": [
                    "fresh DeepSeek v3 live rerun output with raw/structured hashes",
                    "sanitized negative-control row-level source ledger",
                ],
                "command": "python projects/CodeDye/scripts/run_attack_matrix_live_support.py --provider deepseek --claim-bearing-canonical --run-id codedye_v3_20260507",
            },
            "ProbeTrace": {
                "status": "single-owner claim safe; multi-owner rerun fail-closed",
                "pre_run_gate": "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_rerun_readiness_gate_20260507.json",
                "required_input_schema": [
                    "task_id",
                    "true_owner_id",
                    "candidate_owner_id",
                    "score",
                    "split",
                    "control_role",
                    "owner_heldout",
                    "task_heldout",
                    "source_record_hash",
                    "output_record_sha256",
                    "owner_id_hat",
                    "false_attribution",
                    "signed_owner_margin",
                    "family",
                    "language",
                ],
                "strict_smoke_receipt": "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_promotion_gate_probetrace_multi_owner_strict_smoke_20260507.json",
                "command": "python projects/ProbeTrace/scripts/run_multi_owner_support.py --owners 5 --claim-bearing false --run-id probetrace_multi_owner_20260507 --input-score-vectors <score_vectors.jsonl>",
            },
            "SealAudit": {
                "status": "support-ready; v5 final evidence fail-closed",
                "pre_run_gate": "results/SealAudit/artifacts/generated/sealaudit_v5_final_evidence_readiness_gate_20260507.json",
                "required_output": "results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_sealaudit_v5_20260507.json",
                "strict_smoke_receipt": "results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_strict_smoke_20260507.json",
                "required_postrun_artifacts": [
                    "results/SealAudit/artifacts/generated/sealaudit_v5_coverage_risk_frontier_20260507.json",
                    "results/SealAudit/artifacts/generated/sealaudit_v5_visible_marker_diagnostic_boundary_20260507.json",
                    "results/SealAudit/artifacts/generated/sealaudit_v5_threshold_sensitivity_20260507.json",
                ],
                "command": "python projects/SealAudit/scripts/run_second_stage_v5_conjunction.py --provider deepseek --run-id sealaudit_v5_20260507 --v5-evidence <final_v5_rows.json>",
            },
        },
        "portfolio_stop_condition": "Do not mark bestpaper_ready or launch unscoped formal claims until every project-specific promotion gate passes without support-only evidence.",
    }
    write_json(f"results/bestpaper_p1_execution_package_v2_{DATE}.json", package)
    print("[OK] Wrote best-paper P1 execution package v2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
