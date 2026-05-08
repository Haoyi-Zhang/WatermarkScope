from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"


PROJECT_ARTIFACTS: dict[str, list[str]] = {
    "SemCodebook": [
        "results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v1_20260507.json",
        "results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v1_20260507.md",
        "results/SemCodebook/artifacts/generated/semcodebook_whitebox_model_sufficiency_gate_20260505.json",
        "results/SemCodebook/artifacts/generated/semcodebook_whitebox_effect_authenticity_gate_20260505.json",
        "results/SemCodebook/artifacts/generated/semcodebook_causal_contribution_gate_v2_20260507.json",
        "results/SemCodebook/artifacts/generated/semcodebook_causal_contribution_table_v1_20260507.json",
    ],
    "CodeDye": [
        "results/CodeDye/artifacts/generated/codedye_final_claim_lock_v1_20260507.json",
        "results/CodeDye/artifacts/generated/codedye_final_claim_lock_v1_20260507.md",
        "results/CodeDye/artifacts/generated/codedye_live_traceability_manifest_v1_20260507.json",
        "results/CodeDye/artifacts/generated/codedye_v3_run_readiness_classifier_v1_20260507.json",
        "results/CodeDye/artifacts/generated/codedye_v3_fresh_run_preflight_contract_v1_20260507.json",
        "results/CodeDye/artifacts/generated/codedye_v3_postrun_promotion_gate_v1_20260507.json",
        "results/CodeDye/artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json",
        "results/CodeDye/artifacts/generated/codedye_positive_miss_taxonomy_v2_20260507.json",
        "results/CodeDye/artifacts/generated/codedye_negative_control_row_hash_manifest_v2_20260507.json",
        "results/CodeDye/ANONYMIZATION_AUDIT.json",
    ],
    "ProbeTrace": [
        "results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v1_20260507.json",
        "results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v1_20260507.md",
        "results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_scan_v1_20260507.json",
        "results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_row_receipts_v1_20260507.jsonl",
        "results/ProbeTrace/artifacts/generated/probetrace_latency_query_frontier_v1_20260507.json",
        "results/ProbeTrace/artifacts/generated/apis300_live_attribution_evidence.json",
        "results/ProbeTrace/artifacts/generated/probetrace_transfer_validation_integrity_gate_20260506.json",
        "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_package_20260507.json",
        "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_fresh_run_preflight_contract_v1_20260507.json",
        "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_postrun_promotion_gate_v1_20260507.json",
        "results/ProbeTrace/ANONYMIZATION_AUDIT.json",
    ],
    "SealAudit": [
        "results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v1_20260507.json",
        "results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v1_20260507.md",
        "results/SealAudit/artifacts/generated/sealaudit_needs_review_row_taxonomy_v2_20260507.jsonl",
        "results/SealAudit/artifacts/generated/sealaudit_abstention_burden_frontier_v1_20260507.json",
        "results/SealAudit/artifacts/generated/sealaudit_claim_wording_lock_v1_20260507.json",
        "results/SealAudit/artifacts/generated/sealaudit_claim_surface_frontier_join_audit_v1_20260507.json",
        "results/SealAudit/artifacts/generated/sealaudit_v5_fresh_run_preflight_contract_v1_20260507.json",
        "results/SealAudit/artifacts/generated/sealaudit_v5_postrun_promotion_gate_v1_20260507.json",
        "results/SealAudit/artifacts/generated/sealaudit_v5_evidence_classifier_v1_20260507.json",
        "results/SealAudit/artifacts/generated/canonical_claim_surface_results.json",
        "results/SealAudit/artifacts/generated/sealaudit_coverage_risk_frontier_gate_20260505.json",
        "results/SealAudit/ANONYMIZATION_AUDIT.json",
    ],
}


CLAIM_LOCKS = {
    "SemCodebook": "results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v1_20260507.json",
    "CodeDye": "results/CodeDye/artifacts/generated/codedye_final_claim_lock_v1_20260507.json",
    "ProbeTrace": "results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v1_20260507.json",
    "SealAudit": "results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v1_20260507.json",
}


