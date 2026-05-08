from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
OUT = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_multi_owner_evidence_classifier_v1_{DATE}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def read_jsonl(rel: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with (ROOT / rel).open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
    return rows


def main() -> int:
    input_package = load_json("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_package_20260507.json")
    future_gate = load_json("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_generalization_gate_20260505_remote.json")
    transfer = load_json("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_live_results_20260505_remote.json")
    score_rows = read_jsonl("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_score_vectors_20260507.jsonl")

    score_space_status = Counter(str(row.get("signed_owner_margin_status", "missing")) for row in score_rows)
    comparable_margin_rows = sum(1 for row in score_rows if row.get("signed_owner_margin") is not None)
    high_control_no_owner_rows = sum(1 for row in score_rows if row.get("high_control_score_without_owner_emission") is True)
    owner_ids = set()
    for row in score_rows:
        owner = row.get("owner_id_hat_hash")
        if owner:
            owner_ids.add(str(owner))
    blockers = [
        "fresh_multi_owner_multilingual_deepseek_canonical_results_missing",
        "multi_owner_postrun_audit_missing",
        "per_owner_per_language_ci_missing",
        "raw_transcript_and_structured_payload_hash_join_missing",
    ]
    if comparable_margin_rows == 0:
        blockers.append("comparable_signed_owner_margin_rows_missing")
    if int(transfer.get("observed_owner_count_transfer", 0)) <= 1:
        blockers.append("transfer_artifact_is_single_owner_only")

    payload = {
        "schema_version": "probetrace_multi_owner_evidence_classifier_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "formal_multi_owner_claim_allowed": False,
        "gate_pass": False,
        "input_package_status": {
            "row_count": input_package["row_count"],
            "owner_count": input_package["owner_count"],
            "claim_bearing": input_package["claim_bearing"],
            "formal_multi_owner_claim_allowed": input_package["formal_multi_owner_claim_allowed"],
            "role_counts": input_package["control_role_counts"],
            "split_counts": input_package["split_counts"],
        },
        "future_generalization_gate_status": {
            "gate_pass": future_gate["gate_pass"],
            "formal_claim_allowed": future_gate["formal_claim_allowed"],
            "claim_blockers_remaining": future_gate["claim_blockers_remaining"],
        },
        "single_owner_transfer_status": {
            "validation_record_count": transfer["validation_record_count"],
            "observed_owner_count_transfer": transfer["observed_owner_count_transfer"],
            "correct_owner_count": transfer["correct_owner_count"],
            "formal_claim_allowed": transfer["formal_claim_allowed"],
        },
        "score_vector_status": {
            "row_count": len(score_rows),
            "score_space_status_counts": dict(sorted(score_space_status.items())),
            "comparable_signed_owner_margin_rows": comparable_margin_rows,
            "owner_id_hat_hash_count": len(owner_ids),
            "high_control_score_without_owner_emission_rows": high_control_no_owner_rows,
        },
        "classification": {
            "input_package": "executable_input_not_result",
            "single_owner_transfer": "support_only_single_owner_floor",
            "score_vectors": "single_owner_control_score_audit_not_comparable_multi_owner_margin",
            "remote_generalization_gate": "future_rerun_manifest_not_claim_evidence",
        },
        "blockers": sorted(set(blockers)),
        "promotion_policy": "Do not close the multi-owner P1 until fresh 5-owner DeepSeek outputs have comparable score vectors, raw/structured hashes, per-owner/per-language CI, and a postrun promotion gate.",
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
