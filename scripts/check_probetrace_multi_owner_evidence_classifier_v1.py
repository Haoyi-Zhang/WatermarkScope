from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_evidence_classifier_v1_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("ProbeTrace multi-owner evidence classifier artifact is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("claim_bearing") is not False:
        fail("Classifier must be non-claim-bearing.")
    if payload.get("formal_multi_owner_claim_allowed") is not False:
        fail("Classifier must keep multi-owner claim blocked.")
    if payload.get("gate_pass") is not False:
        fail("Classifier gate must fail closed until fresh multi-owner provider outputs exist.")
    status = payload["score_vector_status"]
    if status["comparable_signed_owner_margin_rows"] != 0:
        fail("Comparable signed margins unexpectedly present; inspect before promotion.")
    if payload["input_package_status"]["row_count"] != 6000:
        fail("ProbeTrace multi-owner input package row count drifted.")
    required_blockers = {
        "fresh_multi_owner_multilingual_deepseek_canonical_results_missing",
        "multi_owner_postrun_audit_missing",
        "per_owner_per_language_ci_missing",
        "raw_transcript_and_structured_payload_hash_join_missing",
        "comparable_signed_owner_margin_rows_missing",
        "transfer_artifact_is_single_owner_only",
    }
    blockers = set(payload.get("blockers", []))
    missing = required_blockers - blockers
    if missing:
        fail("Missing expected fail-closed blockers: " + ", ".join(sorted(missing)))
    print("[OK] ProbeTrace multi-owner evidence classifier verified fail-closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
