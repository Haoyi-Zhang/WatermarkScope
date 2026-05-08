from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/watermark_strict_reviewer_audit_v7_{DATE}.json"
ARTIFACT_MD = ROOT / f"results/watermark_strict_reviewer_audit_v7_{DATE}.md"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists() or not ARTIFACT_MD.exists():
        fail("Strict reviewer audit v7 artifacts are missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "watermark_strict_reviewer_audit_v7":
        fail("Unexpected strict reviewer audit v7 schema.")
    projects = {project["project"]: project for project in payload.get("projects", [])}
    if set(projects) != {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}:
        fail("Strict audit v7 project set is incomplete.")
    for project in ("SemCodebook", "CodeDye", "SealAudit"):
        if projects[project]["bestpaper_ready"] is not True:
            fail(f"{project} should be ready for its scoped claim.")
        if projects[project]["remaining_p1"] or projects[project]["remaining_p2"]:
            fail(f"{project} should not retain P1/P2 blockers.")
    if projects["CodeDye"]["effect_metrics"]["claim_rows"] != 300:
        fail("CodeDye v7 should bind 300 claim rows.")
    if projects["CodeDye"]["effect_metrics"]["final_signal"] != 4:
        fail("CodeDye v7 sparse signal should remain 4/300.")
    if projects["CodeDye"]["effect_metrics"]["utility_topup_policy"]["contamination_score_used_for_selection"] is not False:
        fail("CodeDye top-up must remain utility-only.")
    if len(projects["ProbeTrace"]["remaining_p1"]) != 1:
        fail("ProbeTrace should retain one P1 blocker until multi-owner run completes.")
    if payload["remaining_p1_count"] != 1 or payload["remaining_p2_count"] != 0:
        fail("Strict audit v7 totals should be P1=1, P2=0.")
    print("[OK] Strict reviewer audit v7 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
