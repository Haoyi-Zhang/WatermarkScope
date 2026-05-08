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
    support = load_json("results/SealAudit/artifacts/generated/sealaudit_second_stage_support_import_gate_v1_20260507.json")
    guard = load_json("results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_remote_support_guard_20260507.json")

    required_row_fields = [
        "case_id",
        "provider",
        "scheme_kind",
        "language",
        "marker_condition",
        "candidate_code_hash",
        "raw_provider_payload_hash",
        "structured_payload_hash",
        "static_safety_decision",
        "semantic_drift_decision",
        "laundering_decision",
        "spoofability_decision",
        "provider_judge_decision",
        "baseline_control_decision",
        "final_v5_decision",
        "abstain_reason",
        "threshold_version",
        "claim_bearing",
        "visible_marker_diagnostic_only",
    ]
    required_gates = [
        "320 unique cases",
        "960 marker-hidden claim-eligible rows or explicit denominator split",
        "visible-marker rows marked diagnostic-only",
        "coverage-risk frontier with unsafe-pass upper bound",
        "threshold sensitivity table",
        "hard-ambiguity slice",
        "confusion matrix with bootstrap CI",
        "role-based expert support packet retained as support, not signature evidence",
    ]

    blockers = [
        "fresh_final_row_level_v5_evidence_missing",
        "decisive_coverage_upgrade_not_admitted",
    ]
    if support.get("gate_pass") is not True:
        blockers.append("support_conjunction_import_gate_not_passed")
    if guard.get("formal_v5_claim_allowed") is not False:
        blockers.append("support_guard_unexpectedly_promotes_v5_claim")

    payload = {
        "schema_version": "sealaudit_v5_final_evidence_readiness_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": False,
        "support_ready": support.get("support_ready") is True,
        "formal_v5_claim_allowed": False,
        "formal_security_certificate_claim_allowed": False,
        "source_artifacts": {
            "second_stage_support_import_gate": "results/SealAudit/artifacts/generated/sealaudit_second_stage_support_import_gate_v1_20260507.json",
            "support_only_guard": "results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_remote_support_guard_20260507.json",
        },
        "support_summary": {
            "case_count": support.get("case_count"),
            "language_counts": support.get("language_counts"),
            "scheme_kind_counts": support.get("scheme_kind_counts"),
            "subgate_pass_counts": support.get("subgate_pass_counts"),
            "needs_review_taxonomy_record_count": support.get("needs_review_taxonomy_record_count"),
        },
        "current_final_claim_boundary": {
            "decisive_coverage_locked": "81/960 = 8.44% until fresh final v5 row-level evidence is admitted",
            "visible_marker_rows": "diagnostic_only",
            "human_review": "anonymous role-based support and row-level packet confirmation only; not a signed external label artifact",
        },
        "required_row_schema_for_final_v5": required_row_fields,
        "required_promotion_gates": required_gates,
        "blockers": blockers,
        "reviewer_attack_closed_by_this_gate": [
            "Support-only executable conjunction cannot be silently promoted into a main result.",
            "Coverage can only improve through fresh row-level v5 evidence with unsafe-pass bounds.",
            "Expert review language is scoped to role-based support, avoiding unverifiable signature claims.",
        ],
    }
    write_json(f"results/SealAudit/artifacts/generated/sealaudit_v5_final_evidence_readiness_gate_{DATE}.json", payload)
    print("[OK] Wrote SealAudit v5 final-evidence readiness gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
