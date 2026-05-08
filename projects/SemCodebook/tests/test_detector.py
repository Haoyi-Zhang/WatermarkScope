from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from semcodebook.detector import SemCodebookDetector
from semcodebook.inference import _target_aligned_schedule, watermark_generate
from semcodebook.attacks import rename_identifiers
from semcodebook.adaptive_ecc import AdaptiveDecodeResult
from semcodebook.ecc import encode_nibble
from semcodebook.negative_controls import certify_positive_support
from semcodebook.protocol import CarrierEvidence, CarrierScheduleEntry, GenerationRequest, WatermarkSpec
from semcodebook.variant_pool import build_adaptive_carrier_schedule


EXAMPLE = """
def helper_sum(items):
    total = 0
    for item in items:
        if item < 0:
            return 0
        total += item
    return bool(total)
""".strip()


class DetectorTest(unittest.TestCase):
    def test_inspect_returns_family_evidence(self) -> None:
        detector = SemCodebookDetector()
        evidence = detector.inspect(EXAMPLE)
        self.assertEqual(8, len(evidence))
        self.assertTrue(any(item.confidence > 0 for item in evidence))

    def test_detect_returns_structured_output(self) -> None:
        detector = SemCodebookDetector()
        result = detector.detect(EXAMPLE, WatermarkSpec(wm_id=13))
        self.assertIsInstance(result.is_watermarked, bool)
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)
        self.assertTrue(result.decoder_status)
        self.assertGreaterEqual(result.erasure_count, 0)
        self.assertGreaterEqual(result.support_ratio, 0.0)
        self.assertIn(result.decision_status, {"watermarked", "abstain", "reject"})
        self.assertEqual(4, result.ber_denominator)

    def test_plain_reference_is_not_accepted_as_watermarked(self) -> None:
        detector = SemCodebookDetector()
        reference = "def solve(items):\n    total = 0\n    for item in items:\n        if item < 0:\n            return 0\n        total += item\n    return total\n"
        result = detector.detect(reference, WatermarkSpec(wm_id=13, carrier_key="semcodebook-demo-key"))
        self.assertFalse(result.is_watermarked)

    def test_detector_recovers_smoke_payload_from_generated_code(self) -> None:
        detector = SemCodebookDetector()
        generated = watermark_generate(
            GenerationRequest(
                prompt="sum non-negative integers",
                language="python",
                wm_id=13,
                model_name="unit-test-model",
                carrier_key="semcodebook-demo-key",
            ),
            "def solve(items):\n    total = 0\n    for item in items:\n        if item < 0:\n            return 0\n        total += item\n    return total\n",
        )
        result = detector.detect(
            generated.watermarked_code,
            WatermarkSpec(
                wm_id=13,
                carrier_key="semcodebook-demo-key",
                carrier_schedule=tuple(generated.carrier_schedule),
                implementation_stage=generated.implementation_stage,
            ),
        )
        self.assertTrue(result.is_watermarked)
        self.assertEqual("watermarked", result.decision_status)
        self.assertEqual(13, result.wm_id_hat)
        self.assertGreaterEqual(result.confidence, 0.5)
        self.assertEqual(8, len(result.carrier_schedule))
        self.assertIn("bootstrap_rule_based_generation", result.implementation_stage)
        self.assertIn("bootstrap_rule_based_generation_interface", generated.notes)
        self.assertNotIn("white_box_generation_interface", generated.notes)

    def test_detector_rejects_unsupported_payload_width(self) -> None:
        detector = SemCodebookDetector()
        with self.assertRaises(ValueError):
            detector.detect(EXAMPLE, WatermarkSpec(wm_id=13, payload_bits=8))

    def test_detector_acceptance_does_not_depend_on_expected_payload_label(self) -> None:
        detector = SemCodebookDetector()
        generated = watermark_generate(
            GenerationRequest(
                prompt="sum non-negative integers",
                language="python",
                wm_id=13,
                model_name="unit-test-model",
                carrier_key="semcodebook-demo-key",
            ),
            "def solve(items):\n    total = 0\n    for item in items:\n        if item < 0:\n            return 0\n        total += item\n    return total\n",
        )
        result = detector.detect(
            generated.watermarked_code,
            WatermarkSpec(
                wm_id=7,
                carrier_key="semcodebook-demo-key",
                carrier_schedule=tuple(generated.carrier_schedule),
                implementation_stage=generated.implementation_stage,
            ),
        )
        self.assertTrue(result.is_watermarked)
        self.assertEqual("watermarked", result.decision_status)
        self.assertEqual(13, result.wm_id_hat)
        self.assertIsNone(result.bit_error_rate)

    def test_alpha_renaming_preserves_detected_payload(self) -> None:
        detector = SemCodebookDetector()
        generated = watermark_generate(
            GenerationRequest(
                prompt="sum non-negative integers",
                language="python",
                wm_id=13,
                model_name="unit-test-model",
                carrier_key="semcodebook-demo-key",
            ),
            "def solve(items):\n    total = 0\n    for item in items:\n        total += item\n    return total\n",
        )
        renamed = rename_identifiers(generated.watermarked_code, "python")
        result = detector.detect(
            renamed,
            WatermarkSpec(
                wm_id=13,
                carrier_key="semcodebook-demo-key",
                carrier_schedule=tuple(generated.carrier_schedule),
                implementation_stage=generated.implementation_stage,
            ),
        )
        self.assertEqual(13, result.wm_id_hat)

    def test_spoof_helper_and_dead_binding_do_not_force_detection(self) -> None:
        detector = SemCodebookDetector()
        spoof = (
            "def helper_transform(value):\n"
            "    return value\n\n"
            "def solve(items):\n"
            "    total = 0\n"
            "    unused_value = total\n"
            "    for item in items:\n"
            "        total += item\n"
            "    shadow = total\n"
            "    return total\n"
        )
        result = detector.detect(spoof, WatermarkSpec(wm_id=13, carrier_key='semcodebook-demo-key'))
        self.assertFalse(result.is_watermarked)

    def test_detect_low_support_example_abstains_with_reason(self) -> None:
        detector = SemCodebookDetector()
        snippet = (
            "def solve(items):\n"
            "    total = 0\n"
            "    for item in items:\n"
            "        total += item\n"
            "    return total\n"
        )
        result = detector.detect(snippet, WatermarkSpec(wm_id=13, carrier_key="semcodebook-demo-key"))
        self.assertEqual("abstain", result.decision_status)
        self.assertTrue(result.abstain_reason)
        self.assertIsNone(result.wm_id_hat)

    def test_detect_unsupported_snippet_rejects_even_if_decoder_guesses(self) -> None:
        detector = SemCodebookDetector()
        result = detector.detect("value = 1\n", WatermarkSpec(wm_id=13, carrier_key="semcodebook-demo-key"))
        self.assertEqual("reject", result.decision_status)
        self.assertFalse(result.is_watermarked)
        self.assertIsNone(result.wm_id_hat)

    def test_declared_negative_control_never_exposes_payload(self) -> None:
        generated = watermark_generate(
            GenerationRequest(
                prompt="sum non-negative integers",
                language="python",
                wm_id=13,
                model_name="unit-test-model",
                carrier_key="semcodebook-demo-key",
            ),
            "def solve(items):\n    total = 0\n    for item in items:\n        if item < 0:\n            return 0\n        total += item\n    return total\n",
        )
        result = SemCodebookDetector().detect(
            generated.watermarked_code,
            WatermarkSpec(
                wm_id=13,
                carrier_key="semcodebook-demo-key",
                carrier_schedule=tuple(generated.carrier_schedule),
                implementation_stage=generated.implementation_stage,
            ),
            negative_control=True,
        )
        self.assertEqual("reject", result.decision_status)
        self.assertEqual("declared_negative_control_fail_closed", result.abstain_reason)
        self.assertFalse(result.is_watermarked)
        self.assertIsNone(result.wm_id_hat)
        self.assertIn("negative_control_veto:fail_closed", result.notes)

    def test_positive_support_uses_structural_decode_certificate_without_lowering_threshold(self) -> None:
        codeword = encode_nibble(13)
        families = (
            ("accumulator_style", "ssa", True),
            ("helper_extraction_style", "cfg", True),
            ("initialization_idiom", "ssa", False),
            ("iteration_style", "cfg", False),
            ("comparison_idiom", "ast", False),
            ("temporary_binding_style", "ssa", False),
            ("return_expression_style", "ssa", False),
        )
        schedule = tuple(
            CarrierScheduleEntry(
                family=family,
                slot_index=index,
                role="data",
                bit_index=index,
                target_bit=codeword[index],
                applicable=True,
                structural_level=level,
                notes=(
                    ("discriminative_rewrite_backed_carrier",)
                    if rewrite_backed and index == 0
                    else (
                        ("discriminative_generation_planned_carrier", "fingerprint:base")
                        if rewrite_backed
                        else ()
                    )
                ),
            )
            for index, (family, level, rewrite_backed) in enumerate(families)
        )
        evidence = tuple(
            CarrierEvidence(
                family=family,
                option=f"bit_{codeword[index]}",
                confidence=0.84,
                applicable=True,
                structural_level=level,
            )
            for index, (family, level, _rewrite_backed) in enumerate(families)
        )
        decode = AdaptiveDecodeResult(
            value=13,
            confidence=0.10,
            corrected_bits=2,
            corrected_positions=(1, 5),
            decoder_status="decoded_corrected",
            erasure_count=0,
            raw_bit_error_count=2,
            post_correction_bit_error_rate=None,
            codeword=codeword,
        )
        certificate = certify_positive_support(
            evidence,
            schedule,
            decode,
            detector_threshold=0.5,
            current_structural_fingerprint="changed",
        )
        self.assertTrue(certificate.accepted)
        self.assertIn("decode_confidence_gate:false", certificate.reasons)
        self.assertIn("structural_decode_gate:true", certificate.reasons)
        self.assertIn("generation_planned_delta_count:1", certificate.reasons)

    def test_go_compact_accumulator_assignment_is_structural_witness(self) -> None:
        code = (
            "func solve(values []int) int {\n"
            "total:=0;for _,value:= range values{if value < 2 {continue};total = total + value}\n"
            "    return total}"
        )
        evidence = {
            item.family: item
            for item in SemCodebookDetector().inspect(code, language="go")
        }
        self.assertEqual("bit_1", evidence["accumulator_style"].option)

    def test_go_paired_next_total_assignment_is_structural_witness(self) -> None:
        code = (
            "func solve(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        currentItem := value\n"
            "        nextTotal := total + helperTransform(currentItem)\n"
            "        total = nextTotal\n"
            "    }\n"
            "    return total\n"
            "}\n"
            "func helperTransform(value int) int { return value }\n"
        )
        evidence = {
            item.family: item
            for item in SemCodebookDetector().inspect(code, language="go")
        }
        self.assertEqual("bit_1", evidence["accumulator_style"].option)

    def test_go_helper_before_entrypoint_is_helper_boundary_not_entrypoint_echo(self) -> None:
        code = (
            "func helperTransform(value int) int {\n"
            "    return value\n"
            "}\n\n"
            "func guard_loop_accumulator_go_positive_s01(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        total = total + helperTransform(value)\n"
            "    }\n"
            "    return total\n"
            "}\n"
        )
        evidence = {
            item.family: item
            for item in SemCodebookDetector().inspect(code, language="go")
        }
        self.assertEqual("bit_1", evidence["helper_extraction_style"].option)
        self.assertIn("helperTransform", evidence["helper_extraction_style"].matches)
        self.assertNotIn("guard_loop_accumulator_go_positive_s01", evidence["helper_extraction_style"].matches)

    def test_java_paired_next_total_assignment_is_structural_witness(self) -> None:
        code = (
            "public class Solve {\n"
            "    public static int solve(int[] values) {\n"
            "        int total = 0;\n"
            "        for (int value : values) {\n"
            "            int currentItem = value;\n"
            "            int nextTotal = total + helperTransform(currentItem);\n"
            "            total = nextTotal;\n"
            "        }\n"
            "        return total;\n"
            "    }\n"
            "    private static int helperTransform(int value) { return value; }\n"
            "}\n"
        )
        evidence = {
            item.family: item
            for item in SemCodebookDetector().inspect(code, language="java")
        }
        self.assertEqual("bit_1", evidence["accumulator_style"].option)

    def test_go_inline_helper_with_local_control_flow_is_countable_cfg_witness(self) -> None:
        code = (
            "func solve(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        normalized := value + 3 + (value % 2)\n"
            "        if value >= 0 { total += normalized }\n"
            "    }\n"
            "    return total\n"
            "}"
        )
        evidence = {
            item.family: item
            for item in SemCodebookDetector().inspect(code, language="go")
        }
        self.assertEqual("bit_0", evidence["helper_extraction_style"].option)
        self.assertGreaterEqual(evidence["helper_extraction_style"].confidence, 0.72)

    def test_python_plain_inline_logic_remains_below_helper_support_gate(self) -> None:
        code = (
            "def solve(items):\n"
            "    total = 0\n"
            "    for item in items:\n"
            "        if item < 0:\n"
            "            return 0\n"
            "        total += item\n"
            "    return total\n"
        )
        evidence = {
            item.family: item
            for item in SemCodebookDetector().inspect(code, language="python")
        }
        self.assertEqual("bit_0", evidence["helper_extraction_style"].option)
        self.assertLess(evidence["helper_extraction_style"].confidence, 0.72)

    def test_go_s08_materializer_meets_clean_positive_support_contract(self) -> None:
        base = (
            "func helper_container_helper_go_positive_s08(value int) int { return value + 3 + (value % 2) }\n\n"
            "func container_helper_go_positive_s08(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values { normalized := helper_container_helper_go_positive_s08(value); if value >= 0 { total += normalized } }\n"
            "    return total\n"
            "}\n"
        )
        materialized = (
            "func helper_container_helper_go_positive_s08(value int) int { return value + 3 + (value % 2) }\n\n"
            "func container_helper_go_positive_s08(values []int) int {\n"
            "    total := 0\n"
            "    for index := range values {\n"
            "        value := values[index]\n"
            "        currentItem := helper_container_helper_go_positive_s08(value)\n"
            "        if value >= 0 { total = total + currentItem }\n"
            "    }\n"
            "    result := total\n"
            "    return result\n"
            "}\n"
        )
        request = GenerationRequest(
            prompt="Use entrypoint `func container_helper_go_positive_s08(values []int) int`.",
            language="go",
            wm_id=13,
            model_name="unit-test",
            task_id="container_helper_go_positive_s08",
            carrier_key="carrier-key",
        )
        schedule = _target_aligned_schedule(
            base,
            request,
            build_adaptive_carrier_schedule(base, request.carrier_key, request.language),
        )
        result = SemCodebookDetector().detect(
            materialized,
            WatermarkSpec(
                wm_id=13,
                carrier_key="carrier-key",
                carrier_schedule=schedule,
                implementation_stage="trained_checkpoint_generation",
            ),
            language="go",
        )
        self.assertEqual("watermarked", result.decision_status)
        self.assertEqual(13, result.wm_id_hat)
        self.assertGreaterEqual(result.positive_support_family_count, 2)
        self.assertGreaterEqual(result.positive_support_level_count, 2)
        self.assertNotIn("missing_rewrite_backed_positive_support", result.notes)

    def test_cpp_container_type_does_not_spoof_initialization_carrier(self) -> None:
        code = (
            "#include <vector>\n"
            "int solve(const std::vector<int>& values) {\n"
            "    int total = 0;\n"
            "    return total;\n"
            "}\n"
        )
        evidence = {
            item.family: item
            for item in SemCodebookDetector().inspect(code, language="cpp")
        }
        self.assertEqual("bit_0", evidence["initialization_idiom"].option)

    def test_cpp_self_accumulator_assignment_survives_return_binding(self) -> None:
        code = (
            "#include <vector>\n\n"
            "int helper_transform(int value) { return value; }\n\n"
            "int solve(const std::vector<int>& values) {\n"
            "int total=0;for (int value : values){total=total+helper_transform(value);}\n"
            "    return total;}"
        )
        evidence = {
            item.family: item
            for item in SemCodebookDetector().inspect(code, language="cpp")
        }
        self.assertEqual("bit_1", evidence["accumulator_style"].option)

    def test_structural_decode_certificate_still_requires_rewrite_diversity(self) -> None:
        codeword = encode_nibble(13)
        schedule = tuple(
            CarrierScheduleEntry(
                family=f"family_{index}",
                slot_index=index,
                role="data",
                bit_index=index,
                target_bit=codeword[index],
                applicable=True,
                structural_level="ssa",
                notes=(("discriminative_rewrite_backed_carrier",) if index == 0 else ()),
            )
            for index in range(7)
        )
        evidence = tuple(
            CarrierEvidence(
                family=f"family_{index}",
                option=f"bit_{codeword[index]}",
                confidence=0.84,
                applicable=True,
                structural_level="ssa",
            )
            for index in range(7)
        )
        decode = AdaptiveDecodeResult(
            value=13,
            confidence=0.10,
            corrected_bits=2,
            corrected_positions=(1, 5),
            decoder_status="decoded_corrected",
            erasure_count=0,
            raw_bit_error_count=2,
            post_correction_bit_error_rate=None,
            codeword=codeword,
        )
        certificate = certify_positive_support(evidence, schedule, decode, detector_threshold=0.5)
        self.assertFalse(certificate.accepted)
        self.assertIn("missing_rewrite_backed_positive_support", certificate.reasons)

    def test_generation_planned_support_requires_structural_delta(self) -> None:
        codeword = encode_nibble(13)
        schedule = tuple(
            CarrierScheduleEntry(
                family=f"family_{index}",
                slot_index=index,
                role="data",
                bit_index=index,
                target_bit=codeword[index],
                applicable=True,
                structural_level=("cfg" if index % 2 else "ssa"),
                notes=("discriminative_generation_planned_carrier", "fingerprint:base"),
            )
            for index in range(7)
        )
        evidence = tuple(
            CarrierEvidence(
                family=f"family_{index}",
                option=f"bit_{codeword[index]}",
                confidence=0.84,
                applicable=True,
                structural_level=("cfg" if index % 2 else "ssa"),
            )
            for index in range(7)
        )
        decode = AdaptiveDecodeResult(
            value=13,
            confidence=0.80,
            corrected_bits=0,
            corrected_positions=(),
            decoder_status="decoded_clean",
            erasure_count=0,
            raw_bit_error_count=0,
            post_correction_bit_error_rate=None,
            codeword=codeword,
        )
        reference_certificate = certify_positive_support(
            evidence,
            schedule,
            decode,
            detector_threshold=0.5,
            current_structural_fingerprint="base",
        )
        generated_certificate = certify_positive_support(
            evidence,
            schedule,
            decode,
            detector_threshold=0.5,
            current_structural_fingerprint="changed",
        )
        self.assertFalse(reference_certificate.accepted)
        self.assertTrue(generated_certificate.accepted)

    def test_generation_planned_support_accepts_observed_bit_delta(self) -> None:
        codeword = encode_nibble(13)
        schedule = tuple(
            CarrierScheduleEntry(
                family=f"family_{index}",
                slot_index=index,
                role="data",
                bit_index=index,
                target_bit=codeword[index],
                applicable=True,
                structural_level=("cfg" if index % 2 else "ssa"),
                notes=(
                    "discriminative_generation_planned_carrier",
                    f"target_alignment_base_bit:{1 - codeword[index]}",
                ),
            )
            for index in range(7)
        )
        evidence = tuple(
            CarrierEvidence(
                family=f"family_{index}",
                option=f"bit_{codeword[index]}",
                confidence=0.84,
                applicable=True,
                structural_level=("cfg" if index % 2 else "ssa"),
            )
            for index in range(7)
        )
        decode = AdaptiveDecodeResult(
            value=13,
            confidence=0.80,
            corrected_bits=0,
            corrected_positions=(),
            decoder_status="decoded_clean",
            erasure_count=0,
            raw_bit_error_count=0,
            post_correction_bit_error_rate=None,
            codeword=codeword,
        )
        certificate = certify_positive_support(evidence, schedule, decode, detector_threshold=0.5)
        self.assertTrue(certificate.accepted)
        self.assertIn("generation_planned_delta_count:7", certificate.reasons)

    def test_single_generation_delta_requires_exact_codeword_certificate(self) -> None:
        codeword = encode_nibble(13)
        schedule = tuple(
            CarrierScheduleEntry(
                family=f"family_{index}",
                slot_index=index,
                role="data",
                bit_index=index,
                target_bit=codeword[index],
                applicable=True,
                structural_level=("cfg" if index == 0 else "ssa"),
                notes=(
                    (
                        "discriminative_generation_planned_carrier",
                        f"target_alignment_base_bit:{1 - codeword[index]}",
                    )
                    if index == 0
                    else ()
                ),
            )
            for index in range(7)
        )
        evidence = tuple(
            CarrierEvidence(
                family=f"family_{index}",
                option=f"bit_{codeword[index]}",
                confidence=0.84,
                applicable=True,
                structural_level=("cfg" if index == 0 else "ssa"),
            )
            for index in range(7)
        )
        decode = AdaptiveDecodeResult(
            value=13,
            confidence=0.20,
            corrected_bits=1,
            corrected_positions=(2,),
            decoder_status="decoded_corrected",
            erasure_count=0,
            raw_bit_error_count=1,
            post_correction_bit_error_rate=None,
            codeword=codeword,
        )
        certificate = certify_positive_support(evidence, schedule, decode, detector_threshold=0.5)
        self.assertTrue(certificate.accepted)
        self.assertIn("exact_codeword_delta_gate:true", certificate.reasons)
        self.assertIn("exact_codeword_support_gate:true", certificate.reasons)
        self.assertIn("distinctive_delta_gate:true", certificate.reasons)

        noisy_decode = AdaptiveDecodeResult(
            value=13,
            confidence=0.20,
            corrected_bits=2,
            corrected_positions=(2, 5),
            decoder_status="decoded_corrected",
            erasure_count=0,
            raw_bit_error_count=2,
            post_correction_bit_error_rate=None,
            codeword=codeword,
        )
        noisy_certificate = certify_positive_support(evidence, schedule, noisy_decode, detector_threshold=0.5)
        self.assertFalse(noisy_certificate.accepted)
        self.assertIn("exact_codeword_delta_gate:false", noisy_certificate.reasons)

        weak_evidence = tuple(
            CarrierEvidence(
                family=f"family_{index}",
                option=f"bit_{codeword[index]}",
                confidence=0.30,
                applicable=True,
                structural_level=("cfg" if index == 0 else "ssa"),
            )
            for index in range(7)
        )
        weak_certificate = certify_positive_support(weak_evidence, schedule, decode, detector_threshold=0.5)
        self.assertFalse(weak_certificate.accepted)
        self.assertIn("exact_codeword_support_gate:false", weak_certificate.reasons)


if __name__ == "__main__":
    unittest.main()
