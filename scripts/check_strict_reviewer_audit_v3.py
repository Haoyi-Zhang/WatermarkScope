from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
AUDIT = ROOT / f"results/watermark_strict_reviewer_audit_v3_{DATE}.json"
AUDIT_MD = ROOT / f"results/watermark_strict_reviewer_audit_v3_{DATE}.md"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not AUDIT.exists() or not AUDIT_MD.exists():
        fail("Strict reviewer audit v3 artifacts are missing.")
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "watermark_strict_reviewer_audit_v3":
        fail("Unexpected audit v3 schema.")
    if payload.get("claim_bearing") is not False:
        fail("Audit v3 must be non-claim-bearing.")
    if payload.get("portfolio_bestpaper_ready") is not False:
        fail("Portfolio must not be marked best-paper-ready while P1/P2 remain.")
    projects = {project["project"]: project for project in payload.get("projects", [])}
    if set(projects) != {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}:
        fail(f"Unexpected project set: {sorted(projects)}")

    sem = projects["SemCodebook"]
    if sem["remaining_p1"]:
        fail("SemCodebook local P1 should be closed in audit v3.")
    if sem["effect_metrics"]["row_level_miss_taxonomy_gate_pass"] is not True:
        fail("SemCodebook row-level miss taxonomy gate did not pass.")
    if sem["effect_metrics"]["row_level_positive_misses"] != 10210:
        fail("SemCodebook row-level miss count drifted.")
    if sem["remaining_p2"]:
        fail("SemCodebook P2 should be closed by final claim-lock in audit v3.")
    if sem["bestpaper_ready"] is not True:
        fail("SemCodebook should be locally best-paper-ready in audit v3.")
    if sem["effect_metrics"]["final_claim_lock_gate_pass"] is not True:
        fail("SemCodebook final claim-lock gate did not pass in audit v3.")
    if sem["effect_metrics"]["mandatory_component_delta_rows"] < 8:
        fail("SemCodebook component delta table is not locked in audit v3.")

    code = projects["CodeDye"]
    if code["effect_metrics"]["positive_control_misses"] != 130:
        fail("CodeDye positive-control miss taxonomy drifted.")
    if code["effect_metrics"]["positive_miss_bucket_counts"].get("witness_ablation_did_not_collapse") != 130:
        fail("CodeDye miss bucket taxonomy drifted.")
    if len(code["remaining_p1"]) != 2:
        fail("CodeDye should retain two effect-related P1 blockers.")

    probe = projects["ProbeTrace"]
    if probe["effect_metrics"]["multi_owner_input_rows"] != 6000:
        fail("ProbeTrace multi-owner input package drifted.")
    if probe["effect_metrics"]["multi_owner_formal_claim_allowed"] is not False:
        fail("ProbeTrace multi-owner claim must remain blocked.")
    if len(probe["remaining_p1"]) != 2:
        fail("ProbeTrace should retain two multi-owner/leakage P1 blockers.")

    seal = projects["SealAudit"]
    if seal["effect_metrics"]["marker_hidden_decisive_coverage"]["k"] != 81:
        fail("SealAudit decisive coverage drifted.")
    if seal["effect_metrics"]["v5_final_evidence_ready"] is not False:
        fail("SealAudit v5 final evidence must remain blocked until final rows exist.")
    if len(seal["remaining_p1"]) != 2:
        fail("SealAudit should retain two coverage/v5 P1 blockers.")

    p1_count = sum(len(project["remaining_p1"]) for project in projects.values())
    p2_count = sum(len(project["remaining_p2"]) for project in projects.values())
    if payload["remaining_p1_count"] != p1_count or payload["remaining_p2_count"] != p2_count:
        fail("Audit v3 P1/P2 totals do not match project lists.")
    if p1_count != 6:
        fail(f"Expected 6 remaining P1 blockers after local closures, got {p1_count}.")

    if p2_count != 3:
        fail(f"Expected 3 remaining P2 blockers after SemCodebook claim-lock, got {p2_count}.")

    print("[OK] Strict reviewer audit v3 verified.")
    print(f"[OK] Remaining P1={p1_count}, P2={p2_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
