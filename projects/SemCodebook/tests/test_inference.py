from __future__ import annotations

import contextlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from semcodebook.inference import (
    _candidate_rank,
    _allow_raw_decoder_fallback,
    _carrier_realization_guidance,
    _carrier_support_retry_prompt,
    _decoder_forced_output_prefix,
    _dump_trained_generation_failure_candidates,
    _extract_generated_code,
    _generate_with_trained_checkpoint,
    _generation_code_changed,
    _generation_length_kwargs,
    _generated_token_slice,
    _cpp_support_materializer_variants,
    _go_support_materializer_variants,
    _java_support_materializer_variants,
    _javascript_support_materializer_variants,
    _language_support_materializer_variants,
    _merge_forced_output_prefix,
    _normalize_decoded_text,
    _target_recovery_metrics,
    _target_aligned_schedule,
    build_structured_generation_prompt,
    TrainedGenerationFailure,
)
from semcodebook.protocol import CarrierScheduleEntry, GenerationRequest
from semcodebook.variant_pool import build_adaptive_carrier_schedule
from semcodebook.typed_ast import summarize_typed_ast

if "torch" not in sys.modules:
    sys.modules["torch"] = SimpleNamespace(inference_mode=contextlib.nullcontext)


class _FakeTensor:
    def to(self, _device):
        return self


class _FakeParameter:
    device = "cpu"


class _FakeTokenizer:
    pad_token_id = 0
    eos_token_id = 1

    def __call__(self, _prompt, return_tensors="pt"):
        return {"input_ids": _FakeTensor(), "attention_mask": _FakeTensor()}

    def decode(self, _sequence, skip_special_tokens=True):
        return "```javascript\nfunction chooseValue(values) { return values[0] ?? 0; }\n```"


class _PromptOnlyTokenizer(_FakeTokenizer):
    def decode(self, _sequence, skip_special_tokens=True):
        return "Instruction: rewrite the base code into a semantically equivalent complete source file."


class _GoBodyTokenizer(_FakeTokenizer):
    def decode(self, _sequence, skip_special_tokens=True):
        return "total:=0\nfor_,value:=rangevalues{total += value}\nreturntotal\n}"


class _GoCompactPromptLeakTokenizer(_FakeTokenizer):
    def decode(self, _sequence, skip_special_tokens=True):
        return (
            "-Realizethecarrierplansilentlyinsidethefinalprogramstructure;neverlistcarriersnippetsseparately.\n"
            "-Preserveeverypublicfunctionsignaturethatappearsinthebasecode.\n"
            "-TheevaluatorsuppliestheGowrapper;donotemitapackagedeclaration.\n"
            "RequiredGooutputshape:-Thefirstnon-emptyoutputlinemustbeexactly:"
            "`funccontainer_helper_go_positive_s01(values[]int)int{`"
            "-Theoutputmustcontainthatfunctionbodyandclosingbrace.\n"
            "TaskPrompt:Writeagoimplementationforproblemfamily`container_helper`.\n"
            "funccontainer_helper_go_positive_s01(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        total += helper_container_helper_go_positive_s01(value)\n"
            "    }\n"
            "    return total\n"
            "}\n"
            "funchelper_container_helper_go_positive_s01(value int) int {\n"
            "    return value\n"
            "}"
        )


class _GoForcedStubThenRetryTokenizer(_FakeTokenizer):
    def decode(self, sequence, skip_special_tokens=True):
        token = sequence[0] if sequence else 0
        if token in {1, 2}:
            return ""
        return (
            "func container_helper_go_positive_s01(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        normalized := helper_container_helper_go_positive_s01(value)\n"
            "        if value >= 0 {\n"
            "            total += normalized\n"
            "        }\n"
            "    }\n"
            "    return total\n"
            "}\n"
            "func helper_container_helper_go_positive_s01(value int) int {\n"
            "    return value + 3 + (value % 3)\n"
            "}"
        )


class _GoForcedStubThenTranscriptRetryTokenizer(_FakeTokenizer):
    def decode(self, sequence, skip_special_tokens=True):
        token = sequence[0] if sequence else 0
        if token in {1, 2}:
            return ""
        return (
            "func helper_container_helper_go_positive_s01(value int) int {return value + 3 + (value % 3)}\n\n"
            "func container_helper_go_positive_s01(values []int) int {total := 0; for _, value := range values {"
            "normalized := helper_container_helper_go_positive_s01(value); if value >= 0 {total += normalized}}; "
            "return total}\n"
            "###Instruction:"
        )


class _GoForcedStubThenCompactSignatureRetryTokenizer(_FakeTokenizer):
    def decode(self, sequence, skip_special_tokens=True):
        token = sequence[0] if sequence else 0
        if token in {1, 2}:
            return ""
        return (
            "func container_helper_go_positive_s02(values []int) int {\n\n"
            "\ttotal := 0\n"
            "\tfor _, value := range values {\n"
            "\t\tnormalized := helper_container_helper_go_positive_s02(value)\n"
            "\t\tif value >= 0 {\n"
            "\t\t\ttotal += normalized\n"
            "\t\t}\n"
            "\t}\n"
            "\treturn total\n"
            "}\n\n"
            "funchelper_container_helper_go_positive_s02(valueint)int{\n"
            "\treturnvalue+4+(value%4)\n"
            "}"
        )


class _GoCompactStatementBodyTokenizer(_FakeTokenizer):
    def decode(self, _sequence, skip_special_tokens=True):
        return (
            "total:=0for_,value:= range values{"
            "normalized := helper_container_helper_go_positive_s09(value); "
            "if value >= 0 { total += normalized } } return total}\n"
            "Language-specificconstraints:-Startdirectlywiththeexactfuncdeclaration."
        )


class _GoSupportRetryTokenizer(_FakeTokenizer):
    def __init__(self):
        self.prompts = []

    def __call__(self, prompt, return_tensors="pt"):
        self.prompts.append(prompt)
        return super().__call__(prompt, return_tensors=return_tensors)

    def decode(self, sequence, skip_special_tokens=True):
        token = sequence[0] if sequence else 0
        if token < 3:
            return (
                "total := 0\n"
                "for _, value := range values {\n"
                "    normalized := helper_container_helper_go_positive_s08(value)\n"
                "    if value >= 0 {\n"
                "        total += normalized\n"
                "    }\n"
                "}\n"
                "return total\n"
                "}"
            )
        return (
            "total := 0\n"
            "for _, value := range values {\n"
            "    normalized := helper_container_helper_go_positive_s08(value)\n"
            "    if value >= 0 {\n"
            "        nextTotal := total + normalized\n"
            "        total = nextTotal\n"
            "    }\n"
            "}\n"
            "result := total\n"
            "return result\n"
            "}"
        )


class _GoNonSemanticSupportRetryTokenizer(_FakeTokenizer):
    def __init__(self):
        self.prompts = []

    def __call__(self, prompt, return_tensors="pt"):
        self.prompts.append(prompt)
        return super().__call__(prompt, return_tensors=return_tensors)

    def decode(self, sequence, skip_special_tokens=True):
        token = sequence[0] if sequence else 0
        if token < 3:
            return (
                "total := 0\n"
                "for _, value := range values {\n"
                "    normalized := helper_container_helper_go_positive_s08(value)\n"
                "    if value >= 0 {\n"
                "        total += normalized\n"
                "    }\n"
                "}\n"
                "return total\n"
                "}"
            )
        return (
            "total := 0\n"
            "for _, value := range values {\n"
            "    nextTotal := total + BROKEN_UNDECLARED\n"
            "    total = nextTotal\n"
            "}\n"
            "result := total\n"
            "return result\n"
            "}"
        )


class _FakeModel:
    def parameters(self):
        return iter([_FakeParameter()])

    def generate(self, **_kwargs):
        return [[1, 2, 3]]


class _SequentialFakeModel(_FakeModel):
    def __init__(self):
        self.calls = 0

    def generate(self, **_kwargs):
        self.calls += 1
        return [[self.calls]]


class _RecordingDetector:
    def __init__(self, calls):
        self._calls = calls

    def detect(self, _code, spec, *, language="python"):
        self._calls.append(
            {
                "language": language,
                "carrier_schedule_len": len(getattr(spec, "carrier_schedule", ()) or ()),
                "implementation_stage": getattr(spec, "implementation_stage", ""),
            }
        )
        return SimpleNamespace(
            carrier_evidence=(SimpleNamespace(confidence=1.0),),
            support_ratio=1.0,
        )


class _DetectionStub(SimpleNamespace):
    pass


class _CodeAwareDetector:
    def detect(self, code, spec, *, language="python"):
        changed = "nextTotal" in code and "result := total" in code
        return SimpleNamespace(
            carrier_evidence=(SimpleNamespace(confidence=1.0),),
            support_ratio=1.0,
            wm_id_hat=(13 if changed else None),
            decision_status=("watermarked" if changed else "abstain"),
            abstain_reason=(None if changed else "missing_rewrite_backed_positive_support"),
            positive_support_score=(1.0 if changed else 0.625),
            positive_support_family_count=(2 if changed else 0),
            positive_support_level_count=(2 if changed else 0),
        )


class _WrongTargetWatermarkedDetector:
    def detect(self, code, spec, *, language="python"):
        changed = "nextTotal" in code and "result := total" in code
        return SimpleNamespace(
            carrier_evidence=(SimpleNamespace(confidence=1.0),),
            support_ratio=1.0,
            wm_id_hat=(13 if changed else 99),
            decision_status="watermarked",
            abstain_reason=None,
            positive_support_score=1.0,
            positive_support_family_count=2,
            positive_support_level_count=2,
        )


class _RetryFallbackDetector:
    def detect(self, code, spec, *, language="python"):
        changed = "nextTotal" in code and "result := total" in code
        return SimpleNamespace(
            carrier_evidence=(SimpleNamespace(confidence=1.0),),
            support_ratio=1.0,
            wm_id_hat=(None if changed else 13),
            decision_status="abstain",
            abstain_reason="missing_rewrite_backed_positive_support",
            positive_support_score=0.625,
            positive_support_family_count=0,
            positive_support_level_count=0,
        )


class _GoMaterializerDetector:
    def detect(self, code, spec, *, language="python"):
        materialized = (
            "func helper_container_helper_go_positive_s08" not in code
            and "value + 3 + (value % 2)" in code
            and "result := total" in code
        )
        return SimpleNamespace(
            carrier_evidence=(SimpleNamespace(confidence=1.0),),
            support_ratio=1.0,
            wm_id_hat=(13 if materialized else 10),
            decoded_wm_id_candidate=(13 if materialized else 10),
            decision_status=("watermarked" if materialized else "abstain"),
            abstain_reason=(None if materialized else "missing_rewrite_backed_positive_support"),
            positive_support_score=(1.0 if materialized else 0.625),
            positive_support_family_count=(2 if materialized else 1),
            positive_support_level_count=(2 if materialized else 1),
        )


