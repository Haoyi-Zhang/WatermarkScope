from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
SCORECARD = ROOT / f"results/bestpaper_review_scorecard_v1_{DATE}.json"

REQUIRED_PROJECTS = {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}

REQUIRED_ARTIFACTS = [
    "results/SemCodebook/artifacts/generated/semcodebook_failure_taxonomy_v1_20260507.json",
    "results/SemCodebook/artifacts/generated/semcodebook_causal_contribution_gate_v1_20260507.json",
    "results/SemCodebook/artifacts/generated/semcodebook_structural_recoverability_theorem_v1_20260507.md",
    "results/CodeDye/artifacts/generated/codedye_positive_miss_taxonomy_v1_20260507.json",
    "results/CodeDye/artifacts/generated/codedye_v3_protocol_freeze_gate_20260507.json",
    "results/CodeDye/artifacts/generated/codedye_null_audit_utility_framework_v1_20260507.json",
    "results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_gate_v1_20260507.json",
    "results/ProbeTrace/artifacts/generated/probetrace_owner_margin_distribution_v1_20260507.json",
    "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_support_gate_v1_20260507.json",
    "results/SealAudit/artifacts/generated/sealaudit_needs_review_taxonomy_v1_20260507.json",
    "results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_conjunction_gate_20260507.json",
    "results/SealAudit/artifacts/generated/sealaudit_expert_review_role_support_gate_v1_20260507.json",
    "docs/BESTPAPER_GAP_CLOSURE_STATUS_v1_20260507.md",
]


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def load_json(rel: str) -> object:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def main() -> int:
    if not SCORECARD.exists():
        fail(f"Missing scorecard: {SCORECARD.relative_to(ROOT)}")
    missing = [p for p in REQUIRED_ARTIFACTS if not (ROOT / p).exists()]
    if missing:
        fail("Missing closure artifacts:\n" + "\n".join(f"  - {p}" for p in missing))

    scorecard = json.loads(SCORECARD.read_text(encoding="utf-8"))
    if scorecard.get("claim_bearing") is not False:
        fail("Best-paper review scorecard must be non-claim-bearing.")
    if scorecard.get("bestpaper_ready") is not False:
        fail("Current scorecard must not mark the portfolio bestpaper_ready before P1/P2 closure.")

    projects = scorecard.get("projects", [])
    names = {project.get("project") for project in projects}
    if names != REQUIRED_PROJECTS:
        fail(f"Unexpected projects in scorecard: {sorted(names)}")

    for project in projects:
        if project.get("claim_upgrade_allowed") is not False:
            fail(f"{project.get('project')} incorrectly allows claim upgrade.")
        gaps = project.get("gaps", [])
        if not gaps:
            fail(f"{project.get('project')} has no recorded gaps.")
        if not any(gap.get("priority") == "P1" for gap in gaps):
            fail(f"{project.get('project')} must record at least one P1 closure item.")
        scores = project.get("scores", {})
        if len(scores) != 8:
            fail(f"{project.get('project')} must have 8 review dimensions.")
        for name, payload in scores.items():
            value = payload.get("score_1_to_5")
            if not isinstance(value, int) or not 1 <= value <= 5:
                fail(f"Invalid score for {project.get('project')} / {name}: {value}")

    codedye_v3 = load_json("results/CodeDye/artifacts/generated/codedye_v3_protocol_freeze_gate_20260507.json")
    if codedye_v3.get("formal_live_claim_allowed") is not False or codedye_v3.get("frozen") is not True:
        fail("CodeDye v3 freeze gate must be frozen and non-claim-bearing.")

    probe_anti = load_json("results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_gate_v1_20260507.json")
    if probe_anti.get("formal_multi_owner_claim_allowed") is not False:
        fail("ProbeTrace anti-leakage gate must not promote multi-owner claims.")

    seal_v5 = load_json("results/SealAudit/artifacts/generated/sealaudit_second_stage_v5_conjunction_gate_20260507.json")
    if seal_v5.get("formal_v5_claim_allowed") is not False:
        fail("SealAudit v5 prerun gate must not be claim-bearing before rerun.")

    print("[OK] Best-paper closure artifacts verified.")
    print(f"[OK] Projects: {', '.join(sorted(REQUIRED_PROJECTS))}")
    print("[OK] Current portfolio remains not bestpaper_ready until listed P1/P2 closures are implemented.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
