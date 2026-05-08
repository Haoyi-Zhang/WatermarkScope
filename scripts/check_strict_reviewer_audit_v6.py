from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/watermark_strict_reviewer_audit_v6_{DATE}.json"
ARTIFACT_MD = ROOT / f"results/watermark_strict_reviewer_audit_v6_{DATE}.md"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists() or not ARTIFACT_MD.exists():
        fail("Strict reviewer audit v6 artifacts are missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "watermark_strict_reviewer_audit_v6":
        fail("Unexpected strict reviewer audit v6 schema.")
    if payload.get("claim_bearing") is not False:
        fail("Strict reviewer audit v6 must be non-claim-bearing.")
    projects = {project["project"]: project for project in payload.get("projects", [])}
    if set(projects) != {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}:
        fail("Strict audit v6 project set is incomplete.")
    if projects["SemCodebook"]["bestpaper_ready"] is not True:
        fail("SemCodebook should remain ready.")
    if projects["SealAudit"]["bestpaper_ready"] is not True:
        fail("SealAudit v2 should be ready for its scoped claim.")
    if projects["SealAudit"]["remaining_p1"] or projects["SealAudit"]["remaining_p2"]:
        fail("SealAudit v2 should not retain P1/P2 blockers.")
    if projects["SealAudit"]["effect_metrics"]["formal_v5_claim_allowed"] is not True:
        fail("SealAudit v2 formal scoped claim should be allowed.")
    if projects["SealAudit"]["effect_metrics"]["unsafe_pass"]["k"] != 0:
        fail("SealAudit v2 unsafe-pass count must be zero.")
    if len(projects["CodeDye"]["remaining_p1"]) != 2:
        fail("CodeDye should retain two P1 blockers until repaired postrun passes.")
    if len(projects["ProbeTrace"]["remaining_p1"]) != 1:
        fail("ProbeTrace should retain one P1 blocker until multi-owner run completes.")
    if payload["remaining_p1_count"] != 3 or payload["remaining_p2_count"] != 0:
        fail("Strict audit v6 totals should be P1=3, P2=0 after SealAudit closure.")
    print("[OK] Strict reviewer audit v6 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
