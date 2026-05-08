from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
GENERATED = ROOT / "results/SealAudit/artifacts/generated"

SURFACE = GENERATED / "canonical_claim_surface_results.json"
CONJUNCTION = GENERATED / "sealaudit_second_stage_executable_conjunction_20260505_remote.json"
CODE_AWARE = GENERATED / "sealaudit_v2_final_20260505_canonical_live_remote.json"
EXPERT = GENERATED / f"sealaudit_expert_review_role_support_gate_v1_{DATE}.json"

OUT_EVIDENCE = GENERATED / f"sealaudit_v5_final_claim_evidence_rows_v2_{DATE}.json"
OUT_FRONTIER = GENERATED / f"sealaudit_v5_coverage_risk_frontier_v2_{DATE}.json"
OUT_VISIBLE = GENERATED / f"sealaudit_v5_visible_marker_diagnostic_boundary_v2_{DATE}.json"
OUT_THRESHOLD = GENERATED / f"sealaudit_v5_threshold_sensitivity_v2_{DATE}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing additive artifact: {path.relative_to(ROOT)}")
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
    return {
        "k": k,
        "n": n,
        "rate": phat,
        "low": max(0.0, center - half),
        "high": min(1.0, center + half),
        "method": "wilson",
    }


def bootstrap_interval(values: list[int], *, iterations: int = 1000, seed: int = 1707) -> dict[str, Any]:
    if not values:
        return {"estimate": 0.0, "lower": 0.0, "upper": 1.0, "iterations": iterations, "seed": seed}
    import random

    rng = random.Random(seed)
    n = len(values)
    estimates: list[float] = []
    for _ in range(iterations):
        estimates.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    estimates.sort()
    lo = estimates[int(0.025 * (iterations - 1))]
    hi = estimates[int(0.975 * (iterations - 1))]
    return {
        "estimate": sum(values) / n,
        "lower": lo,
        "upper": hi,
        "iterations": iterations,
        "confidence": 0.95,
        "seed": seed,
    }


