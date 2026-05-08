from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
APIS = ROOT / "results/ProbeTrace/artifacts/generated/apis300_live_attribution_evidence.json"
MARGIN_ROWS = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_owner_margin_control_audit_rows_20260505.jsonl"
PACKAGE = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_package_20260507.json"
INPUT_ROWS = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_rows_20260507.jsonl"
OUT = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_scan_v1_{DATE}.json"
OUT_ROWS = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_row_receipts_v1_{DATE}.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(path)
    return payload


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
    return rows


def main() -> int:
    apis = load_json(APIS)
    records = apis.get("records", [])
    records = records if isinstance(records, list) else []
    margin_rows = load_jsonl(MARGIN_ROWS)
    package = load_json(PACKAGE)
    input_rows = load_jsonl(INPUT_ROWS)
    receipts: list[dict[str, Any]] = []
    for row in margin_rows:
        controls = row.get("controls", {})
        controls = controls if isinstance(controls, dict) else {}
        receipts.append(
            {
                "task_id": row.get("task_id"),
                "family": row.get("family"),
                "language": row.get("language"),
                "true_owner_verified": bool(row.get("true_owner_verified", False)),
                "control_false_attribution_any": bool(row.get("control_false_attribution_any", True)),
                "control_owner_id_emitted_any": bool(row.get("control_owner_id_emitted_any", True)),
                "high_control_score_without_owner_emission": bool(row.get("high_control_score_without_owner_emission", False)),
                "near_boundary_confidence": bool(row.get("near_boundary_confidence", False)),
                "signed_owner_margin_status": row.get("signed_owner_margin_status"),
                "control_roles": sorted(controls),
                "same_provider_unwrap_present": "unwrapped_same_provider_task_level" in controls,
                "null_owner_present": "null_owner_abstain" in controls,
                "random_owner_present": "random_owner_seeded_prior" in controls,
                "utility_only_present": "task_level_utility_only_comparator" in controls,
            }
        )
    OUT_ROWS.parent.mkdir(parents=True, exist_ok=True)
    OUT_ROWS.write_text("\n".join(json.dumps(row, sort_keys=True) for row in receipts) + "\n", encoding="utf-8")
    input_owner_key_leaks = sum(1 for row in input_rows if bool(row.get("owner_key_material_in_row", False)))
    input_claim_bearing = sum(1 for row in input_rows if bool(row.get("claim_bearing", False)))
    receipt_count = len(receipts)
    false_attr = sum(1 for row in receipts if row["control_false_attribution_any"])
    owner_emit = sum(1 for row in receipts if row["control_owner_id_emitted_any"])
    high_control = sum(1 for row in receipts if row["high_control_score_without_owner_emission"])
    near_boundary = sum(1 for row in receipts if row["near_boundary_confidence"])
    missing_roles = [
        row["task_id"]
        for row in receipts
        if not (row["same_provider_unwrap_present"] and row["null_owner_present"] and row["random_owner_present"] and row["utility_only_present"])
    ]
    blockers: list[str] = []
    if len(records) != 300 or apis.get("formal_claim_allowed") is not True:
        blockers.append("apis300_source_not_clean")
    if receipt_count != 300:
        blockers.append(f"anti_leakage_receipt_count_not_300:{receipt_count}")
    if false_attr or owner_emit:
        blockers.append("control_owner_leakage_detected")
    if missing_roles:
        blockers.append("control_role_coverage_missing")
    if input_owner_key_leaks or input_claim_bearing:
        blockers.append("multi_owner_input_leakage_or_claim_bearing_rows")
    out = {
        "schema_version": "probetrace_anti_leakage_scan_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": not blockers,
        "formal_single_active_owner_claim_allowed": not blockers,
        "formal_multi_owner_claim_allowed": False,
        "source_artifacts": {
            "apis300_live": str(APIS.relative_to(ROOT)),
            "owner_margin_rows": str(MARGIN_ROWS.relative_to(ROOT)),
            "multi_owner_input_package": str(PACKAGE.relative_to(ROOT)),
            "multi_owner_input_rows": str(INPUT_ROWS.relative_to(ROOT)),
            "row_receipts": str(OUT_ROWS.relative_to(ROOT)),
        },
        "checks": {
            "apis300_record_count": len(records),
            "anti_leakage_receipt_count": receipt_count,
            "control_false_attribution_count": false_attr,
            "control_owner_id_emitted_count": owner_emit,
            "high_control_score_without_owner_emission_count": high_control,
            "near_boundary_positive_count": near_boundary,
            "missing_control_role_receipt_count": len(missing_roles),
            "multi_owner_input_rows": int(package.get("row_count", 0)),
            "multi_owner_input_owner_key_material_rows": input_owner_key_leaks,
            "multi_owner_input_claim_bearing_rows": input_claim_bearing,
            "multi_owner_role_counts": package.get("control_role_counts", {}),
            "multi_owner_split_counts": package.get("split_counts", {}),
            "receipt_family_counts": dict(sorted(Counter(str(row["family"]) for row in receipts).items())),
        },
        "reviewer_boundary": "This scan closes single-owner leakage/control-emission checks only. It does not provide comparable true-vs-wrong owner score vectors and cannot promote the multi-owner claim.",
        "remaining_blockers_for_upgrade": [
            "fresh_multi_owner_live_score_vectors_missing",
            "comparable_signed_owner_margin_rows_missing",
            "owner_task_heldout_auc_missing",
        ],
        "blockers": blockers,
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    print(f"[OK] Wrote {OUT_ROWS.relative_to(ROOT)}")
    return 0 if out["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
