from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260508"
SOURCE = ROOT / "results/SealAudit/artifacts/generated/sealaudit_v5_final_claim_evidence_rows_v2_20260507.json"
OUT = ROOT / f"results/SealAudit/artifacts/generated/sealaudit_v6_failure_taxonomy_audit_v1_{DATE}.json"


DECISIVE = {"confirmed_benign", "confirmed_latent_risk"}
RISK = {"confirmed_latent_risk"}
BENIGN = {"confirmed_benign"}
REQUIRED_FIELDS = [
    "case_id",
    "scheme_kind",
    "language",
    "marker_condition",
    "final_v5_decision",
    "static_safety_decision",
    "semantic_drift_decision",
    "laundering_decision",
    "spoofability_decision",
    "provider_judge_decision",
    "baseline_control_decision",
    "raw_provider_payload_hash",
    "structured_payload_hash",
    "record_hash",
    "claim_bearing",
    "visible_marker_diagnostic_only",
    "unsafe_pass_flag",
]


def wilson(k: int, n: int) -> dict[str, float | int | str]:
    if n <= 0:
        return {"k": k, "n": n, "rate": 0.0, "low": 0.0, "high": 1.0, "method": "wilson"}
    z = 1.959963984540054
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return {"k": k, "n": n, "rate": phat, "low": max(0.0, center - half), "high": min(1.0, center + half), "method": "wilson"}


def load_rows() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = payload.get("records", []) if isinstance(payload, dict) else []
    return payload, [row for row in rows if isinstance(row, dict)]


def missing_fields(row: dict[str, Any]) -> list[str]:
    missing = [field for field in REQUIRED_FIELDS if field not in row or row.get(field) in {None, ""}]
    decision = str(row.get("final_v5_decision", ""))
    if decision not in DECISIVE and not str(row.get("abstain_reason", "")).strip():
        missing.append("abstain_reason")
    return missing


