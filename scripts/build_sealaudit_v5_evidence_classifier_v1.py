from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_v5_evidence_classifier_v1_{DATE}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def classify(rel: str) -> dict[str, Any]:
    payload = load_json(rel)
    return {
        "path": rel,
        "schema_version": payload.get("schema_version"),
        "claim_bearing": payload.get("claim_bearing"),
        "gate_pass": payload.get("gate_pass"),
        "formal_v5_claim_allowed": payload.get("formal_v5_claim_allowed"),
        "blocked": payload.get("blocked"),
        "blockers": payload.get("blockers", []),
        "classification": (
            "claim_eligible_final_v5_evidence"
            if payload.get("claim_bearing") is True
            and payload.get("gate_pass") is True
            and payload.get("formal_v5_claim_allowed") is True
            else "not_final_claim_evidence"
        ),
    }


def main() -> int:
    current = load_json("results/SealAudit/artifacts/generated/canonical_claim_surface_results.json")
    frontier = load_json("results/SealAudit/artifacts/generated/sealaudit_coverage_risk_frontier_gate_20260505.json")
    readiness = load_json("results/SealAudit/artifacts/generated/sealaudit_v5_final_evidence_readiness_gate_20260507.json")
    candidates = [
        "results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_conjunction_gate_20260507.json",
        "results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_sealaudit_v5_20260507.json",
        "results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_strict_smoke_20260507.json",
        "results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_remote_support_guard_20260507.json",
    ]
    classified = [classify(path) for path in candidates]
    claim_eligible = [item for item in classified if item["classification"] == "claim_eligible_final_v5_evidence"]
    blockers = [
        "final_v5_claim_bearing_rows_missing",
        "v5_coverage_risk_frontier_missing",
        "v5_threshold_sensitivity_missing",
        "visible_marker_diagnostic_boundary_missing",
    ]
    if not readiness.get("gate_pass"):
        blockers.extend(readiness.get("blockers", []))

    payload = {
        "schema_version": "sealaudit_v5_evidence_classifier_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": False,
        "formal_v5_claim_allowed": False,
        "current_claim_surface": {
            "case_count": current["main_table_unique_case_count"],
            "hidden_claim_rows": current["claim_bearing_record_count"],
            "visible_marker_diagnostic_rows": current["diagnostic_visible_record_count"],
            "decisive_coverage_locked": "81/960",
            "decision_distribution": frontier["decision_distribution"],
            "unsafe_pass_count": frontier["unsafe_pass_count"],
        },
        "classified_candidates": classified,
        "claim_eligible_candidate_count": len(claim_eligible),
        "readiness_gate_pass": bool(readiness.get("gate_pass")),
        "blockers": sorted(set(blockers)),
        "promotion_policy": "Do not upgrade SealAudit coverage until final v5 row-level evidence exists with claim-bearing rows, visible-marker diagnostic boundary, threshold sensitivity, and unsafe-pass bound.",
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
