from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def write(rel: str, payload: Any) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> int:
    sem = load("results/SemCodebook/artifacts/generated/semcodebook_row_level_miss_attribution_v3_20260507.json")
    sem_causal = load("results/SemCodebook/artifacts/generated/semcodebook_causal_contribution_gate_v2_20260507.json")
    codedye = load("results/CodeDye/artifacts/generated/codedye_positive_miss_taxonomy_v2_20260507.json")
    codedye_live = load("results/CodeDye/artifacts/generated/codedye_v3_live_claim_boundary_gate_20260507.json")
    codedye_support = load("results/CodeDye/artifacts/generated/codedye_v3_support_exclusion_gate_20260507.json")
    codedye_negative = load("results/CodeDye/artifacts/generated/codedye_negative_control_row_source_manifest_20260507.json")
    codedye_support_ledger = load("results/CodeDye/artifacts/generated/codedye_support_exclusion_row_ledger_gate_20260507.json")
    codedye_bridge = load("results/CodeDye/artifacts/generated/codedye_v3_reused_control_bridge_20260507.json")
    probe = load("results/ProbeTrace/artifacts/generated/probetrace_owner_margin_import_gate_v1_20260507.json")
    probe_multi = load("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_promotion_gate_20260507.json")
    probe_readiness = load("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_rerun_readiness_gate_20260507.json")
    seal_support = load("results/SealAudit/artifacts/generated/sealaudit_second_stage_support_import_gate_v1_20260507.json")
    seal_v5_guard = load("results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_remote_support_guard_20260507.json")
    seal_readiness = load("results/SealAudit/artifacts/generated/sealaudit_v5_final_evidence_readiness_gate_20260507.json")
    payload = {
        "schema_version": "watermark_bestpaper_current_state_v2_20260507",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "bestpaper_ready": False,
        "formal_full_experiment_allowed": False,
        "status_summary": {
            "SemCodebook": {
                "status": "real_row_level_ablation_miss_attribution_and_causal_table_complete",
                "gate_pass": sem["gate_pass"],
                "records": sem["record_count"],
                "positive_count": sem["positive_count"],
                "positive_miss_count": sem["positive_miss_count"],
                "primary_failure_boundary": sem["miss_bucket_counts"],
                "causal_contribution_gate_pass": sem_causal["gate_pass"],
                "formal_causal_claim_allowed": sem_causal["formal_causal_claim_allowed"],
                "remaining_bestpaper_gap": "Paper claim wording must foreground the DeepSeek-Coder abstention boundary and avoid no-retry natural-generation claims.",
            },
            "CodeDye": {
                "status": "null_audit_boundary_complete_with_v3_support_exclusion_and_reused_control_bridge",
                "gate_pass": codedye["gate_pass"],
                "positive_controls": f"{codedye['positive_control_detected']}/{codedye['positive_control_denominator']}",
                "positive_control_sensitivity_ci95": codedye["positive_control_sensitivity_ci95"],
                "primary_failure_boundary": codedye["miss_bucket_counts"],
                "v3_live_boundary_gate_pass": codedye_live["gate_pass"],
                "v3_formal_live_claim_allowed": codedye_live["formal_v3_live_claim_allowed"],
                "support_exclusion_gate_pass": codedye_support["gate_pass"],
                "support_exclusion_ledger_rows": codedye_support_ledger["ledger_row_count"],
                "reused_control_bridge_gate_pass": codedye_bridge["gate_pass"],
                "negative_control_row_source_local_available": codedye_negative["row_level_ledger_available_in_local_bundle"],
                "remaining_bestpaper_gap": "DeepSeek live result remains sparse 6/300 and negative-control row-level source is not in the compact local bundle; acceptable only as conservative null-audit unless a fresh v3 rerun improves sensitivity.",
            },
            "ProbeTrace": {
                "status": "single_owner_anti_overfit_margin_import_complete",
                "owner_margin_gate_pass": probe["gate_pass"],
                "single_owner_claim_allowed": probe["formal_single_owner_claim_allowed"],
                "multi_owner_claim_allowed": probe["formal_multi_owner_claim_allowed"],
                "multi_owner_promotion_gate_pass": probe_multi["gate_pass"],
                "multi_owner_rerun_readiness_gate_pass": probe_readiness["gate_pass"],
                "near_boundary_rows": probe["near_boundary_rows"],
                "remaining_bestpaper_gap": "Multi-owner generalization still requires fresh score-vector live rerun; current claim must stay single-owner/source-bound.",
            },
            "SealAudit": {
                "status": "second_stage_executable_conjunction_support_ready_but_v5_claim_blocked",
                "support_import_gate_pass": seal_support["gate_pass"],
                "case_count": seal_support["case_count"],
                "subgate_pass_counts": seal_support["subgate_pass_counts"],
                "formal_v5_claim_allowed": seal_v5_guard["formal_v5_claim_allowed"],
                "v5_final_evidence_readiness_gate_pass": seal_readiness["gate_pass"],
                "v5_guard_blockers": seal_v5_guard["blockers"],
                "remaining_bestpaper_gap": "Fresh final row-level v5 evidence is still required before decisive coverage can be upgraded beyond 8.44%.",
            },
        },
        "new_real_closures_this_round": [
            "Imported js2 SemCodebook 43,200-row generation-changing ablation full eval and fixed positive-row detection in miss attribution.",
            "Imported js2 CodeDye 300-row positive-control result and built row-level v2 taxonomy.",
            "Imported js2 ProbeTrace owner-margin audit rows and promoted them only to single-owner anti-overfit support.",
            "Imported js2 SealAudit 320-case executable conjunction and added a support-only import gate plus v5 support-only guard.",
            "Added CodeDye v3 live-claim boundary/support-exclusion gates, support-row ledger, positive-control row hash manifest, and preserved-control bridge.",
            "Added fail-closed ProbeTrace multi-owner rerun schema readiness and hardened the multi-owner runner schema checks.",
            "Added fail-closed SealAudit v5 final-evidence readiness and hardened the v5 runner schema/coverage-risk checks.",
        ],
        "remaining_non_key_blockers": [
            "CodeDye cannot be written as high-recall detection; only null-audit is defensible unless v3 improves sensitivity under frozen thresholds.",
            "ProbeTrace broad multi-owner claim is still blocked by absence of comparable multi-owner score vectors.",
            "SealAudit v5 decisive-coverage upgrade is blocked by lack of final row-level v5 evidence; current second-stage artifact is support-only.",
        ],
        "claim_policy": "Do not delete weak results; report them as boundary evidence with CI and scoped claims.",
    }
    write("results/watermark_bestpaper_current_state_v2_20260507.json", payload)
    print("[OK] Wrote current best-paper state v2 report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
