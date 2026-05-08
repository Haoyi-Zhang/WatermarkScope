from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def wilson(k: int, n: int) -> dict[str, float | int | str]:
    if n <= 0:
        return {"k": k, "n": n, "rate": 0.0, "low": 0.0, "high": 0.0, "method": "wilson"}
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import ProbeTrace owner-margin control audit rows.")
    parser.add_argument("--rows", required=True)
    parser.add_argument("--remote-gate", required=True)
    parser.add_argument("--distribution-gate", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    rows_path = ROOT / args.rows
    remote_gate_path = ROOT / args.remote_gate
    distribution_path = ROOT / args.distribution_gate
    output_path = ROOT / args.output
    missing = [str(path) for path in [rows_path, remote_gate_path, distribution_path] if not path.exists()]
    if missing:
        payload = {
            "schema_version": "probetrace_owner_margin_import_gate_v1",
            "generated_at_utc": utc_now(),
            "claim_bearing": False,
            "gate_pass": False,
            "blocked": True,
            "blockers": ["input_missing"],
            "missing_inputs": missing,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("[BLOCKED] ProbeTrace owner-margin import inputs missing.")
        return 2

    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    remote_gate = load_json(remote_gate_path)
    distribution = load_json(distribution_path)
    verified = [row for row in rows if row.get("true_owner_verified") is True]
    false_attr = [row for row in rows if row.get("control_false_attribution_any") is True]
    owner_emit = [row for row in rows if row.get("control_owner_id_emitted_any") is True]
    near_boundary = [row for row in rows if row.get("near_boundary_confidence") is True]
    high_control = [row for row in rows if row.get("high_control_score_without_owner_emission") is True]
    languages = Counter(str(row.get("language", "unknown")) for row in rows)
    families = Counter(str(row.get("family", "unknown")) for row in rows)
    missing_controls = [
        row.get("task_id")
        for row in rows
        if not isinstance(row.get("controls"), dict) or len(row.get("controls", {})) < 4
    ]
    comparable_margin_rows = sum(1 for row in rows if row.get("signed_owner_margin") is not None)
    gate_pass = (
        len(rows) >= 300
        and len(verified) == len(rows)
        and len(false_attr) == 0
        and len(owner_emit) == 0
        and not missing_controls
        and bool(remote_gate.get("gate_pass"))
        and bool(distribution.get("gate_pass"))
    )
    blockers = [
        name
        for name, present in [
            ("row_count_below_300", len(rows) < 300),
            ("true_owner_not_verified_for_all_rows", len(verified) != len(rows)),
            ("control_false_attribution_present", len(false_attr) > 0),
            ("control_owner_id_emission_present", len(owner_emit) > 0),
            ("missing_required_four_controls", bool(missing_controls)),
            ("remote_owner_margin_gate_failed", not bool(remote_gate.get("gate_pass"))),
            ("remote_distribution_gate_failed", not bool(distribution.get("gate_pass"))),
        ]
        if present
    ]
    payload = {
        "schema_version": "probetrace_owner_margin_import_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": gate_pass,
        "blocked": False,
        "formal_single_owner_claim_allowed": bool(distribution.get("formal_single_owner_claim_allowed")) and gate_pass,
        "formal_multi_owner_claim_allowed": False,
        "formal_owner_separability_margin_claim_allowed": comparable_margin_rows > 0 and gate_pass,
        "inputs": {
            "rows": args.rows,
            "remote_gate": args.remote_gate,
            "distribution_gate": args.distribution_gate,
        },
        "row_count": len(rows),
        "verified_owner_rows": len(verified),
        "control_false_attribution_rows": len(false_attr),
        "control_owner_id_emission_rows": len(owner_emit),
        "near_boundary_rows": len(near_boundary),
        "high_control_score_without_owner_emission_rows": len(high_control),
        "comparable_signed_owner_margin_rows": comparable_margin_rows,
        "true_owner_verification_ci95": wilson(len(verified), len(rows)),
        "control_false_attribution_ci95": wilson(len(false_attr), len(rows)),
        "control_owner_emission_ci95": wilson(len(owner_emit), len(rows)),
        "languages": dict(sorted(languages.items())),
        "family_count": len(families),
        "top_families": dict(families.most_common(12)),
        "reviewer_defense": [
            "The perfect APIS-300 point estimate is not presented as multi-owner separability.",
            "Control scores are explicitly marked non-comparable to owner verification confidence.",
            "Near-boundary rows are retained as anti-overfit evidence rather than removed.",
        ],
        "warnings": [
            "multi_owner_score_vectors_missing_so_no_multi_owner_claim",
            "signed_owner_margin_not_available_for_current_single_owner_artifact"
            if comparable_margin_rows == 0
            else "signed_owner_margin_available",
        ],
        "blockers": blockers,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("[OK] Wrote ProbeTrace owner-margin import gate.")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
