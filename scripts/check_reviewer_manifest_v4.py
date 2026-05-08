from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/watermark_reviewer_reproducibility_manifest_v4_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def main() -> int:
    if not ARTIFACT.exists():
        fail("Reviewer reproducibility manifest v4 is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "watermark_reviewer_reproducibility_manifest_v4":
        fail("Unexpected reviewer manifest v4 schema.")
    if payload.get("claim_bearing") is not False:
        fail("Reviewer manifest v4 must be non-claim-bearing.")
    if payload.get("gate_pass") is not True:
        fail("Reviewer manifest v4 has missing artifacts.")
    projects = payload.get("project_manifests", {})
    if set(projects) != {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}:
        fail("Reviewer manifest v4 project set is incomplete.")
    for project, rel in projects.items():
        manifest = load_json(rel)
        if manifest.get("claim_bearing") is not False:
            fail(f"{project} manifest v4 must be non-claim-bearing.")
        if manifest.get("missing_artifacts"):
            fail(f"{project} manifest v4 has missing artifacts.")
    sem = load_json(projects["SemCodebook"])
    sem_paths = {row["path"]: row for row in sem["artifacts"]}
    claim_lock = sem_paths["results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v1_20260507.json"]
    if claim_lock["gate_pass"] is not True:
        fail("SemCodebook final claim-lock must pass in reviewer manifest v4.")

    global_paths = {row["path"] for row in payload["global_artifacts"]}
    required_global = {
        "results/provider_launch_readiness_gate_v1_20260507.json",
        "results/watermark_strict_reviewer_audit_v2_20260507.json",
        "results/watermark_strict_reviewer_audit_v3_20260507.json",
        "CLAIM_BOUNDARIES.md",
        "RESULT_MANIFEST.jsonl",
    }
    if not required_global.issubset(global_paths):
        fail("Reviewer manifest v4 is missing required global boundary artifacts.")

    codedye = load_json(projects["CodeDye"])
    code_paths = {row["path"]: row for row in codedye["artifacts"]}
    if code_paths["results/CodeDye/artifacts/generated/codedye_v3_run_readiness_classifier_v1_20260507.json"]["gate_pass"] is not True:
        fail("CodeDye v3 readiness should remain rerun-ready.")
    if code_paths["results/CodeDye/artifacts/generated/codedye_v3_run_readiness_classifier_v1_20260507.json"]["formal_v3_live_claim_allowed"] is not False:
        fail("CodeDye v3 manifest must not promote v3 live claim.")
    postrun = code_paths["results/CodeDye/artifacts/generated/codedye_v3_postrun_promotion_gate_v1_20260507.json"]
    if postrun["gate_pass"] is not False or postrun["formal_v3_live_claim_allowed"] is not False:
        fail("CodeDye v3 postrun manifest row must remain fail-closed until fresh live output exists.")

    probe = load_json(projects["ProbeTrace"])
    probe_paths = {row["path"]: row for row in probe["artifacts"]}
    classifier = probe_paths["results/ProbeTrace/artifacts/generated/probetrace_multi_owner_evidence_classifier_v1_20260507.json"]
    if classifier["gate_pass"] is not False or classifier["formal_multi_owner_claim_allowed"] is not False:
        fail("ProbeTrace multi-owner classifier must remain fail-closed.")
    probe_postrun = probe_paths["results/ProbeTrace/artifacts/generated/probetrace_multi_owner_postrun_promotion_gate_v1_20260507.json"]
    if probe_postrun["gate_pass"] is not False or probe_postrun["formal_multi_owner_claim_allowed"] is not False:
        fail("ProbeTrace multi-owner postrun gate must remain fail-closed until fresh live output exists.")

    seal = load_json(projects["SealAudit"])
    seal_paths = {row["path"]: row for row in seal["artifacts"]}
    v5 = seal_paths["results/SealAudit/artifacts/generated/sealaudit_v5_evidence_classifier_v1_20260507.json"]
    if v5["gate_pass"] is not False or v5["formal_v5_claim_allowed"] is not False:
        fail("SealAudit v5 classifier must remain fail-closed.")
    seal_postrun = seal_paths["results/SealAudit/artifacts/generated/sealaudit_v5_postrun_promotion_gate_v1_20260507.json"]
    if seal_postrun["gate_pass"] is not False or seal_postrun["formal_v5_claim_allowed"] is not False:
        fail("SealAudit v5 postrun gate must remain fail-closed until final v5 evidence exists.")

    print("[OK] Reviewer reproducibility manifest v4 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
