from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sealaudit.benchmark_v2 import (
    FINAL_CONJUNCTION_GATES,
    HARD_AMBIGUITY_SPLIT,
    build_baseline_control_scaffold,
    build_blinded_curation_scaffold,
    build_case_provenance_cards,
    build_provenance_card,
    build_v2_gate_analysis,
    generate_v2_cases,
    summarize_v2_cases,
    validate_v2_cases,
)


class BenchmarkV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = generate_v2_cases()
        self.summary = summarize_v2_cases(self.cases)

    def test_v2_inventory_is_320_case_cartesian_scaffold(self) -> None:
        self.assertEqual(320, len(self.cases))
        self.assertEqual([], self.summary["inventory_issues"])
        self.assertEqual(80, self.summary["language_counts"]["python"])
        self.assertEqual(80, self.summary["scheme_kind_counts"]["latent_trojan"])
        self.assertEqual(160, self.summary["ambiguity_tier_counts"]["hard_ambiguity"])

    def test_hard_ambiguity_is_retained_not_threshold_fit(self) -> None:
        hard_cases = [item for item in self.cases if item["ambiguity_tier"] == "hard_ambiguity"]
        self.assertEqual(160, len(hard_cases))
        self.assertTrue(all(item["split"] == HARD_AMBIGUITY_SPLIT for item in hard_cases))
        self.assertTrue(all(item["threshold_fit_allowed"] is False for item in hard_cases))
        self.assertEqual(40, self.summary["threshold_fit_case_count"])

    def test_provider_execution_is_blocked_by_default(self) -> None:
        self.assertTrue(all(item["provider_execution_allowed"] is False for item in self.cases))
        self.assertEqual(0, self.summary["provider_execution_allowed_count"])

    def test_v2_cases_include_case_bound_executable_fixtures(self) -> None:
        self.assertEqual(320, self.summary["candidate_executable_code_count"])
        for item in self.cases:
            self.assertTrue(str(item["candidate_executable_code"]).strip())
            self.assertEqual(
                "deterministic_case_bound_executable_fixture",
                item["candidate_contract"]["materialization_status"],
            )
            self.assertEqual("fixture_reference_tests_declared", item["test_contract"]["status"])
            self.assertIn("candidate_executable_code_sha256", item)

    def test_curation_and_provenance_scaffolds_are_blinded(self) -> None:
        curation = build_blinded_curation_scaffold(self.cases)
        self.assertEqual(320, len(curation["packets"]))
        self.assertIn("expected_verdict", curation["rubric"]["blind_fields_hidden"])
        self.assertTrue(str(curation["packets"][0]["blind_case_id"]).startswith("blind_"))
        provenance = build_provenance_card(self.cases)
        self.assertFalse(provenance["main_table_admissible"])
        self.assertEqual("not_run", provenance["provider_execution_status"])

    def test_baseline_control_scaffold_includes_negative_controls(self) -> None:
        controls = build_baseline_control_scaffold(self.cases)
        names = {item["name"] for item in controls["controls"]}
        self.assertIn("random_owner_negative", names)
        self.assertIn("decoy_signal_negative", names)
        self.assertIn("provider_canary_deepseek", names)

    def test_case_provenance_cards_are_label_blinded(self) -> None:
        cards = build_case_provenance_cards(self.cases)
        self.assertEqual(320, cards["card_count"])
        first = cards["cards"][0]
        self.assertIn("hidden_label_commitment", first)
        self.assertNotIn("case_id", first)
        self.assertNotIn("expected_verdict", first)
        self.assertNotIn("scheme_kind", first)

    def test_v2_gate_analysis_keeps_cases_out_of_claim_table(self) -> None:
        analysis = build_v2_gate_analysis(self.cases)
        self.assertEqual(320, analysis["case_analysis"]["record_count"])
        self.assertEqual(160, analysis["hard_ambiguity_retention"]["retained_case_count"])
        self.assertEqual(160, analysis["hard_ambiguity_retention"]["threshold_fit_excluded_count"])
        self.assertFalse(analysis["admission_decision"]["main_table_admissible"])
        self.assertEqual(0, analysis["evidence_track_gate"]["final_conjunction"]["pass_count"])
        self.assertEqual(0, analysis["baseline_control_evidence"]["claim_evidence_count"])
        self.assertEqual(40, analysis["statistical_sensitivity"]["threshold_fit_case_count"])
        self.assertEqual(160, analysis["statistical_sensitivity"]["hard_ambiguity_excluded_from_threshold_count"])
        removed = {
            item["removed_gate"]
            for item in analysis["final_conjunction_ablation"]["single_gate_removal"]
        }
        self.assertEqual(set(FINAL_CONJUNCTION_GATES), removed)

    def test_validation_catches_inventory_issues(self) -> None:
        broken = list(self.cases)
        broken[0] = {**broken[0], "provider_execution_allowed": True}
        issues = validate_v2_cases(broken)
        self.assertTrue(any(issue.startswith("provider_execution_not_blocked") for issue in issues))


if __name__ == "__main__":
    unittest.main()
