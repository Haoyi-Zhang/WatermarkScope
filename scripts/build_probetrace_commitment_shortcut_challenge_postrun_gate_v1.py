from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260508"
GENERATED = "artifacts/generated"
PROTOCOL = ROOT / f"results/ProbeTrace/{GENERATED}/probetrace_commitment_shortcut_challenge_protocol_v1_{DATE}.json"
RESULTS = ROOT / f"results/ProbeTrace/{GENERATED}/probetrace_commitment_shortcut_challenge_live_results_v1_{DATE}.jsonl"
OUT = ROOT / f"results/ProbeTrace/{GENERATED}/probetrace_commitment_shortcut_challenge_postrun_gate_v1_{DATE}.json"


REQUIRED_FIELDS = [
    "task_id",
    "true_owner_id",
    "candidate_owner_id",
    "provider",
    "provider_mode_resolved",
    "provider_or_backbone",
    "score",
    "owner_id_hat",
    "abstain",
    "commitment_match",
    "source_witness_commitment_hash",
    "candidate_owner_commitment_hash",
    "raw_provider_transcript_hash",
    "structured_payload_hash",
    "prompt_hash",
    "output_record_sha256",
    "record_hash",
    "claim_bearing",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def wilson(k: int, n: int) -> dict[str, float | int | str]:
    if n <= 0:
        return {"k": k, "n": n, "rate": 0.0, "low": 0.0, "high": 1.0, "method": "wilson"}
    z = 1.959963984540054
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return {"k": k, "n": n, "rate": phat, "low": max(0.0, center - half), "high": min(1.0, center + half), "method": "wilson"}


def missing_fields(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in row or row.get(field) is None:
            missing.append(field)
            continue
        # Empty owner_id_hat is the expected fail-closed form for this corrupted-commitment challenge.
        if field != "owner_id_hat" and row.get(field) == "":
            missing.append(field)
    return missing


def write(payload: dict[str, Any]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    blockers: list[str] = []
    if not PROTOCOL.exists():
        blockers.append("protocol_missing")
        protocol: dict[str, Any] = {}
    else:
        protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        if protocol.get("gate_pass") is not True:
            blockers.append("protocol_not_passed")
    if not RESULTS.exists():
        payload = {
            "schema_version": "probetrace_commitment_shortcut_challenge_postrun_gate_v1",
            "date": DATE,
            "project": "ProbeTrace",
            "claim_bearing": False,
            "gate_pass": False,
            "support_experiment_admitted": False,
            "formal_multi_owner_claim_allowed": False,
            "result_path": RESULTS.relative_to(ROOT).as_posix(),
            "record_count": 0,
            "blockers": blockers + ["result_missing"],
        }
        write(payload)
        print(json.dumps({"gate_pass": False, "blockers": payload["blockers"]}, ensure_ascii=True))
        return 1

    rows = read_jsonl(RESULTS)
    schema_missing_rows = sum(1 for row in rows if missing_fields(row))
    non_live = sum(1 for row in rows if str(row.get("provider_mode_resolved", "")).lower() != "live")
    claim_rows = sum(1 for row in rows if row.get("claim_bearing") is True)
    commitment_matches = sum(1 for row in rows if row.get("commitment_match") is True)
    owner_emit_rows = [
        row for row in rows if str(row.get("owner_id_hat", "")).strip() == str(row.get("candidate_owner_id", "")).strip()
    ]
    high_score_rows = [row for row in rows if float(row.get("score", 0.0) or 0.0) >= 0.5]
    abstain_or_low = len(rows) - len(owner_emit_rows)
    decisions = Counter(
        "owner_emitted"
        if str(row.get("owner_id_hat", "")).strip() == str(row.get("candidate_owner_id", "")).strip()
        else "abstain_or_noncandidate"
        for row in rows
    )
    if len(rows) != int(protocol.get("minimum_live_records", 20) or 20):
        blockers.append("record_count_not_protocol_minimum")
    if schema_missing_rows:
        blockers.append("required_schema_missing")
    if non_live:
        blockers.append("non_live_rows_present")
    if claim_rows:
        blockers.append("claim_bearing_rows_present")
    if commitment_matches:
        blockers.append("corrupted_commitment_unexpectedly_matched")
    if owner_emit_rows:
        blockers.append("candidate_owner_emitted_under_corrupted_commitment")
    if high_score_rows:
        blockers.append("high_score_rows_under_corrupted_commitment")

    payload = {
        "schema_version": "probetrace_commitment_shortcut_challenge_postrun_gate_v1",
        "date": DATE,
        "project": "ProbeTrace",
        "claim_bearing": False,
        "gate_pass": not blockers,
        "support_experiment_admitted": not blockers,
        "formal_multi_owner_claim_allowed": False,
        "formal_provider_general_claim_allowed": False,
        "protocol": PROTOCOL.relative_to(ROOT).as_posix(),
        "result_path": RESULTS.relative_to(ROOT).as_posix(),
        "record_count": len(rows),
        "schema_missing_rows": schema_missing_rows,
        "non_live_rows": non_live,
        "claim_bearing_rows": claim_rows,
        "commitment_match_rows": commitment_matches,
        "candidate_owner_emit_rows": len(owner_emit_rows),
        "high_score_rows": len(high_score_rows),
        "abstain_or_noncandidate_ci95": wilson(abstain_or_low, len(rows)),
        "decision_counts": dict(sorted(decisions.items())),
        "provider_modes": sorted({str(row.get("provider_mode_resolved", "")) for row in rows}),
        "owners": sorted({str(row.get("true_owner_id", "")) for row in rows}),
        "languages": sorted({str(row.get("language", "")) for row in rows}),
        "main_claim_boundary": {
            "challenge_rows_support_only": True,
            "threshold_adjusted_after_result": False,
            "main_multi_owner_score_vectors_unchanged": True,
        },
        "required_record_fields": REQUIRED_FIELDS,
        "blockers": blockers,
    }
    write(payload)
    print(json.dumps({"gate_pass": payload["gate_pass"], "record_count": len(rows), "blockers": blockers}, ensure_ascii=True))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
