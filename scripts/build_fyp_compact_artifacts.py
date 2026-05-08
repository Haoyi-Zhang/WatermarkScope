from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_codedye_exclusion_inventory() -> None:
    gate = json.loads(
        (ROOT / "results/CodeDye/artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json").read_text(
            encoding="utf-8"
        )
    )
    surface = gate["effect_surface"]
    support_rows = int(surface["support_rows_excluded_from_main_denominator"])
    payload = {
        "schema_version": "codedye_support_exclusion_inventory_fyp_v1",
        "artifact_role": "compact_support_exclusion_inventory",
        "support_rows_excluded_from_main_denominator": support_rows,
        "claim_bearing": False,
        "main_denominator_unchanged": 300,
        "exclusion_policy": "These rows are retained as support/public/stress evidence and cannot change the 300-row live audit numerator or denominator.",
        "categories": [
            {
                "category": "public_or_utility_support",
                "row_count": 806,
                "claim_bearing": False,
                "exclusion_reason": "Rows do not satisfy the frozen DeepSeek live CodeDyeBench claim contract.",
            }
        ],
        "source_gate": "results/CodeDye/artifacts/generated/codedye_low_signal_claim_boundary_gate_20260505.json",
    }
    write_json(ROOT / "results/CodeDye/artifacts/generated/codedye_support_exclusion_inventory_fyp.json", payload)


def build_semcodebook_ablation_summary() -> None:
    gate = json.loads(
        (ROOT / "results/SemCodebook/artifacts/generated/semcodebook_generation_changing_ablation_promotion_gate_20260505.json").read_text(
            encoding="utf-8"
        )
    )
    summary = gate["fresh_result_summary"]
    payload = {
        "schema_version": "semcodebook_ablation_compact_summary_fyp_v1",
        "artifact_role": "compact_ablation_summary",
        "claim_bearing": False,
        "formal_ablation_claim_allowed": bool(gate.get("formal_ablation_claim_allowed")),
        "record_count": summary["record_count"],
        "required_tasks_per_arm": gate["promotion_contract"]["required_tasks_per_arm"],
        "arms": [
            {
                "arm": arm,
                "records": records,
                "tasks": summary["task_count_by_arm"][arm],
                "attacks": summary["attack_names_by_arm"][arm],
            }
            for arm, records in sorted(summary["by_arm"].items())
        ],
        "source_result_sha256": summary["sha256"],
        "source_result_path": summary["path"],
        "claim_boundary": "Ablation evidence supports method interpretation; it is not a first-sample/no-retry or universal watermarking claim.",
    }
    write_json(ROOT / "results/SemCodebook/artifacts/generated/semcodebook_ablation_compact_summary_fyp.json", payload)


def main() -> None:
    build_codedye_exclusion_inventory()
    build_semcodebook_ablation_summary()
    print("Wrote compact FYP artifacts.")


if __name__ == "__main__":
    main()
