from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
DEFAULT_OUT = ROOT / f"results/CodeDye/artifacts/generated/codedye_v3_postrun_promotion_gate_v1_{DATE}.json"
DEFAULT_CANDIDATES = [
    "results/CodeDye/artifacts/generated/codedye_v3_live_results_20260507.json",
    "projects/CodeDye/artifacts/generated/codedye_v3_live_results_20260507.json",
    "projects/CodeDye/artifacts/generated/attack_matrix_live_support.json",
]

REQUIRED_RECORD_FIELDS = [
    "task_id",
    "attack_id",
    "run_id",
    "provider_name",
    "provider_mode_resolved",
    "provider_or_backbone",
    "prompt_hash",
    "attack_prompt_hash",
    "raw_payload_hash",
    "raw_provider_transcript_hash",
    "structured_payload_hash",
    "task_hash",
    "record_hash",
    "claim_bearing",
    "claim_bearing_attack_evidence",
    "support_only_not_claim_bearing",
    "utility_admissible_for_attack_claim",
    "selected_utility_score",
    "decision",
    "threshold_version",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fail-closed CodeDye v3 postrun promotion gate.")
    parser.add_argument("--input", default="", help="Optional v3 live result JSON to validate.")
    parser.add_argument("--output", default=str(DEFAULT_OUT.relative_to(ROOT)))
    return parser.parse_args()


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


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


def missing_fields(row: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_RECORD_FIELDS if field not in row or row.get(field) in {None, ""}]


def choose_candidate(explicit: str) -> tuple[str | None, Path | None, list[str]]:
    candidates = [explicit] if explicit else DEFAULT_CANDIDATES
    checked: list[str] = []
    for rel in candidates:
        if not rel:
            continue
        path = ROOT / rel
        checked.append(rel)
        if path.exists():
            return rel, path, checked
    return None, None, checked


def blocked_payload(blockers: list[str], checked: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "codedye_v3_postrun_promotion_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": False,
        "blocked": True,
        "formal_v3_live_claim_allowed": False,
        "formal_high_recall_detection_claim_allowed": False,
        "formal_contamination_prevalence_claim_allowed": False,
        "checked_candidate_paths": checked,
        "required_live_result_schema": {
            "payload": [
                "schema_version",
                "status",
                "run_id",
                "claim_bearing",
                "formal_claim_allowed",
                "summary",
                "records",
            ],
            "records": REQUIRED_RECORD_FIELDS,
        },
        "blockers": blockers,
        "promotion_policy": (
            "A fresh v3 live result can only upgrade the scoped null-audit claim after row-level hashes, "
            "utility admissibility, support exclusion, controls, and fixed-denominator statistics all pass. "
            "This gate never permits high-recall detection or prevalence claims."
        ),
    }


def main() -> int:
    args = parse_args()
    output = ROOT / args.output
    freeze = load_json("results/CodeDye/artifacts/generated/codedye_v3_protocol_freeze_gate_20260507.json")
    controls = load_json("results/CodeDye/artifacts/generated/codedye_v3_positive_negative_control_gate_20260507.json")
    support = load_json("results/CodeDye/artifacts/generated/codedye_v3_support_exclusion_gate_20260507.json")
    candidate_rel, candidate_path, checked = choose_candidate(args.input)

    prereq_blockers: list[str] = []
    if freeze.get("frozen") is not True:
        prereq_blockers.append("v3_protocol_not_frozen")
    if controls.get("gate_pass") is not True:
        prereq_blockers.append("positive_negative_control_gate_not_passed")
    if support.get("gate_pass") is not True:
        prereq_blockers.append("support_exclusion_gate_not_passed")
    if candidate_path is None:
        payload = blocked_payload(prereq_blockers + ["fresh_v3_live_result_missing"], checked)
        payload["prerequisite_gates"] = {
            "protocol_freeze_gate_pass": freeze.get("frozen") is True,
            "positive_negative_control_gate_pass": controls.get("gate_pass") is True,
            "support_exclusion_gate_pass": support.get("gate_pass") is True,
        }
        write_json(output, payload)
        print(f"[BLOCKED] Wrote {output.relative_to(ROOT)}; fresh v3 live result missing.")
        return 0

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    records = candidate.get("records", []) if isinstance(candidate, dict) else []
    records = [row for row in records if isinstance(row, dict)]
    summary = candidate.get("summary", {}) if isinstance(candidate, dict) else {}
    summary = summary if isinstance(summary, dict) else {}
    blockers = list(prereq_blockers)

    if candidate.get("schema_version") != "codedye_attack_matrix_live_canonical_v1":
        blockers.append("candidate_schema_not_v3_canonical_live")
    if candidate.get("claim_bearing") is not True:
        blockers.append("candidate_payload_not_claim_bearing")
    if candidate.get("formal_claim_allowed") is not True:
        blockers.append("candidate_formal_claim_not_allowed")
    if candidate.get("status") != "passed":
        blockers.append("candidate_status_not_passed")
    if len(records) != 300:
        blockers.append("candidate_record_count_not_300")

    schema_missing_rows = sum(1 for row in records if missing_fields(row))
    live_rows = sum(1 for row in records if str(row.get("provider_mode_resolved", "")).lower() == "live")
    claim_rows = [row for row in records if row.get("claim_bearing") is True and row.get("claim_bearing_attack_evidence") is True]
    support_rows_in_candidate = [row for row in records if row.get("support_only_not_claim_bearing") is True]
    utility_admissible_claim_rows = [row for row in claim_rows if row.get("utility_admissible_for_attack_claim") is True]
    missing_hash_rows = [
        row
        for row in records
        if not row.get("raw_provider_transcript_hash")
        or not row.get("structured_payload_hash")
        or not row.get("prompt_hash")
        or not row.get("task_hash")
        or not row.get("record_hash")
    ]
    mock_or_replay_rows = [row for row in records if str(row.get("provider_mode_resolved", "")).lower() != "live"]
    decision_counts = Counter(str(row.get("decision", "missing")) for row in claim_rows)
    detected = int(decision_counts.get("contamination_signal_detected", 0))

    if schema_missing_rows:
        blockers.append("required_record_schema_missing")
    if live_rows != len(records):
        blockers.append("non_live_provider_rows_present")
    if missing_hash_rows:
        blockers.append("row_hash_or_payload_hash_missing")
    if mock_or_replay_rows:
        blockers.append("mock_or_replay_rows_present")
    if support_rows_in_candidate:
        blockers.append("support_only_rows_present_in_v3_main_candidate")
    if len(utility_admissible_claim_rows) != len(claim_rows):
        blockers.append("utility_inadmissible_claim_rows_present")
    if len(claim_rows) != 300:
        blockers.append("claim_denominator_not_300")
    if int(summary.get("payload_hash_missing_count", 0) or 0):
        blockers.append("summary_payload_hash_missing_count_nonzero")
    if summary.get("gate_pass") is not True:
        blockers.append("candidate_summary_gate_not_passed")
    if summary.get("support_gate_pass") is not True and "query_budget_drop" in summary.get("observed_attack_ids", []):
        blockers.append("candidate_support_gate_not_passed")
    if summary.get("claim_denominator_record_count") not in {None, 300}:
        blockers.append("summary_claim_denominator_not_300")

    gate_pass = not blockers
    payload = {
        "schema_version": "codedye_v3_postrun_promotion_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": gate_pass,
        "blocked": not gate_pass,
        "formal_v3_live_claim_allowed": gate_pass,
        "formal_high_recall_detection_claim_allowed": False,
        "formal_contamination_prevalence_claim_allowed": False,
        "candidate_artifact": candidate_rel,
        "checked_candidate_paths": checked,
        "prerequisite_gates": {
            "protocol_freeze_gate_pass": freeze.get("frozen") is True,
            "positive_negative_control_gate_pass": controls.get("gate_pass") is True,
            "support_exclusion_gate_pass": support.get("gate_pass") is True,
            "positive_control_detected": controls.get("positive_control_detected"),
            "positive_control_denominator": controls.get("positive_control_denominator"),
            "negative_control_status": controls.get("negative_control_status"),
            "support_rows_excluded_from_main_denominator": support.get("support_rows_excluded_from_main_denominator"),
        },
        "postrun_metrics": {
            "record_count": len(records),
            "live_rows": live_rows,
            "claim_denominator": len(claim_rows),
            "utility_admissible_claim_rows": len(utility_admissible_claim_rows),
            "support_rows_in_candidate": len(support_rows_in_candidate),
            "schema_missing_rows": schema_missing_rows,
            "missing_hash_rows": len(missing_hash_rows),
            "mock_or_replay_rows": len(mock_or_replay_rows),
            "decision_counts": dict(sorted(decision_counts.items())),
            "signal_ci95": wilson(detected, len(claim_rows)),
            "summary_gate_pass": summary.get("gate_pass"),
            "summary_support_gate_pass": summary.get("support_gate_pass"),
            "support_gate_required_for_v3_main_denominator": "query_budget_drop" in summary.get("observed_attack_ids", []),
            "summary_blockers": summary.get("blockers"),
            "summary_canonical_promotion_blockers": summary.get("canonical_promotion_blockers"),
        },
        "paper_language_lock": {
            "allowed_if_gate_passes": [
                "DeepSeek-only v3 curator-side null-audit postrun",
                "fixed-denominator sparse signal yield with CI",
                "positive-control sensitivity remains separately reported",
                "support rows remain excluded from the 300-row denominator",
            ],
            "forbidden_even_if_gate_passes": [
                "high-recall contamination detector",
                "contamination prevalence estimate",
                "provider accusation",
                "claim that non-signals imply no contamination",
            ],
        },
        "blockers": blockers,
        "promotion_policy": (
            "Passing this gate permits only the scoped v3 DeepSeek null-audit claim surface. "
            "It does not permit high-recall detection, prevalence, or provider-general claims."
        ),
    }
    write_json(output, payload)
    print(f"[OK] Wrote {output.relative_to(ROOT)}")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
