from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_DOCS = [
    "README.md",
    "CLAIM_BOUNDARIES.md",
    "docs/EXAMINER_GUIDE.md",
    "docs/METHOD_INDEX.md",
    "docs/RESULT_PRESERVATION_POLICY.md",
    "docs/TRACEABILITY_MATRIX.md",
    "docs/ENVIRONMENT.md",
    "docs/RUNBOOK.md",
    "docs/RESULTS_SUMMARY.md",
]


def run(cmd: list[str]) -> None:
    print(f"\n$ {' '.join(cmd)}", flush=True)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(cmd, cwd=ROOT, text=True, env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def check_docs() -> None:
    missing = [p for p in REQUIRED_DOCS if not (ROOT / p).exists()]
    if missing:
        raise SystemExit("Missing examiner documents:\n" + "\n".join(f"  - {p}" for p in missing))
    print(f"[OK] Examiner-facing documents present: {len(REQUIRED_DOCS)}", flush=True)


def check_manifest_shape() -> None:
    manifest = ROOT / "RESULT_MANIFEST.jsonl"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    modules = {row["module"] for row in rows}
    expected = {"Dissertation", "CodeMarkBench", "SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}
    if modules != expected:
        raise SystemExit(f"Unexpected manifest modules: {sorted(modules)}")
    ci_rows = [row for row in rows if row.get("ci_required")]
    if len(ci_rows) < 8:
        raise SystemExit("Too few CI-bearing manifest rows.")
    transfer = [row for row in rows if row["module"] == "ProbeTrace" and "Transfer" in row["claim"]]
    if not transfer or any(row.get("primary_independence_unit") != "task_cluster" for row in transfer):
        raise SystemExit("ProbeTrace transfer rows lack task-cluster independence boundary.")
    if any(not row.get("support_only") or row.get("claim_bearing") is not False for row in transfer):
        raise SystemExit("ProbeTrace transfer rows must be support-only in RESULT_MANIFEST.jsonl.")
    sem = {(row["module"], row["claim"]): row for row in rows}
    if sem.get(("SemCodebook", "Positive recovery"), {}).get("denominator") != 24000:
        raise SystemExit("SemCodebook positive recovery denominator is not directly reconstructable from RESULT_MANIFEST.jsonl.")
    if sem.get(("SemCodebook", "Negative-control hits"), {}).get("denominator") != 48000:
        raise SystemExit("SemCodebook negative-control denominator is not directly reconstructable from RESULT_MANIFEST.jsonl.")
    print(f"[OK] Manifest modules: {', '.join(sorted(modules))}", flush=True)
    print(f"[OK] CI-bearing manifest rows: {len(ci_rows)}", flush=True)


def main() -> int:
    with_continuation = "--with-continuation" in sys.argv[1:]
    print("WatermarkScope FYP examiner check", flush=True)
    print("=" * 28, flush=True)
    check_docs()
    check_manifest_shape()
    run([sys.executable, "-B", "scripts/repro_check.py"])
    run([sys.executable, "-B", "scripts/check_project_snapshots.py"])
    run([sys.executable, "-B", "scripts/check_preserved_results.py"])
    if with_continuation:
        run([sys.executable, "-B", "scripts/check_codedye_v3_run_readiness_classifier_v1.py"])
        run([sys.executable, "-B", "scripts/check_codedye_v3_postrun_promotion_gate_v1.py"])
        run([sys.executable, "-B", "scripts/check_probetrace_multi_owner_evidence_classifier_v1.py"])
        run([sys.executable, "-B", "scripts/check_probetrace_multi_owner_postrun_promotion_gate_v1.py"])
        run([sys.executable, "-B", "scripts/check_sealaudit_v5_evidence_classifier_v1.py"])
        run([sys.executable, "-B", "scripts/check_sealaudit_v5_postrun_promotion_gate_v1.py"])
        run([sys.executable, "-B", "scripts/check_provider_launch_readiness_gate_v1.py"])
        run([sys.executable, "-B", "scripts/check_strict_reviewer_audit_v2.py"])
        run([sys.executable, "-B", "scripts/check_semcodebook_final_claim_lock_v1.py"])
        run([sys.executable, "-B", "scripts/check_codedye_final_claim_lock_v1.py"])
        run([sys.executable, "-B", "scripts/check_codedye_live_traceability_manifest_v1.py"])
        run([sys.executable, "-B", "scripts/check_probetrace_final_claim_lock_v1.py"])
        run([sys.executable, "-B", "scripts/check_probetrace_anti_leakage_scan_v1.py"])
        run([sys.executable, "-B", "scripts/check_probetrace_latency_query_frontier_v1.py"])
        run([sys.executable, "-B", "scripts/check_sealaudit_final_claim_lock_v1.py"])
        run([sys.executable, "-B", "scripts/check_sealaudit_abstention_wording_artifacts_v1.py"])
        run([sys.executable, "-B", "scripts/check_strict_reviewer_audit_v3.py"])
        run([sys.executable, "-B", "scripts/check_strict_reviewer_audit_v4.py"])
        run([sys.executable, "-B", "scripts/check_blackbox_fresh_run_contracts_v1.py"])
        run([sys.executable, "-B", "scripts/check_provider_launch_readiness_gate_v2.py"])
        run([sys.executable, "-B", "scripts/check_blackbox_artifact_naming_consistency_v1.py"])
        run([sys.executable, "-B", "scripts/check_reviewer_manifest_v4.py"])
        run([sys.executable, "-B", "scripts/check_reviewer_manifest_v5.py"])
        run([sys.executable, "-B", "scripts/check_reviewer_manifest_v6.py"])
        run([sys.executable, "-B", "scripts/check_strict_reviewer_audit_v5.py"])
    run([sys.executable, "-B", "scripts/summarize_all.py"])
    print("\n[OK] Examiner check completed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
