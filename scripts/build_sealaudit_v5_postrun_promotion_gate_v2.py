from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
GENERATED = ROOT / "results/SealAudit/artifacts/generated"
OUT = GENERATED / f"sealaudit_v5_postrun_promotion_gate_v2_{DATE}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(path)
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing additive artifact: {path.relative_to(ROOT)}")
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
    paths = {
        "evidence": GENERATED / f"sealaudit_v5_final_claim_evidence_rows_v2_{DATE}.json",
        "frontier": GENERATED / f"sealaudit_v5_coverage_risk_frontier_v2_{DATE}.json",
        "visible": GENERATED / f"sealaudit_v5_visible_marker_diagnostic_boundary_v2_{DATE}.json",
        "threshold": GENERATED / f"sealaudit_v5_threshold_sensitivity_v2_{DATE}.json",
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    payloads = {name: load(path) for name, path in paths.items() if path.exists()}
    blockers: list[str] = [f"missing_{name}_artifact" for name in missing]
    evidence = payloads.get("evidence", {})
    frontier = payloads.get("frontier", {})
    visible = payloads.get("visible", {})
    threshold = payloads.get("threshold", {})
    rows = evidence.get("records", []) if isinstance(evidence.get("records"), list) else []
    decisive = int(frontier.get("decisive_count", 0) or 0)
    hidden_rows = int(frontier.get("hidden_claim_rows", 0) or 0)
    unsafe = int(frontier.get("unsafe_pass_count", 0) or 0)
    visible_claim = int(visible.get("visible_marker_claim_rows", 0) or 0)
    if evidence and evidence.get("claim_bearing") is not True:
        blockers.append("evidence_payload_not_claim_bearing")
    if len(rows) != 960:
        blockers.append("materialized_evidence_row_count_not_960")
    if frontier and frontier.get("gate_pass") is not True:
        blockers.append("coverage_risk_frontier_gate_not_passed")
    if hidden_rows != 960:
        blockers.append("hidden_claim_denominator_not_960")
    if unsafe != 0:
        blockers.append("unsafe_pass_present")
    if visible and visible.get("gate_pass") is not True:
        blockers.append("visible_marker_boundary_gate_not_passed")
    if visible_claim != 0:
        blockers.append("visible_marker_rows_entered_claim")
    if threshold and threshold.get("gate_pass") is not True:
        blockers.append("threshold_sensitivity_gate_not_passed")
    materialization_gate_pass = not blockers
    coverage_upgrade_claim_allowed = materialization_gate_pass and decisive > 81
    gate_pass = materialization_gate_pass
    out = {
        "schema_version": "sealaudit_v5_postrun_promotion_gate_v2",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": gate_pass,
        "materialization_gate_pass": materialization_gate_pass,
        "formal_v5_claim_allowed": coverage_upgrade_claim_allowed,
        "formal_v5_materialized_evidence_available": materialization_gate_pass,
        "formal_security_certificate_claim_allowed": False,
        "formal_harmlessness_claim_allowed": False,
        "formal_automatic_classifier_claim_allowed": False,
        "source_artifacts": {name: str(path.relative_to(ROOT)) for name, path in paths.items()},
        "postrun_metrics": {
            "marker_hidden_claim_rows": hidden_rows,
            "materialized_row_count": len(rows),
            "unique_case_count": frontier.get("unique_case_count"),
            "decisive_count": decisive,
            "decisive_coverage": decisive / hidden_rows if hidden_rows else 0.0,
            "decisive_coverage_ci95": wilson(decisive, hidden_rows),
            "unsafe_pass_count": unsafe,
            "unsafe_pass_ci95": wilson(unsafe, hidden_rows),
            "visible_marker_claim_rows": visible_claim,
            "threshold_sweep_count": threshold.get("threshold_sweep_count"),
        },
        "paper_language_lock": {
            "allowed_if_materialization_passes": [
                "DeepSeek-only marker-hidden selective triage with support-evidence binding",
                "coverage-risk frontier and threshold sensitivity reported as audit evidence",
                "visible-marker rows diagnostic-only",
            ],
            "allowed_only_if_formal_v5_claim_allowed": [
                "v5 coverage upgrade over the locked 81/960 v3 decisive coverage"
            ],
            "forbidden_even_if_gate_passes": [
                "security certificate",
                "harmlessness guarantee",
                "automatic latent-trojan classifier",
                "expert-signed or named expert labels",
            ],
        },
        "promotion_policy": (
            "Passing materialization means the v2 evidence package is reproducible and case-bound. "
            "A v5 coverage-upgrade claim additionally requires decisive coverage to exceed the locked v3 81/960 boundary."
        ),
        "blockers": sorted(set(blockers)),
    }
    write_json(OUT, out)
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
