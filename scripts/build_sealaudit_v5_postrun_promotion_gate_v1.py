from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
DEFAULT_OUT = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_v5_postrun_promotion_gate_v1_{DATE}.json"
DEFAULT_RECEIPT = "results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_sealaudit_v5_20260507.json"
DEFAULT_FRONTIER = "results/SealAudit/artifacts/generated/sealaudit_v5_coverage_risk_frontier_20260507.json"
DEFAULT_VISIBLE = "results/SealAudit/artifacts/generated/sealaudit_v5_visible_marker_diagnostic_boundary_20260507.json"
DEFAULT_THRESHOLD = "results/SealAudit/artifacts/generated/sealaudit_v5_threshold_sensitivity_20260507.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fail-closed SealAudit v5 final promotion gate.")
    parser.add_argument("--receipt", default=DEFAULT_RECEIPT)
    parser.add_argument("--frontier", default=DEFAULT_FRONTIER)
    parser.add_argument("--visible-boundary", default=DEFAULT_VISIBLE)
    parser.add_argument("--threshold", default=DEFAULT_THRESHOLD)
    parser.add_argument("--output", default=str(DEFAULT_OUT.relative_to(ROOT)))
    return parser.parse_args()


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def maybe_load(rel: str) -> tuple[bool, Any | None]:
    path = ROOT / rel
    if not path.exists():
        return False, None
    return True, json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def wilson(k: int, n: int) -> dict[str, Any]:
    if n <= 0:
        return {"k": k, "n": n, "rate": 0.0, "low": 0.0, "high": 1.0, "method": "wilson"}
    z = 1.959963984540054
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return {"k": k, "n": n, "rate": phat, "low": max(0.0, center - half), "high": min(1.0, center + half), "method": "wilson"}


def main() -> int:
    args = parse_args()
    output = ROOT / args.output
    readiness = load_json("results/SealAudit/artifacts/generated/sealaudit_v5_final_evidence_readiness_gate_20260507.json")
    receipt_exists, receipt = maybe_load(args.receipt)
    frontier_exists, frontier = maybe_load(args.frontier)
    visible_exists, visible = maybe_load(args.visible_boundary)
    threshold_exists, threshold = maybe_load(args.threshold)

    blockers: list[str] = []
    if readiness.get("support_ready") is not True:
        blockers.append("v5_support_not_ready")
    if not receipt_exists:
        blockers.append("v5_runner_receipt_missing")
    if not frontier_exists:
        blockers.append("v5_coverage_risk_frontier_missing")
    if not visible_exists:
        blockers.append("v5_visible_marker_boundary_missing")
    if not threshold_exists:
        blockers.append("v5_threshold_sensitivity_missing")

    metrics: dict[str, Any] = {}
    if isinstance(receipt, dict):
        if receipt.get("schema_version") != "sealaudit_second_stage_v5_runner_receipt_v1":
            blockers.append("v5_runner_receipt_schema_unexpected")
        if receipt.get("gate_pass") is not True:
            blockers.append("v5_runner_receipt_not_passed")
        if receipt.get("blocked") is True:
            blockers.extend(str(item) for item in receipt.get("blockers", []))
        hidden_rows = int(receipt.get("marker_hidden_claim_rows", 0) or 0)
        decisive = int(receipt.get("decisive_count", 0) or 0)
        unsafe = int(receipt.get("unsafe_pass_count", 0) or 0)
        visible_bad = int(receipt.get("visible_marker_claim_or_non_diagnostic_rows", 0) or 0)
        coverage = decisive / hidden_rows if hidden_rows else 0.0
        if hidden_rows != 960:
            blockers.append("marker_hidden_claim_denominator_not_960")
        if coverage <= 0.084375:
            blockers.append("decisive_coverage_not_improved_over_v3")
        if unsafe != 0:
            blockers.append("unsafe_pass_present")
        if visible_bad != 0:
            blockers.append("visible_marker_rows_not_diagnostic_only")
        metrics.update(
            {
                "marker_hidden_claim_rows": hidden_rows,
                "decisive_count": decisive,
                "decisive_coverage": coverage,
                "decisive_coverage_ci95": wilson(decisive, hidden_rows),
                "unsafe_pass_count": unsafe,
                "unsafe_pass_ci95": wilson(unsafe, hidden_rows),
                "visible_marker_claim_or_non_diagnostic_rows": visible_bad,
                "runner_blockers": receipt.get("blockers", []),
            }
        )
    else:
        metrics.update(
            {
                "marker_hidden_claim_rows": 0,
                "decisive_count": 0,
                "decisive_coverage": 0.0,
                "unsafe_pass_count": 0,
            }
        )

    if isinstance(frontier, dict) and frontier.get("gate_pass") is False:
        blockers.append("coverage_risk_frontier_gate_not_passed")
    if isinstance(visible, dict) and visible.get("gate_pass") is False:
        blockers.append("visible_marker_boundary_gate_not_passed")
    if isinstance(threshold, dict) and threshold.get("gate_pass") is False:
        blockers.append("threshold_sensitivity_gate_not_passed")

    blockers = sorted(set(blockers))
    gate_pass = not blockers
    payload = {
        "schema_version": "sealaudit_v5_postrun_promotion_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": gate_pass,
        "blocked": not gate_pass,
        "formal_v5_claim_allowed": gate_pass,
        "formal_security_certificate_claim_allowed": False,
        "formal_harmlessness_claim_allowed": False,
        "source_artifacts": {
            "readiness_gate": "results/SealAudit/artifacts/generated/sealaudit_v5_final_evidence_readiness_gate_20260507.json",
            "runner_receipt": args.receipt,
            "coverage_risk_frontier": args.frontier,
            "visible_marker_diagnostic_boundary": args.visible_boundary,
            "threshold_sensitivity": args.threshold,
        },
        "source_artifact_existence": {
            "runner_receipt": receipt_exists,
            "coverage_risk_frontier": frontier_exists,
            "visible_marker_diagnostic_boundary": visible_exists,
            "threshold_sensitivity": threshold_exists,
        },
        "postrun_metrics": metrics,
        "paper_language_lock": {
            "allowed_if_gate_passes": [
                "DeepSeek-only marker-hidden v5 selective audit/triage",
                "coverage-risk frontier with unsafe-pass CI",
                "visible-marker rows diagnostic-only",
                "hard ambiguity retained rather than forced labels",
            ],
            "forbidden_even_if_gate_passes": [
                "security certificate",
                "harmlessness guarantee",
                "automatic latent-trojan classifier",
                "expert-signed label artifact",
            ],
        },
        "blockers": blockers,
        "promotion_policy": (
            "Passing this gate permits only the scoped SealAudit v5 selective audit claim. "
            "It does not permit safety-certificate or harmlessness claims."
        ),
    }
    write_json(output, payload)
    print(f"[OK] Wrote {output.relative_to(ROOT)}")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
