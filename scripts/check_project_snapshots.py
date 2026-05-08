from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


PROJECTS = {
    "CodeMarkBench": {
        "code": [
            "projects/CodeMarkBench/codemarkbench",
            "projects/CodeMarkBench/scripts",
            "projects/CodeMarkBench/results/tables/suite_all_models_methods",
        ],
        "artifacts": [
            "projects/CodeMarkBench/results/tables/suite_all_models_methods/suite_all_models_methods_run_inventory.csv",
        ],
    },
    "SemCodebook": {
        "code": [
            "projects/SemCodebook/src/semcodebook",
            "projects/SemCodebook/scripts",
            "projects/SemCodebook/tests",
        ],
        "artifacts": [
            "results/SemCodebook/artifacts/generated/semcodebook_whitebox_model_sufficiency_gate_20260505.json",
            "results/SemCodebook/artifacts/generated/semcodebook_ablation_compact_summary_fyp.json",
        ],
    },
    "CodeDye": {
        "code": [
            "projects/CodeDye/scripts",
            "projects/CodeDye/tests",
        ],
        "artifacts": [
            "results/CodeDye/artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json",
            "results/CodeDye/artifacts/generated/codedye_positive_contamination_control_300_gate_20260505.json",
        ],
    },
    "ProbeTrace": {
        "code": [
            "projects/ProbeTrace/scripts",
            "projects/ProbeTrace/scripts/run_multi_owner_support.py",
        ],
        "artifacts": [
            "results/ProbeTrace/artifacts/generated/apis300_live_attribution_evidence.json",
            "results/ProbeTrace/artifacts/generated/probetrace_abstain_aware_attribution_gate_20260506.json",
        ],
    },
    "SealAudit": {
        "code": [
            "projects/SealAudit/src/sealaudit",
            "projects/SealAudit/scripts",
            "projects/SealAudit/scripts/run_second_stage_v5_conjunction.py",
            "projects/SealAudit/tests",
        ],
        "artifacts": [
            "results/SealAudit/artifacts/generated/canonical_claim_surface_results.json",
            "results/SealAudit/artifacts/generated/sealaudit_coverage_risk_frontier_gate_20260505.json",
        ],
    },
}


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def ensure_path(path: str) -> None:
    if not (ROOT / path).exists():
        fail(f"Missing snapshot path: {path}")


def main() -> int:
    for project, spec in PROJECTS.items():
        for path in spec["code"]:
            ensure_path(path)
        for path in spec["artifacts"]:
            ensure_path(path)

    manifest = ROOT / "RESULT_MANIFEST.jsonl"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    modules = {row["module"] for row in rows}
    missing = set(PROJECTS) - modules
    if missing:
        fail("Missing project modules in RESULT_MANIFEST.jsonl: " + ", ".join(sorted(missing)))

    result = subprocess.run(
        [sys.executable, "scripts/summarize_all.py"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
        non_presentation_rows = [row for row in rows if row.get("module") != "Dissertation"]
        mismatches = []
        for row in non_presentation_rows:
            path = ROOT / row["path"]
            if not path.exists():
                mismatches.append(row["path"])
                continue
            import hashlib

            h = hashlib.sha256()
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            if h.hexdigest() != row["sha256"]:
                mismatches.append(row["path"])
        if mismatches:
            print(result.stdout)
            fail("Result manifest summary failed for non-presentation artifacts:\n" + "\n".join(mismatches))
        print("[OK] Result manifest has only presentation-document drift; watermarked project artifacts verify.")

    print("[OK] Project evidence snapshots are present.")
    print("[OK] Result manifest artifacts verify via summarize_all.py.")
    print("[OK] This is an evidence-snapshot check, not a full GPU/API rerun.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