GLOBAL_ARTIFACTS = [
    "results/provider_launch_readiness_gate_v1_20260507.json",
    "results/provider_launch_readiness_gate_v2_20260507.json",
    "results/blackbox_fresh_run_preflight_contracts_v1_20260507.json",
    "results/blackbox_artifact_naming_consistency_v1_20260507.json",
    "results/watermark_strict_reviewer_audit_v4_20260507.json",
    "results/watermark_strict_reviewer_audit_v4_20260507.md",
    "CLAIM_BOUNDARIES.md",
    "RESULT_MANIFEST.jsonl",
    "PRESERVED_RESULT_MANIFEST.jsonl",
]


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


def artifact_row(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    exists = path.exists()
    payload = load_json_if_possible(path) if exists else {}
    return {
        "path": rel,
        "exists": exists,
        "bytes": path.stat().st_size if exists else None,
        "sha256": sha256(path) if exists else None,
        "schema_version": payload.get("schema_version"),
        "claim_bearing": payload.get("claim_bearing"),
        "gate_pass": payload.get("gate_pass"),
        "blocked": payload.get("blocked"),
        "blockers": payload.get("blockers"),
    }


def write_json(rel: str, payload: dict[str, Any]) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def claim_lock_summary(project: str, rel: str) -> dict[str, Any]:
    payload = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    bestpaper_ready = payload.get("bestpaper_ready")
    if bestpaper_ready is None:
        bestpaper_ready = payload.get("formal_bestpaper_local_semcodebook_ready")
    upgrade_claim_allowed = payload.get("upgrade_claim_allowed")
    if upgrade_claim_allowed is None:
        upgrade_claim_allowed = payload.get("formal_scoped_whitebox_claim_allowed")
    return {
        "project": project,
        "path": rel,
        "schema_version": payload.get("schema_version"),
        "gate_pass": payload.get("gate_pass"),
        "bestpaper_ready": bestpaper_ready,
        "allowed_current_claim": payload.get("allowed_current_claim", payload.get("main_claim_allowed")),
        "upgrade_claim_allowed": upgrade_claim_allowed,
        "forbidden_claims": payload.get("forbidden_claims", []),
        "remaining_blockers": payload.get("remaining_blockers", payload.get("blockers", [])),
    }


def main() -> int:
    missing: list[str] = []
    project_manifests: dict[str, str] = {}
    claim_locks: dict[str, dict[str, Any]] = {}
    for project, artifacts in PROJECT_ARTIFACTS.items():
        rows = [artifact_row(path) for path in artifacts]
        missing.extend(item["path"] for item in rows if not item["exists"])
        claim_locks[project] = claim_lock_summary(project, CLAIM_LOCKS[project])
        rel = f"results/{project}/REPRODUCIBILITY_MANIFEST_v6_{DATE}.json"
        write_json(
            rel,
            {
                "schema_version": f"{project.lower()}_reviewer_reproducibility_manifest_v6",
                "generated_at_utc": utc_now(),
                "claim_bearing": False,
                "project": project,
                "artifact_count": len(rows),
                "missing_artifacts": [item["path"] for item in rows if not item["exists"]],
                "claim_lock": claim_locks[project],
                "artifacts": rows,
                "boundary": "Additive v6 reviewer index with fresh-run contracts and provider readiness v2.",
            },
        )
        project_manifests[project] = rel

    global_rows = [artifact_row(path) for path in GLOBAL_ARTIFACTS]
    missing.extend(item["path"] for item in global_rows if not item["exists"])
    payload = {
        "schema_version": "watermark_reviewer_reproducibility_manifest_v6",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": not missing,
        "manifest_role": "reviewer_entrypoint_after_fresh_run_contract_and_provider_readiness_hardening",
        "project_manifests": project_manifests,
        "claim_locks": claim_locks,
        "global_artifacts": global_rows,
        "missing_artifacts": missing,
        "full_experiment_policy": (
            "SemCodebook remains locally ready. Black-box projects have executable fresh-run contracts, "
            "but claim upgrades still require fresh provider outputs and postrun promotion gates."
        ),
    }
    write_json(f"results/watermark_reviewer_reproducibility_manifest_v6_{DATE}.json", payload)
    print("[OK] Wrote additive reviewer reproducibility manifests v6.")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
