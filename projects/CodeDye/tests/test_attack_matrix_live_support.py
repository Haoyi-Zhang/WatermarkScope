from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_attack_matrix_live_support as live_support
from codedye.benchmarks import load_code_dyebench_tasks


class AttackMatrixLiveSupportTest(unittest.TestCase):
    def test_attack_prompt_marks_support_condition_without_expected_label_leak(self) -> None:
        task = load_code_dyebench_tasks(ROOT)[0]
        prompt = live_support.build_attack_prompt(task, {"attack_id": "canary_preserving_rewrite"})

        self.assertIn("Audit condition", prompt)
        self.assertIn("Return only executable Python code", prompt)
        self.assertNotIn("expected_bit", prompt.lower())
        self.assertNotIn("target answer", prompt.lower())

    def test_live_runner_uses_language_aware_response_normalization(self) -> None:
        raw = (
            "#include <string>\n"
            "#include <vector>\n\n"
            "std::string solve(const std::string& input) {\n"
            "    return input;\n"
            "}\n"
        )
        normalized = live_support.normalize_code_response(raw, language="cpp")

        self.assertIn("#include <vector>", normalized)
        self.assertIn("std::string solve", normalized)
        self.assertIn("return input;", normalized)

    def test_summary_blocks_incomplete_live_contract(self) -> None:
        summary = live_support.summarize_records(
            [
                {
                    "attack_id": "chronology_shuffle",
                    "provider_mode_resolved": "mock",
                    "raw_payload_hash": "",
                    "structured_payload_hash": "structured",
                    "selected_utility_score": 1.0,
                }
            ],
            {"chronology_shuffle", "canary_preserving_rewrite"},
        )

        self.assertFalse(summary["gate_pass"])
        self.assertIn("mock_or_replay_provider_records:1", summary["blockers"])
        self.assertIn("payload_hash_records_missing:1", summary["blockers"])
        self.assertIn("required_attack_live_records_missing", summary["blockers"])
        self.assertIn("declared_attack_live_records_missing", summary["blockers"])

    def test_summary_passes_complete_support_contract(self) -> None:
        records = []
        for attack_id in sorted(live_support.REQUIRED_ATTACK_IDS | {"rename_identifiers"}):
            for index in range(live_support.MIN_ADMISSIBLE_RECORDS_PER_ATTACK):
                records.append(
                    {
                        "attack_id": attack_id,
                        "task_id": f"{attack_id}_{index}",
                        "provider_mode_resolved": "live",
                        "raw_payload_hash": "raw",
                        "structured_payload_hash": "structured",
                        "selected_utility_score": 1.0,
                        "claim_bearing_attack_evidence": True,
                        "support_only_not_claim_bearing": False,
                    }
                )
        for index in range(live_support.MIN_ADMISSIBLE_RECORDS_PER_ATTACK):
            records.append(
                {
                    "attack_id": "query_budget_drop",
                    "task_id": f"query_budget_drop_{index}",
                    "provider_mode_resolved": "live",
                    "raw_payload_hash": "raw",
                    "structured_payload_hash": "structured",
                    "selected_utility_score": 1.0,
                    "utility_admissible_for_attack_claim": True,
                    "claim_bearing": False,
                    "claim_bearing_attack_evidence": False,
                    "support_only_not_claim_bearing": True,
                }
            )

        summary = live_support.summarize_records(records, live_support.REQUIRED_ATTACK_IDS | live_support.SUPPORT_REQUIRED_ATTACK_IDS | {"rename_identifiers"})

        self.assertTrue(summary["gate_pass"])
        self.assertEqual([], summary["blockers"])
        self.assertEqual(20, summary["support_required_valid_record_count"])
        self.assertEqual(80, summary["claim_denominator_record_count"])

    def test_summary_keeps_utility_failures_as_failure_boundary_without_claim_credit(self) -> None:
        records = []
        for attack_id in sorted(live_support.REQUIRED_ATTACK_IDS | {"rename_identifiers"}):
            for index in range(live_support.MIN_ADMISSIBLE_RECORDS_PER_ATTACK):
                records.append(
                    {
                        "attack_id": attack_id,
                        "task_id": f"{attack_id}_{index}",
                        "language": "python",
                        "provider_mode_resolved": "live",
                        "raw_payload_hash": "raw",
                        "structured_payload_hash": "structured",
                        "selected_utility_score": 1.0,
                        "utility_admissible_for_attack_claim": True,
                        "claim_bearing_attack_evidence": True,
                        "support_only_not_claim_bearing": False,
                    }
                )
        for index in range(live_support.MIN_ADMISSIBLE_RECORDS_PER_ATTACK):
            records.append(
                {
                    "attack_id": "query_budget_drop",
                    "task_id": f"query_budget_drop_{index}",
                    "language": "python",
                    "provider_mode_resolved": "live",
                    "raw_payload_hash": "raw",
                    "structured_payload_hash": "structured",
                    "selected_utility_score": 1.0,
                    "utility_admissible_for_attack_claim": True,
                    "claim_bearing": False,
                    "claim_bearing_attack_evidence": False,
                    "support_only_not_claim_bearing": True,
                }
            )
        records.append(
            {
                "attack_id": "cross_language_reexpression",
                "task_id": "failed_cross_language",
                "language": "go",
                "provider_mode_resolved": "live",
                "raw_payload_hash": "raw",
                "structured_payload_hash": "structured",
                "selected_utility_score": 0.0,
                "utility_admissible_for_attack_claim": False,
                "claim_bearing": False,
                "claim_role": "utility_inadmissible_failure_boundary_not_main_claim",
            }
        )

        summary = live_support.summarize_records(records, live_support.REQUIRED_ATTACK_IDS | live_support.SUPPORT_REQUIRED_ATTACK_IDS | {"rename_identifiers"})

        self.assertTrue(summary["gate_pass"])
        self.assertEqual(1, summary["utility_failure_boundary_record_count"])
        self.assertEqual(20, summary["admissible_by_attack"]["cross_language_reexpression"])
        self.assertEqual(1, summary["utility_failure_by_attack"]["cross_language_reexpression"])
        self.assertIn("failure-boundary", summary["claim_boundary"])

    def test_summary_blocks_when_failure_boundary_leaves_attack_undercovered(self) -> None:
        records = []
        for index in range(live_support.MIN_ADMISSIBLE_RECORDS_PER_ATTACK - 1):
            records.append(
                {
                    "attack_id": "cross_language_reexpression",
                    "task_id": f"cross_ok_{index}",
                    "language": "typescript",
                    "provider_mode_resolved": "live",
                    "raw_payload_hash": "raw",
                    "structured_payload_hash": "structured",
                    "selected_utility_score": 1.0,
                    "utility_admissible_for_attack_claim": True,
                    "claim_bearing_attack_evidence": True,
                    "support_only_not_claim_bearing": False,
                }
            )
        for attack_id in sorted((live_support.REQUIRED_ATTACK_IDS | live_support.SUPPORT_REQUIRED_ATTACK_IDS | {"rename_identifiers"}) - {"cross_language_reexpression"}):
            for index in range(live_support.MIN_ADMISSIBLE_RECORDS_PER_ATTACK):
                support_only = attack_id in live_support.SUPPORT_REQUIRED_ATTACK_IDS
                records.append(
                    {
                        "attack_id": attack_id,
                        "task_id": f"{attack_id}_{index}",
                        "language": "python",
                        "provider_mode_resolved": "live",
                        "raw_payload_hash": "raw",
                        "structured_payload_hash": "structured",
                        "selected_utility_score": 1.0,
                        "utility_admissible_for_attack_claim": True,
                        "claim_bearing": False if support_only else True,
                        "claim_bearing_attack_evidence": not support_only,
                        "support_only_not_claim_bearing": support_only,
                    }
                )
        records.append(
            {
                "attack_id": "cross_language_reexpression",
                "task_id": "cross_fail",
                "language": "go",
                "provider_mode_resolved": "live",
                "raw_payload_hash": "raw",
                "structured_payload_hash": "structured",
                "selected_utility_score": 0.0,
                "utility_admissible_for_attack_claim": False,
            }
        )

        summary = live_support.summarize_records(records, live_support.REQUIRED_ATTACK_IDS | live_support.SUPPORT_REQUIRED_ATTACK_IDS | {"rename_identifiers"})

        self.assertFalse(summary["gate_pass"])
        self.assertIn(
            "attack_admissible_records_below_20:cross_language_reexpression:19/20",
            summary["blockers"],
        )

    def test_summary_blocks_missing_query_budget_support_records(self) -> None:
        records = []
        for attack_id in sorted(live_support.REQUIRED_ATTACK_IDS | {"rename_identifiers"}):
            for index in range(live_support.MIN_ADMISSIBLE_RECORDS_PER_ATTACK):
                records.append(
                    {
                        "attack_id": attack_id,
                        "task_id": f"{attack_id}_{index}",
                        "provider_mode_resolved": "live",
                        "raw_payload_hash": "raw",
                        "structured_payload_hash": "structured",
                        "selected_utility_score": 1.0,
                        "utility_admissible_for_attack_claim": True,
                        "claim_bearing_attack_evidence": True,
                        "support_only_not_claim_bearing": False,
                    }
                )

        summary = live_support.summarize_records(records, live_support.REQUIRED_ATTACK_IDS | live_support.SUPPORT_REQUIRED_ATTACK_IDS | {"rename_identifiers"})

        self.assertFalse(summary["gate_pass"])
        self.assertIn("support_required_attack_live_records_missing", summary["blockers"])

    def test_filter_rows_restricts_targeted_repair_health_without_claim_promotion(self) -> None:
        rows = [
            {"task_id": "a", "attack_id": "rename_identifiers"},
            {"task_id": "b", "attack_id": "rename_identifiers"},
            {"task_id": "a", "attack_id": "query_budget_drop"},
        ]

        filtered, status = live_support._filter_rows(
            rows,
            task_ids={"a"},
            attack_ids={"rename_identifiers"},
        )

        self.assertEqual([{"task_id": "a", "attack_id": "rename_identifiers"}], filtered)
        self.assertTrue(status["task_filter_enabled"])
        self.assertTrue(status["attack_filter_enabled"])
        self.assertEqual(3, status["input_row_count"])
        self.assertEqual(1, status["filtered_row_count"])
        self.assertIn("support-only", status["claim_policy_note"])

    def test_targeted_repair_health_can_pass_without_promoting_to_claim(self) -> None:
        records = [
            {
                "attack_id": "cross_language_reexpression",
                "provider_mode_resolved": "live",
                "raw_payload_hash": "raw",
                "structured_payload_hash": "structured",
                "selected_utility_score": 1.0,
            }
        ]
        full_summary = live_support.summarize_records(records, live_support.REQUIRED_ATTACK_IDS)
        repair_health = live_support.summarize_targeted_repair_health(
            records,
            {
                "task_filter_enabled": True,
                "attack_filter_enabled": True,
                "filtered_row_count": 1,
            },
            full_summary,
            requested_claim_bearing=False,
        )

        self.assertFalse(full_summary["gate_pass"])
        self.assertTrue(repair_health["repair_health_pass"])
        self.assertFalse(repair_health["formal_claim_allowed"])
        self.assertIn("required_attack_live_records_missing", repair_health["coverage_blockers_allowed"])

    def test_full_support_only_run_can_pass_support_gate_without_canonical_promotion(self) -> None:
        records = []
        declared = set(live_support.REQUIRED_ATTACK_IDS | live_support.SUPPORT_REQUIRED_ATTACK_IDS | {"rename_identifiers"})
        for attack_id in sorted(declared):
            for index in range(live_support.MIN_ADMISSIBLE_RECORDS_PER_ATTACK):
                records.append(
                    {
                        "attack_id": attack_id,
                        "task_id": f"{attack_id}_{index}",
                        "provider_mode_resolved": "live",
                        "raw_payload_hash": "raw",
                        "structured_payload_hash": "structured",
                        "selected_utility_score": 1.0,
                        "utility_admissible_for_attack_claim": True,
                        "claim_bearing": False,
                        "claim_bearing_attack_evidence": False,
                        "support_only_not_claim_bearing": True,
                    }
                )

        summary = live_support.summarize_records(records, declared)

        self.assertFalse(summary["gate_pass"])
        self.assertTrue(summary["support_gate_pass"])
        self.assertIn("declared_attack_live_records_missing", summary["blockers"])
        self.assertEqual([], summary["support_blockers"])


if __name__ == "__main__":
    unittest.main()
