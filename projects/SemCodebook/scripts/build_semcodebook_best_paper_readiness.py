from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _bootstrap import ARTIFACTS, ROOT

REQUIRED_RECORD_SCHEMA = (
    "carrier_signal_coverage",
    "decision_status",
    "abstain_reason",
    "positive_support_score",
    "positive_support_family_count",
    "positive_support_level_count",
)

EXPECTED_CARRIER_FAMILIES = {
    "guard_loop_accumulator",
    "guard_helper_accumulator",
    "container_helper",
    "multilingual_equivalence",
    "cfg_branch_normalization",
    "ssa_phi_liveness",
}
EXPECTED_CARRIER_LANGUAGES = {"python", "javascript", "java", "go", "cpp"}
EXPECTED_ATTACK_COVERAGE = {
    "identifier_rename",
    "semantic_rewrite",
    "control_flow_rewrite",
    "dead_code_insertion",
    "cross_language_rewrite",
}

LOCKED_CLAIM = (
    "SemCodebook is a semantic-rewrite provenance watermark for code generation: "
    "a keyed AST/CFG/SSA carrier schedule with ECC and fail-closed provenance gates."
)
FORBIDDEN_CLAIMS = (
    "universal code security certificate",
    "diagnostic or canary results as main-table evidence",
    "negative-control hits hidden by threshold changes",
    "validator-repair-dependent final recovery",
    "coverage claims before DeepSeek-Coder CarrierStressBench 7200 records finish cleanly",
)


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("records", [])
    return [dict(item) for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _status(pass_condition: bool, partial_condition: bool = False) -> str:
    if pass_condition:
        return "pass"
    if partial_condition:
        return "partial"
    return "fail"


def _first_missing_schema(records: list[dict[str, Any]]) -> dict[str, Any]:
    missing_by_field = {
        field: sum(1 for item in records if field not in item)
        for field in REQUIRED_RECORD_SCHEMA
    }
    missing_fields = [field for field, count in missing_by_field.items() if count]
    examples = []
    for item in records[:250]:
        item_missing = [field for field in REQUIRED_RECORD_SCHEMA if field not in item]
        if item_missing:
            examples.append(
                {
                    "task_id": item.get("task_id", ""),
                    "benchmark": item.get("benchmark", ""),
                    "model_name": item.get("model_name", ""),
                    "negative_control": bool(item.get("negative_control", False)),
                    "missing_fields": item_missing,
                }
            )
        if len(examples) >= 8:
            break
    return {
        "required_fields": list(REQUIRED_RECORD_SCHEMA),
        "missing_fields": missing_fields,
        "missing_by_field": missing_by_field,
        "example_stale_records": examples,
        "schema_fresh": bool(records) and not missing_fields,
    }


def _carrierstressbench_gate() -> dict[str, Any]:
    prerun = _load(ARTIFACTS / "carrierstressbench_prerun_gate.json")
    if prerun.get("schema") == "semcodebook_carrierstressbench_prerun_gate_v1":
        manifest = prerun.get("manifest", {})
        manifest = dict(manifest) if isinstance(manifest, dict) else {}
        record_contract = prerun.get("record_contract", {})
        record_contract = dict(record_contract) if isinstance(record_contract, dict) else {}
        full_run_gate = prerun.get("full_run_gate", {})
        full_run_gate = dict(full_run_gate) if isinstance(full_run_gate, dict) else {}
        pre_run_requirements = prerun.get("pre_run_requirements", {})
        pre_run_requirements = dict(pre_run_requirements) if isinstance(pre_run_requirements, dict) else {}
        task_count = int(manifest.get("observed_task_count", 0) or 0)
        contract_ok = int(record_contract.get("expected_record_count", 0) or 0) == 7200
        manifest_ok = manifest.get("status") == "pass" and task_count >= 600
        formal_allowed = bool(full_run_gate.get("formal_full_run_allowed", False))
        return {
            "status": "pass" if formal_allowed else "partial" if manifest_ok and contract_ok else "fail",
            "blocker": "" if formal_allowed else "carrierstressbench_prerun_gate_blocked",
            "task_count_target": int(manifest.get("expected_task_count", 0) or 0),
            "task_count_implemented": task_count,
            "family_counts": manifest.get("family_counts", {}),
            "language_counts": manifest.get("language_counts", {}),
            "missing_families": [],
            "missing_languages": [],
            "duplicate_task_ids": manifest.get("duplicate_task_ids", []),
            "review_status": manifest.get("review_status", {}),
            "curation_status": "prerun_gate_materialized",
            "prerun_gate_status": full_run_gate.get("status", "missing"),
            "formal_full_run_allowed": formal_allowed,
            "pre_run_requirements": pre_run_requirements,
            "blockers": full_run_gate.get("blockers", []),
            "expected_record_count": record_contract.get("expected_record_count"),
            "record_contract_pass": record_contract.get("status") == "pass",
        }
    spec = _load(ROOT / "benchmarks" / "carrier_stressbench_spec.json")
    tasks_payload = _load(ROOT / "benchmarks" / "carrier_stressbench_tasks.json")
    tasks = tasks_payload.get("tasks", [])
    tasks = [dict(item) for item in tasks if isinstance(item, dict)] if isinstance(tasks, list) else []
    family_counts = Counter(str(item.get("family") or item.get("task_family") or item.get("carrier_family") or "unknown") for item in tasks)
    language_counts = Counter(str(item.get("language") or "unknown") for item in tasks)
    task_ids = [str(item.get("task_id") or "") for item in tasks]
    duplicate_task_ids = sorted(key for key, count in Counter(task_ids).items() if key and count > 1)
    missing_families = sorted(EXPECTED_CARRIER_FAMILIES - set(family_counts))
    missing_languages = sorted(EXPECTED_CARRIER_LANGUAGES - set(language_counts))
    size_pass = len(tasks) >= 600 and int(spec.get("task_count_target", 0) or 0) >= 600
    balance_pass = (
        not missing_families
        and not missing_languages
        and all(family_counts.get(item, 0) >= 100 for item in EXPECTED_CARRIER_FAMILIES)
        and all(language_counts.get(item, 0) >= 120 for item in EXPECTED_CARRIER_LANGUAGES)
    )
    pass_condition = size_pass and balance_pass and not duplicate_task_ids
    return {
        "status": _status(pass_condition, size_pass),
        "blocker": "" if pass_condition else "carrierstressbench_manifest_not_frozen",
        "task_count_target": int(spec.get("task_count_target", 0) or 0),
        "task_count_implemented": len(tasks),
        "family_counts": dict(sorted(family_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "missing_families": missing_families,
        "missing_languages": missing_languages,
        "duplicate_task_ids": duplicate_task_ids[:20],
        "review_status": spec.get("review_status", ""),
        "curation_status": spec.get("curation_status", ""),
    }


def _baseline_gate(snapshot: dict[str, Any], *, execute_smoke: bool) -> dict[str, Any]:
    baseline_gate = _load(ARTIFACTS / "watermark_baseline_gate.json")
    if baseline_gate.get("schema_version") == "semcodebook_watermark_baseline_gate_v1":
        summary = baseline_gate.get("summary", {})
        summary = dict(summary) if isinstance(summary, dict) else {}
        baselines = baseline_gate.get("baselines", [])
        baselines = [dict(item) for item in baselines if isinstance(item, dict)] if isinstance(baselines, list) else []
        main_table_count = int(summary.get("main_table_admissible_count", 0) or 0)
        support_smoke_count = int(summary.get("support_smoke_pass_count", 0) or 0)
        return {
            "status": _status(main_table_count >= 1, support_smoke_count >= 1),
            "blocker": "" if main_table_count >= 1 else "official_runtime_watermark_baseline_not_main_table_runnable",
            "official_runnable_baseline_count": main_table_count,
            "library_smoke_ok_count": support_smoke_count,
            "citation_or_support_only_count": int(summary.get("citation_or_support_only_count", 0) or 0),
            "baseline_status": [
                {
                    "name": item.get("baseline", ""),
                    "runnable": bool(item.get("main_table_admissible", False)),
                    "smoke_ok": bool(item.get("smoke", {}).get("support", {}).get("ok", False))
                    if isinstance(item.get("smoke", {}), dict) and isinstance(item.get("smoke", {}).get("support", {}), dict)
                    else False,
                    "runnable_status": item.get("status", ""),
                    "status_detail": item.get("status_reason", ""),
                }
                for item in baselines
            ],
            "baseline_gate_status": "materialized",
            "admission_policy": baseline_gate.get(
                "policy",
                "main-table baseline requires task-level end-to-end smoke; library smoke is support-only.",
            ),
        }
    baselines = snapshot.get("runtime_baselines") or snapshot.get("baselines") or []
    if execute_smoke:
        try:
            from integrations.runtime_baselines import describe_runtime_baselines

            baselines = describe_runtime_baselines(ROOT, execute_smoke=True, timeout_seconds=180)
        except Exception as exc:  # pragma: no cover - defensive report path
            baselines = [{"name": "runtime_baseline_loader", "runnable": False, "smoke_ok": False, "runnable_status": f"loader_error:{exc}"}]
    items = [dict(item) for item in baselines if isinstance(item, dict)] if isinstance(baselines, list) else []
    runnable = [item for item in items if bool(item.get("runnable"))]
    smoke_ok = [item for item in items if bool(item.get("smoke_ok"))]
    citation_only = [item for item in items if not bool(item.get("runnable"))]
    return {
        "status": _status(len(runnable) >= 1, len(smoke_ok) >= 1),
        "blocker": "" if runnable else "official_runtime_watermark_baseline_not_main_table_runnable",
        "official_runnable_baseline_count": len(runnable),
        "library_smoke_ok_count": len(smoke_ok),
        "citation_or_support_only_count": len(citation_only),
        "baseline_status": [
            {
                "name": item.get("name", ""),
                "runnable": bool(item.get("runnable")),
                "smoke_ok": bool(item.get("smoke_ok")),
                "runnable_status": item.get("runnable_status", ""),
                "status_detail": item.get("status_detail", ""),
            }
            for item in items
        ],
        "admission_policy": "main-table baseline requires runnable=True; library smoke is support-only.",
    }


def _negative_control_gate(aggregate: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    replay_gate = _load(ARTIFACTS / "negative_control_replay_gate.json")
    negative_hits = [item for item in records if item.get("negative_control") and item.get("detected")]
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "examples": []})
    for item in negative_hits:
        key = f"{item.get('language', 'unknown')}::{item.get('attack_name') or 'clean'}::{item.get('benchmark', '')}"
        grouped[key]["count"] += 1
        if len(grouped[key]["examples"]) < 5:
            grouped[key]["examples"].append(
                {
                    "task_id": item.get("task_id", ""),
                    "model_name": item.get("model_name", ""),
                    "wm_id_hat": item.get("wm_id_hat"),
                    "confidence": item.get("confidence"),
                    "decision_status": item.get("decision_status", ""),
                }
            )
    aggregate_hit_count = int(aggregate.get("negative_control_detection_count", 0) or 0)
    replay_candidate_count = int(replay_gate.get("candidate_count", 0) or 0)
    hit_count = max(len(negative_hits), aggregate_hit_count, replay_candidate_count)
    fresh_audit = replay_gate.get("fresh_materializer_negative_split_audit", {})
    fresh_audit = dict(fresh_audit) if isinstance(fresh_audit, dict) else {}
    return {
        "status": "pass" if hit_count == 0 else "fail",
        "blocker": "" if hit_count == 0 else f"negative_control_detections_present:{hit_count}",
        "negative_control_detection_count": hit_count,
        "replay_gate_status": replay_gate.get("status", "missing"),
        "replay_candidate_count": replay_candidate_count,
        "source_count_matches_aggregate": bool(replay_gate.get("source_count_matches_aggregate", len(negative_hits) == aggregate_hit_count)),
        "fresh_materializer_negative_split_support_only": bool(fresh_audit.get("support_only", True)),
        "fresh_materializer_negative_split_can_support_repair": bool(
            replay_gate.get("canonical_replacement_policy", {}).get("fresh_materializer_negative_split_can_support_repair", False)
        )
        if isinstance(replay_gate.get("canonical_replacement_policy", {}), dict)
        else False,
        "fresh_materializer_negative_split_can_replace_canonical": bool(
            replay_gate.get("canonical_replacement_policy", {}).get("fresh_materializer_negative_split_can_replace_canonical", False)
        )
        if isinstance(replay_gate.get("canonical_replacement_policy", {}), dict)
        else False,
        "highest_risk": replay_gate.get("highest_risk", {}),
        "negative_control_hit_groups": dict(sorted(grouped.items())),
        "promotion_rule": "fresh canonical rerun must replace this artifact; hits cannot be hidden by threshold relaxation or sample removal.",
    }


def _attack_gate(records: list[dict[str, Any]], run_manifest: dict[str, Any]) -> dict[str, Any]:
    manifest_attacks = {str(item) for item in run_manifest.get("attack_names", []) if item}
    observed = {str(item.get("attack_name")) for item in records if item.get("attack_name")}
    mapped = set()
    if "rename" in manifest_attacks or any("rename" in item for item in observed):
        mapped.add("identifier_rename")
    if {"helper_extract_inline", "dataflow_rewrite"} & manifest_attacks or any("dataflow" in item or "helper" in item for item in observed):
        mapped.add("semantic_rewrite")
    if "control_flow_rewrite" in manifest_attacks or any("control_flow" in item for item in observed):
        mapped.add("control_flow_rewrite")
    if "dead_code_add_remove" in manifest_attacks or any("dead_code" in item for item in observed):
        mapped.add("dead_code_insertion")
    if "cross_language_translation" in manifest_attacks or any("cross_language" in item for item in observed):
        mapped.add("cross_language_rewrite")
    missing = sorted(EXPECTED_ATTACK_COVERAGE - mapped)
    return {
        "status": _status(not missing, bool(mapped)),
        "blocker": "" if not missing else "attack_matrix_not_complete",
        "expected_attack_families": sorted(EXPECTED_ATTACK_COVERAGE),
        "covered_attack_families": sorted(mapped),
        "missing_attack_families": missing,
        "manifest_attack_names": sorted(manifest_attacks),
        "observed_attack_names": sorted(observed),
        "claim_policy": "attack implementations are support until rerun on fresh full CarrierStressBench matrix.",
    }


def _statistics_gate(aggregate: dict[str, Any]) -> dict[str, Any]:
    prereg = _load(ARTIFACTS / "semcodebook_stats_ablation_plan.json")
    target_run = prereg.get("target_run", {}) if isinstance(prereg.get("target_run", {}), dict) else {}
    ablation_plan = prereg.get("ablation_plan", {}) if isinstance(prereg.get("ablation_plan", {}), dict) else {}
    carrier_plan = prereg.get("carrier_plan", {}) if isinstance(prereg.get("carrier_plan", {}), dict) else {}
    statistical_plan = prereg.get("statistical_plan", {}) if isinstance(prereg.get("statistical_plan", {}), dict) else {}
    prereg_ready = (
        prereg.get("schema_version") == "semcodebook_stats_ablation_prereg_v1"
        and target_run.get("expected_record_count") == 7200
        and bool(target_run.get("distribution_check", {}).get("pass"))
        if isinstance(target_run.get("distribution_check", {}), dict)
        else False
    )
    carrier_ablation_units = carrier_plan.get("carrier_ablation_units", [])
    carrier_ablation_ids = {
        str(item.get("id"))
        for item in carrier_ablation_units
        if isinstance(item, dict) and item.get("id")
    } if isinstance(carrier_ablation_units, list) else set()
    ecc_units = ablation_plan.get("ecc_ablation", {}).get("units", []) if isinstance(ablation_plan.get("ecc_ablation", {}), dict) else []
    keyed_units = ablation_plan.get("keyed_schedule_ablation", {}).get("units", []) if isinstance(ablation_plan.get("keyed_schedule_ablation", {}), dict) else []
    threshold_grid = ablation_plan.get("threshold_sensitivity", {}).get("sensitivity_grid", []) if isinstance(ablation_plan.get("threshold_sensitivity", {}), dict) else []
    rate_details = aggregate.get("rate_details", {})
    macro_scope = aggregate.get("macro_by_scope", {})
    macro_benchmark = aggregate.get("macro_by_benchmark", {})
    scope_complete = bool(macro_scope.get("clean_detection_rate", {}).get("complete"))
    benchmark_complete = bool(macro_benchmark.get("clean_detection_rate", {}).get("complete"))
    has_wilson = isinstance(rate_details, dict) and all(
        isinstance(rate_details.get(key), dict) and rate_details[key].get("method") == "wilson"
        for key in ("clean_detection", "negative_control_fp", "compile_pass_preservation")
    )
    missing_ablations = []
    for expected in ("drop_ast_carriers", "drop_cfg_carriers", "drop_ssa_carriers"):
        if expected not in carrier_ablation_ids:
            missing_ablations.append(expected)
    if not ecc_units:
        missing_ablations.append("ECC ablation")
    if not keyed_units:
        missing_ablations.append("keyed schedule ablation")
    if len(threshold_grid) < 5:
        missing_ablations.append("threshold sensitivity grid")
    pass_condition = has_wilson and scope_complete and benchmark_complete and not missing_ablations
    return {
        "status": _status(pass_condition, prereg_ready or has_wilson),
        "blocker": "" if pass_condition else "fresh_full_run_ci_and_ablation_results_missing" if prereg_ready else "full_run_ci_and_required_ablation_missing",
        "preregistration_ready": prereg_ready,
        "target_expected_record_count": target_run.get("expected_record_count"),
        "registered_date": prereg.get("registered_date", ""),
        "primary_analysis_population": statistical_plan.get("analysis_population", ""),
        "wilson_ci_present": has_wilson,
        "macro_scope_complete": scope_complete,
        "macro_benchmark_complete": benchmark_complete,
        "required_ablation_blockers": missing_ablations,
        "carrier_ablation_count": len(carrier_ablation_ids),
        "ecc_ablation_count": len(ecc_units) if isinstance(ecc_units, list) else 0,
        "keyed_schedule_ablation_count": len(keyed_units) if isinstance(keyed_units, list) else 0,
        "threshold_grid": threshold_grid,
        "headline_policy": "unweighted macro split is required for final paper table; micro pooled rates remain diagnostic.",
    }


def _paper_claim_gate(blockers: list[str]) -> dict[str, Any]:
    claim_gate = _load(ARTIFACTS / "claim_runops_gate.json")
    release_bundle_gate = claim_gate.get("release_bundle_gate", {})
    release_bundle_gate = dict(release_bundle_gate) if isinstance(release_bundle_gate, dict) else {}
    return {
        "status": "partial" if blockers else "pass",
        "blocker": "claim_locked_but_evidence_gates_open" if blockers else "",
        "locked_claim": LOCKED_CLAIM,
        "forbidden_claims": list(FORBIDDEN_CLAIMS),
        "open_promotion_blockers": blockers,
        "main_table_policy": "only canonical full runs with clean controls, CI, ablations, and reproducible provenance enter main claims.",
        "claim_runops_gate_status": claim_gate.get("claim_gate_status", "missing"),
        "claim_runops_gate_closed_reasons": claim_gate.get("gate_closed_reasons", []),
        "claim_bearing_bundle_allowed": bool(release_bundle_gate.get("claim_bearing_bundle_allowed", False)),
        "claim_runops_required_check": "python scripts/build_claim_runops_gate.py --check",
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SemCodebook Best-Paper Readiness",
        "",
        f"Generated: {payload['generated_at_utc']}",
        f"Formal experiment allowed: {str(payload['formal_experiment_allowed']).lower()}",
        "",
        "| Dimension | Status | Blocker |",
        "| --- | --- | --- |",
    ]
    for name, item in payload["dimensions"].items():
        lines.append(f"| {name} | {item['status']} | {item.get('blocker', '')} |")
    lines.extend(["", "## Locked Claim", "", payload["paper_claim"]["locked_claim"], "", "## Next Action", "", payload["next_action"], ""])
    return "\n".join(lines)


def build(*, execute_baseline_smoke: bool = False) -> dict[str, Any]:
    aggregate = _load(ARTIFACTS / "aggregate_results.json")
    snapshot = _load(ARTIFACTS / "project_snapshot.json")
    full_eval = _load(ARTIFACTS / "full_eval_results.json")
    run_manifest = _load(ARTIFACTS / "run_manifest.json")
    records = _records(full_eval)

    schema = _first_missing_schema(records)
    method_gate = _load(ARTIFACTS / "method_schema_gate.json")
    method_gate_present = method_gate.get("schema") == "semcodebook_method_schema_gate_v1"
    method_gate_claim_bearing = bool(method_gate.get("claim_bearing", False)) if method_gate_present else schema["schema_fresh"]
    method = {
        "status": "pass" if method_gate_claim_bearing else "fail",
        "blocker": "" if method_gate_claim_bearing else "canonical_full_eval_schema_stale_for_fail_closed_detector",
        "required_schema": schema,
        "method_schema_gate_status": method_gate.get("status", "missing"),
        "method_schema_gate_claim_bearing": method_gate_claim_bearing,
        "method_schema_gate_blockers": method_gate.get("blockers", []),
        "method_schema_gate_check": "python scripts/build_method_schema_gate.py --check",
        "method_components": ["AST carrier", "CFG carrier", "SSA carrier", "ECC", "keyed adaptive schedule", "fail-closed provenance"],
        "claim_policy": "old artifacts missing detector decision schema are stale and support-only.",
    }
    benchmark = _carrierstressbench_gate()
    baseline = _baseline_gate(snapshot, execute_smoke=execute_baseline_smoke)
    negative = _negative_control_gate(aggregate, records)
    attack = _attack_gate(records, run_manifest)
    statistics = _statistics_gate(aggregate)
    claim_gate = _load(ARTIFACTS / "claim_runops_gate.json")
    release_gate = claim_gate.get("release_bundle_gate", {})
    release_gate = dict(release_gate) if isinstance(release_gate, dict) else {}
    claim_runops = {
        "status": "pass"
        if claim_gate.get("claim_gate_status") == "candidate_open_after_review_ready_gate"
        else "partial"
        if claim_gate.get("schema_version") == "semcodebook_claim_runops_gate_v1"
        else "fail",
        "blocker": ""
        if claim_gate.get("claim_gate_status") == "candidate_open_after_review_ready_gate"
        else "claim_runops_gate_closed_or_missing",
        "claim_gate_status": claim_gate.get("claim_gate_status", "missing"),
        "gate_closed_reasons": claim_gate.get("gate_closed_reasons", []),
        "p1_attack_surface_count": len(claim_gate.get("reviewer_attack_surfaces", {}).get("P1", []))
        if isinstance(claim_gate.get("reviewer_attack_surfaces", {}), dict)
        else 0,
        "p2_attack_surface_count": len(claim_gate.get("reviewer_attack_surfaces", {}).get("P2", []))
        if isinstance(claim_gate.get("reviewer_attack_surfaces", {}), dict)
        else 0,
        "claim_bearing_bundle_allowed": bool(release_gate.get("claim_bearing_bundle_allowed", False)),
        "check_command": "python scripts/build_claim_runops_gate.py --check",
    }

    dimensions = {
        "method_schema": method,
        "carrierstressbench_workload": benchmark,
        "baseline_admission": baseline,
        "negative_control": negative,
        "attack_matrix": attack,
        "statistics_ablation": statistics,
        "claim_runops": claim_runops,
    }
    blockers = [
        item.get("blocker", "")
        for item in dimensions.values()
        if item.get("status") != "pass" and item.get("blocker")
    ]
    blockers.extend(str(item) for item in snapshot.get("closure_blockers", []) if str(item).strip())
    blockers = sorted(dict.fromkeys(blockers))
    paper_claim = _paper_claim_gate(blockers)
    formal_allowed = all(item.get("status") == "pass" for item in dimensions.values()) and paper_claim["status"] == "pass"
    payload = {
        "schema_version": "semcodebook_best_paper_readiness_v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "SemCodebook",
        "artifact_role": "pre_run_best_paper_gate_not_claim_bearing",
        "formal_experiment_allowed": formal_allowed,
        "next_action": blockers[0] if blockers else "generate_pre_run_gate_report_then_start_canonical_full_experiment",
        "dimensions": dimensions,
        "paper_claim": paper_claim,
        "runops": {
            "active_run_status": snapshot.get("active_run_status", ""),
            "active_run_run_id": snapshot.get("active_run_run_id", ""),
            "review_ready": bool(snapshot.get("review_ready", False)),
            "experiment_entry_allowed": bool(snapshot.get("experiment_entry_allowed", False)),
            "canonical_record_count": len(records),
            "aggregate_record_count": aggregate.get("record_count"),
            "source_of_truth": snapshot.get("source_of_truth", ""),
        },
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-baseline-smoke", action="store_true")
    args = parser.parse_args()
    payload = build(execute_baseline_smoke=args.execute_baseline_smoke)
    out_json = ARTIFACTS / "semcodebook_best_paper_readiness.json"
    out_md = ARTIFACTS / "semcodebook_best_paper_readiness.md"
    _write(out_json, payload)
    out_md.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
