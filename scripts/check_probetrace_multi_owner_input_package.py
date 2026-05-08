from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROWS = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_rows_20260507.jsonl"
GATE = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_prerun_gate_20260507.json"
PACKAGE = ROOT / "results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_package_20260507.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    rows = [json.loads(line) for line in ROWS.read_text(encoding="utf-8").splitlines() if line.strip()]
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    if package.get("claim_bearing") is not False or gate.get("formal_multi_owner_claim_allowed") is not False:
        fail("Input package/gate must not promote a multi-owner claim.")
    if len(rows) != 6000 or package.get("row_count") != 6000:
        fail(f"Expected 6000 input rows, got rows={len(rows)} package={package.get('row_count')}")
    roles = Counter(row["control_role"] for row in rows)
    expected_roles = {
        "true_owner": 750,
        "wrong_owner": 3000,
        "null_owner": 750,
        "random_owner": 750,
        "same_provider_unwrap": 750,
    }
    if dict(roles) != expected_roles:
        fail(f"Unexpected role counts: {dict(roles)}")
    splits = Counter(row["split"] for row in rows)
    if splits.get("owner_heldout") != 1200 or splits.get("task_heldout") != 1200:
        fail(f"Owner/task heldout split missing or wrong: {dict(splits)}")
    if any(row.get("owner_key_material_in_row") is not False for row in rows):
        fail("Owner key material leaked into input rows.")
    required = {"task_id", "true_owner_id", "candidate_owner_id", "prompt_hash", "task_hash", "row_sha256"}
    bad_rows = [idx for idx, row in enumerate(rows) if not required.issubset(row)]
    if bad_rows:
        fail(f"Input rows missing required fields, first bad index {bad_rows[0]}")
    print("[OK] ProbeTrace multi-owner DeepSeek input package verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
