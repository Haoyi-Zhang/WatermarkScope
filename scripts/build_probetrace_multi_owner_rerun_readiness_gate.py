from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def write_json(rel: str, payload: Any) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> int:
    owner_margin = load_json("results/ProbeTrace/artifacts/generated/probetrace_owner_margin_import_gate_v1_20260507.json")
    promotion = load_json("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_promotion_gate_20260507.json")

    required_row_fields = [
        "task_id",
        "source_id",
        "true_owner_id",
        "candidate_owner_id",
        "score",
        "rank",
        "split",
        "control_role",
        "owner_heldout",
        "task_heldout",
        "provider",
        "prompt_hash",
        "raw_payload_hash",
        "structured_payload_hash",
        "threshold_version",
        "claim_bearing",
    ]
    required_aggregates = [
        "owner_count >= 5",
        "candidate_owner_score_vectors_present",
        "positive_rows_per_owner_reported",
        "wrong/null/random owner controls >= 4x positives",
        "owner-heldout and task-heldout integrity receipts",
        "per-owner TPR/FPR Wilson CI",
        "threshold-free rank/AUC summary",
        "near-boundary rows retained",
        "latency/query CI",
    ]

    blockers: list[str] = []
    if promotion.get("gate_pass") is not True:
        blockers.append("current_multi_owner_promotion_gate_not_passed")
    if owner_margin.get("formal_multi_owner_claim_allowed") is not True:
        blockers.append("fresh_multi_owner_score_vectors_missing")
    if int(owner_margin.get("comparable_signed_owner_margin_rows", 0)) <= 0:
        blockers.append("signed_owner_margin_rows_missing")
    if int(promotion.get("owner_count", 0)) < 5:
        blockers.append("owner_count_below_5")
    if int(promotion.get("positive_rows", 0)) <= 0:
        blockers.append("positive_multi_owner_rows_missing")
    if int(promotion.get("control_rows", 0)) <= 0:
        blockers.append("multi_owner_control_rows_missing")

    payload = {
        "schema_version": "probetrace_multi_owner_rerun_readiness_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": False,
        "formal_single_owner_claim_allowed": owner_margin.get("formal_single_owner_claim_allowed") is True,
        "formal_multi_owner_claim_allowed": False,
        "source_artifacts": {
            "owner_margin_import_gate": "results/ProbeTrace/artifacts/generated/probetrace_owner_margin_import_gate_v1_20260507.json",
            "multi_owner_promotion_gate": "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_promotion_gate_20260507.json",
        },
        "current_evidence_summary": {
            "single_owner_verified_rows": owner_margin.get("verified_owner_rows"),
            "single_owner_near_boundary_rows": owner_margin.get("near_boundary_rows"),
            "single_owner_control_false_attribution_rows": owner_margin.get("control_false_attribution_rows"),
            "multi_owner_promotion_gate_pass": promotion.get("gate_pass"),
            "multi_owner_current_owner_count": promotion.get("owner_count"),
            "multi_owner_current_positive_rows": promotion.get("positive_rows"),
            "multi_owner_current_control_rows": promotion.get("control_rows"),
        },
        "required_row_schema_for_claim_bearing_rerun": required_row_fields,
        "required_aggregate_gates_for_promotion": required_aggregates,
        "minimum_rerun_contract": {
            "active_owner_count": 5,
            "splits": ["owner_heldout", "task_heldout"],
            "control_roles": ["wrong_owner", "null_owner", "random_owner", "same_provider_unwrap"],
            "control_to_positive_ratio_minimum": 4,
            "near_boundary_policy": "retain_and_report_not_delete",
            "threshold_policy": "freeze_before_live_scoring",
        },
        "blockers": blockers,
        "reviewer_attack_closed_by_this_gate": [
            "Prevents the current perfect single-owner APIS result from being written as multi-owner generalization.",
            "Defines the exact score-vector schema required for a future multi-owner claim-bearing rerun.",
            "Keeps near-boundary rows as anti-overfit evidence instead of filtering them out.",
        ],
    }
    write_json(f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_rerun_readiness_gate_{DATE}.json", payload)
    print("[OK] Wrote ProbeTrace multi-owner rerun readiness gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
