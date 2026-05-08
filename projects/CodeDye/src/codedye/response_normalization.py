from __future__ import annotations

import ast
import re


_FENCED_BLOCK_RE = re.compile(r"```(?P<lang>[A-Za-z0-9_+-]*)\n(?P<body>.*?)```", re.DOTALL)
_CODE_START_BY_LANGUAGE = {
    "python": re.compile(r"^(def |class |from |import |async def )"),
    "typescript": re.compile(r"^(function |const |let |var |export |class |type |interface )"),
    "javascript": re.compile(r"^(function |const |let |var |export |class )"),
    "java": re.compile(r"^(import |public class |class |public final class )"),
    "cpp": re.compile(r"^(#include|using namespace|template\s*<|std::|static |const |auto |int |long |bool |double |float |void |string |vector )"),
    "go": re.compile(r"^(package |import |func )"),
}
_GENERIC_CODE_START_RE = re.compile(
    r"^(def |class |from |import |async def |package |func |#include|using namespace|"
    r"template\s*<|public class |function |const |let |var |export |std::|static |auto |int |long |bool |double |float |void )"
)
_LANGUAGE_ALIASES = {
    "py": "python",
    "python3": "python",
    "ts": "typescript",
    "typescript": "typescript",
    "js": "javascript",
    "javascript": "javascript",
    "java": "java",
    "c++": "cpp",
    "cpp": "cpp",
    "cxx": "cpp",
    "go": "go",
    "golang": "go",
}


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_language(language: str) -> str:
    return _LANGUAGE_ALIASES.get(language.strip().lower(), language.strip().lower())


def _code_start_re(language: str) -> re.Pattern[str]:
    return _CODE_START_BY_LANGUAGE.get(_normalize_language(language), _GENERIC_CODE_START_RE)


def _best_fenced_block(text: str, *, language: str = "") -> str | None:
    matches = list(_FENCED_BLOCK_RE.finditer(text))
    if not matches:
        return None
    expected_language = _normalize_language(language)
    language_match_sets = {
        "python": {"python", "py", "python3"},
        "typescript": {"typescript", "ts", "javascript", "js"},
        "javascript": {"javascript", "js", "typescript", "ts"},
        "java": {"java"},
        "cpp": {"cpp", "c++", "cxx"},
        "go": {"go", "golang"},
    }
    scored: list[tuple[int, int, int, int, str]] = []
    for index, match in enumerate(matches):
        block_language = match.group("lang").strip().lower()
        body = match.group("body").strip()
        language_bias = 1 if block_language in language_match_sets.get(expected_language, {expected_language}) else 0
        parse_ok = 1 if expected_language in {"", "python"} and _parses_as_python(body) else 0
        scored.append((language_bias, parse_ok, len(body), -index, body))
    scored.sort(reverse=True)
    return scored[0][4].strip() if scored else None


def _leading_code_slice(text: str, *, language: str = "") -> str | None:
    lines = _normalize_newlines(text).split("\n")
    code_start_re = _code_start_re(language)
    start_index: int | None = None
    for index, line in enumerate(lines):
        if code_start_re.match(line.lstrip()):
            start_index = index
            break
    if start_index is None:
        return None
    while start_index > 0 and lines[start_index - 1].lstrip().startswith("#"):
        start_index -= 1
    candidate_lines = lines[start_index:]
    if _normalize_language(language) and _normalize_language(language) != "python":
        trimmed_non_python: list[str] = []
        brace_depth = 0
        saw_code_line = False
        prose_after_code = (
            "explanation:",
            "note:",
            "the code",
            "this code",
            "here is",
            "it works",
        )
        for line in candidate_lines:
            stripped = line.strip()
            lowered = stripped.lower()
            if stripped.startswith("```") or stripped.startswith("###"):
                break
            if saw_code_line and brace_depth <= 0 and lowered.startswith(prose_after_code):
                break
            trimmed_non_python.append(line)
            if stripped:
                saw_code_line = True
            brace_depth += line.count("{") - line.count("}")
        return "\n".join(trimmed_non_python).strip() or None
    trimmed: list[str] = []
    blank_run = 0
    for line in candidate_lines:
        stripped = line.strip()
        if not stripped:
            blank_run += 1
            trimmed.append(line)
            continue
        if blank_run >= 1 and not line.startswith((" ", "\t")) and not code_start_re.match(line.lstrip()):
            break
        blank_run = 0
        trimmed.append(line)
    return "\n".join(trimmed).strip() or None


def extract_code_payload(text: str, *, language: str = "") -> str:
    normalized = _normalize_newlines(text).strip()
    if not normalized:
        return ""
    fenced = _best_fenced_block(normalized, language=language)
    if fenced:
        return fenced
    sliced = _leading_code_slice(normalized, language=language)
    if sliced:
        return sliced
    return normalized


def _parses_as_python(text: str) -> bool:
    try:
        ast.parse(text)
    except SyntaxError:
        return False
    return True


def _trim_to_parseable_prefix(text: str) -> str:
    lines = text.splitlines()
    for end in range(len(lines), 0, -1):
        candidate = "\n".join(lines[:end]).strip()
        if candidate and _parses_as_python(candidate):
            return candidate
    return text.strip()


def normalize_code_response(response_text: str, *, language: str = "") -> str:
    code = extract_code_payload(response_text, language=language)
    if not code:
        return ""
    normalized_language = _normalize_language(language)
    if normalized_language and normalized_language != "python":
        return code.strip()
    if _parses_as_python(code):
        return code.strip()
    return _trim_to_parseable_prefix(code)


def normalize_code_responses(responses: tuple[str, ...] | list[str], *, language: str = "") -> tuple[str, ...]:
    return tuple(normalize_code_response(item, language=language) for item in responses)
