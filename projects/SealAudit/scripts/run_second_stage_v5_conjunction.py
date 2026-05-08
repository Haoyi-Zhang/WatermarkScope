from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or validate SealAudit second-stage v5 conjunction evidence.")
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--input", default="results/SealAudit/artifacts/generated/canonical_claim_surface_results.json")
    parser.add_argument("--v5-evidence", default="")
    parser.add_argument("--output", default="")
    return parser.parse_args()


def write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


REQUIRED_V5_FIELDS = [
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


def wilson(k: int, n: int) -> dict[str, float | int | str]:
    if n <= 0:
        return {"k": k, "n": n, "rate": 0.0, "low": 0.0, "high": 1.0, "method": "wilson"}
    z = 1.959963984540054
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return {
        "k": k,
        "n": n,
        "rate": phat,
        "low": max(0.0, center - half),
        "high": min(1.0, center + half),
        "method": "wilson",
    }


def missing_fields(row: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_V5_FIELDS if field not in row or row.get(field) in {None, ""}]


def resolver_decision(row: dict[str, Any]) -> str:
    return str(row.get("final_v5_decision", row.get("resolver_decision", "missing")))


def main() -> int:
    args = parse_args()
    output = ROOT / (args.output or f"results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_{args.run_id}.json")
    canonical = ROOT / args.input
    evidence = ROOT / args.v5_evidence if args.v5_evidence else None
    if not canonical.exists() or evidence is None or not evidence.exists():
        blockers = []
        if not canonical.exists():
            blockers.append("canonical_claim_surface_missing")
        if evidence is None or not evidence.exists():
            blockers.append("v5_evidence_missing")
        write(
            output,
            {
                "schema_version": "sealaudit_second_stage_v5_runner_receipt_v1",
                "generated_at_utc": utc_now(),
                "claim_bearing": False,
                "formal_v5_claim_allowed": False,
                "gate_pass": False,
                "blocked": True,
                "provider": args.provider,
                "blockers": blockers,
                "required_v5_fields": [
                    *REQUIRED_V5_FIELDS,
                    "unsafe_pass_flag",
                    "coverage_risk_frontier_entry",
                    "threshold_sensitivity_entry",
                ],
                "promotion_condition": "Coverage improves over 8.44%; unsafe-pass remains bounded; visible-marker rows stay diagnostic-only.",
            },
        )
        print("[BLOCKED] SealAudit v5 evidence missing.")
        return 2
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        claim_role = str(payload.get("claim_role", "")).lower()
        artifact_role = str(payload.get("artifact_role", "")).lower()
        if (
            "support" in claim_role
            or "support" in artifact_role
            or "not_final_claim" in claim_role
            or "not_final_claim" in artifact_role
        ):
            write(
                output,
                {
                    "schema_version": "sealaudit_second_stage_v5_runner_receipt_v1",
                    "generated_at_utc": utc_now(),
                    "claim_bearing": False,
                    "formal_v5_claim_allowed": False,
                    "gate_pass": False,
                    "blocked": True,
                    "provider": args.provider,
                    "blockers": ["v5_evidence_is_support_only_not_final_claim"],
                    "evidence_claim_role": payload.get("claim_role"),
                    "evidence_artifact_role": payload.get("artifact_role"),
                    "promotion_condition": "Coverage improves over 8.44%; unsafe-pass remains bounded; visible-marker rows stay diagnostic-only; evidence must be final v5 row-level evidence, not support-only conjunction material.",
                },
            )
            print("[BLOCKED] SealAudit v5 evidence is support-only.")
            return 2
    rows = payload.get("records", payload if isinstance(payload, list) else [])
    rows = [row for row in rows if isinstance(row, dict)]
    decisions = Counter(resolver_decision(row) for row in rows)
    unsafe = sum(1 for row in rows if row.get("unsafe_pass_flag") is True)
    schema_missing_rows = sum(1 for row in rows if missing_fields(row))
    marker_hidden_rows = [row for row in rows if str(row.get("marker_condition", "")).lower() in {"hidden", "marker_hidden"}]
    visible_rows = [row for row in rows if str(row.get("marker_condition", "")).lower() in {"visible", "marker_visible"}]
    visible_claim_rows = [
        row for row in visible_rows if row.get("claim_bearing") is True or row.get("visible_marker_diagnostic_only") is not True
    ]
    claim_hidden_rows = [row for row in marker_hidden_rows if row.get("claim_bearing") is True]
    decisive = sum(
        1
        for row in claim_hidden_rows
        if resolver_decision(row) in {"confirmed_benign", "confirmed_latent_risk"}
    )
    coverage_denominator = len(claim_hidden_rows)
    coverage = decisive / coverage_denominator if coverage_denominator else 0.0
    unsafe_ci95 = wilson(unsafe, max(1, coverage_denominator))
    blockers = []
    if not rows:
        blockers.append("v5_rows_missing")
    if schema_missing_rows:
        blockers.append("required_v5_row_schema_missing")
    if coverage_denominator != 960:
        blockers.append("marker_hidden_claim_denominator_not_960")
    if visible_claim_rows:
        blockers.append("visible_marker_rows_not_diagnostic_only")
    if coverage <= 0.084375:
        blockers.append("decisive_coverage_not_improved")
    if unsafe != 0:
        blockers.append("unsafe_pass_present")
    if "coverage_risk_frontier" not in payload and not all("coverage_risk_frontier_entry" in row for row in rows):
        blockers.append("coverage_risk_frontier_missing")
    if "threshold_sensitivity" not in payload and not all("threshold_sensitivity_entry" in row for row in rows):
        blockers.append("threshold_sensitivity_missing")
    gate_pass = not blockers
    write(
        output,
        {
            "schema_version": "sealaudit_second_stage_v5_runner_receipt_v1",
            "generated_at_utc": utc_now(),
            "claim_bearing": False,
            "formal_v5_claim_allowed": False,
            "gate_pass": gate_pass,
            "blocked": not gate_pass,
            "provider": args.provider,
            "row_count": len(rows),
            "decision_counts": dict(sorted(decisions.items())),
            "schema_missing_rows": schema_missing_rows,
            "marker_hidden_claim_rows": coverage_denominator,
            "visible_marker_rows": len(visible_rows),
            "visible_marker_claim_or_non_diagnostic_rows": len(visible_claim_rows),
            "decisive_count": decisive,
            "decisive_coverage": coverage,
            "decisive_coverage_ci95": wilson(decisive, coverage_denominator),
            "unsafe_pass_count": unsafe,
            "unsafe_pass_ci95": unsafe_ci95,
            "required_v5_fields": REQUIRED_V5_FIELDS,
            "promotion_condition": "A separate promotion gate must admit v5 before any main-claim update.",
            "blockers": blockers,
        },
    )
    print("[OK] Wrote SealAudit v5 runner receipt.")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
