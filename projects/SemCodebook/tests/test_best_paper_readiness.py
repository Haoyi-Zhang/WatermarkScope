from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "generated"


class BestPaperReadinessTest(unittest.TestCase):
    def test_readiness_artifact_is_fail_closed_and_claim_locked(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/build_semcodebook_best_paper_readiness.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, msg=completed.stderr)
        payload = json.loads((ARTIFACTS / "semcodebook_best_paper_readiness.json").read_text(encoding="utf-8"))

        self.assertEqual("semcodebook_best_paper_readiness_v1", payload["schema_version"])
        self.assertFalse(payload["formal_experiment_allowed"])
        self.assertEqual("pre_run_best_paper_gate_not_claim_bearing", payload["artifact_role"])
        self.assertEqual(
            {
                "method_schema",
                "carrierstressbench_workload",
                "baseline_admission",
                "negative_control",
                "attack_matrix",
                "statistics_ablation",
                "claim_runops",
            },
            set(payload["dimensions"]),
        )

        benchmark = payload["dimensions"]["carrierstressbench_workload"]
        self.assertGreaterEqual(benchmark["task_count_implemented"], 600)
        self.assertEqual(6, len(benchmark["family_counts"]))
        self.assertEqual(5, len(benchmark["language_counts"]))
        self.assertEqual(7200, benchmark["expected_record_count"])
        self.assertFalse(benchmark["formal_full_run_allowed"])
        self.assertEqual("carrierstressbench_prerun_gate_blocked", benchmark["blocker"])
        method = payload["dimensions"]["method_schema"]
        self.assertEqual("stale_not_claim_bearing", method["method_schema_gate_status"])
        self.assertFalse(method["method_schema_gate_claim_bearing"])
        self.assertEqual("python scripts/build_method_schema_gate.py --check", method["method_schema_gate_check"])

        negative = payload["dimensions"]["negative_control"]
        if negative["negative_control_detection_count"]:
            self.assertEqual("fail", negative["status"])
            self.assertIn("threshold relaxation", negative["promotion_rule"])

        claim = payload["paper_claim"]
        self.assertIn("semantic-rewrite provenance watermark", claim["locked_claim"])
        self.assertIn("diagnostic or canary results as main-table evidence", claim["forbidden_claims"])
        self.assertIn("main claims", claim["main_table_policy"])
        self.assertIn("claim_runops_gate_status", claim)
        stats = payload["dimensions"]["statistics_ablation"]
        self.assertTrue(stats["preregistration_ready"])
        self.assertEqual(7200, stats["target_expected_record_count"])
        self.assertGreaterEqual(stats["carrier_ablation_count"], 3)
        self.assertGreaterEqual(stats["ecc_ablation_count"], 1)
        self.assertGreaterEqual(stats["keyed_schedule_ablation_count"], 1)
        self.assertEqual(
            "python scripts/build_claim_runops_gate.py --check",
            payload["dimensions"]["claim_runops"]["check_command"],
        )


if __name__ == "__main__":
    unittest.main()
