from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_method_schema_gate as gate


def _write_full_eval(path: Path, records: list[object]) -> None:
    path.write_text(json.dumps({"records": records, "meta": {"mode": "unit"}}, ensure_ascii=True), encoding="utf-8")


class MethodSchemaGateTest(unittest.TestCase):
    def test_old_full_eval_missing_detector_fields_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            full_eval = Path(temp) / "full_eval_results.json"
            _write_full_eval(full_eval, [{"detected": True, "support_ratio": 1.0}])

            manifest = gate.build_manifest(full_eval_path=full_eval)

        self.assertEqual("stale_not_claim_bearing", manifest["status"])
        self.assertFalse(manifest["claim_bearing"])
        self.assertIn("decision_status", manifest["required_record_schema"]["missing_required_fields"])
        self.assertIn("positive_support_score", manifest["required_record_schema"]["missing_required_fields"])
        self.assertIn("positive_support_family_count", manifest["required_record_schema"]["missing_required_fields"])
        self.assertIn("carrier_signal_coverage", manifest["required_record_schema"]["missing_required_fields"])

    def test_full_eval_with_latest_detector_fields_is_claim_bearing(self) -> None:
        latest_record = {
            "decision_status": "watermarked",
            "abstain_reason": None,
            "positive_support_score": 1.0,
            "positive_support_family_count": 2,
            "positive_support_level_count": 2,
            "carrier_signal_coverage": 0.75,
        }
        with tempfile.TemporaryDirectory() as temp:
            full_eval = Path(temp) / "full_eval_results.json"
            _write_full_eval(full_eval, [latest_record])

            manifest = gate.build_manifest(full_eval_path=full_eval)

        self.assertEqual("claim_bearing", manifest["status"])
        self.assertTrue(manifest["claim_bearing"])
        self.assertEqual([], manifest["required_record_schema"]["missing_required_fields"])
        self.assertEqual([], manifest["blockers"])

    def test_check_fails_even_when_stale_manifest_matches_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            full_eval = Path(temp) / "full_eval_results.json"
            output = Path(temp) / "method_schema_gate.json"
            _write_full_eval(full_eval, [{"detected": True}])

            with contextlib.redirect_stdout(io.StringIO()):
                build_status = gate.main(["--full-eval", str(full_eval), "--output", str(output)])
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                check_status = gate.main(["--full-eval", str(full_eval), "--output", str(output), "--check"])

        self.assertEqual(0, build_status)
        self.assertEqual(1, check_status)
        self.assertIn("stale_not_claim_bearing", stderr.getvalue())

    def test_check_passes_for_current_matching_manifest(self) -> None:
        latest_record = {
            "decision_status": "watermarked",
            "abstain_reason": None,
            "positive_support_score": 1.0,
            "positive_support_family_count": 2,
            "positive_support_level_count": 2,
            "carrier_signal_coverage": 0.75,
        }
        with tempfile.TemporaryDirectory() as temp:
            full_eval = Path(temp) / "full_eval_results.json"
            output = Path(temp) / "method_schema_gate.json"
            _write_full_eval(full_eval, [latest_record])

            with contextlib.redirect_stdout(io.StringIO()):
                build_status = gate.main(["--full-eval", str(full_eval), "--output", str(output)])
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                check_status = gate.main(["--full-eval", str(full_eval), "--output", str(output), "--check"])

        self.assertEqual(0, build_status)
        self.assertEqual(0, check_status)
        self.assertIn('"status": "ok"', stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
