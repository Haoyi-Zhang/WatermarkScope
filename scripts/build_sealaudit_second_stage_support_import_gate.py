from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import SealAudit second-stage executable conjunction support evidence.")
    parser.add_argument("--conjunction", required=True)
    parser.add_argument("--readiness", required=True)
    parser.add_argument("--taxonomy", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    paths = {
        "conjunction": ROOT / args.conjunction,
        "readiness": ROOT / args.readiness,
        "taxonomy": ROOT / args.taxonomy,
    }
    output_path = ROOT / args.output
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        payload = {
            "schema_version": "sealaudit_second_stage_support_import_gate_v1",
            "generated_at_utc": utc_now(),
            "claim_bearing": False,
            "gate_pass": False,
            "blocked": True,
            "blockers": [f"{name}_missing" for name in missing],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("[BLOCKED] SealAudit support inputs missing.")
        return 2

    conjunction = load(paths["conjunction"])
    readiness = load(paths["readiness"])
    taxonomy = load(paths["taxonomy"])
    case_analysis = conjunction.get("case_analysis", {})
    records = case_analysis.get("records", []) if isinstance(case_analysis, dict) else []
    gate_names = ["static_safety", "semantic_drift", "laundering", "spoofability", "provider_judge", "baseline_control_evidence"]
    pass_counts = Counter()
    for row in records:
        statuses = row.get("gate_statuses", {}) if isinstance(row, dict) else {}
        for gate in gate_names:
            if isinstance(statuses.get(gate), dict) and statuses[gate].get("pass") is True:
                pass_counts[gate] += 1
    final_pass = sum(1 for row in records if isinstance(row, dict) and row.get("final_conjunction_pass") is True)
    missing_case_code = sum(1 for row in records if isinstance(row, dict) and row.get("candidate_executable_code_present") is not True)
    provider_joined = sum(1 for row in records if isinstance(row, dict) and row.get("provider_judge_trace_joined") is True)
    scheme_counts = Counter(str(row.get("scheme_kind", "unknown")) for row in records if isinstance(row, dict))
    language_counts = Counter(str(row.get("language", "unknown")) for row in records if isinstance(row, dict))
    taxonomy_records = taxonomy.get("records", []) if isinstance(taxonomy, dict) else []
    support_gate_pass = (
        len(records) == 320
        and final_pass == 320
        and missing_case_code == 0
        and provider_joined == 320
        and all(pass_counts[gate] == 320 for gate in gate_names)
        and bool(readiness.get("gate_pass"))
        and bool(taxonomy.get("gate_pass"))
    )
    blockers = [
        name
        for name, present in [
            ("conjunction_record_count_not_320", len(records) != 320),
            ("not_all_final_conjunction_pass", final_pass != 320),
            ("candidate_executable_code_missing", missing_case_code > 0),
            ("provider_trace_join_incomplete", provider_joined != 320),
            ("subgate_pass_incomplete", any(pass_counts[gate] != 320 for gate in gate_names)),
            ("readiness_gate_failed", not bool(readiness.get("gate_pass"))),
            ("taxonomy_gate_failed", not bool(taxonomy.get("gate_pass"))),
        ]
        if present
    ]
    payload = {
        "schema_version": "sealaudit_second_stage_support_import_gate_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": support_gate_pass,
        "blocked": False,
        "formal_v5_claim_allowed": False,
        "formal_second_stage_claim_allowed": False,
        "support_ready": support_gate_pass,
        "inputs": {
            "conjunction": args.conjunction,
            "readiness": args.readiness,
            "taxonomy": args.taxonomy,
        },
        "conjunction_claim_role": conjunction.get("claim_role"),
        "conjunction_artifact_role": conjunction.get("artifact_role"),
        "case_count": len(records),
        "final_conjunction_pass_count": final_pass,
        "candidate_executable_code_present_count": len(records) - missing_case_code,
        "provider_judge_trace_join_count": provider_joined,
        "subgate_pass_counts": dict(sorted(pass_counts.items())),
        "scheme_kind_counts": dict(sorted(scheme_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "needs_review_taxonomy_record_count": len(taxonomy_records),
        "claim_boundary": "This closes executable-conjunction support readiness only. It does not relabel old v3 decisions, does not increase decisive coverage, and does not permit a v5 main claim without final row-level v5 evidence.",
        "blockers": blockers,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("[OK] Wrote SealAudit second-stage support import gate.")
    return 0 if support_gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
