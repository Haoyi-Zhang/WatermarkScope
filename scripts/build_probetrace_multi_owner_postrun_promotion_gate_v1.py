from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
DEFAULT_OUT = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_postrun_promotion_gate_v1_{DATE}.json"
DEFAULT_CANDIDATES = [
    "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_live_score_vectors_20260507.jsonl",
    "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_apis_deepseek_results_20260507.json",
    "projects/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_live_score_vectors_20260507.jsonl",
]

REQUIRED_ROW_FIELDS = [
    "task_id",
    "true_owner_id",
    "candidate_owner_id",
    "candidate_owner_count",
    "score",
    "score_space",
    "split",
    "control_role",
    "owner_heldout",
    "task_heldout",
    "source_record_hash",
    "output_record_sha256",
    "raw_provider_transcript_hash",
    "structured_payload_hash",
    "prompt_hash",
    "owner_id_hat",
    "false_attribution",
    "signed_owner_margin",
    "best_wrong_owner_id",
    "best_wrong_owner_score",
    "family",
    "language",
    "claim_bearing",
]

POSITIVE_ROLES = {"true_owner", "positive"}
CONTROL_ROLES = {"wrong_owner", "null_owner", "random_owner", "same_provider_unwrap"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fail-closed ProbeTrace multi-owner postrun promotion gate.")
    parser.add_argument("--input", default="", help="Optional JSON/JSONL multi-owner live output to validate.")
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


def read_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    rows = payload.get("records", payload.get("score_vectors", payload)) if isinstance(payload, dict) else payload
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def missing_fields(row: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_ROW_FIELDS if field not in row or row.get(field) in {None, ""}]


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


def blocked_payload(blockers: list[str], checked: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "probetrace_multi_owner_postrun_promotion_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": False,
        "blocked": True,
        "formal_multi_owner_claim_allowed": False,
        "checked_candidate_paths": checked,
        "required_row_schema": REQUIRED_ROW_FIELDS,
        "required_aggregate_gates": [
            "row_count == 6000",
            "owner_count >= 5",
            "language_count >= 3",
            "wrong/null/random/same-provider controls present",
            "control_to_positive_ratio >= 4",
            "owner-heldout and task-heldout rows present",
            "raw/structured/prompt/output/source hashes complete",
            "per-owner TPR/FPR Wilson CI",
            "threshold-free rank/AUC computable",
            "near-boundary rows retained",
        ],
        "blockers": blockers,
        "promotion_policy": "No multi-owner claim may be made from input packages, single-owner transfer, or incomplete score vectors.",
    }


def main() -> int:
    args = parse_args()
    output = ROOT / args.output
    input_package = load_json("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_package_20260507.json")
    candidate_rel, candidate_path, checked = choose_candidate(args.input)
    prereq_blockers: list[str] = []
    if input_package.get("gate_pass") is not True:
        prereq_blockers.append("multi_owner_input_package_not_ready")
    if candidate_path is None:
        payload = blocked_payload(prereq_blockers + ["fresh_multi_owner_live_score_vectors_missing"], checked)
        payload["input_package_status"] = {
            "row_count": input_package.get("row_count"),
            "owner_count": input_package.get("owner_count"),
            "language_count": input_package.get("language_count"),
            "claim_bearing": input_package.get("claim_bearing"),
            "formal_multi_owner_claim_allowed": input_package.get("formal_multi_owner_claim_allowed"),
        }
        write_json(output, payload)
        print(f"[BLOCKED] Wrote {output.relative_to(ROOT)}; fresh multi-owner outputs missing.")
        return 0

    rows = read_rows(candidate_path)
    positives = [row for row in rows if row.get("control_role") in POSITIVE_ROLES]
    controls = [row for row in rows if row.get("control_role") in CONTROL_ROLES]
    owners = {str(row.get("true_owner_id")) for row in rows if row.get("true_owner_id")}
    languages = {str(row.get("language")) for row in rows if row.get("language")}
    splits = Counter(str(row.get("split", "missing")) for row in rows)
    control_counts = Counter(str(row.get("control_role", "missing")) for row in rows)
    schema_missing_rows = sum(1 for row in rows if missing_fields(row))
    missing_hash_rows = sum(
        1
        for row in rows
        if not row.get("raw_provider_transcript_hash")
        or not row.get("structured_payload_hash")
        or not row.get("prompt_hash")
        or not row.get("source_record_hash")
        or not row.get("output_record_sha256")
    )
    claim_bearing_rows = sum(1 for row in rows if row.get("claim_bearing") is True)
    owner_heldout_rows = sum(1 for row in rows if row.get("owner_heldout") is True)
    task_heldout_rows = sum(1 for row in rows if row.get("task_heldout") is True)
    false_attributions = sum(1 for row in controls if row.get("false_attribution") is True)
    true_hits = sum(1 for row in positives if row.get("owner_id_hat") == row.get("true_owner_id"))
    by_owner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("true_owner_id"):
            by_owner[str(row["true_owner_id"])].append(row)
    per_owner_ci95 = {}
    for owner, owner_rows in sorted(by_owner.items()):
        owner_pos = [row for row in owner_rows if row.get("control_role") in POSITIVE_ROLES]
        owner_controls = [row for row in owner_rows if row.get("control_role") in CONTROL_ROLES]
        owner_hits = sum(1 for row in owner_pos if row.get("owner_id_hat") == row.get("true_owner_id"))
        owner_false = sum(1 for row in owner_controls if row.get("false_attribution") is True)
        per_owner_ci95[owner] = {
            "positive_rows": len(owner_pos),
            "control_rows": len(owner_controls),
            "tpr_ci95": wilson(owner_hits, len(owner_pos)),
            "fpr_ci95": wilson(owner_false, len(owner_controls)),
        }

    control_ratio = len(controls) / max(1, len(positives))
    auc = rank_auc(rows)
    blockers = list(prereq_blockers)
    if len(rows) != 6000:
        blockers.append("row_count_not_6000")
    if len(owners) < 5:
        blockers.append("owner_count_below_5")
    if len(languages) < 3:
        blockers.append("language_count_below_3")
    if not CONTROL_ROLES.issubset(set(control_counts)):
        blockers.append("required_control_roles_missing")
    if not positives:
        blockers.append("positive_rows_missing")
    if control_ratio < 4:
        blockers.append("control_to_positive_ratio_below_4x")
    if schema_missing_rows:
        blockers.append("required_row_schema_missing")
    if missing_hash_rows:
        blockers.append("hash_fields_missing")
    if owner_heldout_rows == 0:
        blockers.append("owner_heldout_rows_missing")
    if task_heldout_rows == 0:
        blockers.append("task_heldout_rows_missing")
    if auc is None:
        blockers.append("margin_auc_not_computable")
    if claim_bearing_rows != len(rows):
        blockers.append("non_claim_bearing_rows_present_in_candidate")

    gate_pass = not blockers
    payload = {
        "schema_version": "probetrace_multi_owner_postrun_promotion_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": gate_pass,
        "blocked": not gate_pass,
        "formal_multi_owner_claim_allowed": gate_pass,
        "candidate_artifact": candidate_rel,
        "checked_candidate_paths": checked,
        "input_package_status": {
            "row_count": input_package.get("row_count"),
            "owner_count": input_package.get("owner_count"),
            "language_count": input_package.get("language_count"),
            "claim_bearing": input_package.get("claim_bearing"),
            "formal_multi_owner_claim_allowed": input_package.get("formal_multi_owner_claim_allowed"),
        },
        "postrun_metrics": {
            "row_count": len(rows),
            "owner_count": len(owners),
            "language_count": len(languages),
            "positive_rows": len(positives),
            "control_rows": len(controls),
            "control_to_positive_ratio": control_ratio,
            "control_role_counts": dict(sorted(control_counts.items())),
            "split_counts": dict(sorted(splits.items())),
            "owner_heldout_rows": owner_heldout_rows,
            "task_heldout_rows": task_heldout_rows,
            "schema_missing_rows": schema_missing_rows,
            "missing_hash_rows": missing_hash_rows,
            "claim_bearing_rows": claim_bearing_rows,
            "global_tpr_ci95": wilson(true_hits, len(positives)),
            "global_fpr_ci95": wilson(false_attributions, len(controls)),
            "per_owner_ci95": per_owner_ci95,
            "margin_auc": auc,
        },
        "paper_language_lock": {
            "allowed_if_gate_passes": [
                "DeepSeek-only five-owner source-bound attribution",
                "owner-heldout and task-heldout multi-owner margins",
                "wrong/null/random/same-provider control rates with CI",
            ],
            "forbidden_even_if_gate_passes": [
                "provider-general attribution",
                "owner attribution from input package alone",
                "student-transfer generalization beyond source-bound receipts",
            ],
        },
        "blockers": blockers,
        "promotion_policy": "Passing this gate permits only the scoped DeepSeek multi-owner attribution claim surface.",
    }
    write_json(output, payload)
    print(f"[OK] Wrote {output.relative_to(ROOT)}")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
