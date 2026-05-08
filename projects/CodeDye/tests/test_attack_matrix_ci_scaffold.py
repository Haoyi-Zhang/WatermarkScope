from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "codedye_attack_matrix_ci_scaffold",
        ROOT / "scripts" / "run_attack_matrix_ci_scaffold.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_negative_control_module():
    spec = importlib.util.spec_from_file_location(
        "codedye_null_calibration_negative_controls",
        ROOT / "scripts" / "materialize_null_calibration_negative_controls.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


class AttackMatrixCiScaffoldTest(unittest.TestCase):
    def test_scaffold_script_has_main_guard(self) -> None:
        source = (ROOT / "scripts" / "run_attack_matrix_ci_scaffold.py").read_text(encoding="utf-8")
        self.assertIn('if __name__ == "__main__":', source)
        self.assertRegex(source, r'if __name__ == "__main__":\s*\n\s+main\(\)')

    def test_canary_preserving_rewrite_changes_all_generated_languages(self) -> None:
        module = _load_module()
        from codedye.benchmarks import load_code_dyebench_tasks

        tasks = load_code_dyebench_tasks(ROOT)
        sampled_by_language = {}
        for task in tasks:
            if task.subset != "canary_preserving_rewrites":
                continue
            if task.language in {"python", "typescript", "java", "cpp", "go"} and task.language not in sampled_by_language:
                sampled_by_language[task.language] = task
        self.assertEqual({"python", "typescript", "java", "cpp", "go"}, set(sampled_by_language))
        for language, task in sampled_by_language.items():
            rendered, transform_kind, metadata = module._transform_code(task, "canary_preserving_rewrite")
            self.assertEqual("semantic_unreachable_branch_rewrite", transform_kind)
            self.assertNotEqual(task.reference_code, rendered, msg=language)
            self.assertTrue(metadata["rewrite_supported"], msg=language)
            self.assertTrue(metadata["rewrite_changed_code"], msg=language)

    def test_mutation_required_attacks_reject_noop_rows(self) -> None:
        module = _load_module()
        rows = [
            {
                "attack_id": "rename_identifiers",
                "subset": "fresh_unseen_tasks",
                "code_changed": False,
                "utility_preserved": True,
                "canary_preserved": True,
                "placeholder_transform": False,
            },
            {
                "attack_id": "chronology_shuffle",
                "subset": "prompt_chronology",
                "code_changed": False,
                "utility_preserved": True,
                "canary_preserved": True,
                "placeholder_transform": False,
                "transform_metadata": {
                    "matched_chronology_control": True,
                    "original_release_window": "2026Q1",
                    "shuffled_release_window": "2026Q2",
                },
            },
        ]
        contract = module._attack_record_contract(rows, {"attacks": [{"attack_id": "rename_identifiers"}, {"attack_id": "chronology_shuffle"}]})
        self.assertFalse(contract["gate_pass"])
        self.assertEqual(1, contract["mutation_required_noop_count"])
        self.assertEqual(1, contract["mutation_required_noop_counts"]["rename_identifiers"])
        self.assertIn("mutation_required_attack_noop_rows_detected", contract["blockers"])
        self.assertNotIn("chronology_shuffle_unmatched_or_unchanged", contract["blockers"])

    def test_embedded_empirical_null_pool_is_support_only_without_explicit_negative_controls(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            _write_json(
                tmp_root / "artifacts" / "generated" / "full_eval_results.json",
                {
                    "records": [
                        {
                            "task_id": f"task_{index}",
                            "is_negative_control": False,
                            "null_calibration_method": "metadata_matched_empirical_dominance_tail_bound",
                            "null_pool_strategy": "metadata_matched_hard_negative_tier_7_of_8_no_outcome_selection",
                            "null_pool_fallback_used": False,
                            "null_sample_size": 30,
                            "family": "unit_family",
                            "p_value_or_score": 1.0,
                        }
                        for index in range(3)
                    ],
                },
            )
            old_root = module.ROOT
            module.ROOT = tmp_root
            try:
                payload = module._null_calibration_contract()
            finally:
                module.ROOT = old_root

        self.assertFalse(payload["gate_pass"])
        self.assertEqual(0, payload["negative_control_record_count"])
        self.assertEqual(90, payload["empirical_null_sample_count"])
        self.assertEqual("embedded_metadata_matched_empirical_null_pool_support_only", payload["negative_control_source"])
        self.assertIn("negative_control_record_count_below_120:0", payload["blockers"])
        self.assertIn("explicit_negative_control_artifact_missing", payload["blockers"])

    def test_explicit_stratified_negative_control_artifact_closes_null_control_gate(self) -> None:
        module = _load_module()
        neg_module = _load_negative_control_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            full_eval = tmp_root / "artifacts" / "generated" / "full_eval_results.json"
            records = []
            subsets = (
                "prompt_chronology",
                "fresh_unseen_tasks",
                "semantic_canaries",
                "cross_language_variants",
                "canary_preserving_rewrites",
            )
            for index, subset in enumerate(subsets):
                count = 65 if subset == "prompt_chronology" else 15
                for offset in range(count):
                    record_index = index * 100 + offset
                    records.append(
                        {
                            "task_id": f"{subset}_task_{offset:03d}",
                            "task_hash": f"task-hash-{record_index:03d}",
                            "task_provenance_hash": f"prov-hash-{record_index:03d}",
                            "provenance_hash": f"prov-hash-{record_index:03d}",
                            "benchmark": "CodeDyeBench",
                            "subset": subset,
                            "family": f"family_{offset % 6}",
                            "language": ["python", "typescript", "java", "cpp", "go"][offset % 5],
                            "canary_split": ["chronology_marker", "family_pack", "semantic_pack", "rewrite_marker"][offset % 4],
                            "chronology_split": ["same_window", "staggered_window", "post_release_holdout"][offset % 3],
                            "release_window": ["2026Q1", "2026Q2", "2026Q3", "2026Q4"][offset % 4],
                            "provider_name": "DeepSeek",
                            "provider_mode_resolved": "live",
                            "prompt_hash": f"prompt-{record_index:03d}",
                            "raw_provider_transcript_hash": f"transcript-{record_index:03d}",
                            "contaminated": False,
                            "is_negative_control": False,
                            "null_calibration_method": "metadata_matched_empirical_dominance_tail_bound",
                            "null_pool_strategy": "metadata_matched_hard_negative_tier_7_of_8_no_outcome_selection",
                            "null_pool_fallback_used": False,
                            "null_sample_size": 30,
                            "p_value_or_score": 1.0,
                        }
                    )
            canonical_records = []
            for item in records[:5]:
                canonical = dict(item)
                canonical["is_negative_control"] = True
                canonical["false_positive_bound"] = 0.02
                canonical_records.append(canonical)
            _write_json(full_eval, {"records": canonical_records + records})
            artifact = neg_module.build_negative_control_payload(full_eval_path=full_eval)
            _write_json(tmp_root / "artifacts" / "generated" / "null_calibration_negative_controls.json", artifact)
            old_root = module.ROOT
            module.ROOT = tmp_root
            try:
                payload = module._null_calibration_contract()
            finally:
                module.ROOT = old_root

        self.assertTrue(payload["gate_pass"])
        self.assertEqual(120, payload["negative_control_record_count"])
        self.assertEqual(5, payload["canonical_embedded_negative_control_record_count"])
        self.assertEqual(0, payload["negative_control_false_positive_count"])
        self.assertLessEqual(payload["max_negative_control_false_positive_bound"], 0.025)
        self.assertEqual("explicit_negative_control_records", payload["negative_control_source"])
        self.assertTrue(payload["explicit_negative_control_artifact_gate_pass"])
        self.assertLessEqual(payload["negative_control_ci95_high"], 0.025)
        self.assertEqual(120, artifact["record_count"])
        self.assertLessEqual(artifact["ci"]["ci95_high"], 0.025)
        self.assertTrue(artifact["ci"]["gate_pass"])
        for subset in subsets:
            self.assertGreaterEqual(artifact["stratification"]["subset_counts"][subset], 15)

    def test_query_budget_support_artifact_preferred_when_it_has_more_provider_samples(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            canonical = tmp_root / "artifacts" / "generated" / "full_eval_results.json"
            support = tmp_root / "artifacts" / "generated" / "query_budget_drop_support_full_eval.json"
            _write_json(
                canonical,
                {
                    "run_id": "canonical_support",
                    "records": [
                        {
                            "task_id": "task_a",
                            "candidate_sample_count": 1,
                            "candidate_samples": [{"sample_index": 0}],
                        }
                    ],
                },
            )
            _write_json(
                support,
                {
                    "run_id": "query_budget_support",
                    "records": [
                        {
                            "task_id": "task_a",
                            "candidate_sample_count": 4,
                            "candidate_samples": [{"sample_index": index} for index in range(4)],
                        }
                    ],
                },
            )
            old_root = module.ROOT
            module.ROOT = tmp_root
            try:
                records = module._full_eval_records_by_task(support)
            finally:
                module.ROOT = old_root

        self.assertEqual(4, module._record_candidate_sample_count(records["task_a"]))
        self.assertEqual("query_budget_multisample_support_full_eval", records["task_a"]["_provider_record_source_role"])
        self.assertEqual("query_budget_support", records["task_a"]["_provider_record_source_run_id"])

    def test_required_query_budget_attack_accepts_support_only_rows_outside_main_claim(self) -> None:
        module = _load_module()
        rows = []
        for attack_id in module.REQUIRED_ATTACK_IDS:
            for index in range(module.MIN_ADMISSIBLE_RECORDS_PER_ATTACK):
                language = ["typescript", "java", "go", "cpp"][index % 4] if attack_id == "cross_language_reexpression" else "python"
                rows.append(
                    {
                        "attack_id": attack_id,
                        "subset": "fresh_unseen_tasks",
                        "language": language,
                        "code_changed": True,
                        "utility_preserved": True,
                        "canary_preserved": True,
                        "placeholder_transform": False,
                        "support_only_not_claim_bearing": False,
                        "claim_bearing_attack_evidence": True,
                        "utility_admissible_for_attack_claim": True,
                        "transform_metadata": {
                            "matched_chronology_control": True,
                            "original_release_window": "2026Q1",
                            "shuffled_release_window": "2026Q2",
                            "cross_language_provenance_locked": True,
                            "cross_language_source_task_found": True,
                            "source_target_languages_differ": True,
                            "source_target_same_template": True,
                            "source_target_same_canary_pack": True,
                            "source_task_id": f"source_{index}",
                            "source_provenance_hash": f"source_prov_{index}",
                            "target_provenance_hash": f"target_prov_{index}",
                            "source_target_binding_hash": f"binding_{index}",
                        },
                    }
                )
        for _ in range(module.MIN_ADMISSIBLE_RECORDS_PER_ATTACK):
            rows.append(
                {
                    "attack_id": "query_budget_drop",
                    "subset": "fresh_unseen_tasks",
                    "provider_mode_resolved": "live",
                    "raw_payload_hash": "raw",
                    "structured_payload_hash": "structured",
                    "code_changed": False,
                    "utility_preserved": True,
                    "canary_preserved": True,
                    "placeholder_transform": False,
                    "support_only_not_claim_bearing": True,
                    "claim_bearing_attack_evidence": False,
                    "utility_admissible_for_attack_claim": True,
                    "transform_metadata": {
                        "provider_record_source_role": "query_budget_multisample_support_full_eval",
                    },
                }
            )
        attack_matrix = {"attacks": [{"attack_id": attack_id} for attack_id in module.REQUIRED_ATTACK_IDS | module.SUPPORT_REQUIRED_ATTACK_IDS]}
        contract = module._attack_record_contract(rows, attack_matrix)
        self.assertTrue(contract["gate_pass"])
        self.assertEqual(0, contract["required_support_only_record_count"])
        self.assertEqual(module.MIN_ADMISSIBLE_RECORDS_PER_ATTACK, contract["query_budget_support_required_valid_record_count"])
        self.assertNotIn("required_attack_rows_support_only_not_claim_bearing", contract["blockers"])

    def test_query_budget_attack_no_longer_counts_canonical_rows_toward_main_claim_denominator(self) -> None:
        module = _load_module()
        rows = []
        for _ in range(module.MIN_ADMISSIBLE_RECORDS_PER_ATTACK):
            rows.append(
                {
                    "attack_id": "query_budget_drop",
                    "subset": "fresh_unseen_tasks",
                    "code_changed": False,
                    "utility_preserved": True,
                    "canary_preserved": True,
                    "placeholder_transform": False,
                    "support_only_not_claim_bearing": False,
                    "claim_bearing_attack_evidence": True,
                    "transform_metadata": {
                        "query_budget_drop_supported": True,
                        "support_only_not_claim_bearing": False,
                        "provider_record_source_role": "canonical_live_full_eval",
                    },
                }
            )
        attack_matrix = {"attacks": [{"attack_id": "query_budget_drop"}]}
        contract = module._attack_record_contract(rows, attack_matrix)
        self.assertEqual(
            module.MIN_ADMISSIBLE_RECORDS_PER_ATTACK,
            contract["query_budget_claim_bearing_supported_record_count"],
        )
        self.assertEqual(0, contract["claim_denominator_record_count"])
        self.assertEqual(0, contract["required_support_only_record_count"])
        self.assertNotIn("required_attack_rows_support_only_not_claim_bearing", contract["blockers"])
        self.assertIn("query_budget_drop_support_records_below_minimum", contract["blockers"])

    def test_comment_whitespace_locked_control_does_not_require_null_control_summary(self) -> None:
        module = _load_module()
        rows = []
        for attack_id in module.REQUIRED_ATTACK_IDS:
            for index in range(module.MIN_ADMISSIBLE_RECORDS_PER_ATTACK):
                language = ["typescript", "java", "go", "cpp"][index % 4] if attack_id == "cross_language_reexpression" else "python"
                rows.append(
                    {
                        "attack_id": attack_id,
                        "subset": "fresh_unseen_tasks",
                        "language": language,
                        "code_changed": True,
                        "utility_preserved": True,
                        "canary_preserved": True,
                        "placeholder_transform": False,
                        "support_only_not_claim_bearing": False,
                        "claim_bearing_attack_evidence": True,
                        "utility_admissible_for_attack_claim": True,
                        "transform_metadata": {
                            "matched_chronology_control": True,
                            "original_release_window": "2026Q1",
                            "shuffled_release_window": "2026Q2",
                            "cross_language_provenance_locked": True,
                            "cross_language_source_task_found": True,
                            "source_target_languages_differ": True,
                            "source_target_same_template": True,
                            "source_target_same_canary_pack": True,
                            "source_task_id": f"source_{index}",
                            "source_provenance_hash": f"source_prov_{index}",
                            "target_provenance_hash": f"target_prov_{index}",
                            "source_target_binding_hash": f"binding_{index}",
                        },
                    }
                )
        for index in range(module.MIN_ADMISSIBLE_RECORDS_PER_ATTACK):
            rows.append(
                {
                    "attack_id": "query_budget_drop",
                    "subset": "fresh_unseen_tasks",
                    "provider_mode_resolved": "live",
                    "raw_payload_hash": "raw",
                    "structured_payload_hash": "structured",
                    "code_changed": False,
                    "utility_preserved": True,
                    "canary_preserved": True,
                    "placeholder_transform": False,
                    "support_only_not_claim_bearing": True,
                    "claim_bearing_attack_evidence": False,
                    "utility_admissible_for_attack_claim": True,
                    "transform_metadata": {},
                }
            )
        for index in range(module.MIN_ADMISSIBLE_RECORDS_PER_ATTACK):
            rows.append(
                {
                    "attack_id": "comment_whitespace_normalize",
                    "subset": "fresh_unseen_tasks",
                    "language": "python",
                    "code_changed": False,
                    "utility_preserved": True,
                    "canary_preserved": True,
                    "placeholder_transform": False,
                    "support_only_not_claim_bearing": False,
                    "claim_bearing_attack_evidence": True,
                    "utility_admissible_for_attack_claim": True,
                    "transform_metadata": {
                        "semantic_noop_attack_boundary": "format_preserving_comment_whitespace_normalization",
                        "comment_whitespace_noop_locked": True,
                        "code_change_required": False,
                        "mutation_required_attack": False,
                        "matched_null_control_required": True,
                        "no_outcome_selection_required": True,
                        "source_task_id": f"comment_source_{index}",
                        "source_reference_code_sha256": f"comment_code_{index}",
                        "source_provenance_hash": f"comment_prov_{index}",
                    },
                }
            )
        attack_matrix = {"attacks": [{"attack_id": attack_id} for attack_id in module.REQUIRED_ATTACK_IDS | module.SUPPORT_REQUIRED_ATTACK_IDS | {"comment_whitespace_normalize"}]}

        contract = module._attack_record_contract(rows, attack_matrix)

        self.assertTrue(contract["gate_pass"])
        self.assertEqual(module.MIN_ADMISSIBLE_RECORDS_PER_ATTACK, contract["query_budget_support_required_valid_record_count"])
        self.assertNotIn("comment_whitespace_normalize_semantic_noop_boundary_missing", contract["blockers"])

    def test_failure_boundary_rows_do_not_count_toward_claim_coverage(self) -> None:
        module = _load_module()
        rows = []
        for index in range(module.MIN_ADMISSIBLE_RECORDS_PER_ATTACK - 1):
            rows.append(
                {
                    "attack_id": "query_budget_drop",
                    "subset": "fresh_unseen_tasks",
                    "code_changed": False,
                    "utility_preserved": True,
                    "canary_preserved": True,
                    "placeholder_transform": False,
                    "support_only_not_claim_bearing": False,
                    "claim_bearing_attack_evidence": True,
                    "utility_admissible_for_attack_claim": True,
                    "transform_metadata": {
                        "query_budget_drop_supported": True,
                        "support_only_not_claim_bearing": False,
                        "provider_record_source_role": "canonical_live_full_eval",
                    },
                }
            )
        rows.append(
            {
                "attack_id": "query_budget_drop",
                "subset": "fresh_unseen_tasks",
                "code_changed": False,
                "utility_preserved": False,
                "canary_preserved": True,
                "placeholder_transform": False,
                "support_only_not_claim_bearing": True,
                "claim_bearing_attack_evidence": False,
                "utility_admissible_for_attack_claim": False,
                "claim_role": "utility_inadmissible_failure_boundary_not_main_claim",
                "transform_metadata": {
                    "query_budget_drop_supported": True,
                    "support_only_not_claim_bearing": True,
                    "provider_record_source_role": "canonical_live_full_eval",
                },
            }
        )
        attack_matrix = {"attacks": [{"attack_id": "query_budget_drop"}]}

        contract = module._attack_record_contract(rows, attack_matrix)

        self.assertFalse(contract["gate_pass"])
        self.assertEqual(19, contract["query_budget_claim_bearing_supported_record_count"])
        self.assertEqual(1, contract["utility_failure_boundary_record_count"])
        self.assertIn("query_budget_drop_support_records_below_minimum", contract["blockers"])
        self.assertNotIn("attack_admissible_records_below_20:query_budget_drop:19/20", contract["blockers"])

    def test_cross_language_rows_require_source_target_provenance_lock(self) -> None:
        module = _load_module()
        rows = [
            {
                "attack_id": "cross_language_reexpression",
                "subset": "cross_language_variants",
                "language": "typescript",
                "utility_preserved": True,
                "canary_preserved": True,
                "placeholder_transform": False,
                "support_only_not_claim_bearing": False,
                "claim_bearing_attack_evidence": True,
                "transform_metadata": {
                    "target_language": "typescript",
                    "pre_materialized_non_python_variant": True,
                    "cross_language_provenance_locked": False,
                },
            }
        ]
        attack_matrix = {"attacks": [{"attack_id": "cross_language_reexpression"}]}
        contract = module._attack_record_contract(rows, attack_matrix)
        self.assertFalse(contract["gate_pass"])
        self.assertEqual(1, contract["cross_language_provenance_unlocked_count"])
        self.assertIn("cross_language_reexpression_source_target_provenance_unlocked", contract["blockers"])

    def test_cross_language_transform_binds_non_python_target_to_python_source(self) -> None:
        module = _load_module()
        from codedye.benchmarks import load_code_dyebench_tasks

        tasks = load_code_dyebench_tasks(ROOT)
        target = next(
            task
            for task in tasks
            if task.subset == "cross_language_variants"
            and task.language.lower() == "typescript"
            and "reverse_words" in task.task_id
        )
        _, transform_kind, metadata = module._transform_code(target, "cross_language_reexpression", tasks=tasks)
        self.assertEqual("pre_materialized_multilanguage_reexpression", transform_kind)
        self.assertTrue(metadata["cross_language_provenance_locked"])
        self.assertEqual("python", metadata["source_language"])
        self.assertEqual("typescript", metadata["target_language"])
        self.assertNotEqual(metadata["source_task_id"], metadata["target_task_id"])
        self.assertTrue(metadata["source_target_languages_differ"])
        self.assertTrue(metadata["source_target_same_template"])
        self.assertTrue(metadata["source_target_same_canary_pack"])
        self.assertTrue(metadata["source_provenance_hash"])
        self.assertTrue(metadata["target_provenance_hash"])
        self.assertTrue(metadata["source_target_binding_hash"])

    def test_comment_whitespace_normalize_has_explicit_noop_boundary(self) -> None:
        module = _load_module()
        from codedye.benchmarks import load_code_dyebench_tasks

        task = next(task for task in load_code_dyebench_tasks(ROOT) if task.language.lower() == "python")
        rendered, transform_kind, metadata = module._transform_code(task, "comment_whitespace_normalize")

        self.assertEqual("format_preserving_comment_strip", transform_kind)
        self.assertTrue(rendered.endswith("\n"))
        self.assertEqual("format_preserving_comment_whitespace_normalization", metadata["semantic_noop_attack_boundary"])
        self.assertEqual("comment_whitespace_noop_v1", metadata["semantic_noop_boundary_version"])
        self.assertTrue(metadata["comment_whitespace_noop_locked"])
        self.assertFalse(metadata["code_change_required"])
        self.assertFalse(metadata["mutation_required_attack"])
        self.assertTrue(metadata["matched_null_control_required"])
        self.assertTrue(metadata["no_outcome_selection_required"])
        self.assertEqual(task.task_id, metadata["source_task_id"])
        self.assertTrue(metadata["source_reference_code_sha256"])
        self.assertTrue(metadata["source_provenance_hash"])

    def test_comment_whitespace_contract_rejects_missing_noop_boundary(self) -> None:
        module = _load_module()
        rows = [
            {
                "attack_id": "comment_whitespace_normalize",
                "subset": "fresh_unseen_tasks",
                "code_changed": False,
                "utility_preserved": True,
                "canary_preserved": True,
                "placeholder_transform": False,
                "support_only_not_claim_bearing": False,
                "claim_bearing_attack_evidence": True,
                "transform_metadata": {},
                "null_control_summary": {"no_outcome_selection": True},
            }
        ]
        contract = module._attack_record_contract(rows, {"attacks": [{"attack_id": "comment_whitespace_normalize"}]})

        self.assertFalse(contract["gate_pass"])
        self.assertEqual(1, contract["comment_whitespace_noop_boundary_unlocked_count"])
        self.assertIn("comment_whitespace_normalize_semantic_noop_boundary_missing", contract["blockers"])


if __name__ == "__main__":
    unittest.main()
