from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or validate ProbeTrace multi-owner support evidence.")
    parser.add_argument("--owners", type=int, default=5)
    parser.add_argument("--claim-bearing", default="false")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--input-score-vectors", default="")
    parser.add_argument("--output", default="")
    return parser.parse_args()


def write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


REQUIRED_ROW_FIELDS = [
    "task_id",
    "true_owner_id",
    "candidate_owner_id",
    "score",
    "split",
    "control_role",
    "owner_heldout",
    "task_heldout",
]

CLAIM_ROW_FIELDS = [
    *REQUIRED_ROW_FIELDS,
    "source_record_hash",
    "output_record_sha256",
    "owner_id_hat",
    "false_attribution",
    "signed_owner_margin",
    "family",
    "language",
]

CONTROL_ROLES = {"wrong_owner", "null_owner", "random_owner"}
POSITIVE_ROLES = {"true_owner", "positive"}


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


def read_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    rows = payload.get("records", payload) if isinstance(payload, dict) else payload
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def missing_fields(row: dict[str, Any], fields: list[str]) -> list[str]:
    return [field for field in fields if field not in row or row.get(field) in {None, ""}]


def rank_auc(rows: list[dict[str, Any]]) -> float | None:
    positives = [float(row["score"]) for row in rows if row.get("control_role") in POSITIVE_ROLES and "score" in row]
    controls = [float(row["score"]) for row in rows if row.get("control_role") in CONTROL_ROLES and "score" in row]
    if not positives or not controls:
        return None
    wins = 0.0
    total = 0
    for pos in positives:
        for neg in controls:
            total += 1
            if pos > neg:
                wins += 1.0
            elif pos == neg:
                wins += 0.5
    return wins / total if total else None


def build_missing_receipt(args: argparse.Namespace, output: Path, claim_bearing_requested: bool, blockers: list[str]) -> None:
    write(
        output,
        {
            "schema_version": "probetrace_multi_owner_support_runner_receipt_v2",
            "generated_at_utc": utc_now(),
            "claim_bearing": False,
            "formal_multi_owner_claim_allowed": False,
            "gate_pass": False,
            "blocked": True,
            "blockers": blockers,
            "requested_owners": args.owners,
            "claim_bearing_requested": claim_bearing_requested,
            "required_input_schema": CLAIM_ROW_FIELDS,
            "required_aggregate_gates": [
                "owner_count >= requested owners",
                "wrong/null/random controls >= 4x positives",
                "owner_heldout and task_heldout rows present",
                "per-owner TPR/FPR CI present in receipt",
                "rank/AUC computable",
                "near-boundary rows retained",
            ],
            "promotion_condition": "Support-only receipt. A separate promotion gate is required before any multi-owner main claim.",
        },
    )


def main() -> int:
    args = parse_args()
    output = ROOT / (args.output or f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_promotion_gate_{args.run_id}.json")
    input_path = ROOT / args.input_score_vectors if args.input_score_vectors else None
    claim_bearing_requested = str(args.claim_bearing).lower() in {"true", "1", "yes"}
    if input_path is None or not input_path.exists():
        build_missing_receipt(args, output, claim_bearing_requested, ["input_score_vectors_missing"])
        print("[BLOCKED] ProbeTrace multi-owner score vectors missing.")
        return 2

    rows = read_rows(input_path)
    owners = {row.get("true_owner_id") for row in rows if row.get("true_owner_id")}
    controls = [row for row in rows if row.get("control_role") in {"wrong_owner", "null_owner", "random_owner"}]
    positives = [row for row in rows if row.get("control_role") in {"true_owner", "positive"}]
    schema_missing_rows = sum(1 for row in rows if missing_fields(row, REQUIRED_ROW_FIELDS))
    claim_schema_missing_rows = sum(1 for row in rows if missing_fields(row, CLAIM_ROW_FIELDS))
    split_counts = Counter(str(row.get("split", "missing")) for row in rows)
    control_counts = Counter(str(row.get("control_role", "missing")) for row in rows)
    owner_heldout_rows = sum(1 for row in rows if row.get("owner_heldout") is True)
    task_heldout_rows = sum(1 for row in rows if row.get("task_heldout") is True)
    false_attributions = sum(1 for row in rows if row.get("false_attribution") is True)
    true_hits = sum(1 for row in positives if row.get("owner_id_hat") == row.get("true_owner_id"))
    per_owner: dict[str, dict[str, Any]] = {}
    by_owner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("true_owner_id"):
            by_owner[str(row["true_owner_id"])].append(row)
    for owner_id, owner_rows in sorted(by_owner.items()):
        owner_pos = [row for row in owner_rows if row.get("control_role") in POSITIVE_ROLES]
        owner_controls = [row for row in owner_rows if row.get("control_role") in CONTROL_ROLES]
        owner_hits = sum(1 for row in owner_pos if row.get("owner_id_hat") == row.get("true_owner_id"))
        owner_false = sum(1 for row in owner_controls if row.get("false_attribution") is True)
        per_owner[owner_id] = {
            "positive_rows": len(owner_pos),
            "control_rows": len(owner_controls),
            "tpr_ci95": wilson(owner_hits, len(owner_pos)),
            "fpr_ci95": wilson(owner_false, len(owner_controls)),
        }
    auc = rank_auc(rows)
    control_ratio = len(controls) / max(1, len(positives))
    blockers = []
    if claim_bearing_requested:
        blockers.append("claim_bearing_requested_but_runner_is_support_only")
    if schema_missing_rows:
        blockers.append("required_row_schema_missing")
    if claim_schema_missing_rows:
        blockers.append("claim_row_schema_missing")
    if len(owners) < args.owners:
        blockers.append("owner_count_below_requested")
    if not positives:
        blockers.append("positive_rows_missing")
    if control_ratio < 4:
        blockers.append("control_to_positive_ratio_below_4x")
    if not CONTROL_ROLES.issubset(set(control_counts)):
        blockers.append("wrong_null_random_controls_not_all_present")
    if owner_heldout_rows == 0:
        blockers.append("owner_heldout_rows_missing")
    if task_heldout_rows == 0:
        blockers.append("task_heldout_rows_missing")
    if auc is None:
        blockers.append("rank_auc_not_computable")
    gate_pass = not blockers
    write(
        output,
        {
            "schema_version": "probetrace_multi_owner_support_runner_receipt_v2",
            "generated_at_utc": utc_now(),
            "claim_bearing": False,
            "formal_multi_owner_claim_allowed": False,
            "gate_pass": gate_pass,
            "blocked": not gate_pass,
            "claim_bearing_requested": claim_bearing_requested,
            "row_count": len(rows),
            "owner_count": len(owners),
            "positive_rows": len(positives),
            "control_rows": len(controls),
            "control_to_positive_ratio": control_ratio,
            "control_role_counts": dict(sorted(control_counts.items())),
            "split_counts": dict(sorted(split_counts.items())),
            "owner_heldout_rows": owner_heldout_rows,
            "task_heldout_rows": task_heldout_rows,
            "schema_missing_rows": schema_missing_rows,
            "claim_schema_missing_rows": claim_schema_missing_rows,
            "global_tpr_ci95": wilson(true_hits, len(positives)),
            "global_fpr_ci95": wilson(false_attributions, len(controls)),
            "per_owner_ci95": per_owner,
            "margin_auc": auc,
            "required_input_schema": CLAIM_ROW_FIELDS,
            "promotion_condition": "Support-only unless a separate promotion gate admits multi-owner claim-bearing evidence.",
            "blockers": blockers,
        },
    )
    print("[OK] Wrote ProbeTrace multi-owner support receipt.")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
