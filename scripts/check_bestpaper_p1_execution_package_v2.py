from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "results/bestpaper_p1_execution_package_v2_20260507.json"
REQUIRED = {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not PACKAGE.exists():
        fail(f"Missing package: {PACKAGE.relative_to(ROOT)}")
    payload = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if payload.get("claim_bearing") is not False or payload.get("formal_experiment_allowed") is not False:
        fail("P1 v2 package must remain non-claim-bearing and not formal-experiment allowed.")
    projects = payload.get("projects", {})
    if set(projects) != REQUIRED:
        fail(f"Unexpected projects: {sorted(projects)}")
    for name, spec in projects.items():
        pre = spec.get("pre_run_gate")
        if pre and not (ROOT / pre).exists():
            fail(f"{name} pre-run/readiness gate missing: {pre}")
        command = spec.get("command")
        if name != "SemCodebook" and not command:
            fail(f"{name} missing command contract.")
    probe_schema = projects["ProbeTrace"].get("required_input_schema", [])
    for field in ("true_owner_id", "candidate_owner_id", "owner_heldout", "task_heldout", "signed_owner_margin"):
        if field not in probe_schema:
            fail(f"ProbeTrace v2 schema missing {field}")
    seal_required = projects["SealAudit"].get("required_postrun_artifacts", [])
    if not any("coverage_risk_frontier" in path for path in seal_required):
        fail("SealAudit v2 package missing coverage-risk frontier output.")
    print("[OK] Best-paper P1 execution package v2 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
