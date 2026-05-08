from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"


PROJECT_ARTIFACTS: dict[str, list[str]] = {
    "CodeDye": [
        "results/CodeDye/artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json",
        "results/CodeDye/artifacts/generated/codedye_positive_contamination_control_300_gate_20260505.json",
        "results/CodeDye/artifacts/generated/codedye_negative_control_300plus_gate_20260505.json",
        "results/CodeDye/artifacts/generated/codedye_positive_miss_taxonomy_v2_20260507.json",
        "results/CodeDye/artifacts/generated/codedye_v3_protocol_freeze_gate_20260507.json",
        "results/CodeDye/artifacts/generated/codedye_v3_positive_negative_control_gate_20260507.json",
        "results/CodeDye/artifacts/generated/codedye_v3_live_claim_boundary_gate_20260507.json",
        "results/CodeDye/artifacts/generated/codedye_v3_support_exclusion_gate_20260507.json",
        "results/CodeDye/artifacts/generated/codedye_support_exclusion_row_ledger_gate_20260507.json",
        "results/CodeDye/artifacts/generated/codedye_positive_control_row_hash_manifest_20260507.json",
        "results/CodeDye/artifacts/generated/codedye_negative_control_row_source_manifest_20260507.json",
        "results/CodeDye/artifacts/generated/null_calibration_negative_controls_300_20260505_remote.json",
        "results/CodeDye/artifacts/generated/codedye_negative_control_row_hash_manifest_v2_20260507.json",
        "results/CodeDye/artifacts/generated/codedye_v3_reused_control_bridge_20260507.json",
        "results/CodeDye/artifacts/generated/statistics_repro_gate.json",
    ],
    "ProbeTrace": [
        "results/ProbeTrace/artifacts/generated/apis300_live_attribution_evidence.json",
        "results/ProbeTrace/artifacts/generated/probetrace_abstain_aware_attribution_gate_20260506.json",
        "results/ProbeTrace/artifacts/generated/probetrace_owner_margin_import_gate_v1_20260507.json",
        "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_promotion_gate_20260507.json",
        "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_rerun_readiness_gate_20260507.json",
        "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_package_20260507.json",
        "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_prerun_gate_20260507.json",
        "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_promotion_gate_probetrace_multi_owner_strict_smoke_20260507.json",
        "results/ProbeTrace/artifacts/generated/probetrace_transfer_row_binding_manifest_gate_20260505.json",
    ],
    "SealAudit": [
        "results/SealAudit/artifacts/generated/canonical_claim_surface_results.json",
        "results/SealAudit/artifacts/generated/sealaudit_coverage_risk_frontier_gate_20260505.json",
        "results/SealAudit/artifacts/generated/sealaudit_second_stage_support_import_gate_v1_20260507.json",
        "results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_remote_support_guard_20260507.json",
        "results/SealAudit/artifacts/generated/sealaudit_v5_final_evidence_readiness_gate_20260507.json",
        "results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_results_strict_smoke_20260507.json",
        "results/SealAudit/artifacts/generated/sealaudit_expert_review_role_support_gate_v1_20260507.json",
    ],
    "SemCodebook": [
        "results/SemCodebook/artifacts/generated/semcodebook_whitebox_main_denominator_source_manifest_20260505.json",
        "results/SemCodebook/artifacts/generated/semcodebook_whitebox_model_sufficiency_gate_20260505.json",
        "results/SemCodebook/artifacts/generated/semcodebook_whitebox_effect_authenticity_gate_20260505.json",
        "results/SemCodebook/artifacts/generated/semcodebook_row_level_miss_attribution_v3_20260507.json",
        "results/SemCodebook/artifacts/generated/semcodebook_causal_contribution_table_v1_20260507.json",
        "results/SemCodebook/artifacts/generated/semcodebook_causal_contribution_gate_v2_20260507.json",
        "results/SemCodebook/artifacts/generated/semcodebook_structural_recoverability_theorem_v1_20260507.md",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json_if_possible(path: Path) -> dict[str, Any]:
    if path.suffix.lower() != ".json":
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def manifest_row(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    payload = load_json_if_possible(path)
    return {
        "path": rel,
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else None,
        "sha256": sha256(path) if path.exists() else None,
        "schema_version": payload.get("schema_version"),
        "claim_bearing": payload.get("claim_bearing"),
        "gate_pass": payload.get("gate_pass"),
        "formal_claim_allowed": (
            payload.get("formal_v3_live_claim_allowed")
            if "formal_v3_live_claim_allowed" in payload
            else payload.get("formal_multi_owner_claim_allowed")
            if "formal_multi_owner_claim_allowed" in payload
            else payload.get("formal_v5_claim_allowed")
            if "formal_v5_claim_allowed" in payload
            else payload.get("formal_causal_claim_allowed")
        ),
        "blockers": payload.get("blockers"),
    }


def write_json(rel: str, payload: Any) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    portfolio: dict[str, Any] = {
        "schema_version": "reviewer_reproducibility_manifest_v3",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "manifest_role": "additive_reviewer_visible_index_not_replacing_locked_v1_or_v2_manifests",
        "project_manifests": {},
    }
    missing: list[str] = []
    for project, artifacts in sorted(PROJECT_ARTIFACTS.items()):
        rows = [manifest_row(rel) for rel in artifacts]
        missing.extend(row["path"] for row in rows if not row["exists"])
        manifest = {
            "schema_version": f"{project.lower()}_reviewer_reproducibility_manifest_v3",
            "generated_at_utc": utc_now(),
            "claim_bearing": False,
            "project": project,
            "artifact_count": len(rows),
            "missing_artifacts": [row["path"] for row in rows if not row["exists"]],
            "artifacts": rows,
            "boundary": "Additive reviewer manifest. Locked original result artifacts and v1 manifests are not overwritten.",
        }
        rel = f"results/{project}/REPRODUCIBILITY_MANIFEST_v3_{DATE}.json"
        write_json(rel, manifest)
        portfolio["project_manifests"][project] = rel
    portfolio["missing_artifacts"] = missing
    portfolio["gate_pass"] = not missing
    write_json(f"results/watermark_reviewer_reproducibility_manifest_v3_{DATE}.json", portfolio)
    print("[OK] Wrote additive reviewer reproducibility manifests.")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
