from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "results/watermark_submission_gap_diagnosis_v1_20260508.json"
ARTIFACT_MD = ROOT / "results/watermark_submission_gap_diagnosis_v1_20260508.md"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists() or not ARTIFACT_MD.exists():
        fail("Submission gap diagnosis artifacts are missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "watermark_submission_gap_diagnosis_v1":
        fail("Unexpected submission gap diagnosis schema.")
    if payload.get("claim_bearing") is not False:
        fail("Gap diagnosis must be non-claim-bearing.")
    state = payload["portfolio_current_state"]
    if state["remaining_p1"] != 0 or state["remaining_p2"] != 0:
        fail("Diagnosis should be based on final P1/P2-clean audit.")
    projects = {project["project"]: project for project in payload.get("projects", [])}
    if set(projects) != {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}:
        fail("Diagnosis must cover exactly four watermark projects.")
    required_axes = {
        "SemCodebook": {"method_theory", "baseline_positioning", "external_validity"},
        "CodeDye": {"effect_size", "positive_control_sensitivity", "claim_boundary"},
        "ProbeTrace": {"too_perfect_result_risk", "provider_scope", "cost_usability"},
        "SealAudit": {"coverage", "human_support_boundary", "security_overclaim"},
    }
    for project, axes in required_axes.items():
        found = {gap["axis"] for gap in projects[project].get("best_paper_gap", [])}
        missing = axes - found
        if missing:
            fail(f"{project} diagnosis missing axes: {sorted(missing)}")
        if not projects[project].get("next_execution"):
            fail(f"{project} missing next execution.")
    policy = payload["execution_policy"]
    if policy.get("do_not_rerun_blindly") is not True:
        fail("Diagnosis must prevent blind duplicate reruns.")
    print("[OK] Watermark submission gap diagnosis verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