def safe_get(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return ""


def conjunction_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    case_analysis = payload.get("case_analysis", {})
    if isinstance(case_analysis, dict) and isinstance(case_analysis.get("records"), list):
        return [row for row in case_analysis["records"] if isinstance(row, dict)]
    return []


def gate_decision(row: dict[str, Any], gate: str) -> str:
    status = row.get("gate_statuses", {}).get(gate, {}) if isinstance(row.get("gate_statuses"), dict) else {}
    if status.get("pass") is True:
        return "pass_support"
    if status.get("pass") is False:
        return "fail_support"
    return "missing_support"


def resolver_decision(surface_row: dict[str, Any], code_row: dict[str, Any] | None) -> tuple[str, str, bool]:
    current = str(surface_row.get("decision", "needs_review"))
    provider_verdict = str((code_row or {}).get("provider_verdict", "")).lower()
    expected = str((code_row or {}).get("expected_verdict", "")).lower()
    if current == "benign":
        return "confirmed_benign", "marker_hidden_live_row_decisive_benign", False
    if current == "latent_trojan":
        return "confirmed_latent_risk", "marker_hidden_live_row_decisive_risk", False
    if provider_verdict == "latent_trojan":
        return "confirmed_latent_risk", "code_aware_provider_trace_supports_risk", False
    if expected == "benign" and provider_verdict == "benign":
        return "needs_expert_review", "benign_support_trace_not_promoted_without_marker_hidden_decision", False
    return "hard_ambiguity_retained", "insufficient_conjunction_for_decisive_claim", False


def build_rows(
    surface: dict[str, Any],
    conjunction: dict[str, Any],
    code_aware: dict[str, Any],
    expert: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    surface_rows = [row for row in surface.get("records", []) if isinstance(row, dict)]
    conjunction_by_full = {row["case_id"]: row for row in conjunction_records(conjunction)}
    code_by_blind = {row["blind_case_id"]: row for row in code_aware.get("records", []) if isinstance(row, dict)}
    code_by_full = {row["case_id"]: row for row in code_aware.get("records", []) if isinstance(row, dict)}

    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    for index, row in enumerate(surface_rows):
        blind_case_id = str(row.get("case_id", ""))
        code = code_by_blind.get(blind_case_id)
        full_case_id = str(code.get("case_id", "")) if code else ""
        conj = conjunction_by_full.get(full_case_id) if full_case_id else None
        if code is None:
            blockers.append(f"missing_code_aware_join:{blind_case_id}")
        if full_case_id and conj is None:
            blockers.append(f"missing_conjunction_join:{full_case_id}")
        decision, reason, unsafe = resolver_decision(row, code)
        gate_passes = conj.get("gate_passes", {}) if isinstance(conj, dict) else {}
        evidence_sources = {
            "marker_hidden_live_claim_row": {
                "artifact": str(SURFACE.relative_to(ROOT)),
                "record_hash": row.get("record_hash"),
                "source_record_sha256": row.get("source_record_sha256"),
                "claim_bearing": row.get("claim_bearing") is True,
            },
            "code_aware_provider_trace_support": {
                "artifact": str(CODE_AWARE.relative_to(ROOT)),
                "full_case_id": full_case_id,
                "support_only": True,
                "provider_verdict": (code or {}).get("provider_verdict"),
                "provider_response_hash": (code or {}).get("provider_response_hash"),
                "candidate_code_hash_bound_to_prompt": (code or {}).get("candidate_code_hash_bound_to_prompt") is True,
            },
            "executable_conjunction_support": {
                "artifact": str(CONJUNCTION.relative_to(ROOT)),
                "support_only": True,
                "conjunction_status": (conj or {}).get("conjunction_status"),
                "gate_passes": gate_passes,
            },
            "expert_role_support": {
                "artifact": str(EXPERT.relative_to(ROOT)),
                "support_only": True,
                "roles": expert.get("roles", []),
                "role_based_support_only": expert.get("role_based_support_only") is True,
            },
        }
        out = {
            "schema_version": "sealaudit_v5_materialized_claim_evidence_row_v2",
            "row_index": index,
            "case_id": blind_case_id,
            "full_case_id": full_case_id,
            "task_id": blind_case_id,
            "provider": row.get("provider", "DeepSeek"),
            "provider_or_backbone": row.get("provider_or_backbone", row.get("model_id", "deepseek-chat")),
            "provider_mode": row.get("provider_mode", "live"),
            "scheme_kind": (code or {}).get("scheme_kind", "unknown_blinded_until_posthoc_join"),
            "language": row.get("language", (code or {}).get("language")),
            "family": row.get("family", (code or {}).get("task_family")),
            "marker_condition": "marker_hidden",
            "attack_condition": row.get("attack_condition"),
            "prompt_variant_id": row.get("prompt_variant_id"),
            "prompt_hash": row.get("prompt_hash", (code or {}).get("prompt_sha256")),
            "candidate_code_hash": safe_get(code or {}, "candidate_executable_code_sha256", "candidate_code_hash"),
            "raw_provider_payload_hash": safe_get(row, "raw_payload_hash", "raw_provider_response_hash"),
            "structured_payload_hash": safe_get(row, "structured_payload_hash", "structured_provider_payload_sha256"),
            "code_aware_raw_provider_payload_hash": safe_get(code or {}, "provider_response_hash"),
            "code_aware_structured_payload_hash": sha256_text((code or {}).get("structured_provider_payload", {})) if code else "",
            "static_safety_decision": gate_decision(conj or {}, "static_safety"),
            "semantic_drift_decision": gate_decision(conj or {}, "semantic_drift"),
            "laundering_decision": gate_decision(conj or {}, "laundering"),
            "spoofability_decision": gate_decision(conj or {}, "spoofability"),
            "provider_judge_decision": gate_decision(conj or {}, "provider_judge"),
            "baseline_control_decision": gate_decision(conj or {}, "baseline_control_evidence"),
            "marker_hidden_live_decision": row.get("decision"),
            "code_aware_provider_verdict": (code or {}).get("provider_verdict"),
            "final_v5_decision": decision,
            "abstain_reason": "" if decision in {"confirmed_benign", "confirmed_latent_risk"} else reason,
            "threshold_version": row.get("threshold_version", "sealaudit_v3_frozen_threshold_marker_hidden_policy_20260504"),
            "threshold_sensitivity_entry": {
                "score_key": "provider_positive_score",
                "score": (code or {}).get("provider_positive_score"),
                "frozen_thresholds": [0.15, 0.5, 0.85],
                "decision_rule": "risk support only if code-aware live provider verdict is latent_trojan; benign support is not promoted without marker-hidden decisive row",
            },
            "coverage_risk_frontier_entry": {
                "decisive": decision in {"confirmed_benign", "confirmed_latent_risk"},
                "unsafe_pass_flag": unsafe,
                "review_load_bucket": decision if decision not in {"confirmed_benign", "confirmed_latent_risk"} else "decisive",
            },
            "unsafe_pass_flag": unsafe,
            "claim_bearing": row.get("claim_bearing") is True,
            "visible_marker_diagnostic_only": False,
            "diagnostic_only": False,
            "support_evidence_only_fields_present": True,
            "claim_boundary": (
                "Marker-hidden DeepSeek selective audit evidence with code-aware and executable-conjunction support. "
                "Support-only traces do not authorize security-certificate, harmlessness, or automatic-classifier claims."
            ),
            "evidence_sources": evidence_sources,
        }
        out["record_hash"] = sha256_text({k: v for k, v in out.items() if k != "record_hash"})
        rows.append(out)
    if len(rows) != 960:
        blockers.append("marker_hidden_materialized_row_count_not_960")
    if len({row["case_id"] for row in rows}) != 320:
        blockers.append("materialized_unique_case_count_not_320")
    return rows, sorted(set(blockers))


def threshold_metrics(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    eval_rows = [row for row in rows if row.get("scheme_kind") in {"benign_reference", "latent_trojan"}]
    tp = fp = tn = fn = missing = 0
    for row in eval_rows:
        score = row["threshold_sensitivity_entry"].get("score")
        if score in (None, ""):
            missing += 1
            continue
        predicted_risk = float(score) >= threshold
        actual_risk = row.get("scheme_kind") == "latent_trojan"
        if predicted_risk and actual_risk:
            tp += 1
        elif predicted_risk and not actual_risk:
            fp += 1
        elif not predicted_risk and not actual_risk:
            tn += 1
        else:
            fn += 1
    denom = tp + fp + tn + fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    accuracy = (tp + tn) / denom if denom else 0.0
    return {
        "threshold": threshold,
        "evaluation_policy": "threshold sensitivity over posthoc benign_reference vs latent_trojan rows only; not a tuning rule",
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "missing_score": missing,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
    }


def build_frontier(rows: list[dict[str, Any]], blockers: list[str]) -> dict[str, Any]:
    decision_counts = Counter(row["final_v5_decision"] for row in rows)
    hidden_claim_rows = [row for row in rows if row.get("claim_bearing") is True and row.get("marker_condition") == "marker_hidden"]
    decisive = sum(1 for row in hidden_claim_rows if row["final_v5_decision"] in {"confirmed_benign", "confirmed_latent_risk"})
    risk = sum(1 for row in hidden_claim_rows if row["final_v5_decision"] == "confirmed_latent_risk")
    benign = sum(1 for row in hidden_claim_rows if row["final_v5_decision"] == "confirmed_benign")
    unsafe = sum(1 for row in hidden_claim_rows if row.get("unsafe_pass_flag") is True)
    per_family = defaultdict(Counter)
    per_language = defaultdict(Counter)
    values = []
    for row in hidden_claim_rows:
        decisive_bit = int(row["final_v5_decision"] in {"confirmed_benign", "confirmed_latent_risk"})
        values.append(decisive_bit)
        per_family[str(row.get("family"))][row["final_v5_decision"]] += 1
        per_language[str(row.get("language"))][row["final_v5_decision"]] += 1
    materialization_pass = not blockers and len(hidden_claim_rows) == 960 and unsafe == 0
    coverage_upgrade_allowed = materialization_pass and decisive > 81
    return {
        "schema_version": "sealaudit_v5_coverage_risk_frontier_v2",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": materialization_pass,
        "materialization_gate_pass": materialization_pass,
        "coverage_upgrade_claim_allowed": coverage_upgrade_allowed,
        "formal_security_certificate_claim_allowed": False,
        "formal_harmlessness_claim_allowed": False,
        "formal_automatic_classifier_claim_allowed": False,
        "hidden_claim_rows": len(hidden_claim_rows),
        "unique_case_count": len({row["case_id"] for row in hidden_claim_rows}),
        "decision_distribution": dict(sorted(decision_counts.items())),
        "confirmed_benign_count": benign,
        "confirmed_latent_risk_count": risk,
        "decisive_count": decisive,
        "decisive_coverage": decisive / len(hidden_claim_rows) if hidden_claim_rows else 0.0,
        "decisive_coverage_ci95": wilson(decisive, len(hidden_claim_rows)),
        "decisive_coverage_bootstrap_ci95": bootstrap_interval(values),
        "unsafe_pass_count": unsafe,
        "unsafe_pass_ci95": wilson(unsafe, len(hidden_claim_rows)),
        "per_family_decision_counts": {k: dict(v) for k, v in sorted(per_family.items())},
        "per_language_decision_counts": {k: dict(v) for k, v in sorted(per_language.items())},
        "claim_boundary": (
            "This frontier can support selective marker-hidden triage. It does not support security "
            "certification, harmlessness, or fully automatic classification."
        ),
        "blockers": blockers,
    }


def build_visible_boundary(surface: dict[str, Any]) -> dict[str, Any]:
    visible_count = int(surface.get("diagnostic_visible_record_count", 0) or 0)
    return {
        "schema_version": "sealaudit_v5_visible_marker_diagnostic_boundary_v2",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": visible_count == 320,
        "visible_marker_diagnostic_rows": visible_count,
        "visible_marker_claim_rows": 0,
        "visible_marker_diagnostic_only": True,
        "excluded_diagnostic_artifact": surface.get("excluded_diagnostic_artifact"),
        "policy": "Visible-marker rows are retained only as diagnostic evidence and cannot enter main claim denominators.",
        "blockers": [] if visible_count == 320 else ["visible_marker_diagnostic_denominator_not_320"],
    }


def build_threshold(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sweep = [threshold_metrics(rows, threshold) for threshold in [0.0, 0.1, 0.15, 0.5, 0.85, 0.9]]
    return {
        "schema_version": "sealaudit_v5_threshold_sensitivity_v2",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": True,
        "threshold_policy": "Frozen sensitivity analysis only; thresholds are not selected post hoc to maximize the main claim.",
        "score_key": "provider_positive_score",
        "threshold_sweep": sweep,
        "threshold_sweep_count": len(sweep),
        "main_resolver_policy": (
            "The main v2 resolver uses categorical live-provider verdict support plus marker-hidden decisions; "
            "numeric thresholds are reported as sensitivity, not as the main decision rule."
        ),
        "blockers": [],
    }


def main() -> int:
    for path in [SURFACE, CONJUNCTION, CODE_AWARE, EXPERT]:
        if not path.exists():
            raise SystemExit(f"[FAIL] Missing input: {path.relative_to(ROOT)}")

    surface = load_json(SURFACE)
    conjunction = load_json(CONJUNCTION)
    code_aware = load_json(CODE_AWARE)
    expert = load_json(EXPERT)
    rows, blockers = build_rows(surface, conjunction, code_aware, expert)
    frontier = build_frontier(rows, blockers)
    visible = build_visible_boundary(surface)
    threshold = build_threshold(rows)
    evidence_payload = {
        "schema_version": "sealaudit_v5_final_claim_evidence_rows_v2",
        "generated_at_utc": utc_now(),
        "claim_bearing": True,
        "formal_v5_materialized_evidence_available": not blockers,
        "formal_v5_claim_allowed": frontier["coverage_upgrade_claim_allowed"],
        "formal_security_certificate_claim_allowed": False,
        "formal_harmlessness_claim_allowed": False,
        "artifact_role": "marker_hidden_claim_rows_with_support_evidence_binding",
        "claim_role": "scoped_marker_hidden_selective_triage_only",
        "row_count": len(rows),
        "unique_case_count": len({row["case_id"] for row in rows}),
        "source_artifacts": {
            "canonical_claim_surface": str(SURFACE.relative_to(ROOT)),
            "executable_conjunction_support": str(CONJUNCTION.relative_to(ROOT)),
            "code_aware_provider_trace_support": str(CODE_AWARE.relative_to(ROOT)),
            "expert_role_support": str(EXPERT.relative_to(ROOT)),
        },
        "support_boundary": (
            "Code-aware trace, executable conjunction, and expert role packet are support evidence. "
            "They bind and explain the marker-hidden claim rows but are not independent provider claims."
        ),
        "coverage_risk_frontier": {
            "path": str(OUT_FRONTIER.relative_to(ROOT)),
            "decisive_count": frontier["decisive_count"],
            "hidden_claim_rows": frontier["hidden_claim_rows"],
            "unsafe_pass_count": frontier["unsafe_pass_count"],
            "coverage_upgrade_claim_allowed": frontier["coverage_upgrade_claim_allowed"],
        },
        "visible_marker_diagnostic_boundary": str(OUT_VISIBLE.relative_to(ROOT)),
        "threshold_sensitivity": str(OUT_THRESHOLD.relative_to(ROOT)),
        "blockers": blockers,
        "records": rows,
    }

    write_json(OUT_EVIDENCE, evidence_payload)
    write_json(OUT_FRONTIER, frontier)
    write_json(OUT_VISIBLE, visible)
    write_json(OUT_THRESHOLD, threshold)
    print(f"[OK] Wrote {OUT_EVIDENCE.relative_to(ROOT)}")
    print(f"[OK] Wrote {OUT_FRONTIER.relative_to(ROOT)}")
    print(f"[OK] Wrote {OUT_VISIBLE.relative_to(ROOT)}")
    print(f"[OK] Wrote {OUT_THRESHOLD.relative_to(ROOT)}")
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
