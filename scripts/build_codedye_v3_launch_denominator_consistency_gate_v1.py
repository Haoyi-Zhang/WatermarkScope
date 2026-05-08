from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT = ROOT / f"results/CodeDye/artifacts/generated/codedye_v3_launch_denominator_consistency_gate_v1_{DATE}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(rel: str) -> dict[str, Any]:
    payload = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(rel)
    return payload


def remote_free_count() -> int:
    code = r"""
import json
from pathlib import Path
import sys
sys.path.insert(0, 'projects/CodeDye/src')
sys.path.insert(0, 'projects/CodeDye/scripts')
from codedye.benchmarks import load_code_dyebench_tasks
from run_attack_matrix_ci_scaffold import SUPPORT_REQUIRED_ATTACK_IDS, _read_json
from run_attack_matrix_live_support import _build_target_claim_rows
ROOT = Path('projects/CodeDye')
tasks = load_code_dyebench_tasks(ROOT)
matrix = _read_json(ROOT / 'configs' / 'attack_matrix.json')
declared = {str(item.get('attack_id','')).strip() for item in matrix.get('attacks', []) if isinstance(item, dict) and str(item.get('attack_id','')).strip()}
rows, target = _build_target_claim_rows(tasks, matrix, target_records=300)
print(json.dumps({
  'task_count': len(tasks),
  'declared_attack_ids': sorted(declared),
  'claim_attack_ids': sorted(declared - SUPPORT_REQUIRED_ATTACK_IDS),
  'support_attack_ids': sorted(SUPPORT_REQUIRED_ATTACK_IDS & declared),
  **target,
}))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    if result.returncode != 0:
        return -1
    return json.loads(result.stdout)


def main() -> int:
    contract = load(f"results/CodeDye/artifacts/generated/codedye_v3_fresh_run_preflight_contract_v1_{DATE}.json")
    output = remote_free_count()
    blockers: list[str] = []
    if output == -1:
        blockers.append("codedye_runner_denominator_probe_failed")
        output = {}
    if contract.get("expected_record_count") != 300:
        blockers.append("contract_expected_record_count_not_300")
    if "--target-records 300" not in str(contract.get("launch_command_redacted", "")):
        blockers.append("contract_launch_missing_target_records_300")
    if int(output.get("post_target_row_count", 0) or 0) != 300:
        blockers.append(f"runner_post_target_row_count_not_300:{output.get('post_target_row_count')}")
    if int(output.get("task_count", 0) or 0) != 300:
        blockers.append(f"runner_task_count_not_300:{output.get('task_count')}")
    if int(output.get("unused_task_count", 0) or 0) != 0:
        blockers.append(f"runner_unused_task_count_nonzero:{output.get('unused_task_count')}")
    if output.get("target_records_mode") != "one_claim_row_per_task_balanced_by_attack":
        blockers.append("runner_target_records_mode_unexpected")
    if "query_budget_drop" in output.get("post_target_by_attack", {}):
        blockers.append("support_only_query_budget_in_main_denominator")
    payload = {
        "schema_version": "codedye_v3_launch_denominator_consistency_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": not blockers,
        "formal_v3_live_claim_allowed": False,
        "contract_path": f"results/CodeDye/artifacts/generated/codedye_v3_fresh_run_preflight_contract_v1_{DATE}.json",
        "runner_probe": output,
        "blockers": blockers,
        "policy": "The canonical v3 launch must be able to materialize exactly 300 claim-denominator rows before any live full run starts.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