def slice_summary(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = str(row.get(key, "missing"))
        if key == "abstain_reason" and not value:
            value = "decisive_no_abstain" if str(row.get("final_v5_decision", "")) in DECISIVE else "missing_abstain_reason"
        groups[value].append(row)
    out: dict[str, dict[str, Any]] = {}
    for value, group in sorted(groups.items()):
        decisions = Counter(str(row.get("final_v5_decision", "missing")) for row in group)
        decisive = sum(decisions.get(item, 0) for item in DECISIVE)
        unsafe = sum(1 for row in group if row.get("unsafe_pass_flag") is True)
        out[value] = {
            "rows": len(group),
            "decision_counts": dict(sorted(decisions.items())),
            "decisive_count": decisive,
            "decisive_ci95": wilson(decisive, len(group)),
            "unsafe_pass_count": unsafe,
            "unsafe_pass_ci95": wilson(unsafe, len(group)),
        }
    return out


def conjunction_patterns(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        decision = str(row.get("final_v5_decision", "missing"))
        if decision in DECISIVE:
            continue
        pattern = "|".join(
            [
                f"static={row.get('static_safety_decision', 'missing')}",
                f"drift={row.get('semantic_drift_decision', 'missing')}",
                f"launder={row.get('laundering_decision', 'missing')}",
                f"spoof={row.get('spoofability_decision', 'missing')}",
                f"judge={row.get('provider_judge_decision', 'missing')}",
                f"baseline={row.get('baseline_control_decision', 'missing')}",
                f"abstain={row.get('abstain_reason', 'missing')}",
            ]
        )
        counts[pattern] += 1
    return dict(counts.most_common(30))


def main() -> int:
    blockers: list[str] = []
    if not SOURCE.exists():
        blockers.append("source_missing")
        payload = {
            "schema_version": "sealaudit_v6_failure_taxonomy_audit_v1",
            "date": DATE,
            "claim_bearing": False,
            "gate_pass": False,
            "blockers": blockers,
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"gate_pass": False, "blockers": blockers}, ensure_ascii=True))
        return 1

    source_payload, rows = load_rows()
    hidden_claim_rows = [
        row
        for row in rows
        if str(row.get("marker_condition", "")).lower() in {"hidden", "marker_hidden"}
        and row.get("claim_bearing") is True
    ]
    visible_non_diagnostic = [
        row
        for row in rows
        if str(row.get("marker_condition", "")).lower() in {"visible", "marker_visible"}
        and (row.get("claim_bearing") is True or row.get("visible_marker_diagnostic_only") is not True)
    ]
    schema_missing_rows = sum(1 for row in hidden_claim_rows if missing_fields(row))
    hash_missing_rows = sum(
        1
        for row in hidden_claim_rows
        if not row.get("raw_provider_payload_hash") or not row.get("structured_payload_hash") or not row.get("record_hash")
    )
    decisions = Counter(str(row.get("final_v5_decision", "missing")) for row in hidden_claim_rows)
    decisive = sum(decisions.get(item, 0) for item in DECISIVE)
    risk = sum(decisions.get(item, 0) for item in RISK)
    benign = sum(decisions.get(item, 0) for item in BENIGN)
    unsafe = sum(1 for row in hidden_claim_rows if row.get("unsafe_pass_flag") is True)
    needs_expert = decisions.get("needs_expert_review", 0)
    hard_ambiguity = decisions.get("hard_ambiguity_retained", 0)

    if len(hidden_claim_rows) != 960:
        blockers.append("hidden_claim_denominator_not_960")
    if visible_non_diagnostic:
        blockers.append("visible_marker_rows_not_diagnostic_only")
    if schema_missing_rows:
        blockers.append("required_schema_missing")
    if hash_missing_rows:
        blockers.append("hash_fields_missing")
    if unsafe:
        blockers.append("unsafe_pass_present")
    if decisive <= 81:
        blockers.append("decisive_coverage_not_above_v3_floor")
    if risk == 0 or benign == 0:
        blockers.append("both_benign_and_risk_decisive_classes_required")

    payload = {
        "schema_version": "sealaudit_v6_failure_taxonomy_audit_v1",
        "date": DATE,
        "project": "SealAudit",
        "claim_bearing": False,
        "gate_pass": not blockers,
        "support_audit_admitted": not blockers,
        "formal_security_certificate_claim_allowed": False,
        "formal_harmlessness_claim_allowed": False,
        "formal_full_classifier_claim_allowed": False,
        "source_artifact": SOURCE.relative_to(ROOT).as_posix(),
        "source_schema_version": source_payload.get("schema_version"),
        "source_formal_v5_claim_allowed": source_payload.get("formal_v5_claim_allowed"),
        "hidden_claim_rows": len(hidden_claim_rows),
        "visible_marker_non_diagnostic_rows": len(visible_non_diagnostic),
        "schema_missing_rows": schema_missing_rows,
        "hash_missing_rows": hash_missing_rows,
        "decision_counts": dict(sorted(decisions.items())),
        "decisive_count": decisive,
        "decisive_ci95": wilson(decisive, len(hidden_claim_rows)),
        "confirmed_benign_count": benign,
        "confirmed_latent_risk_count": risk,
        "needs_expert_review_count": needs_expert,
        "hard_ambiguity_retained_count": hard_ambiguity,
        "unsafe_pass_count": unsafe,
        "unsafe_pass_ci95": wilson(unsafe, len(hidden_claim_rows)),
        "by_scheme_kind": slice_summary(hidden_claim_rows, "scheme_kind"),
        "by_language": slice_summary(hidden_claim_rows, "language"),
        "by_abstain_reason": slice_summary(hidden_claim_rows, "abstain_reason"),
        "nondecisive_conjunction_patterns_top30": conjunction_patterns(hidden_claim_rows),
        "paper_claim_boundary": {
            "allowed": [
                "Selective marker-hidden triage with coverage-risk frontier.",
                "Needs-review and hard-ambiguity are explicit abstentions.",
                "Unsafe-pass count is reported as zero with Wilson upper bound.",
            ],
            "forbidden": [
                "Watermark harmlessness certificate.",
                "General security certificate.",
                "Automatic full classifier over all security outcomes.",
                "Visible-marker diagnostic rows as main claim evidence.",
            ],
        },
        "blockers": blockers,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"gate_pass": payload["gate_pass"], "decisive": decisive, "unsafe": unsafe, "blockers": blockers}, ensure_ascii=True))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
