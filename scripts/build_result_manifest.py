from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "RESULT_MANIFEST.jsonl"


def wilson(k: int, n: int) -> dict[str, Any]:
    z = 1.959963984540054
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * ((phat * (1 - phat) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return {
        "rate": phat,
        "ci95_low": max(0.0, center - half),
        "ci95_high": min(1.0, center + half),
        "ci_method": "Wilson score interval",
    }


ARTIFACTS: list[dict[str, Any]] = [
    {
        "module": "Dissertation",
        "claim": "Final FYP report",
        "path": "dissertation/WatermarkScope_FYP_Dissertation.pdf",
        "denominator": None,
        "numerator": None,
        "boundary": "PDF report; rebuildable from dissertation/latex.",
    },
    {
        "module": "CodeMarkBench",
        "claim": "Canonical executable run inventory",
        "path": "projects/CodeMarkBench/results/tables/suite_all_models_methods/suite_all_models_methods_run_inventory.csv",
        "denominator": 140,
        "numerator": 140,
        "independence_unit": "model_method_source_run",
        "boundary": "Finite released run-completion matrix only; not a watermark success-rate claim.",
    },
    {
        "module": "CodeMarkBench",
        "claim": "Method leaderboard",
        "path": "projects/CodeMarkBench/results/tables/suite_all_models_methods/suite_all_models_methods_method_master_leaderboard.csv",
        "denominator": 140,
        "numerator": None,
        "independence_unit": "model_method_source_run",
        "boundary": "Leaderboard summarizes evaluated baselines; not a universal failure claim.",
    },
    {
        "module": "CodeMarkBench",
        "claim": "Robustness and utility tradeoff",
        "path": "projects/CodeMarkBench/results/tables/suite_all_models_methods/suite_all_models_methods_utility_robustness_summary.csv",
        "denominator": 140,
        "numerator": None,
        "independence_unit": "model_method_source_run",
        "boundary": "Aggregate tradeoff over released suite only.",
    },
    {
        "module": "SemCodebook",
        "claim": "White-box denominator and source manifest",
        "path": "results/SemCodebook/artifacts/generated/semcodebook_whitebox_main_denominator_source_manifest_20260505.json",
        "denominator": 72000,
        "numerator": None,
        "independence_unit": "model_task_attack_control_row",
        "boundary": "Admitted white-box cells only.",
    },
    {
        "module": "SemCodebook",
        "claim": "White-box model sufficiency",
        "path": "results/SemCodebook/artifacts/generated/semcodebook_whitebox_model_sufficiency_gate_20260505.json",
        "denominator": 72000,
        "numerator": None,
        "independence_unit": "admitted_model_cell",
        "boundary": "Family/scale sufficiency gate; not a provider-general claim.",
    },
    {
        "module": "SemCodebook",
        "claim": "Positive recovery and negative-control authenticity",
        "path": "results/SemCodebook/artifacts/generated/semcodebook_whitebox_effect_authenticity_gate_20260505.json",
        "denominator": 72000,
        "numerator": None,
        "independence_unit": "model_task_attack_control_row",
        "ci_note": "Artifact contains positive and negative denominators; headline negative zero-event upper bound is 0.008% for 0/48,000.",
        "boundary": "Recovery and controls inside fixed denominator.",
    },
    {
        "module": "SemCodebook",
        "claim": "Positive recovery",
        "path": "results/SemCodebook/artifacts/generated/semcodebook_whitebox_effect_authenticity_gate_20260505.json",
        "denominator": 24000,
        "numerator": 23342,
        "independence_unit": "positive_model_task_attack_row",
        "ci_required": True,
        **wilson(23342, 24000),
        "boundary": "Headline white-box recovery over claim-bearing positive rows only.",
    },
    {
        "module": "SemCodebook",
        "claim": "Negative-control hits",
        "path": "results/SemCodebook/artifacts/generated/semcodebook_whitebox_effect_authenticity_gate_20260505.json",
        "denominator": 48000,
        "numerator": 0,
        "independence_unit": "negative_control_row",
        "ci_required": True,
        **wilson(0, 48000),
        "boundary": "Headline clean-control surface; zero observed hits is reported with its upper bound.",
    },
    {
        "module": "SemCodebook",
        "claim": "Generation-changing ablation",
        "path": "results/SemCodebook/artifacts/generated/semcodebook_generation_changing_ablation_promotion_gate_20260505.json",
        "denominator": 43200,
        "numerator": None,
        "independence_unit": "ablation_arm_task_attack_row",
        "boundary": "Ablation evidence only; no first-sample/no-retry promotion.",
    },
    {
        "module": "SemCodebook",
        "claim": "Compact ablation summary for examiner review",
        "path": "results/SemCodebook/artifacts/generated/semcodebook_ablation_compact_summary_fyp.json",
        "denominator": 43200,
        "numerator": None,
        "independence_unit": "ablation_arm_task_attack_row",
        "boundary": "Compact review index derived from the ablation promotion gate.",
    },
    {
        "module": "CodeDye",
        "claim": "Sparse null-audit signal boundary",
        "path": "results/CodeDye/artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json",
        "denominator": 300,
        "numerator": 6,
        "independence_unit": "live_audit_task",
        "ci_required": True,
        **wilson(6, 300),
        "boundary": "Null-audit effect summary and claim-boundary gate; not a prevalence or accusation claim.",
    },
    {
        "module": "CodeDye",
        "claim": "Positive contamination control",
        "path": "results/CodeDye/artifacts/generated/codedye_positive_contamination_control_300_gate_20260505.json",
        "denominator": 300,
        "numerator": 170,
        "independence_unit": "positive_control_task",
        "ci_required": True,
        **wilson(170, 300),
        "boundary": "Known-control calibration, separate from live-audit denominator.",
    },
    {
        "module": "CodeDye",
        "claim": "Negative control",
        "path": "results/CodeDye/artifacts/generated/codedye_negative_control_300plus_gate_20260505.json",
        "denominator": 300,
        "numerator": 0,
        "independence_unit": "negative_control_task",
        "ci_required": True,
        **wilson(0, 300),
        "boundary": "False-positive control surface only.",
    },
    {
        "module": "CodeDye",
        "claim": "Frozen dual-evidence protocol",
        "path": "results/CodeDye/artifacts/generated/codedye_v2_dual_evidence_protocol_freeze_gate_20260506.json",
        "denominator": None,
        "numerator": None,
        "boundary": "Protocol freeze and threshold discipline; not extra positive evidence.",
    },
    {
        "module": "CodeDye",
        "claim": "Support row exclusion inventory",
        "path": "results/CodeDye/artifacts/generated/codedye_support_exclusion_inventory_fyp.json",
        "denominator": 806,
        "numerator": None,
        "independence_unit": "support_row",
        "support_only": True,
        "claim_bearing": False,
        "support_denominator": 806,
        "boundary": "Excluded support rows cannot change the 300-row live-audit denominator.",
    },
    {
        "module": "ProbeTrace",
        "claim": "APIS-300 attribution evidence",
        "path": "results/ProbeTrace/artifacts/generated/apis300_live_attribution_evidence.json",
        "denominator": 300,
        "numerator": 300,
        "independence_unit": "apis_task",
        "ci_required": True,
        **wilson(300, 300),
        "boundary": "Single-active-owner/source-bound setting.",
    },
    {
        "module": "ProbeTrace",
        "claim": "False-owner and abstain-aware controls",
        "path": "results/ProbeTrace/artifacts/generated/probetrace_abstain_aware_attribution_gate_20260506.json",
        "denominator": 1200,
        "numerator": 0,
        "independence_unit": "false_owner_control_row",
        "ci_required": True,
        **wilson(0, 1200),
        "boundary": "Control evidence; not multi-owner provider-general attribution.",
    },
    {
        "module": "ProbeTrace",
        "claim": "Owner margin control audit",
        "path": "results/ProbeTrace/artifacts/generated/probetrace_owner_margin_control_audit_gate_20260505.json",
        "denominator": 1200,
        "numerator": 0,
        "independence_unit": "owner_margin_control_row",
        "ci_required": True,
        **wilson(0, 1200),
        "boundary": "Margin/control audit under fixed owner registry.",
    },
    {
        "module": "ProbeTrace",
        "claim": "Transfer validation results",
        "path": "results/ProbeTrace/artifacts/generated/student_transfer_live_validation_results.owner_witness_v6_clean_holdout.json",
        "denominator": 900,
        "numerator": 900,
        "independence_unit": "transfer_receipt_row",
        "primary_independence_unit": "task_cluster",
        "primary_task_clusters": 300,
        "ci_required": True,
        "support_only": True,
        "claim_bearing": False,
        **wilson(900, 900),
        "support_denominator": 900,
        "boundary": "Transfer rows are source-bound support rows; primary attribution task clusters remain 300.",
    },
    {
        "module": "ProbeTrace",
        "claim": "Transfer row binding manifest",
        "path": "results/ProbeTrace/artifacts/generated/probetrace_transfer_row_binding_manifest_gate_20260505.json",
        "denominator": 900,
        "numerator": 900,
        "independence_unit": "transfer_receipt_row",
        "primary_independence_unit": "task_cluster",
        "primary_task_clusters": 300,
        "ci_required": True,
        "support_only": True,
        "claim_bearing": False,
        **wilson(900, 900),
        "boundary": "Receipt and dataset integrity gate; transfer support surface, not a separate 900-task primary attribution denominator.",
    },
    {
        "module": "SealAudit",
        "claim": "Marker-hidden canonical triage surface",
        "path": "results/SealAudit/artifacts/generated/canonical_claim_surface_results.json",
        "denominator": 960,
        "numerator": 81,
        "independence_unit": "marker_hidden_claim_row",
        "ci_required": True,
        **wilson(81, 960),
        "boundary": "Selective marker-hidden triage only.",
    },
    {
        "module": "SealAudit",
        "claim": "Coverage-risk frontier",
        "path": "results/SealAudit/artifacts/generated/sealaudit_coverage_risk_frontier_gate_20260505.json",
        "denominator": 960,
        "numerator": 81,
        "independence_unit": "marker_hidden_claim_row",
        "ci_required": True,
        **wilson(81, 960),
        "boundary": "Coverage-risk tradeoff; not a safety certificate.",
    },
    {
        "module": "SealAudit",
        "claim": "Second-stage side-by-side resolver gate",
        "path": "results/SealAudit/artifacts/generated/sealaudit_second_stage_v4_side_by_side_resolver_gate_20260505.json",
        "denominator": 960,
        "numerator": None,
        "independence_unit": "marker_hidden_claim_row",
        "boundary": "Resolver evidence; does not silently relabel old results.",
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def row_count(path: Path) -> int | None:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
    if suffix == ".csv":
        with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
            rows = list(csv.reader(f))
        return max(0, len(rows) - 1)
    if suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            for key in ("records", "rows", "results", "items", "cases"):
                value = data.get(key)
                if isinstance(value, list):
                    return len(value)
        return None
    return None


def main() -> None:
    rows = []
    for spec in ARTIFACTS:
        path = ROOT / spec["path"]
        if not path.exists():
            raise SystemExit(f"Missing artifact: {spec['path']}")
        rows.append(
            {
                **spec,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "file_row_count": row_count(path),
            }
        )

    OUT.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT.relative_to(ROOT)} with {len(rows)} artifacts.")


if __name__ == "__main__":
    main()
