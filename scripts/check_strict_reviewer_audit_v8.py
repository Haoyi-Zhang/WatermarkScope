from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/watermark_strict_reviewer_audit_v8_{DATE}.json"
ARTIFACT_MD = ROOT / f"results/watermark_strict_reviewer_audit_v8_{DATE}.md"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists() or not ARTIFACT_MD.exists():
        fail("Strict reviewer audit v8 artifacts are missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "watermark_strict_reviewer_audit_v8":
        fail("Unexpected strict reviewer audit v8 schema.")
    if payload.get("claim_bearing") is not False:
        fail("Strict reviewer audit v8 must be non-claim-bearing.")
    projects = {project["project"]: project for project in payload.get("projects", [])}
    if set(projects) != {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}:
        fail("Strict audit v8 project set is incomplete.")
    if payload.get("remaining_p1_count") != 0 or payload.get("remaining_p2_count") != 0:
        fail("Strict audit v8 should close all P1/P2 blockers.")
    if payload.get("portfolio_bestpaper_ready") is not True:
        fail("Strict audit v8 should mark the locked scoped portfolio ready.")
    if payload.get("portfolio_verdict") != "bestpaper_ready_by_strict_artifact_gate":
        fail("Strict audit v8 portfolio verdict drifted.")
    if payload.get("formal_full_experiment_allowed") is not True:
        fail("Strict audit v8 should allow only locked scoped full experiments.")
    for name, project in projects.items():
        if project.get("bestpaper_ready") is not True:
            fail(f"{name} should be ready for its locked scoped claim.")
        if project.get("remaining_p1") or project.get("remaining_p2"):
            fail(f"{name} should have no P1/P2 blockers.")
        if float(project.get("mean_score", 0)) < 4.5:
            fail(f"{name} strict score is below best-paper gate.")
    probe = projects["ProbeTrace"]
    metrics = probe["effect_metrics"]
    if metrics["multi_owner_row_count"] != 6000:
        fail("ProbeTrace v8 must bind 6000 multi-owner live rows.")
    if metrics["multi_owner_owner_count"] < 5 or metrics["multi_owner_language_count"] < 3:
        fail("ProbeTrace v8 owner/language breadth insufficient.")
    if metrics["multi_owner_control_to_positive_ratio"] < 4:
        fail("ProbeTrace v8 control ratio insufficient.")
    if metrics["multi_owner_missing_hash_rows"] != 0 or metrics["multi_owner_schema_missing_rows"] != 0:
        fail("ProbeTrace v8 hash/schema integrity must be clean.")
    if metrics["multi_owner_margin_auc"] is None:
        fail("ProbeTrace v8 must include margin AUC.")
    codedye = projects["CodeDye"]
    if codedye["effect_metrics"]["claim_rows"] != 300 or codedye["effect_metrics"]["final_signal"] != 4:
        fail("CodeDye v8 sparse null-audit surface drifted.")
    seal = projects["SealAudit"]
    if seal["effect_metrics"]["marker_hidden_claim_rows"] != 960 or seal["effect_metrics"]["unsafe_pass"]["k"] != 0:
        fail("SealAudit v8 surface drifted.")
    sem = projects["SemCodebook"]
    if sem["effect_metrics"]["admitted_records"] != 72000 or sem["effect_metrics"]["negative_control_hits"]["k"] != 0:
        fail("SemCodebook v8 surface drifted.")
    print("[OK] Strict reviewer audit v8 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
