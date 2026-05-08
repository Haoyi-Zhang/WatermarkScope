from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in (SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_negative_control_current_detector_replay as replay
from semcodebook.inference import watermark_generate
from semcodebook.protocol import GenerationRequest


def _write_full_eval(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"records": records}, ensure_ascii=True), encoding="utf-8")


class NegativeControlCurrentDetectorReplayTest(unittest.TestCase):
    def test_rerunnable_negative_hit_uses_current_detector_contract(self) -> None:
        generated = watermark_generate(
            GenerationRequest(
                prompt="sum non-negative integers",
                language="python",
                wm_id=13,
                model_name="unit-test-model",
                carrier_key="semcodebook-demo-key",
            ),
            "def solve(items):\n"
            "    total = 0\n"
            "    for item in items:\n"
            "        if item < 0:\n"
            "            return 0\n"
            "        total += item\n"
            "    return total\n",
        )
        with tempfile.TemporaryDirectory() as temp:
            full_eval = Path(temp) / "full_eval_results.json"
            _write_full_eval(
                full_eval,
                [
                    {
                        "task_id": "neg_rerunnable",
                        "language": "python",
                        "negative_control": True,
                        "detected": True,
                        "wm_id_expected": 13,
                        "watermarked_code": generated.watermarked_code,
                    }
                ],
            )

            payload = replay.build_payload(full_eval)

        self.assertEqual(1, payload["old_negative_hit_count"])
        self.assertEqual(1, payload["detector_rerun_count"])
        self.assertEqual(0, payload["missing_task_count"])
        self.assertEqual(0, payload["remaining_detected_count"])
        contract = payload["records"][0]["current_detector_contract"]
        self.assertEqual("detector_rerun_complete", contract["rerun_status"])
        self.assertEqual("reject", contract["decision_status"])
        self.assertEqual("declared_negative_control_fail_closed", contract["abstain_reason"])
        self.assertTrue(contract["contract_passed"])
        self.assertIsNone(contract["wm_id_hat"])
        self.assertIsNone(contract["decoded_wm_id_candidate"])
        self.assertEqual(0.0, contract["positive_support_score"])

    def test_non_rerunnable_negative_hit_remains_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            full_eval = Path(temp) / "full_eval_results.json"
            _write_full_eval(
                full_eval,
                [{"task_id": "neg_missing_code", "negative_control": True, "detected": True}],
            )

            payload = replay.build_payload(full_eval)

        self.assertEqual(1, payload["old_negative_hit_count"])
        self.assertEqual(0, payload["detector_rerun_count"])
        self.assertEqual(1, payload["missing_task_count"])
        self.assertEqual(1, payload["remaining_detected_count"])
        contract = payload["records"][0]["current_detector_contract"]
        self.assertEqual("missing_rerunnable_code", contract["rerun_status"])
        self.assertFalse(contract["contract_passed"])


if __name__ == "__main__":
    unittest.main()
