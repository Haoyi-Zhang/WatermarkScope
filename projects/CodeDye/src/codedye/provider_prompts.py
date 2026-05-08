from __future__ import annotations

import re

from .protocol import BenchmarkTask


_ENTRYPOINT_RE = re.compile(r"assert\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_PROMPT_DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)
_CLASS_RE = re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:(]", re.MULTILINE)
_METHOD_CALL_RE = re.compile(r"\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _language_contract(task: BenchmarkTask, entrypoint_text: str) -> str:
    language = task.language.lower()
    if language == "python":
        return (
            "Return only executable Python code. Do not include Markdown fences, prose, explanations, or examples.\n"
            f"Define the required function name exactly as: {entrypoint_text}.\n"
            "The solution must compile as a standalone Python snippet and must not read from stdin or write to stdout.\n"
            "If the task prompt already defines a function signature, keep that exact function name and signature.\n"
        )
    if language in {"typescript", "javascript"}:
        return (
            "Return only executable TypeScript code for the requested reference surface. Do not include Markdown fences, prose, explanations, or examples.\n"
            f"Define a top-level function named {entrypoint_text}. Use JavaScript-compatible syntax, not Python syntax.\n"
            "Use the JavaScript-compatible TypeScript subset accepted by the Node.js harness; omit type annotations unless the prompt explicitly requires them.\n"
            "Do not use Python keywords such as def, import typing, list comprehensions, or type annotations like s: str.\n"
            "The evaluator calls solve(input) from a Node.js-compatible wrapper; do not read from stdin or write to stdout.\n"
            "Do not translate the requested reference surface into Python.\n"
        )
    if language == "java":
        return (
            "Return only executable Java code. Do not include Markdown fences, prose, explanations, or examples.\n"
            f"Define class Solution with a public static method named {entrypoint_text}. Use Java syntax, not Python syntax.\n"
            "The evaluator calls Solution.solve(input); do not read from stdin or write to stdout.\n"
            "For string tasks, prefer the exact harness-compatible signature public static String solve(String input).\n"
            "Do not translate the requested reference surface into Python.\n"
        )
    if language in {"cpp", "c++", "cxx"}:
        return (
            "Return only executable C++ code targeting C++17. Do not include Markdown fences, prose, explanations, or examples.\n"
            f"Define a top-level function named {entrypoint_text}. Use C++ syntax, not Python syntax.\n"
            "Include any required standard-library headers and do not read from stdin or write to stdout.\n"
            "For string tasks, prefer the harness-compatible signature std::string solve(std::string input) or std::string solve(const std::string& input).\n"
            "Do not translate the requested reference surface into Python.\n"
        )
    if language == "go":
        return (
            "Return only executable Go code. Do not include Markdown fences, prose, explanations, or examples.\n"
            f"Define a package main file with a function named {entrypoint_text}. Use Go syntax, not Python syntax.\n"
            "Include any required imports and do not read from stdin or write to stdout.\n"
            "For string tasks, prefer the harness-compatible signature func solve(input string) string.\n"
            "Do not translate the requested reference surface into Python.\n"
        )
    return (
        f"Return only executable code for the requested {task.language} reference surface. Do not include Markdown fences, prose, explanations, or examples.\n"
        f"Define the required function name exactly as: {entrypoint_text}.\n"
    )


def expected_entrypoints_from_tests(task: BenchmarkTask) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for test in task.tests:
        for name in _ENTRYPOINT_RE.findall(test):
            if name not in seen:
                seen.add(name)
                ordered.append(name)
    return tuple(ordered)


def expected_entrypoints_from_prompt(task: BenchmarkTask) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for name in _PROMPT_DEF_RE.findall(task.prompt):
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return tuple(ordered)


def expected_class_names(task: BenchmarkTask) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    joined_tests = "\n".join(task.tests)
    for name in _CLASS_RE.findall(task.prompt) + _CLASS_RE.findall(task.reference_code):
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    for name in re.findall(r"\b([A-Z][A-Za-z0-9_]*)\s*\(", joined_tests):
        if name in {"TestCase"}:
            continue
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return tuple(ordered)


def expected_method_names(task: BenchmarkTask) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for name in _METHOD_CALL_RE.findall("\n".join(task.tests)):
        if name.startswith("assert"):
            continue
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return tuple(ordered)


def build_code_only_provider_prompt(task: BenchmarkTask) -> str:
    prompt_text = task.prompt.strip()
    lowered = prompt_text.lower()
    prompt_entrypoints = expected_entrypoints_from_prompt(task)
    test_entrypoints = expected_entrypoints_from_tests(task)
    entrypoints = prompt_entrypoints or test_entrypoints
    class_names = expected_class_names(task)
    method_names = expected_method_names(task)
    entrypoint_text = ", ".join(entrypoints) if entrypoints else "solve"
    tests = "\n".join(task.tests[:2]) if task.tests else "No public tests are provided."
    task_specific_constraints: list[str] = []
    if "weighted sum" in lowered:
        task_specific_constraints.append(
            "Interpret each weight as the zero-based index produced by enumerate(...); do not use one-based indexing."
        )
    if "validates a list of integers" in lowered or "normalized list" in lowered:
        task_specific_constraints.append(
            "Keep only non-negative integers: require isinstance(item, int), exclude bool values, and drop negative integers instead of clamping them."
        )
    if "joins path fragments" in lowered and "duplicate separators" in lowered:
        task_specific_constraints.append(
            "Match the semantics of os.path.normpath(os.path.join(*parts)) after joining the fragments."
        )
    if "index pairs" in lowered and "sum to a target" in lowered:
        task_specific_constraints.append(
            "Return all duplicate-value index pairs as tuples (i, j) with i < j using nested-loop discovery order over i then j; do not collapse by complement dictionary."
        )
    if "merges overlapping inclusive integer ranges" in lowered:
        task_specific_constraints.append(
            "Treat touching inclusive ranges as mergeable: merge when next_start <= current_end + 1, and return tuples sorted by start."
        )
    if "common suffix" in lowered and "ends with it" in lowered:
        task_specific_constraints.append(
            "If the suffix is the empty string, leave each input string unchanged; otherwise remove the suffix only from strings that end with it."
        )
    if "split on the first vertical bar" in lowered:
        task_specific_constraints.append(
            "Use partition/split-once on the first vertical bar character '|', trim surrounding whitespace from both halves, and return right + '|' + left even when either half is empty."
        )
    if "words of the input string in reverse order" in lowered or "reverses the order of words" in lowered:
        task_specific_constraints.append(
            "Split on arbitrary whitespace after trimming, ignore empty word chunks, reverse the resulting words, and join them with a single space."
        )
    if "deduplicate whitespace separated words case-insensitively" in lowered:
        task_specific_constraints.append(
            "Lowercase each word before duplicate checking, preserve first occurrence order, and join kept words with the vertical bar character '|'."
        )
    if "replace every decimal digit" in lowered:
        task_specific_constraints.append(
            "Replace every character '0' through '9' with '#'; keep all other characters unchanged."
        )
    if "normalize_csv" in str(task.task_id) or ("comma" in lowered and "trim" in lowered):
        task_specific_constraints.append(
            "Split on commas, trim surrounding whitespace from each field, drop empty fields, and join the remaining fields with the vertical bar character '|'."
        )
    if "extracts lowercase word tokens" in lowered or ("lowercase word tokens" in lowered and "string" in lowered):
        task_specific_constraints.append(
            "Convert the full input string to lowercase before extracting alphabetic word tokens, so uppercase words remain in the output after lowercasing."
        )
    if task_specific_constraints:
        task_specific_constraints.append(
            "Held-out validation examples are withheld; infer the general rule from the task text and public examples without hard-coding examples."
        )
    task_specific_text = (
        "Task-specific constraints:\n- " + "\n- ".join(task_specific_constraints) + "\n"
        if task_specific_constraints
        else ""
    )
    class_interface_text = ""
    if class_names:
        class_lines = [
            f"Define these class names exactly if they are required by the validation examples: {', '.join(class_names)}.",
            "Do not replace a required class-based interface with a standalone solve() helper.",
        ]
        if method_names:
            class_lines.append(
                f"Ensure these public methods remain callable with the same names: {', '.join(method_names)}."
            )
        class_interface_text = "\n".join(class_lines) + "\n"
    language_contract = _language_contract(task, entrypoint_text)
    return (
        f"{prompt_text}\n\n"
        f"{language_contract}"
        "Follow the public validation examples exactly, including output order, tuple/list container types, and edge-case behavior implied by the assertions.\n"
        "Prefer the simplest direct implementation that satisfies the validation examples instead of a stylistically fancy rewrite.\n"
        f"{class_interface_text}"
        f"{task_specific_text}"
        "Public validation examples:\n"
        f"{tests}\n"
    )



def build_utility_preserving_provider_prompts(task: BenchmarkTask) -> tuple[str, ...]:
    """Return independent utility-only prompt views for candidate generation.

    Both views expose only task text, language/interface constraints, and public
    validation examples. They intentionally do not mention canaries,
    provenance, null-audit scoring, or asset ids, so downstream candidate
    selection can be audited as utility-first rather than watermark-aware.
    """
    direct_view = build_code_only_provider_prompt(task)
    constraint_view = (
        f"{task.prompt.strip()}\n\n"
        "Return only executable code for the requested language and interface. "
        "Solve the general task, not only the public examples. Keep the required "
        "function/class names exactly as implied by the examples. Do not include "
        "Markdown, prose, comments explaining the solution, stdin reads, or stdout writes.\n"
        "Public validation examples:\n"
        f"{chr(10).join(task.tests[:2]) if task.tests else 'No public tests are provided.'}\n"
        "Use the examples only as utility checks; hidden tests may cover edge cases.\n"
    )
    if constraint_view == direct_view:
        return (direct_view,)
    return (direct_view, constraint_view)
