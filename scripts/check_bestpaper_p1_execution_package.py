from __future__ import annotations

import json
import shlex
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
PACKAGE = ROOT / f"results/bestpaper_p1_execution_package_v1_{DATE}.json"
REQUIRED_PROJECTS = {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not PACKAGE.exists():
        fail(f"Missing execution package: {PACKAGE.relative_to(ROOT)}")
    payload = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if payload.get("claim_bearing") is not False or payload.get("formal_experiment_allowed") is not False:
        fail("P1 execution package must not be claim-bearing or formal-experiment allowed.")
    projects = payload.get("projects", {})
    if set(projects) != REQUIRED_PROJECTS:
        fail(f"Unexpected projects: {sorted(projects)}")
    for name, spec in projects.items():
        contract = spec.get("runner_contract", {})
        if not contract:
            fail(f"{name} missing runner_contract.")
        if "promotion_condition" not in contract:
            fail(f"{name} missing promotion_condition.")
        if not spec.get("command"):
            fail(f"{name} missing command.")
        parts = shlex.split(spec["command"], posix=False)
        if len(parts) < 2 or not parts[0].startswith("python"):
            fail(f"{name} command must start with python and a script path.")
        script = ROOT / parts[1]
        if not script.exists():
            fail(f"{name} command script does not exist: {parts[1]}")
    if projects["SemCodebook"]["local_ready"] is not False:
        fail("SemCodebook local_ready should remain false in this compact package because raw 237MB artifact is represented by manifest, not bundled.")
    for name in ("CodeDye", "ProbeTrace"):
        if projects[name]["local_ready"] is not False:
            fail(f"{name} should require remote/API inputs before formal P1 execution.")
    print("[OK] Best-paper P1 execution package verified.")
    print("[OK] Commands/contracts are present; formal experiments remain blocked until inputs and promotion gates are available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
