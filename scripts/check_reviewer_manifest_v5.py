from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/watermark_reviewer_reproducibility_manifest_v5_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def main() -> int:
    if not ARTIFACT.exists():
        fail("Reviewer manifest v5 is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "watermark_reviewer_reproducibility_manifest_v5":
        fail("Unexpected reviewer manifest v5 schema.")
    if payload.get("claim_bearing") is not False:
        fail("Reviewer manifest v5 must be non-claim-bearing.")
    if payload.get("gate_pass") is not True:
        fail("Reviewer manifest v5 has missing artifacts.")
    global_paths = {row["path"]: row for row in payload.get("global_artifacts", [])}
    for rel in (
        "results/watermark_strict_reviewer_audit_v4_20260507.json",
        "results/watermark_strict_reviewer_audit_v4_20260507.md",
    ):
        if rel not in global_paths or global_paths[rel]["exists"] is not True:
            fail(f"Reviewer manifest v5 missing strict audit v4 artifact: {rel}")
    projects = payload.get("project_manifests", {})
    if set(projects) != {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}:
        fail("Reviewer manifest v5 project set is incomplete.")
    locks = payload.get("claim_locks", {})
    if set(locks) != set(projects):
        fail("Reviewer manifest v5 claim-lock set is incomplete.")
    if locks["SemCodebook"]["gate_pass"] is not True or locks["SemCodebook"]["bestpaper_ready"] is not True:
        fail("SemCodebook should remain locally best-paper-ready in v5.")
    for project in ("CodeDye", "ProbeTrace", "SealAudit"):
        lock = locks[project]
        if lock["gate_pass"] is not True:
            fail(f"{project} current conservative claim lock should pass.")
        if lock["bestpaper_ready"] is not False:
            fail(f"{project} must not be marked best-paper-ready.")
        if lock["upgrade_claim_allowed"] is not False:
            fail(f"{project} upgrade claim must remain blocked.")
        if not lock.get("remaining_blockers"):
            fail(f"{project} remaining blockers must be explicit.")
    for project, rel in projects.items():
        manifest = load(rel)
        if manifest.get("claim_bearing") is not False:
            fail(f"{project} v5 project manifest must be non-claim-bearing.")
        if manifest.get("missing_artifacts"):
            fail(f"{project} v5 project manifest has missing artifacts.")
    codedye = load(projects["CodeDye"])
    paths = {row["path"]: row for row in codedye["artifacts"]}
    trace = paths["results/CodeDye/artifacts/generated/codedye_live_traceability_manifest_v1_20260507.json"]
    if trace["gate_pass"] is not True:
        fail("CodeDye traceability manifest should pass.")
    probe = load(projects["ProbeTrace"])
    paths = {row["path"]: row for row in probe["artifacts"]}
    if paths["results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_scan_v1_20260507.json"]["gate_pass"] is not True:
        fail("ProbeTrace anti-leakage scan should pass.")
    seal = load(projects["SealAudit"])
    paths = {row["path"]: row for row in seal["artifacts"]}
    if paths["results/SealAudit/artifacts/generated/sealaudit_abstention_burden_frontier_v1_20260507.json"]["gate_pass"] is not True:
        fail("SealAudit abstention burden artifact should pass.")
    print("[OK] Reviewer reproducibility manifest v5 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
