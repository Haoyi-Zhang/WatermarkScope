from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
PORTFOLIO = ROOT / f"results/blackbox_fresh_run_preflight_contracts_v1_{DATE}.json"


PROJECTS = {
    "CodeDye": {
        "path": f"results/CodeDye/artifacts/generated/codedye_v3_fresh_run_preflight_contract_v1_{DATE}.json",
        "schema_version": "codedye_v3_fresh_run_preflight_contract_v1",
        "canonical_output": f"results/CodeDye/artifacts/generated/codedye_v3_live_results_{DATE}.json",
        "postrun": f"results/CodeDye/artifacts/generated/codedye_v3_postrun_promotion_gate_v1_{DATE}.json",
        "expected_rows": 300,
        "forbidden_true_flags": [
            "formal_v3_live_claim_allowed",
            "formal_high_recall_detection_claim_allowed",
        ],
    },
    "ProbeTrace": {
        "path": f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_fresh_run_preflight_contract_v1_{DATE}.json",
        "schema_version": "probetrace_multi_owner_fresh_run_preflight_contract_v1",
        "canonical_output": f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_live_score_vectors_{DATE}.jsonl",
        "postrun": f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_postrun_promotion_gate_v1_{DATE}.json",
        "expected_rows": 6000,
        "forbidden_true_flags": [
            "formal_multi_owner_claim_allowed",
            "formal_provider_general_claim_allowed",
        ],
    },
    "SealAudit": {
        "path": f"results/SealAudit/artifacts/generated/sealaudit_v5_fresh_run_preflight_contract_v1_{DATE}.json",
        "schema_version": "sealaudit_v5_fresh_run_preflight_contract_v1",
        "canonical_output": f"results/SealAudit/artifacts/generated/sealaudit_v5_final_claim_evidence_rows_{DATE}.json",
        "postrun": f"results/SealAudit/artifacts/generated/sealaudit_v5_postrun_promotion_gate_v1_{DATE}.json",
        "expected_rows": 960,
        "forbidden_true_flags": [
            "formal_v5_claim_allowed",
            "formal_security_certificate_claim_allowed",
            "formal_harmlessness_claim_allowed",
        ],
    },
}

SECRET_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"ghp_[A-Za-z0-9_]{20,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"bearer\s+[A-Za-z0-9_.-]{12,}",
        r"api[_-]?key\s*=",
        r"authorization:",
    ]
]


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def load(rel: str) -> dict:
    path = ROOT / rel
    if not path.exists():
        fail(f"Missing contract artifact: {rel}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail(f"Contract is not a JSON object: {rel}")
    return payload


def check_no_secrets(text: str, label: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            fail(f"Secret-like token in {label}: {pattern.pattern}")


def main() -> int:
    if not PORTFOLIO.exists():
        fail("Portfolio fresh-run contract is missing.")
    portfolio = json.loads(PORTFOLIO.read_text(encoding="utf-8"))
    if portfolio.get("schema_version") != "blackbox_fresh_run_preflight_contracts_v1":
        fail("Unexpected portfolio fresh-run contract schema.")
    if portfolio.get("claim_bearing") is not False:
        fail("Portfolio fresh-run contract must be non-claim-bearing.")
    if portfolio.get("formal_blackbox_upgrade_claims_allowed") is not False:
        fail("Fresh-run contracts cannot promote black-box upgrade claims.")
    if portfolio.get("secret_values_recorded") is not False:
        fail("Fresh-run contracts must not record secret values.")
    if set(portfolio.get("project_contracts", {})) != set(PROJECTS):
        fail("Portfolio project-contract set is incomplete.")
    if portfolio.get("gate_pass") is not True:
        fail("Fresh-run contract portfolio should pass; provider execution readiness is checked separately.")

    for project, spec in PROJECTS.items():
        payload = load(spec["path"])
        if payload.get("schema_version") != spec["schema_version"]:
            fail(f"{project} contract schema drifted.")
        if payload.get("project") != project:
            fail(f"{project} contract project field drifted.")
        if payload.get("claim_bearing") is not False:
            fail(f"{project} fresh-run contract must be non-claim-bearing.")
        if payload.get("gate_pass") is not True or payload.get("execution_contract_ready") is not True:
            fail(f"{project} fresh-run execution contract is not ready.")
        if payload.get("provider") != "deepseek" or payload.get("provider_mode_required") != "live":
            fail(f"{project} contract must require DeepSeek live provider mode.")
        if payload.get("secret_values_recorded") is not False:
            fail(f"{project} contract must not record secret values.")
        for field in spec["forbidden_true_flags"]:
            if payload.get(field) is not False:
                fail(f"{project} contract unexpectedly allows {field}.")
        output = payload.get("canonical_output", payload.get("canonical_v5_evidence_input"))
        if output != spec["canonical_output"]:
            fail(f"{project} canonical output path drifted: {output}")
        if payload.get("expected_record_count", payload.get("expected_marker_hidden_claim_rows")) != spec["expected_rows"]:
            fail(f"{project} expected row count drifted.")
        if payload.get("postrun_promotion_gate") != spec["postrun"]:
            fail(f"{project} postrun promotion gate path drifted.")
        if payload.get("blockers"):
            fail(f"{project} contract has blockers: {payload['blockers']}")
        command = str(payload.get("launch_command_redacted", ""))
        check_no_secrets(command, f"{project} launch_command_redacted")
        if spec["canonical_output"] not in command and project != "SealAudit":
            fail(f"{project} launch command does not bind canonical output.")
        if project == "CodeDye" and "--target-records 300" not in command:
            fail("CodeDye canonical launch command must bind --target-records 300.")
        if project == "ProbeTrace" and "run_multi_owner_deepseek_live.py" not in command:
            fail("ProbeTrace canonical launch command must use the live DeepSeek scorer.")
        if project == "ProbeTrace" and "--claim-bearing-canonical" not in command:
            fail("ProbeTrace canonical launch command must request full canonical claim-bearing output.")
        if project == "CodeDye" and payload.get("expected_claim_denominator_record_count") != 300:
            fail("CodeDye contract must bind the 300-row claim denominator.")
        if project == "SealAudit" and spec["canonical_output"] not in command:
            fail("SealAudit launch command does not bind canonical v5 evidence input.")
        prereqs = payload.get("prerequisite_artifacts", [])
        if not prereqs or any(item.get("exists") is not True for item in prereqs):
            fail(f"{project} contract has missing prerequisite artifacts.")
        if not payload.get("required_record_fields"):
            fail(f"{project} contract lacks required row fields.")

    print("[OK] Black-box fresh-run preflight contracts verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
