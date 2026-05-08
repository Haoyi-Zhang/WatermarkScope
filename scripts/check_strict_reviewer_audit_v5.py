from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/watermark_strict_reviewer_audit_v5_{DATE}.json"
ARTIFACT_MD = ROOT / f"results/watermark_strict_reviewer_audit_v5_{DATE}.md"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists() or not ARTIFACT_MD.exists():
        fail("Strict reviewer audit v5 artifacts are missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "watermark_strict_reviewer_audit_v5":
        fail("Unexpected strict reviewer audit v5 schema.")
    if payload.get("claim_bearing") is not False:
        fail("Strict reviewer audit v5 must be non-claim-bearing.")
    if payload.get("portfolio_bestpaper_ready") is not False:
        fail("Portfolio must remain not best-paper-ready while P1 blockers remain.")
    if payload.get("fresh_run_contracts_gate_pass") is not True:
        fail("Fresh-run contract/naming gates should pass in strict audit v5.")
    projects = {project["project"]: project for project in payload.get("projects", [])}
    if set(projects) != {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}:
        fail("Strict audit v5 project set is incomplete.")
    if projects["SemCodebook"]["bestpaper_ready"] is not True:
        fail("SemCodebook should remain locally best-paper-ready.")
    for project in ("CodeDye", "ProbeTrace", "SealAudit"):
        if projects[project]["bestpaper_ready"] is not False:
            fail(f"{project} must not be marked best-paper-ready.")
        if projects[project]["remaining_p2"]:
            fail(f"{project} should have local P2s closed in v5.")
        if projects[project]["effect_metrics"].get("fresh_run_contract_gate_pass") is not True:
            fail(f"{project} should have a passing fresh-run contract.")
    if len(projects["CodeDye"]["remaining_p1"]) != 2:
        fail("CodeDye should retain two P1 blockers.")
    if len(projects["ProbeTrace"]["remaining_p1"]) != 1:
        fail("ProbeTrace should retain one multi-owner P1 blocker.")
    if len(projects["SealAudit"]["remaining_p1"]) != 2:
        fail("SealAudit should retain two v5/coverage P1 blockers.")
    if payload["remaining_p1_count"] != 5 or payload["remaining_p2_count"] != 0:
        fail("Strict audit v5 totals should be P1=5, P2=0.")
    if payload["formal_full_experiment_allowed"] is not False:
        fail("Strict audit v5 must not allow full black-box experiments.")
    print("[OK] Strict reviewer audit v5 verified.")
    print("[OK] Remaining P1=5, P2=0; fresh-run contracts pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
