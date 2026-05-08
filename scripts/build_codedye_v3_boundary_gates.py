from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT_DIR = ROOT / "results" / "CodeDye" / "artifacts" / "generated"


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def write_json(rel: str, payload: Any) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def as_int(value: Any) -> int:
    return int(value)


def main() -> int:
    low = load_json("results/CodeDye/artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json")
    freeze = load_json(f"results/CodeDye/artifacts/generated/codedye_v3_protocol_freeze_gate_{DATE}.json")
    controls = load_json(f"results/CodeDye/artifacts/generated/codedye_v3_positive_negative_control_gate_{DATE}.json")
    support = load_json("results/CodeDye/artifacts/generated/codedye_support_exclusion_inventory_fyp.json")
    surface = low["effect_surface"]

    claim_rows = as_int(surface["claim_rows"])
    final_signals = as_int(surface["decision_counts"]["contamination_signal_detected"])
    missing_hashes = as_int(surface["claim_rows_missing_payload_or_transcript_hash"])
    support_rows = as_int(surface["support_rows_excluded_from_main_denominator"])
    stats_boundary = surface["statistics_artifact_boundary"]

    live_blockers: list[str] = []
    if freeze.get("frozen") is not True:
        live_blockers.append("v3_protocol_not_frozen")
    if claim_rows != 300:
        live_blockers.append("legacy_live_denominator_not_300")
    if missing_hashes != 0:
        live_blockers.append("legacy_live_rows_missing_payload_or_transcript_hash")
    if controls.get("gate_pass") is not True:
        live_blockers.append("positive_negative_control_gate_not_passed")
    if freeze.get("formal_live_claim_allowed") is not False:
        live_blockers.append("freeze_gate_already_promotes_live_claim")

    live_gate = {
        "schema_version": "codedye_v3_live_claim_boundary_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": len(live_blockers) == 0,
        "blocked": False,
        "formal_v3_live_claim_allowed": False,
        "formal_high_recall_detection_claim_allowed": False,
        "formal_contamination_prevalence_claim_allowed": False,
        "formal_curator_side_null_audit_claim_allowed": True,
        "source_artifacts": {
            "legacy_live_boundary_gate": "results/CodeDye/artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json",
            "v3_protocol_freeze_gate": f"results/CodeDye/artifacts/generated/codedye_v3_protocol_freeze_gate_{DATE}.json",
            "v3_positive_negative_control_gate": f"results/CodeDye/artifacts/generated/codedye_v3_positive_negative_control_gate_{DATE}.json",
        },
        "legacy_live_denominator": claim_rows,
        "legacy_live_final_signal": final_signals,
        "legacy_live_final_signal_ci95": surface["final_signal_wilson95"],
        "legacy_statistics_artifact_signal": as_int(stats_boundary["statistics_artifact_positive_count"]),
        "statistics_vs_final_signal_boundary": {
            "statistics_artifact_positive_count": as_int(stats_boundary["statistics_artifact_positive_count"]),
            "final_conservative_signal_count": as_int(stats_boundary["final_conservative_signal_count"]),
            "interpretation": stats_boundary["interpretation"],
            "table_note_required": stats_boundary["table_note_required"],
        },
        "positive_control_sensitivity_ci95": controls["positive_control_sensitivity_ci95"],
        "negative_control_false_positive_ci95": surface["negative_control_false_positive_wilson95"],
        "payload_transcript_hash_missing_rows": missing_hashes,
        "support_rows_excluded_from_main_denominator": support_rows,
        "blockers": live_blockers,
        "promotion_policy": (
            "This gate only admits the existing DeepSeek 300-row result as a scoped null-audit boundary. "
            "A fresh v3 live rerun is still required before any v3 live claim promotion."
        ),
        "paper_language_lock": {
            "allowed": [
                "DeepSeek-only curator-side null-audit",
                "sparse high-confidence signal yield with CI",
                "positive-control sensitivity is moderate",
                "negative-control upper bound is reported rather than treated as zero risk",
            ],
            "forbidden": [
                "high-recall contamination detector",
                "contamination prevalence estimate",
                "provider accusation",
                "claim that non-signals imply clean training",
                "use of support/public rows in the 300-row denominator",
            ],
        },
    }

    support_blockers: list[str] = []
    if support.get("claim_bearing") is not False:
        support_blockers.append("support_inventory_is_claim_bearing")
    if as_int(support.get("main_denominator_unchanged")) != 300:
        support_blockers.append("main_denominator_changed")
    if as_int(support.get("support_rows_excluded_from_main_denominator")) != support_rows:
        support_blockers.append("support_exclusion_count_mismatch")
    if support_rows <= 0:
        support_blockers.append("no_support_rows_recorded_for_exclusion_audit")

    support_gate = {
        "schema_version": "codedye_v3_support_exclusion_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": len(support_blockers) == 0,
        "formal_v3_live_claim_allowed": False,
        "source_inventory": "results/CodeDye/artifacts/generated/codedye_support_exclusion_inventory_fyp.json",
        "main_denominator": claim_rows,
        "main_denominator_unchanged": support.get("main_denominator_unchanged"),
        "support_rows_excluded_from_main_denominator": support_rows,
        "support_categories": support.get("categories", []),
        "exclusion_policy": support.get("exclusion_policy"),
        "join_policy": (
            "Support/public/stress rows can be cited as auxiliary evidence only when every table clearly separates "
            "them from the 300 claim-bearing DeepSeek live denominator."
        ),
        "blockers": support_blockers,
    }

    write_json(f"results/CodeDye/artifacts/generated/codedye_v3_live_claim_boundary_gate_{DATE}.json", live_gate)
    write_json(f"results/CodeDye/artifacts/generated/codedye_v3_support_exclusion_gate_{DATE}.json", support_gate)
    print("[OK] Wrote CodeDye v3 live-claim boundary and support-exclusion gates.")
    return 0 if live_gate["gate_pass"] and support_gate["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
