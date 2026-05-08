from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/watermark_reviewer_reproducibility_manifest_v6_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def main() -> int:
    if not ARTIFACT.exists():
        fail("Reviewer manifest v6 is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "watermark_reviewer_reproducibility_manifest_v6":
        fail("Unexpected reviewer manifest v6 schema.")
    if payload.get("claim_bearing") is not False:
        fail("Reviewer manifest v6 must be non-claim-bearing.")
    if payload.get("gate_pass") is not True:
        fail("Reviewer manifest v6 has missing artifacts.")
    global_paths = {row["path"]: row for row in payload.get("global_artifacts", [])}
    for rel in (
        "results/provider_launch_readiness_gate_v2_20260507.json",
        "results/blackbox_fresh_run_preflight_contracts_v1_20260507.json",
        "results/blackbox_artifact_naming_consistency_v1_20260507.json",
        "results/watermark_strict_reviewer_audit_v4_20260507.json",
    ):
        if rel not in global_paths or global_paths[rel]["exists"] is not True:
            fail(f"Reviewer manifest v6 missing global artifact: {rel}")
    projects = payload.get("project_manifests", {})
    if set(projects) != {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}:
        fail("Reviewer manifest v6 project set is incomplete.")
    locks = payload.get("claim_locks", {})
    if set(locks) != set(projects):
        fail("Reviewer manifest v6 claim-lock set is incomplete.")
    if locks["SemCodebook"]["gate_pass"] is not True or locks["SemCodebook"]["bestpaper_ready"] is not True:
        fail("SemCodebook should remain locally best-paper-ready in v6.")
    for project in ("CodeDye", "ProbeTrace", "SealAudit"):
        lock = locks[project]
        if lock["gate_pass"] is not True:
            fail(f"{project} conservative claim lock should pass.")
        if lock["bestpaper_ready"] is not False:
            fail(f"{project} must not be marked best-paper-ready.")
        if lock["upgrade_claim_allowed"] is not False:
            fail(f"{project} upgrade claim must remain blocked.")
        if not lock.get("remaining_blockers"):
            fail(f"{project} remaining blockers must be explicit.")
    codedye = load(projects["CodeDye"])
    codedye_paths = {row["path"]: row for row in codedye["artifacts"]}
    if codedye_paths["results/CodeDye/artifacts/generated/codedye_v3_fresh_run_preflight_contract_v1_20260507.json"]["gate_pass"] is not True:
        fail("CodeDye fresh-run contract should pass.")
    probe = load(projects["ProbeTrace"])
    probe_paths = {row["path"]: row for row in probe["artifacts"]}
    if probe_paths["results/ProbeTrace/artifacts/generated/probetrace_multi_owner_fresh_run_preflight_contract_v1_20260507.json"]["gate_pass"] is not True:
        fail("ProbeTrace fresh-run contract should pass.")
    seal = load(projects["SealAudit"])
    seal_paths = {row["path"]: row for row in seal["artifacts"]}
    if seal_paths["results/SealAudit/artifacts/generated/sealaudit_v5_fresh_run_preflight_contract_v1_20260507.json"]["gate_pass"] is not True:
        fail("SealAudit fresh-run contract should pass.")
    if seal_paths["results/SealAudit/artifacts/generated/sealaudit_v5_evidence_classifier_v1_20260507.json"]["gate_pass"] is not False:
        fail("SealAudit v5 classifier should remain fail-closed.")
    print("[OK] Reviewer reproducibility manifest v6 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
