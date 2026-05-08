from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
SURFACE = ROOT / "results/SealAudit/artifacts/generated/canonical_claim_surface_results.json"
FRONTIER = ROOT / "results/SealAudit/artifacts/generated/sealaudit_coverage_risk_frontier_gate_20260505.json"
EXPERT = ROOT / "results/SealAudit/artifacts/generated/sealaudit_expert_review_role_support_gate_v1_20260507.json"
TAXONOMY_ROWS = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_needs_review_row_taxonomy_v2_{DATE}.jsonl"
ABSTENTION = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_abstention_burden_frontier_v1_{DATE}.json"
WORDING = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_claim_wording_lock_v1_{DATE}.json"
JOIN = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_claim_surface_frontier_join_audit_v1_{DATE}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(path)
    return payload


def wilson(k: int, n: int) -> dict[str, Any]:
    if n <= 0:
        return {"k": k, "n": n, "rate": 0.0, "low": 0.0, "high": 1.0, "method": "wilson"}
    z = 1.959963984540054
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return {"k": k, "n": n, "rate": phat, "low": max(0.0, center - half), "high": min(1.0, center + half), "method": "wilson"}


def needs_review_bucket(record: dict[str, Any]) -> str:
    split = str(record.get("split", ""))
    variant = str(record.get("prompt_variant_id", ""))
    score = float(record.get("score", 0.5) or 0.5)
    if split == "retained_hard_ambiguity":
        return "retained_hard_ambiguity"
    if variant == "marker_hidden_schema_only":
        return "minimal_schema_insufficient_evidence"
    if score == 0.5:
        return "threshold_boundary_needs_review"
    if score > 0.5:
        return "risk_evidence_inconclusive"
    return "benign_evidence_inconclusive"


