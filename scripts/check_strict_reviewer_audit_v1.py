from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
AUDIT = ROOT / f"results/watermark_strict_reviewer_audit_v1_{DATE}.json"
AUDIT_MD = ROOT / f"results/watermark_strict_reviewer_audit_v1_{DATE}.md"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not AUDIT.exists():
        fail(f"Missing audit artifact: {AUDIT.relative_to(ROOT)}")
    if not AUDIT_MD.exists():
        fail(f"Missing markdown audit artifact: {AUDIT_MD.relative_to(ROOT)}")
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "watermark_strict_reviewer_audit_v1":
        fail("Unexpected strict reviewer audit schema.")
    if payload.get("claim_bearing") is not False:
        fail("Strict reviewer audit must be non-claim-bearing.")
    if payload.get("portfolio_bestpaper_ready") is not False:
        fail("Portfolio must not be marked best-paper-ready while P1/P2 remain.")
    if payload.get("formal_full_experiment_allowed") is not False:
        fail("Strict audit must not allow full formal experiments.")
    projects = {project["project"]: project for project in payload.get("projects", [])}
    expected_projects = {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}
    if set(projects) != expected_projects:
        fail(f"Unexpected project set: {sorted(projects)}")

    sem = projects["SemCodebook"]
    if sem["effect_metrics"]["admitted_records"] != 72000:
        fail("SemCodebook admitted record count drifted.")
    if sem["effect_metrics"]["admitted_models"] < 9 or sem["effect_metrics"]["admitted_families"] < 5:
        fail("SemCodebook family/model sufficiency is too weak.")
    if sem["effect_metrics"]["negative_control_hits"]["k"] != 0 or sem["effect_metrics"]["negative_control_hits"]["n"] != 48000:
        fail("SemCodebook negative-control surface drifted.")
    if "first-sample/no-retry natural-generation guarantee" not in sem["forbidden_claims"]:
        fail("SemCodebook no-retry overclaim boundary missing.")

    code = projects["CodeDye"]
    if code["effect_metrics"]["live_signal"]["k"] != 6 or code["effect_metrics"]["live_signal"]["n"] != 300:
        fail("CodeDye live signal boundary drifted.")
    if code["effect_metrics"]["positive_control_sensitivity"]["k"] != 170:
        fail("CodeDye positive-control sensitivity drifted.")
    if code["effect_metrics"]["negative_control_false_positive"]["k"] != 0:
        fail("CodeDye negative-control false positive drifted.")
    if not any("Effect is weak" in item for item in code["remaining_p1"]):
        fail("CodeDye weak-effect P1 must remain explicit.")

    probe = projects["ProbeTrace"]
    if probe["effect_metrics"]["apis_attribution"]["k"] != 300:
        fail("ProbeTrace APIS metric drifted.")
    if probe["effect_metrics"]["multi_owner_input_rows"] != 6000:
        fail("ProbeTrace multi-owner input package is missing or wrong.")
    if probe["effect_metrics"]["multi_owner_formal_claim_allowed"] is not False:
        fail("ProbeTrace multi-owner claim must remain blocked without provider outputs.")
    if not any("multi-owner" in item.lower() for item in probe["remaining_p1"]):
        fail("ProbeTrace multi-owner P1 must remain explicit.")

    seal = projects["SealAudit"]
    if seal["effect_metrics"]["marker_hidden_decisive_coverage"]["k"] != 81:
        fail("SealAudit decisive coverage drifted.")
    if seal["effect_metrics"]["needs_review_rate"]["k"] != 879:
        fail("SealAudit needs-review count drifted.")
    if seal["effect_metrics"]["unsafe_pass"]["k"] != 0:
        fail("SealAudit unsafe-pass count drifted.")
    if "security certificate" not in seal["forbidden_claims"]:
        fail("SealAudit security-certificate boundary missing.")

    p1_count = sum(len(project["remaining_p1"]) for project in projects.values())
    p2_count = sum(len(project["remaining_p2"]) for project in projects.values())
    if payload["remaining_p1_count"] != p1_count or payload["remaining_p2_count"] != p2_count:
        fail("Portfolio P1/P2 totals do not match project lists.")

    print("[OK] Strict reviewer audit verified.")
    print(f"[OK] Projects: {', '.join(sorted(projects))}")
    print(f"[OK] Remaining P1={p1_count}, P2={p2_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
