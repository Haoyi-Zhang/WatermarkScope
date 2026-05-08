from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
GENERATED = ROOT / "results/SealAudit/artifacts/generated"
EVIDENCE = GENERATED / f"sealaudit_v5_final_claim_evidence_rows_v2_{DATE}.json"
FRONTIER = GENERATED / f"sealaudit_v5_coverage_risk_frontier_v2_{DATE}.json"
VISIBLE = GENERATED / f"sealaudit_v5_visible_marker_diagnostic_boundary_v2_{DATE}.json"
THRESHOLD = GENERATED / f"sealaudit_v5_threshold_sensitivity_v2_{DATE}.json"


REQUIRED_ROW_FIELDS = {
    "case_id",
    "full_case_id",
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
    "coverage_risk_frontier_entry",
    "threshold_sensitivity_entry",
    "evidence_sources",
}


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def load(path: Path) -> dict:
    if not path.exists():
        fail(f"Missing artifact: {path.relative_to(ROOT)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail(f"Artifact is not a JSON object: {path.relative_to(ROOT)}")
    return payload


def main() -> int:
    evidence = load(EVIDENCE)
    frontier = load(FRONTIER)
    visible = load(VISIBLE)
    threshold = load(THRESHOLD)
    if evidence.get("schema_version") != "sealaudit_v5_final_claim_evidence_rows_v2":
        fail("Unexpected materialized evidence schema.")
    if frontier.get("schema_version") != "sealaudit_v5_coverage_risk_frontier_v2":
        fail("Unexpected coverage-risk frontier schema.")
    if visible.get("schema_version") != "sealaudit_v5_visible_marker_diagnostic_boundary_v2":
        fail("Unexpected visible-marker boundary schema.")
    if threshold.get("schema_version") != "sealaudit_v5_threshold_sensitivity_v2":
        fail("Unexpected threshold sensitivity schema.")
    rows = evidence.get("records", [])
    if not isinstance(rows, list) or len(rows) != 960:
        fail("Materialized evidence must contain exactly 960 marker-hidden rows.")
    if len({row.get("case_id") for row in rows if isinstance(row, dict)}) != 320:
        fail("Materialized evidence must bind exactly 320 blind cases.")
    missing_rows = [
        index
        for index, row in enumerate(rows)
        if not isinstance(row, dict) or REQUIRED_ROW_FIELDS.difference(row)
    ]
    if missing_rows:
        fail(f"Rows missing required fields: {missing_rows[:10]}")
    if any(row.get("claim_bearing") is not True for row in rows):
        fail("All materialized marker-hidden rows must stay claim-bearing.")
    if any(row.get("marker_condition") != "marker_hidden" for row in rows):
        fail("Materialized evidence must not include visible-marker rows.")
    if any(row.get("visible_marker_diagnostic_only") is not False for row in rows):
        fail("Marker-hidden rows must not be marked visible-marker diagnostic.")
    if any(row.get("unsafe_pass_flag") is True for row in rows):
        fail("Materialized v2 evidence introduced unsafe-pass rows.")
    if any("support" not in row.get("evidence_sources", {}) for row in []):
        fail("unreachable")
    if not all(row["evidence_sources"]["code_aware_provider_trace_support"]["support_only"] is True for row in rows):
        fail("Code-aware provider trace must remain support-only.")
    if not all(row["evidence_sources"]["executable_conjunction_support"]["support_only"] is True for row in rows):
        fail("Executable conjunction must remain support-only.")
    if not all(row["evidence_sources"]["expert_role_support"]["support_only"] is True for row in rows):
        fail("Expert role evidence must remain support-only.")
    if frontier.get("gate_pass") is not True or frontier.get("materialization_gate_pass") is not True:
        fail("Coverage-risk frontier materialization gate should pass.")
    if frontier.get("hidden_claim_rows") != 960 or frontier.get("unique_case_count") != 320:
        fail("Coverage-risk frontier denominator drifted.")
    if frontier.get("unsafe_pass_count") != 0:
        fail("Coverage-risk frontier unsafe-pass count must be zero.")
    if frontier.get("formal_security_certificate_claim_allowed") is not False:
        fail("Security-certificate claim must remain forbidden.")
    if frontier.get("formal_harmlessness_claim_allowed") is not False:
        fail("Harmlessness claim must remain forbidden.")
    if visible.get("gate_pass") is not True:
        fail("Visible-marker diagnostic boundary gate should pass.")
    if visible.get("visible_marker_diagnostic_rows") != 320 or visible.get("visible_marker_claim_rows") != 0:
        fail("Visible-marker rows must remain diagnostic-only.")
    if threshold.get("gate_pass") is not True or threshold.get("threshold_sweep_count", 0) < 6:
        fail("Threshold sensitivity artifact is incomplete.")
    policy = threshold.get("threshold_policy", "").lower()
    if "post hoc" not in policy and "tuning" not in policy:
        fail("Threshold policy must explicitly forbid post-hoc tuning.")
    print("[OK] SealAudit v5 materialized evidence v2 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
