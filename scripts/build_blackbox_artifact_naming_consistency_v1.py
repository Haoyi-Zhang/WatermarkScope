from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT = ROOT / f"results/blackbox_artifact_naming_consistency_v1_{DATE}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(rel: str) -> dict[str, Any]:
    payload = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(rel)
    return payload


def path_exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def project_contract_rows() -> list[dict[str, Any]]:
    portfolio = load(f"results/blackbox_fresh_run_preflight_contracts_v1_{DATE}.json")
    rows: list[dict[str, Any]] = []
    for project, meta in sorted(portfolio.get("project_contracts", {}).items()):
        contract_path = str(meta["path"])
        contract = load(contract_path)
        postrun_path = str(contract["postrun_promotion_gate"])
        postrun = load(postrun_path)
        canonical_output = str(contract.get("canonical_output", contract.get("canonical_v5_evidence_input", "")))
        checked_candidates = set(str(item) for item in postrun.get("checked_candidate_paths", []))
        source_artifacts = postrun.get("source_artifacts", {})
        expected_receipt = str(contract.get("runner_receipt_output", ""))
        expected_frontier = str(contract.get("coverage_risk_frontier_output", ""))
        expected_visible = str(contract.get("visible_marker_boundary_output", ""))
        expected_threshold = str(contract.get("threshold_sensitivity_output", ""))
        rows.append(
            {
                "project": project,
                "contract_path": contract_path,
                "contract_schema_version": contract.get("schema_version"),
                "contract_gate_pass": contract.get("gate_pass"),
                "contract_claim_bearing": contract.get("claim_bearing"),
                "postrun_path": postrun_path,
                "postrun_schema_version": postrun.get("schema_version"),
                "postrun_claim_bearing": postrun.get("claim_bearing"),
                "postrun_gate_pass": postrun.get("gate_pass"),
                "canonical_output": canonical_output,
                "canonical_output_exists_now": path_exists(canonical_output),
                "canonical_output_bound_to_postrun": (
                    canonical_output in checked_candidates
                    or source_artifacts.get("runner_receipt") == expected_receipt
                    or source_artifacts.get("coverage_risk_frontier") == expected_frontier
                    or source_artifacts.get("visible_marker_diagnostic_boundary") == expected_visible
                    or source_artifacts.get("threshold_sensitivity") == expected_threshold
                ),
                "postrun_checked_candidate_paths": sorted(checked_candidates),
                "postrun_source_artifacts": source_artifacts,
                "expected_auxiliary_outputs": {
                    key: value
                    for key, value in {
                        "runner_receipt": expected_receipt,
                        "coverage_risk_frontier": expected_frontier,
                        "visible_marker_boundary": expected_visible,
                        "threshold_sensitivity": expected_threshold,
                    }.items()
                    if value
                },
            }
        )
    return rows


def main() -> int:
    rows = project_contract_rows()
    blockers: list[str] = []
    expected_prefix = {
        "CodeDye": "codedye_",
        "ProbeTrace": "probetrace_",
        "SealAudit": "sealaudit_",
    }
    for row in rows:
        project = row["project"]
        prefix = expected_prefix[project]
        contract_name = Path(row["contract_path"]).name
        postrun_name = Path(row["postrun_path"]).name
        if not contract_name.startswith(prefix):
            blockers.append(f"{project}:contract_prefix_mismatch")
        if not postrun_name.startswith(prefix):
            blockers.append(f"{project}:postrun_prefix_mismatch")
        if f"_{DATE}.json" not in contract_name:
            blockers.append(f"{project}:contract_date_missing")
        if f"_{DATE}.json" not in postrun_name:
            blockers.append(f"{project}:postrun_date_missing")
        if "fresh_run_preflight_contract" not in str(row["contract_schema_version"]):
            blockers.append(f"{project}:contract_schema_not_fresh_run_preflight")
        if "postrun_promotion_gate" not in str(row["postrun_schema_version"]):
            blockers.append(f"{project}:postrun_schema_not_promotion_gate")
        if row["contract_claim_bearing"] is not False or row["postrun_claim_bearing"] is not False:
            blockers.append(f"{project}:gate_artifact_claim_bearing")
        if row["contract_gate_pass"] is not True:
            blockers.append(f"{project}:contract_gate_not_passed")
        if row["canonical_output_bound_to_postrun"] is not True:
            blockers.append(f"{project}:canonical_output_not_bound_to_postrun")
        # It is acceptable for canonical outputs to be absent before execution.
        if row["postrun_gate_pass"] is True:
            blockers.append(f"{project}:postrun_gate_passed_before_consistency_gate_refresh")

    payload = {
        "schema_version": "blackbox_artifact_naming_consistency_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": not blockers,
        "project_rows": rows,
        "blockers": blockers,
        "policy": (
            "Fresh-run contracts, canonical output names, and postrun promotion gates must stay aligned. "
            "Canonical outputs may be absent before provider execution."
        ),
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