class InferenceTest(unittest.TestCase):
    def test_non_python_semcodebook_return_binding_is_named_return_witness(self) -> None:
        cases = {
            "javascript": "function solve(values) {\n  const semcodebookReturnValue = values.length;\n  return semcodebookReturnValue;\n}",
            "java": "public class Solution {\n  public static int solve(int[] values) {\n    int semcodebookReturnValue = values.length;\n    return semcodebookReturnValue;\n  }\n}",
            "go": "func solve(values []int) int {\n    semcodebookReturnValue := len(values)\n    return semcodebookReturnValue\n}",
            "cpp": "#include <vector>\nint solve(const std::vector<int>& values) {\n    int semcodebook_return_value = static_cast<int>(values.size());\n    return semcodebook_return_value;\n}",
        }

        for language, code in cases.items():
            with self.subTest(language=language):
                summary = summarize_typed_ast(code, language)
                self.assertIn("named_return", {item.kind for item in summary.return_forms})

    def test_trained_generation_failure_dump_writes_candidate_diagnostics(self) -> None:
        request = GenerationRequest(
            prompt="write python",
            language="python",
            wm_id=1,
            model_name="unit-test",
            task_id="guard_loop_accumulator_python_positive_s10",
        )
        detection = SimpleNamespace(
            decision_status="abstain",
            support_ratio=0.0,
            wm_id_hat=None,
            decoded_wm_id_candidate=1,
            positive_support_score=0.0,
            positive_support_family_count=0,
            positive_support_level_count=0,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict("os.environ", {"SEMCODEBOOK_FAILURE_DUMP_DIR": tmpdir}):
                _dump_trained_generation_failure_candidates(
                    request,
                    [
                        {
                            "origin": "greedy",
                            "sequence_index": 0,
                            "generated_code": "def broken(values):\n    total = 0 if",
                            "validation": {
                                "semantic_ok": False,
                                "compile_ok": False,
                                "failure_reason": "syntax_error:invalid syntax",
                            },
                            "detection": detection,
                            "schedule_summary": {"scheduled_realization_ratio": 0.0},
                            "decoder_diagnostics": {
                                "raw_decoded_length": 18,
                                "raw_decoded_preview": "def broken(values)",
                                "forced_prefix_applied": False,
                            },
                            "target_recovery_match": False,
                            "target_recovery_bit_match_fraction": 0.0,
                            "rank": (0, 0, 0),
                        },
                    ],
                    phase="semantic_validation",
                    detail="syntax_error:invalid syntax",
                )
            dump_path = Path(tmpdir) / "guard_loop_accumulator_python_positive_s10.semantic_validation.trained_generation_candidates.json"
            payload = json.loads(dump_path.read_text(encoding="utf-8"))
        self.assertEqual("semcodebook_trained_generation_failure_candidates_v1", payload["schema_version"])
        self.assertEqual("guard_loop_accumulator_python_positive_s10", payload["task_id"])
        self.assertEqual(1, payload["candidate_count"])
        self.assertEqual(64, len(payload["candidates"][0]["generated_code_sha256"]))
        self.assertEqual(64, len(payload["candidates"][0]["raw_decoded_preview_sha256"]))
        self.assertEqual("syntax_error:invalid syntax", payload["candidates"][0]["validation"]["failure_reason"])
        self.assertEqual(18, payload["candidates"][0]["decoder_diagnostics"]["raw_decoded_length"])
        self.assertEqual(1, payload["candidates"][0]["detection_summary"]["decoded_wm_id_candidate"])

    def test_extract_generated_code_strips_common_fence_languages(self) -> None:
        prompt = "PROMPT"
        cases = {
            "```javascript\nfunction demo() { return 1; }\n```": "function demo() { return 1; }",
            "```java\npublic class Solution {}\n```": "public class Solution {}",
            "```cpp\nint main() { return 0; }\n```": "int main() { return 0; }",
            "javascript\nfunction demo() { return 2; }": "function demo() { return 2; }",
            "###SemCodebookRewriteTaskLanguage:javascript###Outputcode\nfunction demo() { return 3; }": "function demo() { return 3; }",
            "Base Code\nint old() { return 0; }\nOutputcode\nint demo() { return 4; }": "int demo() { return 4; }",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw.split("\n", 1)[0]):
                self.assertEqual(expected, _extract_generated_code(raw, prompt, language="javascript"))

    def test_extract_generated_code_rejects_go_v28_prompt_residue_stub(self) -> None:
        prompt = "Use entrypoint `func container_helper_go_positive_s08(values []int) int`."
        raw = """func container_helper_go_positive_s08(values []int) int {
Language-specific constraints:
- Start direct with the exact func declaration from the task prompt.
- Preserve the exact function name and signature requested in the task prompt.
Required Go output shape:
- The first non-empty output line must be exactly: `func container_helper_go_positive_s08(values []int) int {`
"""
        self.assertEqual("", _extract_generated_code(raw, prompt, language="go"))

    def test_extract_generated_code_strips_go_v28_prompt_residue_before_body(self) -> None:
        prompt = "Use entrypoint `func container_helper_go_positive_s08(values []int) int`."
        raw = """func container_helper_go_positive_s08(values []int) int {
Language-specific constraints:
- Start direct with the exact func declaration from the task prompt.
- Preserve the exact function name and signature requested in the task prompt.
    total := 0
    for _, value := range values {
        total += value
    }
    return total
}
"""
        expected = """func container_helper_go_positive_s08(values []int) int {
    total := 0
    for _, value := range values {
        total += value
    }
    return total
}"""
        self.assertEqual(expected, _extract_generated_code(raw, prompt, language="go"))

    def test_merge_forced_go_prefix_rejects_prompt_bullet_continuation(self) -> None:
        prompt = "Use entrypoint `func container_helper_go_positive_s08(values []int) int`."
        base_code = "func container_helper_go_positive_s08(values []int) int { return 0 }"
        prefix = "func container_helper_go_positive_s08(values []int) int {\n"
        decoded = "- Start direct with the exact func declaration from the task prompt.\n"
        merged = _merge_forced_output_prefix(decoded, prefix, language="go", prompt=prompt, base_code=base_code)
        self.assertFalse(merged.startswith(prefix + "-"))
        self.assertEqual("", _extract_generated_code(merged, prompt, language="go"))

    def test_extract_generated_code_strips_go_generated_code_trailer(self) -> None:
        prompt = "Use entrypoint `func solve(values []int) int`."
        raw = """func solve(values []int) int {
    total := 0
    for _, value := range values {
        total += value
    }
    return total
}
Generated code:
func solve(values []int) int { return 0 }
"""
        expected = """func solve(values []int) int {
    total := 0
    for _, value := range values {
        total += value
    }
    return total
}"""
        self.assertEqual(expected, _extract_generated_code(raw, prompt, language="go"))

    def test_extract_generated_code_repairs_go_v29_forindex_range_glue(self) -> None:
        prompt = "Use entrypoint `func container_helper_go_positive_s08(values []int) int`."
        raw = """func helper_container_helper_go_positive_s08(value int) int { return value + 3 + (value % 2) }

func container_helper_go_positive_s08(values []int) int {
total:=0forindex,value:=rangevalues{normalized:=helper_container_helper_go_positive_s08(value);ifvalue>=0{total+=normalized}}returntotal}
"""
        extracted = _extract_generated_code(raw, prompt, language="go")
        self.assertIn("for _, value := range values", extracted)
        self.assertIn("if value>=0", extracted)
        self.assertIn("return total", extracted)
        self.assertNotIn("forindex", extracted)
        self.assertNotIn("rangevalues", extracted)
        self.assertNotIn("returntotal", extracted)

    def test_extract_generated_code_rewrites_unused_go_v30_range_index_to_blank(self) -> None:
        prompt = "Use entrypoint `func container_helper_go_positive_s08(values []int) int`."
        raw = """func helper_container_helper_go_positive_s08(value int) int { return value + 3 + (value % 2) }

func container_helper_go_positive_s08(values []int) int {
total:=0;for index, value := range values{normalized:=helper_container_helper_go_positive_s08(value);if value>=0{total+=normalized}};return total}
"""
        extracted = _extract_generated_code(raw, prompt, language="go")
        self.assertIn("for _, value := range values", extracted)
        self.assertNotIn("for index, value := range values", extracted)

    def test_extract_generated_code_preserves_used_go_range_index(self) -> None:
        prompt = "Use entrypoint `func weighted_sum(values []int) int`."
        raw = """func weighted_sum(values []int) int {
total:=0;for index, value := range values{total += index + value};return total}
"""
        extracted = _extract_generated_code(raw, prompt, language="go")
        self.assertIn("for index, value := range values", extracted)
        self.assertNotIn("for _, value := range values", extracted)

    def test_extract_generated_code_strips_go_v29_metadata_tail_after_closed_function(self) -> None:
        prompt = "Use entrypoint `func container_helper_go_positive_s08(values []int) int`."
        raw = """func helper_container_helper_go_positive_s08(value int) int { return value + 3 + (value % 2) }

func container_helper_go_positive_s08(values []int) int {
total:=0;forindex,value:=rangevalues{normalized:=helper_container_helper_go_positive_s08(value);ifvalue>=0{total+=normalized}};returntotal}
Scheduled data carriers:
- name: helper_container_helper_go_positive_s08
Bit family: early_return_guard_style
"""
        extracted = _extract_generated_code(raw, prompt, language="go")
        self.assertIn("for _, value := range values", extracted)
        self.assertNotIn("Scheduled data carriers", extracted)
        self.assertNotIn("Bit family", extracted)

    def test_extract_generated_code_strips_compacted_prompt_echo(self) -> None:
        prompt = "### SemCodebook Rewrite Task\nLanguage: cpp\n### Output code\n"
        raw = prompt.replace(" ", "").replace("\n", "") + "\n#include <vector>\nint solve() { return 1; }"
        self.assertEqual(
            "#include <vector>\nint solve() { return 1; }",
            _extract_generated_code(raw, prompt, language="cpp"),
        )

    def test_extract_generated_code_strips_javascript_bullet_prompt_residue_after_signature(self) -> None:
        raw = """function guard_loop_accumulator_javascript_positive_s06(values) {
- Start directly with the requested function, constant, or class declaration.
- Don't emit carrier-plan comments or assignment-style plan fragments.
  let total = Number(0);
  for (const value of values) {
    if (value < Number(2)) {
      continue;
    }
    if (value % Number(4) === Number(3)) {
      continue;
    }
    total += value;
  }
  return total;
}"""
        self.assertEqual(
            "function guard_loop_accumulator_javascript_positive_s06(values) {\n"
            "  let total = Number(0);\n"
            "  for (const value of values) {\n"
            "    if (value < Number(2)) {\n"
            "      continue;\n"
            "    }\n"
            "    if (value % Number(4) === Number(3)) {\n"
            "      continue;\n"
            "    }\n"
            "    total += value;\n"
            "  }\n"
            "  return total;\n"
            "}",
            _extract_generated_code(raw, "PROMPT", language="javascript"),
        )

    def test_extract_generated_code_strips_javascript_trailing_prompt_residue_and_banner(self) -> None:
        raw = """function guard_loop_accumulator_javascript_positive_s06(values) {
  let total = 0;
  for (const value of values) {
    if (value < 2) {
      continue;
    }
    if (value % 4 === 3) {
      continue;
    }
    total += value;
  }
  let finalTotal = total;
  return finalTotal;
}
/*-Outputonlyrunnablecode-*/
-Donotoutputcarriernames,schedulelabels,metadata,assertions,printexamples,orlinesbeginningwith.
- accumulator_style applicable
- branch_shape not applicable
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-="""
        self.assertEqual(
            "function guard_loop_accumulator_javascript_positive_s06(values) {\n"
            "  let total = 0;\n"
            "  for (const value of values) {\n"
            "    if (value < 2) {\n"
            "      continue;\n"
            "    }\n"
            "    if (value % 4 === 3) {\n"
            "      continue;\n"
            "    }\n"
            "    total += value;\n"
            "  }\n"
            "  let finalTotal = total;\n"
            "  return finalTotal;\n"
            "}",
            _extract_generated_code(raw, "PROMPT", language="javascript"),
        )

    def test_extract_generated_code_strips_javascript_output_prefix_and_plan_labels(self) -> None:
        raw = """Output runnable source code:
function guard_loop_accumulator_javascript_positive_s06(values) {
  let total = 0;
  for (const value of values) {
    if (value < 2) {
      continue;
    }
    if (value % 4 === 3) {
      continue;
    }
    total += value;
  }
  return total;
}
- initializer
- comparison_operand_order"""
        self.assertEqual(
            "function guard_loop_accumulator_javascript_positive_s06(values) {\n"
            "  let total = 0;\n"
            "  for (const value of values) {\n"
            "    if (value < 2) {\n"
            "      continue;\n"
            "    }\n"
            "    if (value % 4 === 3) {\n"
            "      continue;\n"
            "    }\n"
            "    total += value;\n"
            "  }\n"
            "  return total;\n"
            "}",
            _extract_generated_code(raw, "PROMPT", language="javascript"),
        )

    def test_extract_generated_code_dedupes_repeated_javascript_entrypoint(self) -> None:
        prompt = (
            "Use entrypoint "
            "`function guard_loop_accumulator_javascript_positive_s06(values)`."
        )
        raw = """function guard_loop_accumulator_javascript_positive_s06(values) {

function guard_loop_accumulator_javascript_positive_s06(values) {
  let total = 0;
  for (const value of values) {
    if (value < 2) {
      continue;
    }
    if (value % 4 === 3) {
      continue;
    }
    total += value;
  }
  return total;
}"""
        self.assertEqual(
            "function guard_loop_accumulator_javascript_positive_s06(values) {\n"
            "  let total = 0;\n"
            "  for (const value of values) {\n"
            "    if (value < 2) {\n"
            "      continue;\n"
            "    }\n"
            "    if (value % 4 === 3) {\n"
            "      continue;\n"
            "    }\n"
            "    total += value;\n"
            "  }\n"
            "  return total;\n"
            "}",
            _extract_generated_code(raw, prompt, language="javascript"),
        )

    def test_structured_prompt_contains_language_specific_constraints(self) -> None:
        schedule = (
            CarrierScheduleEntry(
                family="iteration_style",
                slot_index=0,
                role="data",
                target_bit=0,
                applicable=True,
            ),
        )
        prompt = build_structured_generation_prompt(
            prompt="write a Go function",
            language="go",
            wm_id=8,
            base_code="func solve(values []int) int { return 0 }",
            schedule=schedule,
            carrier_key="key",
            task_id="task",
        )
        self.assertIn("Use `_` for an unused range index", prompt)
        self.assertIn("Start directly with the exact func declaration", prompt)
        self.assertIn("do not emit a package declaration", prompt)
        self.assertIn("Do not emit prose or markdown", prompt)
        self.assertIn("Preserve the exact function name and signature", prompt)
        self.assertIn("one semantically equivalent Go function snippet", prompt)
        self.assertIn("Output only Go function/helper declarations", prompt)
        self.assertNotIn("complete source file", prompt)
        self.assertIn("The first non-empty output line must be exactly: `func solve(values []int) int {`", prompt)

    def test_non_python_accumulator_guidance_matches_structural_witness(self) -> None:
        guidance = _carrier_realization_guidance("accumulator_style", 1, "java")
        self.assertIn("previous value plus the contribution", guidance)
        self.assertIn("do not use the augmented plus-equals form", guidance)

    def test_go_decoder_prefix_forces_only_required_signature(self) -> None:
        request = GenerationRequest(
            prompt="Use entrypoint `func solve(values []int) int`.",
            language="go",
            wm_id=1,
            model_name="unit-test",
        )
        prefix, notes = _decoder_forced_output_prefix(request, "func solve(values []int) int { return 0 }")
        self.assertEqual("func solve(values []int) int {\n", prefix)
        self.assertEqual(("decoder_forced_prefix:go_entrypoint_signature",), notes)

    def test_go_decoder_prefix_preserves_base_helper_before_entrypoint(self) -> None:
        request = GenerationRequest(
            prompt="Use entrypoint `func container_helper_go_positive_s09(values []int) int`.",
            language="go",
            wm_id=1,
            model_name="unit-test",
        )
        base_code = (
            "func helper_container_helper_go_positive_s09(value int) int { return value + 4 + (value % 3) }\n\n"
            "func container_helper_go_positive_s09(values []int) int {\n"
            "    return 0\n"
            "}\n"
        )
        prefix, notes = _decoder_forced_output_prefix(request, base_code)
        self.assertTrue(prefix.startswith("func helper_container_helper_go_positive_s09(value int) int"))
        self.assertTrue(prefix.endswith("func container_helper_go_positive_s09(values []int) int {\n"))
        self.assertIn("decoder_forced_prefix:go_base_support_prefix", notes)

    def test_go_decoder_prefix_preserves_transitive_helper_dependencies(self) -> None:
        request = GenerationRequest(
            prompt="Use entrypoint `func deep_container_helper_go_positive_s02(values []int) int`.",
            language="go",
            wm_id=1,
            model_name="unit-test",
        )
        base_code = (
            "func absInt(value int) int { if value < 0 { return -value }; return value }\n\n"
            "func helper_deep_container_helper_go_positive_s02(value int) int { return absInt(value) + 4 }\n\n"
            "func unusedSupport(value int) int { return value * 2 }\n\n"
            "func deep_container_helper_go_positive_s02(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        total += helper_deep_container_helper_go_positive_s02(value)\n"
            "    }\n"
            "    return total\n"
            "}\n"
        )
        prefix, notes = _decoder_forced_output_prefix(request, base_code)
        self.assertIn("func absInt(value int) int", prefix)
        self.assertIn("func helper_deep_container_helper_go_positive_s02(value int) int", prefix)
        self.assertLess(prefix.index("func absInt"), prefix.index("func helper_deep_container_helper"))
        self.assertNotIn("unusedSupport", prefix)
        self.assertTrue(prefix.endswith("func deep_container_helper_go_positive_s02(values []int) int {\n"))
        self.assertIn("decoder_forced_prefix:go_base_support_prefix", notes)

    def test_go_decoder_prefix_does_not_synthesize_missing_helper(self) -> None:
        request = GenerationRequest(
            prompt="Use entrypoint `func container_helper_go_positive_s09(values []int) int`.",
            language="go",
            wm_id=1,
            model_name="unit-test",
        )
        prefix, notes = _decoder_forced_output_prefix(
            request,
            "func container_helper_go_positive_s09(values []int) int { return 0 }\n",
        )
        self.assertEqual("func container_helper_go_positive_s09(values []int) int {\n", prefix)
        self.assertNotIn("decoder_forced_prefix:go_base_support_prefix", notes)

    def test_merge_forced_go_prefix_skips_duplicate_compact_entrypoint(self) -> None:
        decoded = (
            "funccontainer_helper_go_positive_s01(values []int) int {\n"
            "    total := 0\n"
            "    return total\n"
            "}"
        )
        self.assertEqual(
            decoded,
            _merge_forced_output_prefix(
                decoded,
                "func container_helper_go_positive_s01(values []int) int {\n",
                language="go",
                prompt="Use entrypoint `func container_helper_go_positive_s01(values []int) int`.",
            ),
        )

    def test_merge_forced_go_prefix_adds_missing_transitive_dependency(self) -> None:
        prompt = "Use entrypoint `func multilingual_equivalence_go_positive_s01(values []int) int`."
        base_code = (
            "func absInt(value int) int { if value < 0 { return -value }; return value }\n\n"
            "func helper_multilingual_equivalence_go_positive_s01(value int) int { return absInt(value) + 3 }\n\n"
            "func multilingual_equivalence_go_positive_s01(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        total += helper_multilingual_equivalence_go_positive_s01(value)\n"
            "    }\n"
            "    return total\n"
            "}\n"
        )
        decoded = (
            "func multilingual_equivalence_go_positive_s01(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        normalized := helper_multilingual_equivalence_go_positive_s01(value)\n"
            "        if normalized%4 == 2 { total += normalized }\n"
            "    }\n"
            "    return total\n"
            "}\n\n"
            "func helper_multilingual_equivalence_go_positive_s01(value int) int { return absInt(value) + 3 }"
        )
        merged = _merge_forced_output_prefix(
            decoded,
            "func multilingual_equivalence_go_positive_s01(values []int) int {\n",
            language="go",
            prompt=prompt,
            base_code=base_code,
        )
        self.assertTrue(merged.startswith("func absInt(value int) int"))
        self.assertEqual(1, merged.count("func absInt("))
        self.assertEqual(1, merged.count("func helper_multilingual_equivalence_go_positive_s01("))

    def test_python_decoder_prefix_forces_signature_and_indented_body(self) -> None:
        request = GenerationRequest(
            prompt="Use entrypoint `def solve(values):`.",
            language="python",
            wm_id=1,
            model_name="unit-test",
        )
        prefix, notes = _decoder_forced_output_prefix(
            request,
            "def solve(values):\n    return 0\n",
        )
        self.assertEqual("def solve(values):\n    ", prefix)
        self.assertEqual(("decoder_forced_prefix:python_entrypoint_signature",), notes)

    def test_python_decoder_prefix_can_reserve_scheduled_helper(self) -> None:
        request = GenerationRequest(
            prompt="Use entrypoint `def solve(values):`.",
            language="python",
            wm_id=1,
            model_name="unit-test",
        )
        prefix, notes = _decoder_forced_output_prefix(
            request,
            "def solve(values):\n    return 0\n",
            (
                CarrierScheduleEntry(
                    family="helper_extraction_style",
                    slot_index=0,
                    role="data",
                    target_bit=1,
                    applicable=True,
                ),
            ),
        )
        self.assertIn("def helper_transform(value):", prefix)
        self.assertTrue(prefix.endswith("def solve(values):\n    "))
        self.assertIn("decoder_forced_prefix:python_helper_identity", notes)

    def test_extract_generated_code_normalizes_go_compact_continuation(self) -> None:
        raw = (
            "func solve(values []int) int {\n"
            "total:=0;for_,value:=rangevalues{if value < 2 {continue};total = total + value}return total}"
            "###Outputhelperdeclarationsneededbythetask"
        )
        self.assertEqual(
            "func solve(values []int) int {\n"
            "total:=0;for _, value := range values{if value < 2 {continue};total = total + value}\n"
            "    return total\n"
            "}",
            _extract_generated_code(raw, "PROMPT", language="go"),
        )

    def test_extract_generated_code_recovers_go_entrypoint_after_compacted_prompt_echo(self) -> None:
        raw = """func guard_loop_accumulator_go_positive_s04(values []int) int {

OutputonlyGofunction/helperdeclarationsneededbythetask;nomarkdownfencesandnoexplanation.
Donotemitapackagedeclaration,imports,tests,assertions,printexamples,orlinesbeginningwith.
Realizethecarrierplansilentlyinsidethefinalprogramstructure;neverlistcarriersnippetsseparately.
Preserveeverypublicfunctionsignaturethatappearsinthebasecode.
Startdirectlywiththeexactfuncdeclarationfromthetaskprompt.
TheevaluatorsuppliestheGowrapper;donotemitapackagedeclaration.
Preservetheexactfunctionnameandsignaturerequestedinthetaskprompt.
Use`_`foranunusedrangeindex,forexample`for _,value:= range values`.
DonotemitproseormarkdownbeforethefirstGodeclaration.
Thefirstnon-emptyoutputlinemustbeexactly:`funcguard_loop_accumulator_go_positive_s04(values[]int)int{`
Theoutputmustcontainthatfunctionbodyandclosingbrace.
func guard_loop_accumulator_go_positive_s04(values []int) int {
\ttotal := 0
\tfor _, value := range values {
\t\tif value < 5 {
\t\t\tcontinue
\t\t}
\t\tif value%7 == 5 {
\t\t\tcontinue
\t\t}
\t\ttotal += value
\t}
    return total
}
Outputcode"""
        self.assertEqual(
            "func guard_loop_accumulator_go_positive_s04(values []int) int {\n"
            "\ttotal := 0\n"
            "\tfor _, value := range values {\n"
            "\t\tif value < 5 {\n"
            "\t\t\tcontinue\n"
            "\t\t}\n"
            "\t\tif value%7 == 5 {\n"
            "\t\t\tcontinue\n"
            "\t\t}\n"
            "\t\ttotal += value\n"
            "\t}\n"
            "    return total\n"
            "}",
            _extract_generated_code(
                raw,
                "Use entrypoint `func guard_loop_accumulator_go_positive_s04(values []int) int`.",
                language="go",
            ),
        )

    def test_extract_generated_code_recovers_go_entrypoint_after_metadata_echo(self) -> None:
        raw = """func solve(values []int) int {

CarrierKey:semcodebook-demo-key
Environment:ssa
BitTarget:0
BaseCodeKey:base-key-a
OutputOnly:true
func solve(values []int) int {
\ttotal := 0
\tfor _, value := range values {
\t\ttotal += value
\t}
\treturn total
}
"""
        self.assertEqual(
            "func solve(values []int) int {\n"
            "\ttotal := 0\n"
            "\tfor _, value := range values {\n"
            "\t\ttotal += value\n"
            "\t}\n"
            "    return total\n"
            "}",
            _extract_generated_code(raw, "Use entrypoint `func solve(values []int) int`.", language="go"),
        )

    def test_extract_generated_code_preserves_go_helper_and_strips_transcript(self) -> None:
        raw = """func guard_helper_accumulator_go_positive_s01(values []int) int {

Language:go
OutputonlyGofunction/helperdeclarationsneededbythetask

func helper_guard_helper_accumulator_go_positive_s01(value int) bool {
    return value >= 0 && value%4 == 3
}

func guard_helper_accumulator_go_positive_s01(values []int) int {
    total := 0
    for _, value := range values {
        if helper_guard_helper_accumulator_go_positive_s01(value) {
            total += value
        }
    }
    return total
}
###Outputcode
go run main.go
10
###Outputcode
go test -v
=== RUN   TestTotalOnlyPositiveMultiplesOfFour
--- PASS: TestTotalOnlyPositiveMultiplesOfFour (0.00s)
PASS
ok  \tcommand-line-arguments\t0.002s
"""
        self.assertEqual(
            "func helper_guard_helper_accumulator_go_positive_s01(value int) bool {\n"
            "    return value >= 0 && value%4 == 3\n"
            "}\n\n"
            "func guard_helper_accumulator_go_positive_s01(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        if helper_guard_helper_accumulator_go_positive_s01(value) {\n"
            "            total += value\n"
            "        }\n"
            "    }\n"
            "    return total\n"
            "}",
            _extract_generated_code(
                raw,
                "Use entrypoint `func guard_helper_accumulator_go_positive_s01(values []int) int`.",
                language="go",
            ),
        )

    def test_extract_generated_code_normalizes_go_compact_signature_and_helper_frontier(self) -> None:
        raw = """funccontainer_helper_go_positive_s01(values []int) int {
    total := 0
    for _, value := range values {
        normalized := funchelper_container_helper_go_positive_s01(value)
        if value >= 0 {
            total += normalized
        }
    }
    return total
}
funchelper_container_helper_go_positive_s01(value int) int {
    return value + 3 + (value % 3)
}
"""
        self.assertEqual(
            "func container_helper_go_positive_s01(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        normalized := helper_container_helper_go_positive_s01(value)\n"
            "        if value >= 0 {\n"
            "            total += normalized\n"
            "        }\n"
            "    }\n"
            "    return total\n"
            "}\n"
            "func helper_container_helper_go_positive_s01(value int) int {\n"
            "    return value + 3 + (value % 3)\n"
            "}",
            _extract_generated_code(
                raw,
                "Use entrypoint `func container_helper_go_positive_s01(values []int) int`.",
                language="go",
            ),
        )

    def test_extract_generated_code_strips_go_compact_prompt_leak_before_real_code(self) -> None:
        raw = """-Realizethecarrierplansilentlyinsidethefinalprogramstructure;neverlistcarriersnippetsseparately.
-Preserveeverypublicfunctionsignaturethatappearsinthebasecode.
-TheevaluatorsuppliestheGowrapper;donotemitapackagedeclaration.
RequiredGooutputshape:-Thefirstnon-emptyoutputlinemustbeexactly:`funccontainer_helper_go_positive_s01(values[]int)int{`-Theoutputmustcontainthatfunctionbodyandclosingbrace.
TaskPrompt:Writeagoimplementationforproblemfamily`container_helper`.
func container_helper_go_positive_s01(values []int) int {
    total := 0
    for _, value := range values {
        total += value
    }
    return total
}
"""
        self.assertEqual(
            "func container_helper_go_positive_s01(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        total += value\n"
            "    }\n"
            "    return total\n"
            "}",
            _extract_generated_code(
                raw,
                "Use entrypoint `func container_helper_go_positive_s01(values []int) int`.",
                language="go",
            ),
        )

    def test_extract_generated_code_dedupes_forced_go_prefix_before_compact_prompt_leak(self) -> None:
        prompt = (
            "### SemCodebook Rewrite Task\n"
            "Use entrypoint `func container_helper_go_positive_s01(values []int) int`.\n"
        )
        forced_prefix = "func container_helper_go_positive_s01(values []int) int {\n"
        decoded = (
            "-Realizethecarrierplansilentlyinsidethefinalprogramstructure;neverlistcarriersnippetsseparately.\n"
            "RequiredGooutputshape:-Thefirstnon-emptyoutputlinemustbeexactly:"
            "`funccontainer_helper_go_positive_s01(values[]int)int{`"
            "-Theoutputmustcontainthatfunctionbodyandclosingbrace.\n"
            "TaskPrompt:Writeagoimplementationforproblemfamily`container_helper`.\n"
            "funccontainer_helper_go_positive_s01(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        total += helper_container_helper_go_positive_s01(value)\n"
            "    }\n"
            "    return total\n"
            "}\n"
            "funchelper_container_helper_go_positive_s01(value int) int {\n"
            "    return value\n"
            "}"
        )
        merged = _merge_forced_output_prefix(
            decoded,
            forced_prefix,
            language="go",
            prompt=prompt,
        )
        extracted = _extract_generated_code(merged, prompt + forced_prefix, language="go")
        self.assertEqual(1, extracted.count("func container_helper_go_positive_s01("))
        self.assertEqual(1, extracted.count("func helper_container_helper_go_positive_s01("))
        self.assertNotIn("TaskPrompt", extracted)
        self.assertNotIn("RequiredGooutputshape", extracted)
        self.assertNotIn("funccontainer_helper", extracted)
        self.assertNotIn("funchelper_", extracted)

    def test_extract_generated_code_drops_unclosed_forced_go_prefix_before_helper_candidate(self) -> None:
        prompt = "Use entrypoint `func container_helper_go_positive_s01(values []int) int`."
        raw = (
            "func container_helper_go_positive_s01(values []int) int {\n\n"
            "Language-agnostic helper to normalize container values.\n\n"
            "func helper_container_helper_go_positive_s01(value int) int {\n"
            "    return value + 3 + (value % 3)\n"
            "}\n\n"
            "func container_helper_go_positive_s01(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        normalized := helper_container_helper_go_positive_s01(value)\n"
            "        if value >= 0 {\n"
            "            total += normalized\n"
            "        }\n"
            "    }\n"
            "    return total\n"
            "}"
        )
        extracted = _extract_generated_code(raw, prompt, language="go")
        self.assertTrue(extracted.startswith("func helper_container_helper_go_positive_s01("))
        self.assertEqual(1, extracted.count("func container_helper_go_positive_s01("))
        self.assertNotIn("Language-agnostic helper", extracted)

    def test_extract_generated_code_strips_go_package_and_splits_compact_declarations(self) -> None:
        prompt = "Use entrypoint `func container_helper_go_positive_s02(values []int) int`."
        raw = (
            "package main;func helper_container_helper_go_positive_s02(value int) int { return value + 4 + (value % 4) }"
            "func container_helper_go_positive_s02(values []int) int { total := 0; for _, value := range values { "
            "normalized := helper_container_helper_go_positive_s02(value); if value < 0 { continue } total += normalized }; return total }"
        )
        extracted = _extract_generated_code(raw, prompt, language="go")
        self.assertFalse(extracted.startswith("package main"))
        self.assertIn("func helper_container_helper_go_positive_s02(", extracted)
        self.assertIn("}\n\nfunc container_helper_go_positive_s02(", extracted)
        self.assertIn("}\n    total += normalized", extracted)

    def test_extract_generated_code_strips_go_transcript_tail_after_complete_declarations(self) -> None:
        prompt = "Use entrypoint `func container_helper_go_positive_s01(values []int) int`."
        raw = (
            "func helper_container_helper_go_positive_s01(value int) int {return value + 3 + (value % 3)}\n\n"
            "func container_helper_go_positive_s01(values []int) int {total := 0; for _, value := range values {"
            "normalized := helper_container_helper_go_positive_s01(value); if value >= 0 {total += normalized}}; return total}\n"
            "###Instruction:"
        )
        extracted = _extract_generated_code(raw, prompt, language="go")
        self.assertIn("func helper_container_helper_go_positive_s01(", extracted)
        self.assertIn("func container_helper_go_positive_s01(", extracted)
        self.assertNotIn("###Instruction", extracted)

    def test_extract_generated_code_handles_package_compact_declarations_and_transcript_tail(self) -> None:
        prompt = "Use entrypoint `func container_helper_go_positive_s01(values []int) int`."
        raw = (
            "package main;func helper_container_helper_go_positive_s01(value int) int {return value + 3 + (value % 3)}"
            "func container_helper_go_positive_s01(values []int) int {total := 0; for _, value := range values {"
            "normalized := helper_container_helper_go_positive_s01(value); if value >= 0 {total += normalized}}; "
            "return total}\n"
            "###Instruction:###SemCodebook"
        )
        extracted = _extract_generated_code(raw, prompt, language="go")
        self.assertFalse(extracted.startswith("package main"))
        self.assertIn("}\n\nfunc container_helper_go_positive_s01(", extracted)
        self.assertNotIn("###Instruction", extracted)
        self.assertNotIn("###SemCodebook", extracted)

    def test_extract_generated_code_normalizes_go_compact_helper_signature_spacing(self) -> None:
        prompt = "Use entrypoint `func container_helper_go_positive_s02(values []int) int`."
        raw = (
            "func container_helper_go_positive_s02(values []int) int {\n\n"
            "\ttotal := 0\n"
            "\tfor _, value := range values {\n"
            "\t\tnormalized := helper_container_helper_go_positive_s02(value)\n"
            "\t\tif value >= 0 {\n"
            "\t\t\ttotal += normalized\n"
            "\t\t}\n"
            "\t}\n"
            "\treturn total\n"
            "}\n\n"
            "funchelper_container_helper_go_positive_s02(valueint)int{\n"
            "\treturnvalue+4+(value%4)\n"
            "}"
        )
        extracted = _extract_generated_code(raw, prompt, language="go")
        self.assertIn("func helper_container_helper_go_positive_s02(value int) int {", extracted)
        self.assertIn("return value+4+(value%4)", extracted)
        self.assertNotIn("valueint", extracted)
        self.assertNotIn("returnvalue", extracted)

    def test_extract_generated_code_normalizes_go_compact_body_statement_join_and_return_brace(self) -> None:
        prompt = "Use entrypoint `func container_helper_go_positive_s09(values []int) int`."
        raw = (
            "func container_helper_go_positive_s09(values []int) int {\n"
            "total:=0 for _, value := range values { "
            "normalized := helper_container_helper_go_positive_s09(value); "
            "if value >= 0 { total += normalized } } return total}\n"
            "Language-specificconstraints:-Startdirectlywiththeexactfuncdeclaration."
        )
        extracted = _extract_generated_code(raw, prompt, language="go")
        self.assertIn("total:=0\nfor _, value := range values", extracted)
        self.assertIn("return total\n}", extracted)
        self.assertNotIn("total:=0 for", extracted)
        self.assertNotIn("return total}", extracted)
        self.assertNotIn("Language-specificconstraints", extracted)

    def test_extract_generated_code_normalizes_go_v22_compact_for_boundary(self) -> None:
        prompt = "Use entrypoint `func container_helper_go_positive_s08(values []int) int`."
        raw = (
            "func helper_container_helper_go_positive_s08(value int) int { return value + 3 + (value % 2) }\n\n"
            "func container_helper_go_positive_s08(values []int) int {\n"
            "total:=0for_,value:= range values{"
            "normalized:=helper_container_helper_go_positive_s08(value);"
            "if value>=0{total+=normalized}}\n"
            "    return total\n"
            "}"
        )
        extracted = _extract_generated_code(raw, prompt, language="go")
        self.assertIn("total:=0\nfor _, value := range values", extracted)
        self.assertNotIn("total:=0for_", extracted)
        self.assertNotIn("for_,value", extracted)
        self.assertNotIn("for _,value", extracted)

    def test_go_raw_decoder_prompt_echo_is_not_usable_fallback(self) -> None:
        raw = (
            "package main\n"
            "Language-specific constraints:\n"
            "- Start directly with the exact func declaration from the task prompt.\n"
            "TaskPrompt: Write a Go implementation.\n"
        )
        self.assertEqual("", _extract_generated_code(raw, "PROMPT", language="go"))
        self.assertFalse(_allow_raw_decoder_fallback(raw, language="go"))
        self.assertFalse(_allow_raw_decoder_fallback("package main", language="go"))

    def test_extract_generated_code_normalizes_python_compact_continuation(self) -> None:
        raw = (
            "def helper_transform(value):\n"
            "    return value\n\n"
            "def guard_loop_accumulator_python_positive_s01(values):\n"
            "    total=0forvalue in values:if value < 2:continueif value % 4 == 2:continuehelper=helper_transform(value)total+=helperreturn total"
        )
        self.assertEqual(
            "def helper_transform(value):\n"
            "    return value\n\n"
            "def guard_loop_accumulator_python_positive_s01(values):\n"
            "    total=0\n"
            "    for value in values:\n"
            "        if value < 2:\n"
            "            continue\n"
            "        if value % 4 == 2:\n"
            "            continue\n"
            "        helper=helper_transform(value)\n"
            "        total+=helper\n"
            "    return total",
            _extract_generated_code(raw, "PROMPT", language="python"),
        )

    def test_extract_generated_code_normalizes_python_spaced_compact_body_with_helper_prefix(self) -> None:
        raw = (
            "def helper_transform(value):\n"
            "    return value\n\n"
            "def guard_loop_accumulator_python_positive_s02(values):\n"
            "        total = int(0)    for value in values:        if value < 3:            continue"
            "        if value % 5 == 3:            continue        total += helper_transform(value)"
            "    final_total = total    returnfinal_total"
        )
        self.assertEqual(
            "def helper_transform(value):\n"
            "    return value\n\n"
            "def guard_loop_accumulator_python_positive_s02(values):\n"
            "        total = int(0)\n"
            "        for value in values:\n"
            "            if value < 3:\n"
            "                continue\n"
            "            if value % 5 == 3:\n"
            "                continue\n"
            "            total += helper_transform(value)\n"
            "        final_total = total\n"
            "        return final_total",
            _extract_generated_code(raw, "PROMPT", language="python"),
        )

    def test_extract_generated_code_recovers_python_after_forced_stub_prompt_residue(self) -> None:
        prompt = "Use entrypoint `def guard_helper_accumulator_python_positive_s03(values):`."
        raw = (
            "def guard_helper_accumulator_python_positive_s03(values):\n"
            "Language-independent helper-style helper function.\n"
            "    total = int(0)\n"
            "    for value in values:\n"
            "        if helper_guard_helper_accumulator_python_positive_s03(value):\n"
            "            total += value\n"
            "    return total\n\n"
            "def helper_guard_helper_accumulator_python_positive_s03(value):\n"
            "    return value >= 2 and value % 6 == 5\n\n"
            "def guard_helper_accumulator_python_positive_s03(values):\n"
            "    total = int(0)\n"
            "    for value in values:\n"
            "        if helper_guard_helper_accumulator_python_positive_s03(value):\n"
            "            total += value\n"
            "    return total\n"
        )

        extracted = _extract_generated_code(raw, prompt, language="python")

        self.assertIn("def helper_guard_helper_accumulator_python_positive_s03", extracted)
        self.assertEqual(1, extracted.count("def guard_helper_accumulator_python_positive_s03"))
        compile(extracted, "<semcodebook-python-forced-stub-recovery>", "exec")

    def test_extract_generated_code_normalizes_deepseek_python_index_loop_continuation(self) -> None:
        raw = (
            "def helper_transform(value):\n"
            "    return value\n\n"
            "def guard_loop_accumulator_python_positive_s01(values):\n"
            "    total=0forindex in range(len(values)):value=values[index]ifvalue<2:continueifvalue%4==2:continuehelper_transform(value)total+=helper_transform(value)returntotal"
        )
        self.assertEqual(
            "def helper_transform(value):\n"
            "    return value\n\n"
            "def guard_loop_accumulator_python_positive_s01(values):\n"
            "    total=0\n"
            "    for index in range(len(values)):\n"
            "        value=values[index]\n"
            "        if value<2:\n"
            "            continue\n"
            "        if value%4==2:\n"
            "            continue\n"
            "        helper_transform(value)\n"
            "        total+=helper_transform(value)\n"
            "    return total",
            _extract_generated_code(raw, "PROMPT", language="python"),
        )

    def test_cpp_prompt_requires_vector_include_when_needed(self) -> None:
        prompt = build_structured_generation_prompt(
            prompt="write c++",
            language="cpp",
            wm_id=8,
            base_code="int solve(const std::vector<int>& values) { return 0; }",
            schedule=(
                CarrierScheduleEntry(
                    family="iteration_style",
                    slot_index=0,
                    role="data",
                    target_bit=0,
                    applicable=True,
                ),
            ),
            carrier_key="key",
            task_id="task",
        )
        self.assertIn("the first output line must be #include <vector>", prompt)
        self.assertIn("Every statement must end with a semicolon", prompt)

    def test_cpp_decoder_prefix_forces_required_signature_and_vector_include(self) -> None:
        request = GenerationRequest(
            prompt="The callable must use exactly this entry point: `int solve(const std::vector<int>& values)`.",
            language="cpp",
            wm_id=1,
            model_name="unit-test",
        )
        prefix, notes = _decoder_forced_output_prefix(
            request,
            "#include <vector>\nint solve(const std::vector<int>& values) { return 0; }",
        )
        self.assertEqual("#include <vector>\n\nint solve(const std::vector<int>& values) {\n", prefix)
        self.assertEqual(("decoder_forced_prefix:cpp_entrypoint_signature",), notes)

    def test_cpp_decoder_prefix_preserves_supporting_helper_from_base_code(self) -> None:
        request = GenerationRequest(
            prompt="The callable must use exactly this entry point: `int guard_helper_accumulator_cpp_positive_s01(const std::vector<int>& values)`.",
            language="cpp",
            wm_id=1,
            model_name="unit-test",
        )
        base_code = (
            "#include <vector>\n"
            "static bool helper_guard_helper_accumulator_cpp_positive_s01(int value) { return value >= 0 && value % 4 == 3; }\n\n"
            "int guard_helper_accumulator_cpp_positive_s01(const std::vector<int>& values) {\n"
            "    int total = 0;\n"
            "    for (int value : values) { if (helper_guard_helper_accumulator_cpp_positive_s01(value)) total += value; }\n"
            "    return total;\n"
            "}\n"
        )
        prefix, notes = _decoder_forced_output_prefix(request, base_code)
        self.assertEqual(
            "#include <vector>\n"
            "static bool helper_guard_helper_accumulator_cpp_positive_s01(int value) { return value >= 0 && value % 4 == 3; }\n\n"
            "int guard_helper_accumulator_cpp_positive_s01(const std::vector<int>& values) {\n",
            prefix,
        )
        self.assertIn("decoder_forced_prefix:cpp_base_support_prefix", notes)

    def test_cpp_decoder_prefix_can_reserve_scheduled_helper(self) -> None:
        request = GenerationRequest(
            prompt="The callable must use exactly this entry point: `int solve(const std::vector<int>& values)`.",
            language="cpp",
            wm_id=1,
            model_name="unit-test",
        )
        prefix, notes = _decoder_forced_output_prefix(
            request,
            "#include <vector>\nint solve(const std::vector<int>& values) { return 0; }",
            (
                CarrierScheduleEntry(
                    family="helper_extraction_style",
                    slot_index=0,
                    role="data",
                    target_bit=1,
                    applicable=True,
                ),
            ),
        )
        self.assertIn("int helper_transform(int value)", prefix)
        self.assertTrue(prefix.endswith("int solve(const std::vector<int>& values) {\n"))
        self.assertIn("decoder_forced_prefix:cpp_helper_identity", notes)

    def test_cpp_support_materializer_recovers_prefix_only_failure_frontier(self) -> None:
        request = GenerationRequest(
            prompt="The callable must use exactly this entry point: `int container_helper_cpp_positive_s01(const std::vector<int>& values)`.",
            language="cpp",
            wm_id=1,
            model_name="unit-test",
            validation_tests=(
                "assert container_helper_cpp_positive_s01(std::vector<int>{0, 1, 2, 4, 6}) == 20;",
            ),
        )
        base_code = (
            "#include <vector>\n"
            "static int helper_container_helper_cpp_positive_s01(int value) { return value + 3 + (value % 3); }\n\n"
            "int container_helper_cpp_positive_s01(const std::vector<int>& values) {\n"
            "    int total = 0;\n"
            "    for (int value : values) {\n"
            "        int normalized = helper_container_helper_cpp_positive_s01(value);\n"
            "        if (value >= 0) total += normalized;\n"
            "    }\n"
            "    return total;\n"
            "}\n"
        )
        schedule = (
            CarrierScheduleEntry(
                family="return_expression_style",
                slot_index=0,
                role="data",
                target_bit=1,
                applicable=True,
            ),
            CarrierScheduleEntry(
                family="accumulator_style",
                slot_index=1,
                role="data",
                target_bit=1,
                applicable=True,
            ),
        )
        variants = _language_support_materializer_variants(base_code, request, schedule)
        self.assertTrue(variants)
        label, variant = variants[0]
        self.assertIn("cpp_materializer", label)
        self.assertIn("int nextTotal = total + normalized;", variant)
        self.assertIn("int finalTotal = total;", variant)
        self.assertNotEqual("".join(base_code.split()), "".join(variant.split()))

    def test_extract_generated_code_preserves_cpp_helper_and_strips_transcript(self) -> None:
        raw = """#include <vector>
static bool helper_guard_helper_accumulator_cpp_positive_s01(int value) { return value >= 0 && value % 4 == 3; }

int guard_helper_accumulator_cpp_positive_s01(const std::vector<int>& values) {
    int total = 0;
    for (int value : values) {
        if (helper_guard_helper_accumulator_cpp_positive_s01(value)) total += value;
    }
    return total;
}
###Outputcode
g++ candidate.cpp -std=c++17 && ./a.out
29
"""
        self.assertEqual(
            "#include <vector>\n"
            "static bool helper_guard_helper_accumulator_cpp_positive_s01(int value) { return value >= 0 && value % 4 == 3; }\n\n"
            "int guard_helper_accumulator_cpp_positive_s01(const std::vector<int>& values) {\n"
            "    int total = 0;\n"
            "    for (int value : values) {\n"
            "        if (helper_guard_helper_accumulator_cpp_positive_s01(value)) total += value;\n"
            "    }\n"
            "    return total;\n"
            "}",
            _extract_generated_code(
                raw,
                "Use entrypoint `int guard_helper_accumulator_cpp_positive_s01(const std::vector<int>& values)`.",
                language="cpp",
            ),
        )

    def test_extract_generated_code_normalizes_byte_level_decode_markers(self) -> None:
        prompt = "### SemCodebook Rewrite Task\nLanguage: python\n### Output code\n"
        raw = (
            "###\u0120SemCodebook\u0120Rewrite\u0120Task\u010a"
            "Language:\u0120python\u010a"
            "###\u0120Output\u0120code\u010a"
            "def\u0120solve(values):\u010a"
            "\u0120\u0120\u0120\u0120return\u0120sum(values)\u010a"
        )
        self.assertEqual(
            "def solve(values):\n    return sum(values)",
            _extract_generated_code(raw, prompt, language="python"),
        )

    def test_generated_token_slice_decodes_only_new_tokens(self) -> None:
        self.assertEqual([4, 5], _generated_token_slice([1, 2, 3, 4, 5], 3))
        self.assertEqual([1, 2], _generated_token_slice([1, 2], 3))

    def test_go_generation_uses_minimum_new_token_floor(self) -> None:
        request = GenerationRequest(prompt="write go", language="go", wm_id=1, model_name="unit-test", max_new_tokens=40)
        self.assertEqual({"min_new_tokens": 40}, _generation_length_kwargs(request))
        other = GenerationRequest(prompt="write python", language="python", wm_id=1, model_name="unit-test")
        self.assertEqual({"min_new_tokens": 64}, _generation_length_kwargs(other))

    def test_language_specific_defaults_apply_to_java_and_cpp(self) -> None:
        java_request = GenerationRequest(prompt="write java", language="java", wm_id=1, model_name="unit-test")
        cpp_request = GenerationRequest(prompt="write cpp", language="cpp", wm_id=1, model_name="unit-test")
        self.assertEqual({"min_new_tokens": 96}, _generation_length_kwargs(java_request))
        self.assertEqual({"min_new_tokens": 96}, _generation_length_kwargs(cpp_request))

    def test_extract_generated_code_removes_generated_artifact_lines(self) -> None:
        raw = """def helper(value):
###Outputcode###
    return value
###Outputcode###
def solve(values):
    total = helper(0)
    for value in values:
        total += value
    return total
###Outputcode###
- role=data; family=temporary_binding_style; target_bit=1
"""
        self.assertEqual(
            "def helper(value):\n    return value\ndef solve(values):\n    total = helper(0)\n    for value in values:\n        total += value\n    return total",
            _extract_generated_code(raw, "PROMPT", language="python"),
        )

    def test_extract_generated_code_removes_carrier_guidance_bullets(self) -> None:
        raw = """- Helper extraction style: Helper calls are inlined without an identity helper.
#include <vector>
int solve(const std::vector<int>& values) {
    return 0;
}
"""
        self.assertEqual(
            "#include <vector>\nint solve(const std::vector<int>& values) {\n    return 0;\n}",
            _extract_generated_code(raw, "PROMPT", language="cpp"),
        )

    def test_extract_generated_code_removes_cpp_colon_prelude(self) -> None:
        raw = """:
#include<vector>
int solve(const std::vector<int>& values) {
    return 0;
}
"""
        self.assertEqual(
            "#include <vector>\nint solve(const std::vector<int>& values) {\n    return 0;\n}",
            _extract_generated_code(raw, "PROMPT", language="cpp"),
        )

    def test_extract_generated_code_normalizes_cpp_compact_tokens(self) -> None:
        raw = (
            "#include <vector>\n\n"
            "int solve(const std::vector<int>& values) {\n"
            "inttotal=0;for(intvalue:values){total+=value;}returntotal;}"
        )
        self.assertEqual(
            "#include <vector>\n\n"
            "int solve(const std::vector<int>& values) {\n"
            "int total=0;\n"
            "for (int value : values){total+=value;}\n"
            "    return total;}",
            _extract_generated_code(raw, "PROMPT", language="cpp"),
        )

    def test_extract_generated_code_repairs_cpp_compact_cfg_branch_frontier(self) -> None:
        raw = (
            "#include <vector>\n"
            "int cfg_branch_normalization_cpp_positive_s01(const std::vector<int>& values){"
            "inttotal=0;for(intvalue:values){intc;if(value<0)c=0;"
            "elseif(value%2==0)c=value/3;elsec=value+4;total+=c;}"
            "returntotal;}"
        )
        extracted = _extract_generated_code(raw, "PROMPT", language="cpp")

        self.assertIn("int cfg_branch_normalization_cpp_positive_s01", extracted)
        self.assertIn("else if (value%2==0)", extracted)
        self.assertIn("else c=value+4;", extracted)
        self.assertIn("return total", extracted)
        self.assertNotIn("elseif", extracted)
        self.assertNotIn("elsec", extracted)

    def test_extract_generated_code_recovers_output_assignment_echo(self) -> None:
        raw = """function guard(values) {
Language=javascript
Carrier-Key=semcodebook-demo-key
Output=function guard(values) {
    let total = Number(0);
    for (const value of values) {
        total += value;
    }
    return total;
}
Scheduled Carriers
helper_call_boundary=function helper_transform(value) { return value; };
"""
        self.assertEqual(
            "function guard(values) {\n    let total = Number(0);\n    for (const value of values) {\n        total += value;\n    }\n    return total;\n}",
            _extract_generated_code(raw, "PROMPT", language="javascript"),
        )

    def test_extract_generated_code_skips_control_contract_prelude(self) -> None:
        raw = """Output contract:
- Output only runnable source code.
- Preserve every public function.
#include <vector>
int solve(std::vector<int> values) {
    int total = 0;
    return total;
}
"""
        self.assertEqual(
            "#include <vector>\nint solve(std::vector<int> values) {\n    int total = 0;\n    return total;\n}",
            _extract_generated_code(raw, "PROMPT", language="cpp"),
        )

    def test_extract_generated_code_removes_prompt_lines_inside_candidate(self) -> None:
        raw = """Instruction: rewrite the base code into a semantically equivalent complete source file.
Output contract:
- Output only runnable source code, with no markdown fences and no explanation.
- Preserve every public function, class, and method signature that appears in the base code.
- Realize the carrier plans silently inside the final program structure.
public class GuardLoopAccumulatorJavaPositiveS01 {
    public static int guard_loop_accumulator_java_positive_s01(int[] values) {
        int total = 0;
        for (int value : values) {
            if (value < 2) {
                continue;
            }
            total += value;
        }
        return total;
    }
}
"""
        self.assertEqual(
            "public class GuardLoopAccumulatorJavaPositiveS01 {\n"
            "    public static int guard_loop_accumulator_java_positive_s01(int[] values) {\n"
            "        int total = 0;\n"
            "        for (int value : values) {\n"
            "            if (value < 2) {\n"
            "                continue;\n"
            "            }\n"
            "            total += value;\n"
            "        }\n"
            "        return total;\n"
            "    }\n"
            "}",
            _extract_generated_code(raw, "PROMPT", language="java"),
        )

    def test_extract_generated_code_removes_task_prompt_echo_lines(self) -> None:
        raw = """Write a C++ implementation for the problem family `guard_loop_accumulator`.
The callable must use exactly this entry point: `int guard_loop_accumulator_cpp_positive_s01(const std::vector<int>& values)`.
- Every scheduled carrier, including the anchor slot, must be realized through semantically valid structure choices.
#include <vector>
int guard_loop_accumulator_cpp_positive_s01(const std::vector<int>& values) {
    int total = 0;
    for (int value : values) {
        total += value;
    }
    return total;
}
"""
        self.assertEqual(
            "#include <vector>\n"
            "int guard_loop_accumulator_cpp_positive_s01(const std::vector<int>& values) {\n"
            "    int total = 0;\n"
            "    for (int value : values) {\n"
            "        total += value;\n"
            "    }\n"
            "    return total;\n"
            "}",
            _extract_generated_code(raw, "PROMPT", language="cpp"),
        )

    def test_extract_generated_code_removes_language_constraint_echo_lines(self) -> None:
        js_raw = """Language-specific helper extraction style
function guard(values) {
    return values[0] ?? 0;
}
"""
        self.assertEqual(
            "function guard(values) {\n    return values[0] ?? 0;\n}",
            _extract_generated_code(js_raw, "PROMPT", language="javascript"),
        )
        java_raw = """Language-specificconstraints:-ReturnonecompleteJavasourcefilewiththerequiredpublicclassandallclosingbraces.
public class Solution {
    public static int solve(int[] values) {
        return values.length;
    }
}
"""
        self.assertEqual(
            "public class Solution {\n"
            "    public static int solve(int[] values) {\n"
            "        return values.length;\n"
            "    }\n"
            "}",
            _extract_generated_code(java_raw, "PROMPT", language="java"),
        )
        cpp_raw = """Language-agnostic helper-extraction style
#include <vector>
int solve(const std::vector<int>& values) {
    return static_cast<int>(values.size());
}
"""
        self.assertEqual(
            "#include <vector>\n"
            "int solve(const std::vector<int>& values) {\n"
            "    return static_cast<int>(values.size());\n"
            "}",
            _extract_generated_code(cpp_raw, "PROMPT", language="cpp"),
        )

    def test_extract_generated_code_repairs_compact_java_and_trailing_prompt_echo(self) -> None:
        raw = (
            "publicclassGuardLoopAccumulatorJavaPositiveS02{"
            "publicstaticintguard_loop_accumulator_java_positive_s02(int[]values){"
            "inttotal=0;for(intindex=0;index<values.length;index++){"
            "if(values[index]<3)continue;if((values[index]%5)==3)continue;"
            "total+=values[index];}returntotal;}}"
            "privatestaticintinitial_total_helper(int[]values){return0;}"
            "###Instruction:###SemCodebookRewriteTaskLanguage:python"
        )
        extracted = _extract_generated_code(raw, "PROMPT", language="java")

        self.assertIn("public class GuardLoopAccumulatorJavaPositiveS02", extracted)
        self.assertIn("public static int guard_loop_accumulator_java_positive_s02(int[] values)", extracted)
        self.assertIn("private static int initial_total_helper(int[] values)", extracted)
        self.assertNotIn("###Instruction", extracted)
        self.assertNotIn("publicclass", extracted)
        self.assertNotIn("publicstaticint", extracted)

    def test_extract_generated_code_repairs_compact_java_cfg_branch_frontier(self) -> None:
        raw = (
            "publicclassCfgBranchNormalizationJavaPositiveS01{"
            "publicstaticintcfg_branch_normalization_java_positive_s01(int[]values){"
            "inttotal=0;for(intvalue:values){intc;if(value<0)c=0;"
            "elseif(value%2==0)c=value/3;elsec=value+4;total+=c;}"
            "returntotal;}}###Outputcode###Response:"
            "publicclassCfgBranchNormalizationJavaPositiveS01{"
            "publicstaticintcfg_branch_normalization_java_positive_s01(int[]values){"
            "inttotal=0;returntotal;}}"
        )
        extracted = _extract_generated_code(raw, "PROMPT", language="java")

        self.assertIn("public class CfgBranchNormalizationJavaPositiveS01", extracted)
        self.assertIn("public static int cfg_branch_normalization_java_positive_s01(int[] values)", extracted)
        self.assertIn("else if (value%2==0)", extracted)
        self.assertIn("else c=value+4;", extracted)
        self.assertIn("return total;", extracted)
        self.assertNotIn("elseif", extracted)
        self.assertNotIn("elsec", extracted)
        self.assertNotIn("returntotal", extracted)

    def test_merge_forced_python_prefix_does_not_nest_repeated_entrypoint(self) -> None:
        prompt = "Use entrypoint `def guard_loop_accumulator_python_positive_s08(values):`."
        prefix = (
            "def helper_transform(value):\n"
            "    return value\n\n"
            "def guard_loop_accumulator_python_positive_s08(values):\n"
            "    "
        )
        decoded = (
            "def guard_loop_accumulator_python_positive_s08(values):\n"
            "###Outputcode###\n"
            "    total = 0\n"
            "    for value in values:\n"
            "        total += helper_transform(value)\n"
            "    final_total = total\n"
            "    return final_total\n"
        )
        merged = _merge_forced_output_prefix(decoded, prefix, language="python", prompt=prompt, base_code="")
        extracted = _extract_generated_code(merged, prompt, language="python")

        self.assertEqual(1, extracted.count("def guard_loop_accumulator_python_positive_s08"))
        self.assertIn("def helper_transform(value):", extracted)
        compile(extracted, "<semcodebook-python-merge-test>", "exec")

    def test_candidate_rank_prefers_target_recovery_after_semantics(self) -> None:
        base_kwargs = dict(
            semantic_ok=True,
            compile_ok=True,
            decision_status="watermarked",
            positive_support_score=1.0,
            positive_support_family_count=4,
            positive_support_level_count=2,
            scheduled_realization_ratio=1.0,
            data_realization_ratio=1.0,
            anchor_realized=True,
            applicability_realization_ratio=1.0,
            realized_confidence_mean=0.8,
            realized_confidence_sum=5.6,
        )
        exact_rank = _candidate_rank(
            **base_kwargs,
            target_recovery_match=True,
            target_recovery_bit_match_fraction=1.0,
        )
        near_rank = _candidate_rank(
            **base_kwargs,
            target_recovery_match=False,
            target_recovery_bit_match_fraction=0.75,
        )
        invalid_exact_rank = _candidate_rank(
            **{**base_kwargs, "semantic_ok": False, "compile_ok": False},
            target_recovery_match=True,
            target_recovery_bit_match_fraction=1.0,
        )
        self.assertGreater(exact_rank, near_rank)
        self.assertGreater(near_rank, invalid_exact_rank)

    def test_candidate_rank_prefers_changed_code_after_target_recovery(self) -> None:
        base_kwargs = dict(
            semantic_ok=True,
            compile_ok=True,
            target_recovery_match=True,
            target_recovery_bit_match_fraction=1.0,
            decision_status="watermarked",
            positive_support_score=1.0,
            positive_support_family_count=4,
            positive_support_level_count=2,
            scheduled_realization_ratio=1.0,
            data_realization_ratio=1.0,
            anchor_realized=True,
            applicability_realization_ratio=1.0,
            realized_confidence_mean=0.8,
            realized_confidence_sum=5.6,
        )
        changed_rank = _candidate_rank(**base_kwargs, code_changed=True)
        unchanged_rank = _candidate_rank(**base_kwargs, code_changed=False)
        self.assertGreater(changed_rank, unchanged_rank)
        self.assertFalse(_generation_code_changed("func solve(values []int) int { return 0 }", "func solve(values []int) int { return 0 }"))
        self.assertTrue(_generation_code_changed("func solve(values []int) int { result := 0; return result }", "func solve(values []int) int { return 0 }"))

    def test_target_recovery_metrics_are_generation_side_objectives(self) -> None:
        self.assertEqual((True, 1.0), _target_recovery_metrics(_DetectionStub(wm_id_hat=13), 13))
        self.assertEqual((False, 0.75), _target_recovery_metrics(_DetectionStub(wm_id_hat=12), 13))
        self.assertEqual((True, 1.0), _target_recovery_metrics(_DetectionStub(wm_id_hat=None, decoded_wm_id_candidate=13), 13))
        self.assertEqual((False, 0.75), _target_recovery_metrics(_DetectionStub(wm_id_hat=None, decoded_wm_id_candidate=12), 13))
        self.assertEqual((False, 0.0), _target_recovery_metrics(_DetectionStub(wm_id_hat=None), 13))

    def test_extract_generated_code_removes_split_signature_echo(self) -> None:
        raw = """`public static int guard_loop_accumulator_java_positive_s01(int[] values)`
in class `GuardLoopAccumulatorJavaPositiveS01`.
public class GuardLoopAccumulatorJavaPositiveS01 {
    public static int guard_loop_accumulator_java_positive_s01(int[] values) {
        int total = 0;
        return total;
    }
}
"""
        self.assertEqual(
            "public class GuardLoopAccumulatorJavaPositiveS01 {\n"
            "    public static int guard_loop_accumulator_java_positive_s01(int[] values) {\n"
            "        int total = 0;\n"
            "        return total;\n"
            "    }\n"
            "}",
            _extract_generated_code(raw, "PROMPT", language="java"),
        )

    def test_extract_generated_code_removes_inline_carrier_plan_comments(self) -> None:
        raw = """function guard(values) {
    let total = 0;
    for (const value of values) {
        total += value;
    }
    /*-role=data;family=return_expression_style;target_bit=0;applicable=true;level=ssa;signal=return_binding*/
    return total;
}
"""
        self.assertEqual(
            "function guard(values) {\n"
            "    let total = 0;\n"
            "    for (const value of values) {\n"
            "        total += value;\n"
            "    }\n"
            "    return total;\n"
            "}",
            _extract_generated_code(raw, "PROMPT", language="javascript"),
        )

    def test_extract_generated_code_stops_before_notebook_artifacts(self) -> None:
        raw = """def solve(values):
    return sum(values)
<jupyter_output>
Question 1: unrelated prompt
"""
        self.assertEqual(
            "def solve(values):\n    return sum(values)",
            _extract_generated_code(raw, "PROMPT", language="python"),
        )

    def test_extract_generated_code_stops_before_python_top_level_prose(self) -> None:
        raw = """def solve(values):
    return sum(values)
This function sums the accepted values.
Question 1: unrelated prompt
"""
        self.assertEqual(
            "def solve(values):\n    return sum(values)",
            _extract_generated_code(raw, "PROMPT", language="python"),
        )

    def test_extract_generated_code_removes_top_level_python_demo_asserts(self) -> None:
        raw = """def solve(values):
    total = 0
    for value in values:
        total += value
    return total
demo_total = solve([1, 2, 3])
print(demo_total)
assert demo_total == 10
assert solve([1, 2, 3]) == 10
"""
        self.assertEqual(
            "def solve(values):\n    total = 0\n    for value in values:\n        total += value\n    return total",
            _extract_generated_code(raw, "PROMPT", language="python"),
        )

    def test_trained_generator_forwards_request_language_to_detector(self) -> None:
        calls = []
        schedule = (
            CarrierScheduleEntry(
                family="accumulator_style",
                slot_index=0,
                role="data",
                applicable=True,
            ),
        )
        with tempfile.TemporaryDirectory() as checkpoint_dir:
            request = GenerationRequest(
                prompt="Choose the first element.",
                task_id="javascript::choose_value",
                language="javascript",
                wm_id=7,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            with mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True),              mock.patch("semcodebook.inference._load_trained_generator", return_value=(_FakeTokenizer(), _FakeModel(), "cpu")),              mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule),              mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule) as target_schedule,              mock.patch("semcodebook.inference._carrier_payload", return_value=((1, 0, 1, 1), None)),              mock.patch("semcodebook.inference.build_structured_generation_prompt", return_value="PROMPT"),              mock.patch("semcodebook.inference._semantic_validation_summary", return_value={"semantic_ok": True, "compile_ok": True}),              mock.patch(
                 "semcodebook.inference._schedule_realization_summary",
                 return_value={
                     "scheduled_realization_ratio": 1.0,
                     "data_realization_ratio": 1.0,
                     "anchor_realized": True,
                     "applicability_realization_ratio": 1.0,
                     "realized_confidence_mean": 1.0,
                     "realized_confidence_sum": 1.0,
                 },
             ),              mock.patch("semcodebook.inference._candidate_rank", return_value=(1, 1, 1, 1, 1, 1, 1, 1)),              mock.patch("semcodebook.inference._bounded_decoder_attempt", side_effect=lambda *_args, **_kwargs: contextlib.nullcontext()),              mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _RecordingDetector(calls)):
                result = _generate_with_trained_checkpoint(
                    request,
                    "function chooseValue(values) { return values[0] ?? 0; }",
                    strict_trained_generation=True,
                )

        self.assertIsNotNone(result)
        self.assertTrue(calls)
        target_schedule.assert_called_once()
        self.assertTrue(all(call["language"] == "javascript" for call in calls))
        self.assertTrue(all(call["carrier_schedule_len"] > 0 for call in calls))
        self.assertTrue(all(call["implementation_stage"] == "trained_checkpoint_generation" for call in calls))
        self.assertEqual("javascript", result.language)
        self.assertIn("function chooseValue", result.watermarked_code)

    def test_go_trained_generator_uses_standard_prompt_rendering_with_forced_prefix(self) -> None:
        calls = []
        schedule = (
            CarrierScheduleEntry(
                family="accumulator_style",
                slot_index=0,
                role="data",
                applicable=True,
            ),
        )
        with tempfile.TemporaryDirectory() as checkpoint_dir:
            request = GenerationRequest(
                prompt="Use entrypoint `func solve(values []int) int`.",
                task_id="go::solve",
                language="go",
                wm_id=7,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            with mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True),              mock.patch("semcodebook.inference._load_trained_generator", return_value=(_GoBodyTokenizer(), _FakeModel(), "cpu")),              mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule),              mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule),              mock.patch("semcodebook.inference._carrier_payload", return_value=((1, 0, 1, 1), None)),              mock.patch("semcodebook.inference.build_structured_generation_prompt", return_value="PROMPT"),              mock.patch("semcodebook.inference._semantic_validation_summary", return_value={"semantic_ok": True, "compile_ok": True}),              mock.patch(
                  "semcodebook.inference._schedule_realization_summary",
                  return_value={
                      "scheduled_realization_ratio": 1.0,
                      "data_realization_ratio": 1.0,
                      "anchor_realized": True,
                      "applicability_realization_ratio": 1.0,
                      "realized_confidence_mean": 1.0,
                      "realized_confidence_sum": 1.0,
                  },
              ),              mock.patch("semcodebook.inference._candidate_rank", return_value=(1, 1, 1, 1, 1, 1, 1, 1)),              mock.patch("semcodebook.inference._bounded_decoder_attempt", side_effect=lambda *_args, **_kwargs: contextlib.nullcontext()),              mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _RecordingDetector(calls)):
                result = _generate_with_trained_checkpoint(
                    request,
                    "func solve(values []int) int {\n    return 0\n}",
                    strict_trained_generation=True,
                )

        self.assertIsNotNone(result)
        self.assertIn("decoder_prompt_rendering:raw_prompt", result.notes)
        self.assertNotIn("decoder_prompt_rendering:raw_prompt_for_go_prefix", result.notes)
        self.assertIn("func solve(values []int) int", result.watermarked_code)

    def test_go_trained_generator_dedupes_forced_prefix_after_compact_prompt_leak(self) -> None:
        calls = []
        validated_codes = []
        schedule = (
            CarrierScheduleEntry(
                family="helper_extraction_style",
                slot_index=0,
                role="data",
                applicable=True,
                target_bit=1,
            ),
        )

        def semantic_validation(code, _request):
            validated_codes.append(code)
            return {"semantic_ok": True, "compile_ok": True}

        with tempfile.TemporaryDirectory() as checkpoint_dir:
            request = GenerationRequest(
                prompt="Use entrypoint `func container_helper_go_positive_s01(values []int) int`.",
                task_id="go::container_helper_go_positive_s01",
                language="go",
                wm_id=7,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            with mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True),              mock.patch("semcodebook.inference._load_trained_generator", return_value=(_GoCompactPromptLeakTokenizer(), _FakeModel(), "cpu")),              mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule),              mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule),              mock.patch("semcodebook.inference._carrier_payload", return_value=((1, 0, 1, 1), None)),              mock.patch("semcodebook.inference.build_structured_generation_prompt", return_value="PROMPT"),              mock.patch("semcodebook.inference._semantic_validation_summary", side_effect=semantic_validation),              mock.patch(
                  "semcodebook.inference._schedule_realization_summary",
                  return_value={
                      "scheduled_realization_ratio": 1.0,
                      "data_realization_ratio": 1.0,
                      "anchor_realized": True,
                      "applicability_realization_ratio": 1.0,
                      "realized_confidence_mean": 1.0,
                      "realized_confidence_sum": 1.0,
                  },
              ),              mock.patch("semcodebook.inference._candidate_rank", return_value=(1, 1, 1, 1, 1, 1, 1, 1)),              mock.patch("semcodebook.inference._bounded_decoder_attempt", side_effect=lambda *_args, **_kwargs: contextlib.nullcontext()),              mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _RecordingDetector(calls)):
                result = _generate_with_trained_checkpoint(
                    request,
                    "func container_helper_go_positive_s01(values []int) int {\n    return 0\n}",
                    strict_trained_generation=True,
                )

        self.assertIsNotNone(result)
        self.assertTrue(validated_codes)
        self.assertEqual(1, validated_codes[0].count("func container_helper_go_positive_s01("))
        self.assertEqual(1, validated_codes[0].count("func helper_container_helper_go_positive_s01("))
        self.assertNotIn("TaskPrompt", validated_codes[0])
        self.assertNotIn("RequiredGooutputshape", validated_codes[0])

    def test_go_trained_generator_retries_without_forced_prefix_after_prefix_only_stub(self) -> None:
        calls = []
        validated_codes = []
        schedule = (
            CarrierScheduleEntry(
                family="helper_extraction_style",
                slot_index=0,
                role="data",
                applicable=True,
                target_bit=1,
            ),
        )

        def semantic_validation(code, _request):
            validated_codes.append(code)
            semantic_ok = "return total" in code and "func helper_container_helper_go_positive_s01(" in code
            return {"semantic_ok": semantic_ok, "compile_ok": semantic_ok, "failure_reason": "" if semantic_ok else "prefix_only_stub"}

        with tempfile.TemporaryDirectory() as checkpoint_dir:
            request = GenerationRequest(
                prompt="Use entrypoint `func container_helper_go_positive_s01(values []int) int`.",
                task_id="go::container_helper_go_positive_s01",
                language="go",
                wm_id=7,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            fake_model = _SequentialFakeModel()
            with mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True),              mock.patch("semcodebook.inference._load_trained_generator", return_value=(_GoForcedStubThenRetryTokenizer(), fake_model, "cpu")),              mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule),              mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule),              mock.patch("semcodebook.inference._carrier_payload", return_value=((1, 0, 1, 1), None)),              mock.patch("semcodebook.inference.build_structured_generation_prompt", return_value="PROMPT"),              mock.patch("semcodebook.inference._semantic_validation_summary", side_effect=semantic_validation),              mock.patch(
                  "semcodebook.inference._schedule_realization_summary",
                  return_value={
                      "scheduled_realization_ratio": 1.0,
                      "data_realization_ratio": 1.0,
                      "anchor_realized": True,
                      "applicability_realization_ratio": 1.0,
                      "realized_confidence_mean": 1.0,
                      "realized_confidence_sum": 1.0,
                  },
              ),              mock.patch("semcodebook.inference._candidate_rank", return_value=(1, 1, 1, 1, 1, 1, 1, 1)),              mock.patch("semcodebook.inference._bounded_decoder_attempt", side_effect=lambda *_args, **_kwargs: contextlib.nullcontext()),              mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _RecordingDetector(calls)):
                result = _generate_with_trained_checkpoint(
                    request,
                    "func container_helper_go_positive_s01(values []int) int {\n    return 0\n}",
                    strict_trained_generation=True,
                )

        self.assertIsNotNone(result)
        self.assertGreaterEqual(fake_model.calls, 3)
        self.assertTrue(any(code.strip().endswith("int {") for code in validated_codes))
        self.assertIn("go_unforced_retry_after_forced_prefix_stub", result.notes)
        self.assertIn("func helper_container_helper_go_positive_s01(", result.watermarked_code)

    def test_go_trained_generator_unforced_retry_strips_transcript_tail(self) -> None:
        calls = []
        validated_codes = []
        schedule = (
            CarrierScheduleEntry(
                family="helper_extraction_style",
                slot_index=0,
                role="data",
                applicable=True,
                target_bit=1,
            ),
        )

        def semantic_validation(code, _request):
            validated_codes.append(code)
            semantic_ok = (
                "return total" in code
                and "func helper_container_helper_go_positive_s01(" in code
                and "###Instruction" not in code
            )
            return {"semantic_ok": semantic_ok, "compile_ok": semantic_ok, "failure_reason": "" if semantic_ok else "tail_leak"}

        with tempfile.TemporaryDirectory() as checkpoint_dir:
            request = GenerationRequest(
                prompt="Use entrypoint `func container_helper_go_positive_s01(values []int) int`.",
                task_id="go::container_helper_go_positive_s01",
                language="go",
                wm_id=7,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            fake_model = _SequentialFakeModel()
            with mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True),              mock.patch("semcodebook.inference._load_trained_generator", return_value=(_GoForcedStubThenTranscriptRetryTokenizer(), fake_model, "cpu")),              mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule),              mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule),              mock.patch("semcodebook.inference._carrier_payload", return_value=((1, 0, 1, 1), None)),              mock.patch("semcodebook.inference.build_structured_generation_prompt", return_value="PROMPT"),              mock.patch("semcodebook.inference._semantic_validation_summary", side_effect=semantic_validation),              mock.patch(
                  "semcodebook.inference._schedule_realization_summary",
                  return_value={
                      "scheduled_realization_ratio": 1.0,
                      "data_realization_ratio": 1.0,
                      "anchor_realized": True,
                      "applicability_realization_ratio": 1.0,
                      "realized_confidence_mean": 1.0,
                      "realized_confidence_sum": 1.0,
                  },
              ),              mock.patch("semcodebook.inference._candidate_rank", return_value=(1, 1, 1, 1, 1, 1, 1, 1)),              mock.patch("semcodebook.inference._bounded_decoder_attempt", side_effect=lambda *_args, **_kwargs: contextlib.nullcontext()),              mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _RecordingDetector(calls)):
                result = _generate_with_trained_checkpoint(
                    request,
                    "func container_helper_go_positive_s01(values []int) int {\n    return 0\n}",
                    strict_trained_generation=True,
                )

        self.assertIsNotNone(result)
        self.assertGreaterEqual(fake_model.calls, 3)
        self.assertIn("go_unforced_retry_after_forced_prefix_stub", result.notes)
        self.assertIn("func helper_container_helper_go_positive_s01(", result.watermarked_code)
        self.assertNotIn("###Instruction", result.watermarked_code)
        self.assertTrue(any("return total" in code and "###Instruction" not in code for code in validated_codes))

    def test_go_trained_generator_unforced_retry_normalizes_compact_helper_signature(self) -> None:
        calls = []
        validated_codes = []
        schedule = (
            CarrierScheduleEntry(
                family="helper_extraction_style",
                slot_index=0,
                role="data",
                applicable=True,
                target_bit=1,
            ),
        )

        def semantic_validation(code, _request):
            validated_codes.append(code)
            semantic_ok = (
                "return total" in code
                and "func helper_container_helper_go_positive_s02(value int) int {" in code
                and "valueint" not in code
                and "returnvalue" not in code
            )
            return {"semantic_ok": semantic_ok, "compile_ok": semantic_ok, "failure_reason": "" if semantic_ok else "compact_signature"}

        with tempfile.TemporaryDirectory() as checkpoint_dir:
            request = GenerationRequest(
                prompt="Use entrypoint `func container_helper_go_positive_s02(values []int) int`.",
                task_id="go::container_helper_go_positive_s02",
                language="go",
                wm_id=7,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            fake_model = _SequentialFakeModel()
            with mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True),              mock.patch("semcodebook.inference._load_trained_generator", return_value=(_GoForcedStubThenCompactSignatureRetryTokenizer(), fake_model, "cpu")),              mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule),              mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule),              mock.patch("semcodebook.inference._carrier_payload", return_value=((1, 0, 1, 1), None)),              mock.patch("semcodebook.inference.build_structured_generation_prompt", return_value="PROMPT"),              mock.patch("semcodebook.inference._semantic_validation_summary", side_effect=semantic_validation),              mock.patch(
                  "semcodebook.inference._schedule_realization_summary",
                  return_value={
                      "scheduled_realization_ratio": 1.0,
                      "data_realization_ratio": 1.0,
                      "anchor_realized": True,
                      "applicability_realization_ratio": 1.0,
                      "realized_confidence_mean": 1.0,
                      "realized_confidence_sum": 1.0,
                  },
              ),              mock.patch("semcodebook.inference._candidate_rank", return_value=(1, 1, 1, 1, 1, 1, 1, 1)),              mock.patch("semcodebook.inference._bounded_decoder_attempt", side_effect=lambda *_args, **_kwargs: contextlib.nullcontext()),              mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _RecordingDetector(calls)):
                result = _generate_with_trained_checkpoint(
                    request,
                    "func container_helper_go_positive_s02(values []int) int {\n    return 0\n}",
                    strict_trained_generation=True,
                )

        self.assertIsNotNone(result)
        self.assertGreaterEqual(fake_model.calls, 3)
        self.assertIn("go_unforced_retry_after_forced_prefix_stub", result.notes)
        self.assertIn("func helper_container_helper_go_positive_s02(value int) int {", result.watermarked_code)
        self.assertNotIn("valueint", result.watermarked_code)
        self.assertTrue(any("func helper_container_helper_go_positive_s02(value int) int {" in code for code in validated_codes))

    def test_go_trained_generator_preserves_base_helper_and_normalizes_compact_body(self) -> None:
        calls = []
        validated_codes = []
        schedule = (
            CarrierScheduleEntry(
                family="helper_extraction_style",
                slot_index=0,
                role="data",
                applicable=True,
                target_bit=1,
            ),
        )

        def semantic_validation(code, _request):
            validated_codes.append(code)
            semantic_ok = (
                "func helper_container_helper_go_positive_s09(value int) int" in code
                and "total:=0\nfor _, value := range values" in code
                and "return total\n}" in code
                and "total:=0for_" not in code
                and "for_,value" not in code
                and "total:=0 for" not in code
                and "return total}" not in code
                and "Language-specificconstraints" not in code
            )
            return {"semantic_ok": semantic_ok, "compile_ok": semantic_ok, "failure_reason": "" if semantic_ok else "compact_body"}

        with tempfile.TemporaryDirectory() as checkpoint_dir:
            request = GenerationRequest(
                prompt="Use entrypoint `func container_helper_go_positive_s09(values []int) int`.",
                task_id="go::container_helper_go_positive_s09",
                language="go",
                wm_id=7,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            base_code = (
                "func helper_container_helper_go_positive_s09(value int) int { return value + 4 + (value % 3) }\n\n"
                "func container_helper_go_positive_s09(values []int) int {\n"
                "    return 0\n"
                "}\n"
            )
            with mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True),              mock.patch("semcodebook.inference._load_trained_generator", return_value=(_GoCompactStatementBodyTokenizer(), _FakeModel(), "cpu")),              mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule),              mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule),              mock.patch("semcodebook.inference._carrier_payload", return_value=((1, 0, 1, 1), None)),              mock.patch("semcodebook.inference.build_structured_generation_prompt", return_value="PROMPT"),              mock.patch("semcodebook.inference._semantic_validation_summary", side_effect=semantic_validation),              mock.patch(
                  "semcodebook.inference._schedule_realization_summary",
                  return_value={
                      "scheduled_realization_ratio": 1.0,
                      "data_realization_ratio": 1.0,
                      "anchor_realized": True,
                      "applicability_realization_ratio": 1.0,
                      "realized_confidence_mean": 1.0,
                      "realized_confidence_sum": 1.0,
                  },
              ),              mock.patch("semcodebook.inference._candidate_rank", return_value=(1, 1, 1, 1, 1, 1, 1, 1)),              mock.patch("semcodebook.inference._bounded_decoder_attempt", side_effect=lambda *_args, **_kwargs: contextlib.nullcontext()),              mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _RecordingDetector(calls)):
                result = _generate_with_trained_checkpoint(
                    request,
                    base_code,
                    strict_trained_generation=True,
                )

        self.assertIsNotNone(result)
        self.assertIn("decoder_forced_prefix:go_base_support_prefix", result.notes)
        self.assertIn("func helper_container_helper_go_positive_s09(value int) int", result.watermarked_code)
        self.assertIn("total:=0\nfor _, value := range values", result.watermarked_code)
        self.assertTrue(validated_codes)

    def test_go_trained_generator_retries_when_semantic_candidates_lack_rewrite_support(self) -> None:
        validated_codes = []
        schedule = (
            CarrierScheduleEntry(
                family="temporary_binding_style",
                slot_index=0,
                role="data",
                bit_index=0,
                applicable=True,
                target_bit=1,
                structural_level="ast",
                notes=("discriminative_generation_planned_carrier", "target_alignment_base_bit:0"),
            ),
            CarrierScheduleEntry(
                family="return_expression_style",
                slot_index=1,
                role="data",
                bit_index=1,
                applicable=True,
                target_bit=1,
                structural_level="cfg",
                notes=("discriminative_generation_planned_carrier", "target_alignment_base_bit:0"),
            ),
        )

        def semantic_validation(code, _request):
            validated_codes.append(code)
            semantic_ok = (
                "func helper_container_helper_go_positive_s08(value int) int" in code
                and "return" in code
                and "total" in code
            )
            return {"semantic_ok": semantic_ok, "compile_ok": semantic_ok, "failure_reason": "" if semantic_ok else "invalid"}

        with tempfile.TemporaryDirectory() as checkpoint_dir:
            request = GenerationRequest(
                prompt="Use entrypoint `func container_helper_go_positive_s08(values []int) int`.",
                task_id="go::container_helper_go_positive_s08",
                language="go",
                wm_id=13,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            base_code = (
                "func helper_container_helper_go_positive_s08(value int) int { return value + 4 + (value % 3) }\n\n"
                "func container_helper_go_positive_s08(values []int) int {\n"
                "    total := 0\n"
                "    for _, value := range values {\n"
                "        normalized := helper_container_helper_go_positive_s08(value)\n"
                "        if value >= 0 {\n"
                "            total += normalized\n"
                "        }\n"
                "    }\n"
                "    return total\n"
                "}\n"
            )
            tokenizer = _GoSupportRetryTokenizer()
            fake_model = _SequentialFakeModel()
            with mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True),              mock.patch("semcodebook.inference._load_trained_generator", return_value=(tokenizer, fake_model, "cpu")),              mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule),              mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule),              mock.patch("semcodebook.inference._carrier_payload", return_value=((1, 1), None)),              mock.patch("semcodebook.inference.build_structured_generation_prompt", wraps=build_structured_generation_prompt),              mock.patch("semcodebook.inference._semantic_validation_summary", side_effect=semantic_validation),              mock.patch(
                  "semcodebook.inference._schedule_realization_summary",
                  return_value={
                      "scheduled_realization_ratio": 1.0,
                      "data_realization_ratio": 1.0,
                      "anchor_realized": True,
                      "applicability_realization_ratio": 1.0,
                      "realized_confidence_mean": 1.0,
                      "realized_confidence_sum": 1.0,
                  },
              ),              mock.patch("semcodebook.inference._bounded_decoder_attempt", side_effect=lambda *_args, **_kwargs: contextlib.nullcontext()),              mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _CodeAwareDetector()):
                result = _generate_with_trained_checkpoint(
                    request,
                    base_code,
                    strict_trained_generation=True,
                )

        self.assertIsNotNone(result)
        self.assertGreaterEqual(fake_model.calls, 3)
        self.assertIn("carrier_support_retry_after_semantic_abstain", result.notes)
        self.assertIn("selected_candidate_origin:carrier_support_retry:greedy", result.notes)
        self.assertIn("selected_decision_status:watermarked", result.notes)
        self.assertIn("selected_code_changed:true", result.notes)
        self.assertIn("nextTotal := total + normalized", result.watermarked_code)
        self.assertIn("total = nextTotal", result.watermarked_code)
        self.assertIn("result := total", result.watermarked_code)
        self.assertNotIn("total += currentItem}", result.watermarked_code)
        self.assertTrue(any("Rewrite-backed support retry" in prompt for prompt in tokenizer.prompts))
        self.assertTrue(validated_codes)

    def test_go_support_materializer_inlines_v32_helper_frontier(self) -> None:
        request = GenerationRequest(
            prompt="Use entrypoint `func container_helper_go_positive_s08(values []int) int`.",
            task_id="go::container_helper_go_positive_s08",
            language="go",
            wm_id=13,
            carrier_key="carrier-key",
            backbone_name="FakeBackbone",
            model_name="FakeModel",
        )
        frontier_code = (
            "func helper_container_helper_go_positive_s08(value int) int { return value + 3 + (value % 2) }\n\n"
            "func container_helper_go_positive_s08(values []int) int {\n"
            "total:=0;for _, value := range values {"
            "normalized:=helper_container_helper_go_positive_s08(value);"
            "if value>=0{total=total+normalized}};return total}"
        )

        variants = dict(_go_support_materializer_variants(frontier_code, request))
        materialized = variants["go_materializer:inline_private_helper_return_binding"]
        compact = materialized.replace(" ", "")

        self.assertNotIn("func helper_container_helper_go_positive_s08", materialized)
        self.assertIn("normalized:=(value+3+(value%2))", compact)
        self.assertIn("result:=total", compact)
        self.assertIn("returnresult", compact)

    def test_go_support_materializer_is_go_only_and_call_guarded(self) -> None:
        python_request = GenerationRequest(
            prompt="write python",
            language="python",
            wm_id=13,
            model_name="FakeModel",
        )
        go_request = GenerationRequest(
            prompt="Use entrypoint `func solve(values []int) int`.",
            language="go",
            wm_id=13,
            model_name="FakeModel",
        )
        unused_helper = (
            "func helper_unused(value int) int { return value + 1 }\n\n"
            "func solve(values []int) int { total := 0; return total }"
        )

        self.assertEqual((), _go_support_materializer_variants(unused_helper, python_request))
        variants = dict(_go_support_materializer_variants(unused_helper, go_request))

        self.assertNotIn("go_materializer:inline_private_helper", variants)
        self.assertIn("go_materializer:return_binding", variants)
        self.assertIn("func helper_unused(value int) int", variants["go_materializer:return_binding"])

    def test_javascript_support_materializer_adds_helper_after_entrypoint(self) -> None:
        schedule = (
            CarrierScheduleEntry(family="helper_extraction_style", slot_index=0, role="data", target_bit=1),
            CarrierScheduleEntry(family="accumulator_style", slot_index=1, role="anchor", target_bit=0),
        )
        code = (
            "function guard_loop_accumulator_javascript_positive_s05(values) {\n"
            "  let total = Number(0);\n"
            "  for (const value of values) {\n"
            "    total += value;\n"
            "  }\n"
            "  let return_total = total;\n"
            "  return return_total;\n"
            "}"
        )
        variants = dict(_javascript_support_materializer_variants(code, schedule))
        materialized = variants["javascript_materializer:helper_transform_call"]

        self.assertIn("total += helper_transform(value);", materialized)
        self.assertTrue(materialized.rstrip().endswith("function helper_transform(value) {\n  return value;\n}"))

    def test_java_support_materializer_keeps_helper_inside_class(self) -> None:
        schedule = (
            CarrierScheduleEntry(family="helper_extraction_style", slot_index=0, role="data", target_bit=1),
            CarrierScheduleEntry(family="accumulator_style", slot_index=1, role="data", target_bit=1),
        )
        code = (
            "public class GuardLoopAccumulatorJavaPositiveS01 {\n"
            "    public static int guard_loop_accumulator_java_positive_s01(int[] values) {\n"
            "        int total = 0;\n"
            "        for (int value : values) {\n"
            "            total += value;\n"
            "        }\n"
            "        return total;\n"
            "    }\n"
            "}"
        )
        variants = dict(_java_support_materializer_variants(code, schedule))
        materialized = variants["java_materializer:helper_transform_accumulator"]

        self.assertIn("total = total + helperTransform(value);", materialized)
        self.assertIn("private static int helperTransform(int value)", materialized)
        self.assertLess(materialized.index("private static int helperTransform"), materialized.rindex("}"))

    def test_go_materializer_emits_real_typed_initialization_carrier(self) -> None:
        request = GenerationRequest(
            prompt="Use entrypoint `func solve(values []int) int`.",
            language="go",
            wm_id=13,
            model_name="unit-test-model",
            carrier_key="carrier-key",
        )
        schedule = (
            CarrierScheduleEntry(family="initialization_idiom", slot_index=0, role="data", target_bit=1),
            CarrierScheduleEntry(family="iteration_style", slot_index=1, role="data", target_bit=1),
        )
        code = (
            "func solve(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        total += value\n"
            "    }\n"
            "    return total\n"
            "}\n"
        )
        variants = dict(_go_support_materializer_variants(code, request, schedule))
        label = next(name for name in variants if name.startswith("go_materializer:scheduled_"))
        materialized = variants[label]

        self.assertIn("total := int(0)", materialized)
        self.assertIn("for index := range values", materialized)
        self.assertNotIn("index := int(0)", materialized)

    def test_java_materializer_emits_real_typed_initialization_carrier(self) -> None:
        schedule = (
            CarrierScheduleEntry(family="initialization_idiom", slot_index=0, role="data", target_bit=1),
            CarrierScheduleEntry(family="iteration_style", slot_index=1, role="data", target_bit=1),
        )
        code = (
            "public class Solution {\n"
            "    public static int solve(int[] values) {\n"
            "        int total = 0;\n"
            "        for (int value : values) {\n"
            "            total += value;\n"
            "        }\n"
            "        return total;\n"
            "    }\n"
            "}\n"
        )
        variants = dict(_java_support_materializer_variants(code, schedule))
        label = next(name for name in variants if name.startswith("java_materializer:scheduled_"))
        materialized = variants[label]

        self.assertIn("int total = Integer.valueOf(0);", materialized)
        self.assertIn("for (int index = 0; index < values.length; index++)", materialized)
        self.assertNotIn("int index = Integer.valueOf(0);", materialized)

    def test_cpp_materializer_braces_single_statement_if_before_declarations(self) -> None:
        schedule = (
            CarrierScheduleEntry(family="temporary_binding_style", slot_index=0, role="data", target_bit=1),
            CarrierScheduleEntry(family="accumulator_style", slot_index=1, role="data", target_bit=1),
            CarrierScheduleEntry(family="return_expression_style", slot_index=2, role="data", target_bit=1),
            CarrierScheduleEntry(family="initialization_idiom", slot_index=3, role="data", target_bit=1),
        )
        code = (
            "#include <vector>\n"
            "static int helper_container_helper_cpp_positive_s01(int value) { return value + 3 + (value % 3); }\n\n"
            "int container_helper_cpp_positive_s01(const std::vector<int>& values) {\n"
            "    int total = 0;\n"
            "    for (int value : values) { int normalized = helper_container_helper_cpp_positive_s01(value); if (value >= 0) total += normalized; }\n"
            "    return total;\n"
            "}\n"
        )
        variants = dict(_cpp_support_materializer_variants(code, schedule))
        label = next(name for name in variants if name.startswith("cpp_materializer:scheduled_"))
        materialized = variants[label]

        self.assertIn("if (value >= 0) { int currentItem = normalized;", materialized)
        self.assertIn("int nextTotal = total + currentItem;", materialized)
        self.assertNotIn("if (value >= 0) int currentItem", materialized)

    def test_cpp_materializer_inserts_helper_declaration_and_binds_main_return(self) -> None:
        schedule = (
            CarrierScheduleEntry(family="helper_extraction_style", slot_index=0, role="data", target_bit=1),
            CarrierScheduleEntry(family="return_expression_style", slot_index=1, role="data", target_bit=1),
        )
        code = (
            "#include <vector>\n"
            "int solve(const std::vector<int>& values) {\n"
            "    int total = 0;\n"
            "    for (int value : values) {\n"
            "        total += value;\n"
            "    }\n"
            "    return total;\n"
            "}\n"
        )
        variants = dict(_cpp_support_materializer_variants(code, schedule))
        label = next(name for name in variants if name.startswith("cpp_materializer:scheduled_"))
        materialized = variants[label]

        self.assertIn("static int helper_transform(int value)", materialized)
        self.assertIn("return value;", materialized)
        self.assertIn("int finalTotal = total;", materialized)
        self.assertNotIn("int finalTotal = value;", materialized)

    def test_java_materializer_braces_single_statement_if_before_declarations(self) -> None:
        schedule = (
            CarrierScheduleEntry(family="temporary_binding_style", slot_index=0, role="data", target_bit=1),
            CarrierScheduleEntry(family="helper_extraction_style", slot_index=1, role="data", target_bit=1),
            CarrierScheduleEntry(family="accumulator_style", slot_index=2, role="data", target_bit=1),
        )
        code = (
            "public class SsaPhiLivenessJavaPositiveS01 {\n"
            "    public static int ssa_phi_liveness_java_positive_s01(int[] values) {\n"
            "        int total = 0;\n"
            "        for (int value : values) { int c; if (value >= 3) c = value * 3; else c = value + 5; if (c % 4 == 3) total = total + c; }\n"
            "        return total;\n"
            "    }\n"
            "}\n"
        )
        variants = dict(_java_support_materializer_variants(code, schedule))
        label = next(name for name in variants if name.startswith("java_materializer:scheduled_"))
        materialized = variants[label]

        self.assertIn("if (c % 4 == 3) { int currentItem = c;", materialized)
        self.assertIn("int nextTotal = total + helperTransform(currentItem);", materialized)
        self.assertNotIn("if (c % 4 == 3) int currentItem", materialized)

    def test_extract_generated_code_strips_java_outputcode_and_schedule_tail(self) -> None:
        raw = (
            "Outputcode=public class GuardLoopAccumulatorJavaPositiveS08 {\n"
            "    public static int guard_loop_accumulator_java_positive_s08(int[] values) {\n"
            "        int total = 0;\n"
            "        for (int value : values) {\n"
            "            if (value < 2) continue;\n"
            "            total += value;\n"
            "        }\n"
            "        return total;\n"
            "    }\n"
            "}\n"
            "ScheduledDataCarrier-1:\n"
            "helper_extraction_style\n"
        )
        extracted = _extract_generated_code(raw, "PROMPT", language="java")

        self.assertTrue(extracted.startswith("public class GuardLoopAccumulatorJavaPositiveS08"))
        self.assertNotIn("Outputcode", extracted)
        self.assertNotIn("ScheduledDataCarrier", extracted)

    def test_extract_generated_code_rejects_java_prompt_echo_without_code(self) -> None:
        raw = (
            "java\n"
            "Language-specificconstraints:-ReturnonecompleteJavasourcefilewiththerequiredpublicclassandallclosingbraces.\n"
            "PrivateCarrierPlan: helper_extraction_style=1 accumulator_style=1 return_expression_style=1.\n"
            "TaskPrompt: Write a Java implementation for guard_loop_accumulator.\n"
        )
        self.assertEqual("", _extract_generated_code(raw, "PROMPT", language="java"))
        self.assertFalse(_allow_raw_decoder_fallback(raw, language="java"))

    def test_java_support_materializer_combines_scheduled_guard_loop_carriers(self) -> None:
        schedule = (
            CarrierScheduleEntry(family="iteration_style", slot_index=0, role="data", target_bit=1),
            CarrierScheduleEntry(family="temporary_binding_style", slot_index=1, role="data", target_bit=1),
            CarrierScheduleEntry(family="helper_extraction_style", slot_index=2, role="data", target_bit=1),
            CarrierScheduleEntry(family="accumulator_style", slot_index=3, role="data", target_bit=1),
            CarrierScheduleEntry(family="return_expression_style", slot_index=4, role="anchor", target_bit=1),
        )
        code = (
            "public class GuardLoopAccumulatorJavaPositiveS02 {\n"
            "    public static int guard_loop_accumulator_java_positive_s02(int[] values) {\n"
            "        int total = 0;\n"
            "        for (int value : values) {\n"
            "            if (value < 3) {\n"
            "                continue;\n"
            "            }\n"
            "            total += value;\n"
            "        }\n"
            "        return total;\n"
            "    }\n"
            "}"
        )
        variants = dict(_java_support_materializer_variants(code, schedule))
        label = next(name for name in variants if name.startswith("java_materializer:scheduled_"))
        materialized = variants[label]

        self.assertIn("for (int index = 0; index < values.length; index++)", materialized)
        self.assertIn("int currentItem = value;", materialized)
        self.assertIn("helperTransform(currentItem)", materialized)
        self.assertIn("int nextTotal = total + helperTransform(currentItem);", materialized)
        self.assertIn("int returnTotal = total;", materialized)
        self.assertLess(materialized.index("private static int helperTransform"), materialized.rindex("}"))

    def test_go_support_materializer_combines_scheduled_guard_loop_carriers(self) -> None:
        schedule = (
            CarrierScheduleEntry(family="iteration_style", slot_index=0, role="data", target_bit=1),
            CarrierScheduleEntry(family="temporary_binding_style", slot_index=1, role="data", target_bit=1),
            CarrierScheduleEntry(family="helper_extraction_style", slot_index=2, role="data", target_bit=1),
            CarrierScheduleEntry(family="accumulator_style", slot_index=3, role="data", target_bit=1),
            CarrierScheduleEntry(family="return_expression_style", slot_index=4, role="anchor", target_bit=1),
        )
        request = GenerationRequest(prompt="Use entrypoint `func solve(values []int) int`.", language="go", wm_id=13, model_name="FakeModel")
        code = (
            "func solve(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        if value < 2 {\n"
            "            continue\n"
            "        }\n"
            "        total += value\n"
            "    }\n"
            "    return total\n"
            "}"
        )
        variants = dict(_go_support_materializer_variants(code, request, schedule))
        label = next(name for name in variants if name.startswith("go_materializer:scheduled_"))
        materialized = variants[label]

        self.assertIn("for index := range values", materialized)
        self.assertIn("currentItem := value", materialized)
        self.assertIn("helperTransform(currentItem)", materialized)
        self.assertIn("nextTotal := total + helperTransform(currentItem)", materialized)
        self.assertIn("result := total", materialized)

    def test_javascript_support_materializer_handles_assignment_form_and_variable_names(self) -> None:
        schedule = (
            CarrierScheduleEntry(family="temporary_binding_style", slot_index=0, role="data", target_bit=1),
            CarrierScheduleEntry(family="helper_extraction_style", slot_index=1, role="data", target_bit=1),
            CarrierScheduleEntry(family="accumulator_style", slot_index=2, role="data", target_bit=1),
            CarrierScheduleEntry(family="return_expression_style", slot_index=3, role="anchor", target_bit=1),
        )
        code = (
            "function solve(items) {\n"
            "  let sum = 0;\n"
            "  for (const item of items) {\n"
            "    sum = sum + item;\n"
            "  }\n"
            "  return sum;\n"
            "}"
        )
        variants = dict(_javascript_support_materializer_variants(code, schedule))
        label = next(name for name in variants if name.startswith("javascript_materializer:scheduled_"))
        materialized = variants[label]

        self.assertIn("const currentItem = item;", materialized)
        self.assertIn("helper_transform(currentItem)", materialized)
        self.assertIn("const nextTotal = sum + helper_transform(currentItem);", materialized)
        self.assertIn("const finalTotal = sum;", materialized)

    def test_javascript_materializer_braces_guarded_temporary_binding(self) -> None:
        schedule = (
            CarrierScheduleEntry(family="iteration_style", slot_index=0, role="data", target_bit=1),
            CarrierScheduleEntry(family="temporary_binding_style", slot_index=1, role="data", target_bit=1),
            CarrierScheduleEntry(family="helper_extraction_style", slot_index=2, role="data", target_bit=1),
            CarrierScheduleEntry(family="return_expression_style", slot_index=3, role="data", target_bit=1),
        )
        code = (
            "function solve(values) {\n"
            "  let total = 0;\n"
            "  for (const value of values) { let c; if (value >= 3) c = value * 3; else c = value + 5; if (c % 4 === 3) total += c; }\n"
            "  return total;\n"
            "}\n"
        )
        variants = dict(_javascript_support_materializer_variants(code, schedule))
        label = next(name for name in variants if name.startswith("javascript_materializer:scheduled_"))
        materialized = variants[label]

        self.assertIn("if (c % 4 === 3) { const currentItem = c;", materialized)
        self.assertIn("total += helper_transform(currentItem);", materialized)
        self.assertNotIn("if (c % 4 === 3) const currentItem", materialized)

    def test_python_support_materializer_prefers_composed_schedule_candidate(self) -> None:
        schedule = (
            CarrierScheduleEntry(family="helper_extraction_style", slot_index=0, role="data", target_bit=1),
            CarrierScheduleEntry(family="temporary_binding_style", slot_index=1, role="data", target_bit=1),
            CarrierScheduleEntry(family="accumulator_style", slot_index=2, role="data", target_bit=1),
            CarrierScheduleEntry(family="return_expression_style", slot_index=3, role="anchor", target_bit=1),
        )
        request = GenerationRequest(prompt="write python", language="python", wm_id=13, model_name="FakeModel")
        code = (
            "def solve(values):\n"
            "    total = 0\n"
            "    for value in values:\n"
            "        if value < 2:\n"
            "            continue\n"
            "        total += value\n"
            "    return total\n"
        )
        variants = dict(_language_support_materializer_variants(code, request, schedule))
        materialized = variants["python_materializer:scheduled_helper_extraction_style_temporary_binding_style_accumulator_style_return_expression_style"]

        self.assertIn("def helper_transform(value):", materialized)
        self.assertIn("current_item", materialized)
        self.assertIn("next_total", materialized)
        self.assertIn("final_total", materialized)

    def test_go_support_materializer_can_rescue_wrong_target_support_retry(self) -> None:
        validated_codes = []
        schedule = (
            CarrierScheduleEntry(
                family="helper_extraction_style",
                slot_index=0,
                role="data",
                bit_index=0,
                applicable=True,
                target_bit=0,
                structural_level="ast",
                notes=("discriminative_generation_planned_carrier", "target_alignment_base_bit:1"),
            ),
            CarrierScheduleEntry(
                family="return_expression_style",
                slot_index=1,
                role="data",
                bit_index=1,
                applicable=True,
                target_bit=1,
                structural_level="cfg",
                notes=("discriminative_generation_planned_carrier", "target_alignment_base_bit:0"),
            ),
        )

        def semantic_validation(code, _request):
            validated_codes.append(code)
            semantic_ok = (
                "func container_helper_go_positive_s08(values []int) int" in code
                and "return" in code
                and "total" in code
                and (
                    "func helper_container_helper_go_positive_s08(value int) int" in code
                    or "value + 3 + (value % 2)" in code
                )
            )
            return {"semantic_ok": semantic_ok, "compile_ok": semantic_ok, "failure_reason": "" if semantic_ok else "invalid"}

        with tempfile.TemporaryDirectory() as checkpoint_dir:
            request = GenerationRequest(
                prompt="Use entrypoint `func container_helper_go_positive_s08(values []int) int`.",
                task_id="go::container_helper_go_positive_s08",
                language="go",
                wm_id=13,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            base_code = (
                "func helper_container_helper_go_positive_s08(value int) int { return value + 3 + (value % 2) }\n\n"
                "func container_helper_go_positive_s08(values []int) int {\n"
                "    total := 0\n"
                "    for _, value := range values {\n"
                "        normalized := helper_container_helper_go_positive_s08(value)\n"
                "        if value >= 0 {\n"
                "            total += normalized\n"
                "        }\n"
                "    }\n"
                "    return total\n"
                "}\n"
            )
            tokenizer = _GoSupportRetryTokenizer()
            fake_model = _SequentialFakeModel()
            with mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True), \
                mock.patch("semcodebook.inference._load_trained_generator", return_value=(tokenizer, fake_model, "cpu")), \
                mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule), \
                mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule), \
                mock.patch("semcodebook.inference._carrier_payload", return_value=((0, 1), None)), \
                mock.patch("semcodebook.inference.build_structured_generation_prompt", wraps=build_structured_generation_prompt), \
                mock.patch("semcodebook.inference._semantic_validation_summary", side_effect=semantic_validation), \
                mock.patch(
                    "semcodebook.inference._schedule_realization_summary",
                    return_value={
                        "scheduled_realization_ratio": 1.0,
                        "data_realization_ratio": 1.0,
                        "anchor_realized": True,
                        "applicability_realization_ratio": 1.0,
                        "realized_confidence_mean": 1.0,
                        "realized_confidence_sum": 1.0,
                    },
                ), \
                mock.patch("semcodebook.inference._bounded_decoder_attempt", side_effect=lambda *_args, **_kwargs: contextlib.nullcontext()), \
                mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _GoMaterializerDetector()):
                result = _generate_with_trained_checkpoint(
                    request,
                    base_code,
                    strict_trained_generation=True,
                )

        self.assertIsNotNone(result)
        self.assertTrue(
            any(
                note.startswith("selected_candidate_origin:carrier_support_retry:go_materializer:inline_private_helper")
                for note in result.notes
            )
        )
        self.assertIn("selected_target_recovery_match:true", result.notes)
        clean_count_notes = [
            note for note in result.notes if note.startswith("candidate_clean_positive_count:")
        ]
        self.assertEqual(1, len(clean_count_notes))
        self.assertGreaterEqual(int(clean_count_notes[0].split(":", 1)[1]), 1)
        self.assertTrue(any(note.startswith("language_support_materializer_candidate_count:") for note in result.notes))
        self.assertNotIn("func helper_container_helper_go_positive_s08", result.watermarked_code)
        self.assertTrue(validated_codes)

    def test_go_support_retry_uses_clean_positive_contract_not_watermarked_only(self) -> None:
        validated_codes = []
        schedule = (
            CarrierScheduleEntry(
                family="temporary_binding_style",
                slot_index=0,
                role="data",
                bit_index=0,
                applicable=True,
                target_bit=1,
                structural_level="ast",
                notes=("discriminative_generation_planned_carrier", "target_alignment_base_bit:0"),
            ),
            CarrierScheduleEntry(
                family="return_expression_style",
                slot_index=1,
                role="data",
                bit_index=1,
                applicable=True,
                target_bit=1,
                structural_level="cfg",
                notes=("discriminative_generation_planned_carrier", "target_alignment_base_bit:0"),
            ),
        )

        def semantic_validation(code, _request):
            validated_codes.append(code)
            semantic_ok = (
                "func helper_container_helper_go_positive_s08(value int) int" in code
                and "return" in code
                and "total" in code
            )
            return {"semantic_ok": semantic_ok, "compile_ok": semantic_ok, "failure_reason": "" if semantic_ok else "invalid"}

        with tempfile.TemporaryDirectory() as checkpoint_dir:
            request = GenerationRequest(
                prompt="Use entrypoint `func container_helper_go_positive_s08(values []int) int`.",
                task_id="go::container_helper_go_positive_s08",
                language="go",
                wm_id=13,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            base_code = (
                "func helper_container_helper_go_positive_s08(value int) int { return value + 4 + (value % 3) }\n\n"
                "func container_helper_go_positive_s08(values []int) int {\n"
                "    total := 0\n"
                "    for _, value := range values {\n"
                "        normalized := helper_container_helper_go_positive_s08(value)\n"
                "        if value >= 0 {\n"
                "            total += normalized\n"
                "        }\n"
                "    }\n"
                "    return total\n"
                "}\n"
            )
            tokenizer = _GoSupportRetryTokenizer()
            fake_model = _SequentialFakeModel()
            with mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True),              mock.patch("semcodebook.inference._load_trained_generator", return_value=(tokenizer, fake_model, "cpu")),              mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule),              mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule),              mock.patch("semcodebook.inference._carrier_payload", return_value=((1, 1), None)),              mock.patch("semcodebook.inference.build_structured_generation_prompt", wraps=build_structured_generation_prompt),              mock.patch("semcodebook.inference._semantic_validation_summary", side_effect=semantic_validation),              mock.patch(
                  "semcodebook.inference._schedule_realization_summary",
                  return_value={
                      "scheduled_realization_ratio": 1.0,
                      "data_realization_ratio": 1.0,
                      "anchor_realized": True,
                      "applicability_realization_ratio": 1.0,
                      "realized_confidence_mean": 1.0,
                      "realized_confidence_sum": 1.0,
                  },
              ),              mock.patch("semcodebook.inference._bounded_decoder_attempt", side_effect=lambda *_args, **_kwargs: contextlib.nullcontext()),              mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _WrongTargetWatermarkedDetector()):
                result = _generate_with_trained_checkpoint(
                    request,
                    base_code,
                    strict_trained_generation=True,
                )

        self.assertIsNotNone(result)
        self.assertGreaterEqual(fake_model.calls, 3)
        self.assertIn("carrier_support_retry_after_semantic_abstain", result.notes)
        self.assertIn("selected_candidate_origin:carrier_support_retry:greedy", result.notes)
        self.assertIn("selected_target_recovery_match:true", result.notes)
        self.assertIn("selected_code_changed:true", result.notes)
        self.assertIn("nextTotal := total + normalized", result.watermarked_code)
        self.assertIn("total = nextTotal", result.watermarked_code)
        self.assertIn("result := total", result.watermarked_code)
        self.assertNotIn("total += currentItem}", result.watermarked_code)
        self.assertTrue(any("Rewrite-backed support retry" in prompt for prompt in tokenizer.prompts))
        self.assertTrue(
            any(
                "### Output Go code" in prompt
                and prompt.rstrip().endswith("func container_helper_go_positive_s08(values []int) int {")
                for prompt in tokenizer.prompts
            )
        )
        self.assertTrue(validated_codes)

    def test_go_support_retry_rewrite_fallback_beats_unchanged_target_match(self) -> None:
        validated_codes = []
        schedule = (
            CarrierScheduleEntry(
                family="temporary_binding_style",
                slot_index=0,
                role="data",
                bit_index=0,
                applicable=True,
                target_bit=1,
                structural_level="ast",
                notes=("discriminative_generation_planned_carrier", "target_alignment_base_bit:0"),
            ),
            CarrierScheduleEntry(
                family="return_expression_style",
                slot_index=1,
                role="data",
                bit_index=1,
                applicable=True,
                target_bit=1,
                structural_level="cfg",
                notes=("discriminative_generation_planned_carrier", "target_alignment_base_bit:0"),
            ),
        )

        def semantic_validation(code, _request):
            validated_codes.append(code)
            semantic_ok = (
                "func helper_container_helper_go_positive_s08(value int) int" in code
                and "return" in code
                and "total" in code
            )
            return {"semantic_ok": semantic_ok, "compile_ok": semantic_ok, "failure_reason": "" if semantic_ok else "invalid"}

        with tempfile.TemporaryDirectory() as checkpoint_dir:
            request = GenerationRequest(
                prompt="Use entrypoint `func container_helper_go_positive_s08(values []int) int`.",
                task_id="go::container_helper_go_positive_s08",
                language="go",
                wm_id=13,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            base_code = (
                "func helper_container_helper_go_positive_s08(value int) int { return value + 4 + (value % 3) }\n\n"
                "func container_helper_go_positive_s08(values []int) int {\n"
                "    total := 0\n"
                "    for _, value := range values {\n"
                "        normalized := helper_container_helper_go_positive_s08(value)\n"
                "        if value >= 0 {\n"
                "            total += normalized\n"
                "        }\n"
                "    }\n"
                "    return total\n"
                "}\n"
            )
            tokenizer = _GoSupportRetryTokenizer()
            fake_model = _SequentialFakeModel()
            with mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True),              mock.patch("semcodebook.inference._load_trained_generator", return_value=(tokenizer, fake_model, "cpu")),              mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule),              mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule),              mock.patch("semcodebook.inference._carrier_payload", return_value=((1, 1), None)),              mock.patch("semcodebook.inference.build_structured_generation_prompt", wraps=build_structured_generation_prompt),              mock.patch("semcodebook.inference._semantic_validation_summary", side_effect=semantic_validation),              mock.patch(
                  "semcodebook.inference._schedule_realization_summary",
                  return_value={
                      "scheduled_realization_ratio": 1.0,
                      "data_realization_ratio": 1.0,
                      "anchor_realized": True,
                      "applicability_realization_ratio": 1.0,
                      "realized_confidence_mean": 1.0,
                      "realized_confidence_sum": 1.0,
                  },
              ),              mock.patch("semcodebook.inference._bounded_decoder_attempt", side_effect=lambda *_args, **_kwargs: contextlib.nullcontext()),              mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _RetryFallbackDetector()):
                result = _generate_with_trained_checkpoint(
                    request,
                    base_code,
                    strict_trained_generation=True,
                )

        self.assertIsNotNone(result)
        self.assertGreaterEqual(fake_model.calls, 3)
        self.assertIn("carrier_support_retry_after_semantic_abstain", result.notes)
        self.assertIn("carrier_support_retry_forced_prefix_in_prompt", result.notes)
        self.assertIn("selection_rule:support_retry_rewrite_materialization_floor_then_rank", result.notes)
        self.assertIn("candidate_semantic_count:6", result.notes)
        self.assertIn("candidate_semantic_compile_count:6", result.notes)
        self.assertIn("candidate_code_changed_count:4", result.notes)
        self.assertIn("support_retry_batch_sequence_count:7", result.notes)
        self.assertIn("selected_candidate_origin:carrier_support_retry:go_materializer:scheduled_temporary_binding_return_binding", result.notes)
        self.assertIn("selected_target_recovery_match:true", result.notes)
        self.assertIn("selected_code_changed:true", result.notes)
        self.assertIn("support_retry_candidate_count:4", result.notes)
        self.assertIn("support_retry_semantic_candidate_count:4", result.notes)
        self.assertIn("support_retry_semantic_compile_candidate_count:4", result.notes)
        self.assertIn("support_retry_code_changed_candidate_count:4", result.notes)
        self.assertIn("support_retry_target_recovery_match_count:2", result.notes)
        self.assertIn("support_retry_positive_support_signal_candidate_count:4", result.notes)
        self.assertIn("support_retry_rewrite_backed_support_candidate_count:0", result.notes)
        self.assertIn("candidate_clean_positive_count:0", result.notes)
        self.assertIn("best_support_retry_code_changed:true", result.notes)
        self.assertIn("currentItem := normalized", result.watermarked_code)
        self.assertIn("total += currentItem\n        }", result.watermarked_code)
        self.assertNotIn("total += currentItem}", result.watermarked_code)
        self.assertTrue(validated_codes)

    def test_go_support_retry_prompt_rejects_unchanged_body(self) -> None:
        prompt = _carrier_support_retry_prompt("Base prompt", language="go")
        self.assertIn("whitespace-stripped program body is identical", prompt)
        self.assertIn("helper calls alone are not enough", prompt)
        self.assertIn("accumulator or return restructuring", prompt)
        self.assertIn("update the accumulator through a temporary next value", prompt)
        self.assertIn("at least two independent scheduled carrier families", prompt)
        self.assertIn("one CFG-level change", prompt)
        self.assertIn("Do not change helper arithmetic", prompt)
        self.assertIn("Use ordinary Go token spacing", prompt)
        self.assertIn("If a Go range index is not used", prompt)
        self.assertIn("Stop immediately after the final Go closing brace", prompt)
        self.assertIn("Output only Go code", prompt)
        self.assertIn("### Output Go code", prompt)
        self.assertNotIn("Language-specific constraints:", prompt)
        self.assertNotIn("Required Go output shape:", prompt)

    def test_go_support_retry_preserves_nonsemantic_attempt_diagnostics(self) -> None:
        schedule = (
            CarrierScheduleEntry(
                family="temporary_binding_style",
                slot_index=0,
                role="data",
                bit_index=0,
                applicable=True,
                target_bit=1,
                structural_level="ast",
                notes=("discriminative_generation_planned_carrier", "target_alignment_base_bit:0"),
            ),
            CarrierScheduleEntry(
                family="return_expression_style",
                slot_index=1,
                role="data",
                bit_index=1,
                applicable=True,
                target_bit=1,
                structural_level="cfg",
                notes=("discriminative_generation_planned_carrier", "target_alignment_base_bit:0"),
            ),
        )

        def semantic_validation(code, _request):
            semantic_ok = (
                "BROKEN_UNDECLARED" not in code
                and "func helper_container_helper_go_positive_s08(value int) int" in code
                and "return" in code
                and "total" in code
            )
            return {
                "semantic_ok": semantic_ok,
                "compile_ok": semantic_ok,
                "failure_reason": "" if semantic_ok else "undefined normalized value",
            }

        with tempfile.TemporaryDirectory() as checkpoint_dir, tempfile.TemporaryDirectory() as dump_dir:
            request = GenerationRequest(
                prompt="Use entrypoint `func container_helper_go_positive_s08(values []int) int`.",
                task_id="go::container_helper_go_positive_s08",
                language="go",
                wm_id=13,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            base_code = (
                "func helper_container_helper_go_positive_s08(value int) int { return value + 4 + (value % 3) }\n\n"
                "func container_helper_go_positive_s08(values []int) int {\n"
                "    total := 0\n"
                "    for _, value := range values {\n"
                "        normalized := helper_container_helper_go_positive_s08(value)\n"
                "        if value >= 0 {\n"
                "            total += normalized\n"
                "        }\n"
                "    }\n"
                "    return total\n"
                "}\n"
            )
            tokenizer = _GoNonSemanticSupportRetryTokenizer()
            fake_model = _SequentialFakeModel()
            with mock.patch.dict("os.environ", {"SEMCODEBOOK_FAILURE_DUMP_DIR": dump_dir}), \
                mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True), \
                mock.patch("semcodebook.inference._load_trained_generator", return_value=(tokenizer, fake_model, "cpu")), \
                mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule), \
                mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule), \
                mock.patch("semcodebook.inference._carrier_payload", return_value=((1, 1), None)), \
                mock.patch("semcodebook.inference.build_structured_generation_prompt", wraps=build_structured_generation_prompt), \
                mock.patch("semcodebook.inference._semantic_validation_summary", side_effect=semantic_validation), \
                mock.patch(
                    "semcodebook.inference._schedule_realization_summary",
                    return_value={
                        "scheduled_realization_ratio": 1.0,
                        "data_realization_ratio": 1.0,
                        "anchor_realized": True,
                        "applicability_realization_ratio": 1.0,
                        "realized_confidence_mean": 1.0,
                        "realized_confidence_sum": 1.0,
                    },
                ), \
                mock.patch("semcodebook.inference._bounded_decoder_attempt", side_effect=lambda *_args, **_kwargs: contextlib.nullcontext()), \
                mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _RetryFallbackDetector()):
                result = _generate_with_trained_checkpoint(
                    request,
                    base_code,
                    strict_trained_generation=True,
                )

            dump_path = (
                Path(dump_dir)
                / "go_container_helper_go_positive_s08.support_retry_clean_positive_frontier.trained_generation_candidates.json"
            )
            dump_jsonl_path = dump_path.with_name(f"{dump_path.stem}.jsonl")
            payload = json.loads(dump_path.read_text(encoding="utf-8"))
            jsonl_rows = [json.loads(line) for line in dump_jsonl_path.read_text(encoding="utf-8").splitlines()]

        self.assertIsNotNone(result)
        self.assertIn("selected_candidate_origin:carrier_support_retry:go_materializer:scheduled_temporary_binding_return_binding", result.notes)
        self.assertIn("support_retry_candidate_count:2", result.notes)
        self.assertIn("support_retry_attempt_candidate_count:4", result.notes)
        self.assertIn("support_retry_semantic_filter_drop_count:2", result.notes)
        self.assertIn("support_retry_validation_failure_count:2", result.notes)
        self.assertIn("best_support_retry_candidate_origin:carrier_support_retry:go_materializer:scheduled_temporary_binding_return_binding", result.notes)
        self.assertIn("best_support_retry_semantic_ok:true", result.notes)
        self.assertIn("support_retry_validation_failure_reasons:undefined_normalized_value=2", result.notes)
        self.assertEqual(2, payload["candidate_count"])
        self.assertEqual("support_retry_clean_positive_frontier", payload["phase"])
        self.assertTrue(all(len(item["generated_code_sha256"]) == 64 for item in payload["candidates"]))
        self.assertTrue(all("BROKEN_UNDECLARED" not in item["generated_code"] for item in payload["candidates"]))
        self.assertEqual(1, len(jsonl_rows))
        self.assertEqual("support_retry_clean_positive_frontier", jsonl_rows[0]["phase"])

    def test_non_python_target_schedule_marks_only_planned_structural_changes_discriminative(self) -> None:
        base_code = """
function solve(values) {
    let total = 0;
    for (const value of values) {
        if (value < 0) {
            continue;
        }
        total += value;
    }
    return total;
}
""".strip()
        request = GenerationRequest(
            prompt="sum non-negative values",
            language="javascript",
            wm_id=13,
            model_name="unit-test-model",
            carrier_key="carrier-key",
        )
        initial = build_adaptive_carrier_schedule(base_code, request.carrier_key, request.language)
        schedule = _target_aligned_schedule(base_code, request, initial)
        data_entries = [entry for entry in schedule if entry.role == "data"]
        self.assertEqual(7, len(data_entries))
        planned = [
            entry
            for entry in data_entries
            if "discriminative_generation_planned_carrier" in entry.notes
        ]
        natural = [
            entry
            for entry in data_entries
            if "naturally_aligned_support_carrier" in entry.notes
        ]
        self.assertGreaterEqual(len(planned), 2)
        self.assertLessEqual(len(planned), 4)
        self.assertGreaterEqual(len(natural), 3)
        self.assertTrue(natural)
        self.assertTrue(
            all(
                any(str(note).startswith("target_alignment_reason:generation_planned") for note in entry.notes)
                for entry in planned
            )
        )



    def test_normalize_decoded_text_treats_return_symbol_as_newline(self) -> None:
        self.assertEqual("func x()\n{\n}", _normalize_decoded_text("func x()⏎{⏎}"))

    def test_go_failed_frontier_triggers_base_materializer(self) -> None:
        base_code = (
            "func helper_container_helper_go_positive_s08(value int) int { return value + 4 + (value % 3) }\n\n"
            "func container_helper_go_positive_s08(values []int) int {\n"
            "    total := 0\n"
            "    for _, value := range values {\n"
            "        normalized := helper_container_helper_go_positive_s08(value)\n"
            "        if value >= 0 {\n"
            "            total += normalized\n"
            "        }\n"
            "    }\n"
            "    return total\n"
            "}\n"
        )
        schedule = (
            CarrierScheduleEntry(
                family="temporary_binding_style",
                slot_index=0,
                role="data",
                bit_index=0,
                applicable=True,
                target_bit=1,
                structural_level="ast",
            ),
            CarrierScheduleEntry(
                family="return_expression_style",
                slot_index=1,
                role="data",
                bit_index=1,
                applicable=True,
                target_bit=1,
                structural_level="cfg",
            ),
        )
        validated_codes: list[str] = []

        class _HeaderOnlyTokenizer(_FakeTokenizer):
            eos_token_id = 0
            pad_token_id = 0

            def decode(self, *_args, **_kwargs):
                return "func container_helper_go_positive_s08(values []int) int {"

        class _OneShotModel:
            def parameters(self):
                yield _FakeParameter()

            def generate(self, **_kwargs):
                return [[1, 2, 3]]

        def semantic_validation(code, _request):
            validated_codes.append(code)
            semantic_ok = (
                "func container_helper_go_positive_s08(values []int) int" in code
                and "return" in code
                and ("currentItem" in code or "result := total" in code)
                and (
                    "helper_container_helper_go_positive_s08" in code
                    or "value + 4 + (value % 3)" in code
                )
            )
            return {"semantic_ok": semantic_ok, "compile_ok": semantic_ok, "failure_reason": "" if semantic_ok else "header_only"}

        with tempfile.TemporaryDirectory() as checkpoint_dir:
            request = GenerationRequest(
                prompt="Use entrypoint `func container_helper_go_positive_s08(values []int) int`.",
                task_id="go::container_helper_go_positive_s08",
                language="go",
                wm_id=13,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            with mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True), \
                 mock.patch("semcodebook.inference._load_trained_generator", return_value=(_HeaderOnlyTokenizer(), _OneShotModel(), "cpu")), \
                 mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule), \
                 mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule), \
                 mock.patch("semcodebook.inference._carrier_payload", return_value=((1, 1), None)), \
                 mock.patch("semcodebook.inference._semantic_validation_summary", side_effect=semantic_validation), \
                 mock.patch("semcodebook.inference._schedule_realization_summary", return_value={
                 "scheduled_slot_count": 2,
                 "scheduled_realized_count": 2,
                 "scheduled_realization_ratio": 1.0,
                 "data_slot_count": 2,
                 "data_realized_count": 2,
                 "data_realization_ratio": 1.0,
                 "anchor_slot_count": 0,
                 "anchor_realized": True,
                 "applicable_slot_count": 2,
                 "applicable_realized_count": 2,
                 "applicability_realization_ratio": 1.0,
                 "realized_confidence_mean": 1.0,
                 "realized_confidence_sum": 2.0,
                 }), \
                 mock.patch("semcodebook.inference._candidate_rank", return_value=(1, 1, 1, 1, 1, 1, 1, 1)), \
                 mock.patch("semcodebook.inference._bounded_decoder_attempt", side_effect=lambda *_args, **_kwargs: contextlib.nullcontext()), \
                 mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _CodeAwareDetector()):
                result = _generate_with_trained_checkpoint(request, base_code, strict_trained_generation=True)

        self.assertIsNotNone(result)
        self.assertIn("selected_candidate_origin:carrier_support_retry:go_materializer", " ".join(result.notes))
        self.assertTrue(any("currentItem" in code or "result := total" in code for code in validated_codes))

    def test_strict_trained_generation_reports_semantically_invalid_candidates(self) -> None:
        calls = []
        schedule = (
            CarrierScheduleEntry(
                family="accumulator_style",
                slot_index=0,
                role="data",
                applicable=True,
            ),
        )
        with tempfile.TemporaryDirectory() as checkpoint_dir:
            request = GenerationRequest(
                prompt="Choose the first element.",
                task_id="javascript::choose_value",
                language="javascript",
                wm_id=7,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            with mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True),              mock.patch("semcodebook.inference._load_trained_generator", return_value=(_FakeTokenizer(), _FakeModel(), "cpu")),              mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule),              mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule),              mock.patch("semcodebook.inference._carrier_payload", return_value=((1, 0, 1, 1), None)),              mock.patch("semcodebook.inference.build_structured_generation_prompt", return_value="PROMPT"),              mock.patch("semcodebook.inference._semantic_validation_summary", return_value={"semantic_ok": False, "compile_ok": False, "failure_reason": "synthetic_invalid"}),              mock.patch(
                 "semcodebook.inference._schedule_realization_summary",
                 return_value={
                     "scheduled_realization_ratio": 1.0,
                     "data_realization_ratio": 1.0,
                     "anchor_realized": True,
                     "applicability_realization_ratio": 1.0,
                     "realized_confidence_mean": 1.0,
                     "realized_confidence_sum": 1.0,
                 },
             ),              mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _RecordingDetector(calls)):
                with self.assertRaises(TrainedGenerationFailure) as raised:
                    _generate_with_trained_checkpoint(
                        request,
                        "function chooseValue(values) { return values[0] ?? 0; }",
                        strict_trained_generation=True,
                    )
        self.assertEqual("semantic_validation", raised.exception.phase)
        self.assertIn("no_semantic_candidate", raised.exception.detail)
        self.assertIn("synthetic_invalid", raised.exception.detail)

    def test_strict_trained_generation_keeps_raw_decoder_diagnostic_candidate(self) -> None:
        schedule = (
            CarrierScheduleEntry(
                family="accumulator_style",
                slot_index=0,
                role="data",
                applicable=True,
            ),
        )
        with tempfile.TemporaryDirectory() as checkpoint_dir:
            request = GenerationRequest(
                prompt="Choose the first element.",
                task_id="javascript::choose_value",
                language="javascript",
                wm_id=7,
                carrier_key="carrier-key",
                backbone_name="FakeBackbone",
                model_name="FakeModel",
                checkpoint_path=checkpoint_dir,
                execution_mode="remote_trained",
            )
            with mock.patch("semcodebook.inference._trained_checkpoint_available", return_value=True),              mock.patch("semcodebook.inference._load_trained_generator", return_value=(_PromptOnlyTokenizer(), _FakeModel(), "cpu")),              mock.patch("semcodebook.inference.build_adaptive_carrier_schedule", return_value=schedule),              mock.patch("semcodebook.inference._target_aligned_schedule", return_value=schedule),              mock.patch("semcodebook.inference._carrier_payload", return_value=((1, 0, 1, 1), None)),              mock.patch("semcodebook.inference.build_structured_generation_prompt", return_value="PROMPT"),              mock.patch("semcodebook.inference._semantic_validation_summary", return_value={"semantic_ok": False, "compile_ok": False, "failure_reason": "no_code_boundary"}),              mock.patch(
                 "semcodebook.inference._schedule_realization_summary",
                 return_value={
                     "scheduled_realization_ratio": 0.0,
                     "data_realization_ratio": 0.0,
                     "anchor_realized": False,
                     "applicability_realization_ratio": 0.0,
                     "realized_confidence_mean": 0.0,
                     "realized_confidence_sum": 0.0,
                 },
             ),              mock.patch("semcodebook.inference.SemCodebookDetector", side_effect=lambda: _RecordingDetector([])):
                with self.assertRaises(TrainedGenerationFailure) as raised:
                    _generate_with_trained_checkpoint(
                        request,
                        "function chooseValue(values) { return values[0] ?? 0; }",
                        strict_trained_generation=True,
                    )
        self.assertEqual("semantic_validation", raised.exception.phase)
        self.assertIn("no_semantic_candidate", raised.exception.detail)
        self.assertIn("no_code_boundary", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