def main() -> int:
    surface = load_json(SURFACE)
    frontier = load_json(FRONTIER)
    expert = load_json(EXPERT)
    records = surface.get("records", [])
    records = records if isinstance(records, list) else []
    needs_rows = []
    for index, record in enumerate(records):
        if not isinstance(record, dict) or record.get("decision") != "needs_review":
            continue
        needs_rows.append(
            {
                "row_index": index,
                "case_id": record.get("case_id"),
                "task_id": record.get("task_id"),
                "family": record.get("family"),
                "language": record.get("language"),
                "split": record.get("split"),
                "prompt_variant_id": record.get("prompt_variant_id"),
                "score": record.get("score"),
                "bucket": needs_review_bucket(record),
                "claim_bearing": bool(record.get("claim_bearing", False)),
                "diagnostic_only": bool(record.get("diagnostic_only", False)),
                "raw_payload_hash_present": bool(record.get("raw_payload_hash") or record.get("raw_provider_response_hash")),
                "structured_payload_hash_present": bool(record.get("structured_payload_hash") or record.get("structured_provider_payload_sha256")),
                "record_hash": record.get("record_hash"),
                "threshold_version": record.get("threshold_version"),
                "review_policy": "retained_for_expert_review_not_forced_label",
            }
        )
    TAXONOMY_ROWS.parent.mkdir(parents=True, exist_ok=True)
    TAXONOMY_ROWS.write_text("\n".join(json.dumps(row, sort_keys=True) for row in needs_rows) + "\n", encoding="utf-8")
    hidden_rows = int(surface.get("claim_bearing_record_count", 0) or 0)
    dist = Counter(str(record.get("decision", "")) for record in records if isinstance(record, dict))
    decisive = dist["benign"] + dist["latent_trojan"]
    needs_count = dist["needs_review"]
    bucket_counts = Counter(row["bucket"] for row in needs_rows)
    missing_hash_rows = sum(1 for row in needs_rows if not (row["raw_payload_hash_present"] and row["structured_payload_hash_present"]))
    frontier_dist = frontier.get("decision_distribution", {})
    join_blockers: list[str] = []
    if hidden_rows != int(frontier.get("hidden_claim_rows", 0)):
        join_blockers.append("hidden_row_count_mismatch")
    for key in ("benign", "latent_trojan", "needs_review"):
        if dist[key] != int(frontier_dist.get(key, -1)):
            join_blockers.append(f"decision_distribution_mismatch:{key}")
    if missing_hash_rows:
        join_blockers.append("needs_review_hash_rows_missing")
    abstention = {
        "schema_version": "sealaudit_abstention_burden_frontier_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": hidden_rows == 960 and needs_count == 879 and decisive == 81 and missing_hash_rows == 0,
        "hidden_claim_rows": hidden_rows,
        "decisive_count": decisive,
        "decisive_coverage_ci95": wilson(decisive, hidden_rows),
        "needs_review_count": needs_count,
        "needs_review_ci95": wilson(needs_count, hidden_rows),
        "unsafe_pass_count": int(frontier.get("unsafe_pass_count", 0) or 0),
        "unsafe_pass_ci95": wilson(int(frontier.get("unsafe_pass_count", 0) or 0), hidden_rows),
        "needs_review_bucket_counts": dict(sorted(bucket_counts.items())),
        "taxonomy_rows": str(TAXONOMY_ROWS.relative_to(ROOT)),
        "reviewer_boundary": "High abstention is a first-class review-load metric. These rows must not be forced into benign/risk labels to improve apparent accuracy.",
        "formal_classifier_claim_allowed": False,
        "formal_security_certificate_claim_allowed": False,
        "blockers": [] if hidden_rows == 960 and needs_count == 879 and decisive == 81 and missing_hash_rows == 0 else ["abstention_frontier_drift_or_hash_gap"],
    }
    ABSTENTION.write_text(json.dumps(abstention, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    wording = {
        "schema_version": "sealaudit_claim_wording_lock_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": True,
        "allowed_wording": [
            "DeepSeek-only marker-hidden selective audit/triage",
            "coverage-risk frontier with high abstention disclosed",
            "role-based expert support packet reviewed through anonymous project roles",
            "visible-marker rows are diagnostic-only",
        ],
        "forbidden_wording": [
            "security certificate",
            "harmlessness guarantee",
            "automatic latent-trojan classifier",
            "expert-signed gold labels",
            "named or institutionally certified expert labels",
            "AI-prefilled expert labels",
            "visible-marker rows as main evidence",
        ],
        "expert_support_boundary": {
            "source_artifact": str(EXPERT.relative_to(ROOT)),
            "role_based_support_only": bool(expert.get("role_based_support_only", False)),
            "allowed_wording": expert.get("allowed_wording"),
            "roles": expert.get("roles", []),
        },
        "paper_sentence_required": "Expert review is reported only as anonymous role-based support and packet confirmation; row-level claim evidence comes from machine-verifiable DeepSeek marker-hidden artifacts and stated thresholds.",
    }
    WORDING.write_text(json.dumps(wording, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    join = {
        "schema_version": "sealaudit_claim_surface_frontier_join_audit_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": not join_blockers,
        "source_artifacts": {
            "canonical_claim_surface": str(SURFACE.relative_to(ROOT)),
            "coverage_risk_frontier": str(FRONTIER.relative_to(ROOT)),
            "taxonomy_rows": str(TAXONOMY_ROWS.relative_to(ROOT)),
        },
        "canonical_record_count": len(records),
        "frontier_hidden_claim_rows": int(frontier.get("hidden_claim_rows", 0) or 0),
        "decision_distribution_from_rows": dict(sorted(dist.items())),
        "decision_distribution_from_frontier": frontier_dist,
        "needs_review_taxonomy_row_count": len(needs_rows),
        "needs_review_hash_gap_count": missing_hash_rows,
        "blockers": join_blockers,
    }
    JOIN.write_text(json.dumps(join, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {TAXONOMY_ROWS.relative_to(ROOT)}")
    print(f"[OK] Wrote {ABSTENTION.relative_to(ROOT)}")
    print(f"[OK] Wrote {WORDING.relative_to(ROOT)}")
    print(f"[OK] Wrote {JOIN.relative_to(ROOT)}")
    return 0 if abstention["gate_pass"] and join["gate_pass"] and wording["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
