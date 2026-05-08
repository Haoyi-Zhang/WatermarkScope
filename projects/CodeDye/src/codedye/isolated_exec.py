from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_CHILD_SCRIPT = r"""
import ast
import builtins
import contextlib
import io
import json
import sys

SAFE_BUILTIN_NAMES = (
    "__build_class__",
    "ArithmeticError",
    "AssertionError",
    "AttributeError",
    "BaseException",
    "IndexError",
    "Exception",
    "False",
    "KeyError",
    "LookupError",
    "NameError",
    "RuntimeError",
    "True",
    "TypeError",
    "ValueError",
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "float",
    "int",
    "isinstance",
    "len",
    "list",
    "max",
    "min",
    "range",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "object",
    "zip",
)


def _root_name(name):
    return name.split(".", 1)[0]


def _allowed_import_roots(code, tests):
    tree = ast.parse(code, filename="codedye_eval.py")
    roots = set()
    trees = [tree]
    for index, test in enumerate(tests):
        try:
            trees.append(ast.parse(test, filename=f"codedye_test_{index}.py"))
        except SyntaxError:
            continue
    for parsed in trees:
        for node in ast.walk(parsed):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    roots.add(_root_name(alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(_root_name(node.module))
    return tree, roots


def _safe_builtins(allowed_roots):
    payload = {name: getattr(builtins, name) for name in SAFE_BUILTIN_NAMES}
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        root = _root_name(name)
        if root not in allowed_roots:
            raise ImportError("import_blocked:" + name)
        return original_import(name, globals, locals, fromlist, level)

    payload["__import__"] = guarded_import
    return payload


def main():
    payload = json.loads(sys.stdin.read())
    code = payload["code"]
    tests = payload.get("tests", [])
    entrypoints = payload.get("entrypoints", [])
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
        try:
            tree, allowed_roots = _allowed_import_roots(code, tests)
            namespace = {"__builtins__": _safe_builtins(allowed_roots), "__name__": "__codedye_eval__"}
            exec(compile(tree, "codedye_eval.py", "exec"), namespace, namespace)
            if "solve" in namespace:
                for entrypoint in entrypoints:
                    namespace.setdefault(entrypoint, namespace["solve"])
            test_results = []
            pass_ok = True if not tests else None
            for test in tests:
                try:
                    exec(test, namespace, namespace)
                except Exception as exc:
                    pass_ok = False
                    test_results.append({"statement": test, "passed": False, "detail": f"{type(exc).__name__}:{exc}"})
                    break
                else:
                    pass_ok = True
                    test_results.append({"statement": test, "passed": True, "detail": ""})
            result = {
                "compile_ok": True,
                "executed": True,
                "pass_ok": pass_ok,
                "callable_names": sorted(name for name, value in namespace.items() if callable(value)),
                "test_results": test_results,
                "error": "",
            }
        except SyntaxError as exc:
            result = {"compile_ok": False, "executed": False, "pass_ok": False, "callable_names": [], "test_results": [], "error": "syntax_error:" + exc.msg}
        except Exception as exc:
            result = {"compile_ok": True, "executed": False, "pass_ok": False, "callable_names": [], "test_results": [], "error": f"{type(exc).__name__}:{exc}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
"""


@dataclass(frozen=True, slots=True)
class IsolatedTaskRun:
    compile_ok: bool
    executed: bool
    pass_ok: bool | None
    callable_names: tuple[str, ...]
    error: str | None


def execute_python_task(
    code: str,
    tests: tuple[str, ...] | list[str],
    *,
    entrypoints: tuple[str, ...] | list[str] = (),
    timeout_seconds: int = 5,
) -> IsolatedTaskRun:
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", _CHILD_SCRIPT],
            input=json.dumps({"code": code, "tests": list(tests), "entrypoints": list(entrypoints)}, ensure_ascii=True),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return IsolatedTaskRun(False, False, False, (), "timeout")
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit_code:{completed.returncode}"
        return IsolatedTaskRun(False, False, False, (), detail)
    payload = json.loads(completed.stdout)
    return IsolatedTaskRun(
        compile_ok=bool(payload.get("compile_ok", False)),
        executed=bool(payload.get("executed", False)),
        pass_ok=payload.get("pass_ok"),
        callable_names=tuple(str(name) for name in payload.get("callable_names", [])),
        error=str(payload.get("error", "")) or None,
    )


_PYTHON_IO_CHILD_SCRIPT = r"""
import json
import sys


def main():
    payload = json.loads(sys.stdin.read())
    namespace = {"__name__": "__codedye_io_eval__"}
    try:
        exec(compile(payload["code"], "codedye_io_eval.py", "exec"), namespace, namespace)
    except SyntaxError as exc:
        print(json.dumps({"compile_ok": False, "executed": False, "pass_ok": False, "error": "syntax_error:" + exc.msg}))
        return
    except Exception as exc:
        print(json.dumps({"compile_ok": True, "executed": False, "pass_ok": False, "error": f"{type(exc).__name__}:{exc}"}))
        return
    solve = namespace.get("solve")
    if not callable(solve):
        print(json.dumps({"compile_ok": True, "executed": False, "pass_ok": False, "error": "missing_callable:solve"}))
        return
    for case in payload["cases"]:
        try:
            observed = solve(*case.get("args", []))
        except Exception as exc:
            print(json.dumps({"compile_ok": True, "executed": True, "pass_ok": False, "error": f"{type(exc).__name__}:{exc}"}))
            return
        if observed != case.get("expected"):
            print(json.dumps({"compile_ok": True, "executed": True, "pass_ok": False, "error": "assertion_mismatch"}))
            return
    print(json.dumps({"compile_ok": True, "executed": True, "pass_ok": True, "error": ""}))


if __name__ == "__main__":
    main()
"""


def _parse_io_cases(tests: tuple[str, ...] | list[str]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for raw in tests:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("io_case_must_be_object")
        args = payload.get("args", [])
        if not isinstance(args, list):
            raise ValueError("io_case_args_must_be_list")
        cases.append({"args": args, "expected": payload.get("expected")})
    return cases


def _run_completed(
    command: list[str],
    *,
    cwd: Path | None = None,
    input_text: str = "",
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.setdefault("LC_ALL", "C.UTF-8")
    try:
        return subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            input=input_text,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
            env=env,
        )
    except OSError as exc:
        raise RuntimeError(f"runtime_unavailable:{command[0]}:{type(exc).__name__}") from exc


def _json_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _string_cases(cases: list[dict[str, Any]]) -> list[tuple[str, str]]:
    string_cases: list[tuple[str, str]] = []
    for case in cases:
        args = case.get("args", [])
        expected = case.get("expected")
        if len(args) != 1 or not isinstance(args[0], str) or not isinstance(expected, str):
            raise ValueError("non_python_io_cases_require_single_string_arg_and_string_expected")
        string_cases.append((args[0], expected))
    return string_cases


def _execute_python_io_task(code: str, cases: list[dict[str, Any]], timeout_seconds: int) -> IsolatedTaskRun:
    try:
        completed = _run_completed(
            [sys.executable, "-I", "-c", _PYTHON_IO_CHILD_SCRIPT],
            input_text=json.dumps({"code": code, "cases": cases}, ensure_ascii=True),
            timeout_seconds=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return IsolatedTaskRun(False, False, False, (), "timeout")
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit_code:{completed.returncode}"
        return IsolatedTaskRun(False, False, False, (), detail)
    payload = json.loads(completed.stdout)
    return IsolatedTaskRun(
        compile_ok=bool(payload.get("compile_ok", False)),
        executed=bool(payload.get("executed", False)),
        pass_ok=payload.get("pass_ok"),
        callable_names=("solve",),
        error=str(payload.get("error", "")) or None,
    )


def _execute_typescript_io_task(code: str, cases: list[dict[str, Any]], timeout_seconds: int) -> IsolatedTaskRun:
    js_cases = json.dumps(cases, ensure_ascii=True)
    runner = (
        '"use strict";\n'
        "const cases = " + js_cases + ";\n"
        + code
        + "\n"
        "if (typeof solve !== 'function') { throw new Error('missing_callable:solve'); }\n"
        "function same(a, b) { return JSON.stringify(a) === JSON.stringify(b); }\n"
        "for (const item of cases) {\n"
        "  const observed = solve(...item.args);\n"
        "  if (!same(observed, item.expected)) { throw new Error('assertion_mismatch'); }\n"
        "}\n"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "codedye_io_task.js"
        path.write_text(runner, encoding="utf-8")
        try:
            completed = _run_completed(["node", str(path)], timeout_seconds=timeout_seconds)
        except subprocess.TimeoutExpired:
            return IsolatedTaskRun(False, False, False, (), "timeout")
        except RuntimeError as exc:
            return IsolatedTaskRun(False, False, False, (), str(exc))
    if completed.returncode == 0:
        return IsolatedTaskRun(True, True, True, ("solve",), None)
    detail = completed.stderr.strip() or completed.stdout.strip() or f"exit_code:{completed.returncode}"
    compile_ok = "SyntaxError" not in detail
    return IsolatedTaskRun(compile_ok, compile_ok, False, (), detail[:240])


def _execute_java_io_task(code: str, cases: list[dict[str, Any]], timeout_seconds: int) -> IsolatedTaskRun:
    string_cases = _string_cases(cases)
    rows = ",\n".join(
        "      {" + _json_string(arg) + ", " + _json_string(expected) + "}" for arg, expected in string_cases
    )
    runner = (
        "public class Runner {\n"
        "  public static void main(String[] args) throws Exception {\n"
        "    String[][] cases = new String[][] {\n"
        f"{rows}\n"
        "    };\n"
        "    for (String[] item : cases) {\n"
        "      String observed = Solution.solve(item[0]);\n"
        "      if (!observed.equals(item[1])) {\n"
        "        throw new RuntimeException(\"assertion_mismatch\");\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "Solution.java").write_text(code, encoding="utf-8")
        (root / "Runner.java").write_text(runner, encoding="utf-8")
        try:
            compile_completed = _run_completed(["javac", "Solution.java", "Runner.java"], cwd=root, timeout_seconds=timeout_seconds)
        except subprocess.TimeoutExpired:
            return IsolatedTaskRun(False, False, False, (), "timeout")
        except RuntimeError as exc:
            return IsolatedTaskRun(False, False, False, (), str(exc))
        if compile_completed.returncode != 0:
            detail = compile_completed.stderr.strip() or compile_completed.stdout.strip()
            return IsolatedTaskRun(False, False, False, (), detail[:240])
        try:
            run_completed = _run_completed(["java", "Runner"], cwd=root, timeout_seconds=timeout_seconds)
        except subprocess.TimeoutExpired:
            return IsolatedTaskRun(True, True, False, (), "timeout")
        except RuntimeError as exc:
            return IsolatedTaskRun(True, False, False, (), str(exc))
    if run_completed.returncode == 0:
        return IsolatedTaskRun(True, True, True, ("Solution.solve",), None)
    detail = run_completed.stderr.strip() or run_completed.stdout.strip() or f"exit_code:{run_completed.returncode}"
    return IsolatedTaskRun(True, True, False, ("Solution.solve",), detail[:240])


def _execute_cpp_io_task(code: str, cases: list[dict[str, Any]], timeout_seconds: int) -> IsolatedTaskRun:
    string_cases = _string_cases(cases)
    rows = ",\n".join("    {" + _json_string(arg) + ", " + _json_string(expected) + "}" for arg, expected in string_cases)
    runner = (
        "#include <string>\n"
        "#include <utility>\n"
        "#include <vector>\n"
        + code
        + "\nint main() {\n"
        + "  std::vector<std::pair<std::string, std::string>> cases = {\n"
        + rows
        + "\n  };\n"
        + "  for (const auto& item : cases) {\n"
        + "    if (solve(item.first) != item.second) { return 17; }\n"
        + "  }\n"
        + "  return 0;\n"
        + "}\n"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        source = root / "main.cpp"
        binary = root / "codedye_io_task"
        source.write_text(runner, encoding="utf-8")
        try:
            compile_completed = _run_completed(["g++", "-std=c++17", "-O0", str(source), "-o", str(binary)], timeout_seconds=timeout_seconds)
        except subprocess.TimeoutExpired:
            return IsolatedTaskRun(False, False, False, (), "timeout")
        except RuntimeError as exc:
            return IsolatedTaskRun(False, False, False, (), str(exc))
        if compile_completed.returncode != 0:
            detail = compile_completed.stderr.strip() or compile_completed.stdout.strip()
            return IsolatedTaskRun(False, False, False, (), detail[:240])
        try:
            run_completed = _run_completed([str(binary)], timeout_seconds=timeout_seconds)
        except subprocess.TimeoutExpired:
            return IsolatedTaskRun(True, True, False, (), "timeout")
        except RuntimeError as exc:
            return IsolatedTaskRun(True, False, False, (), str(exc))
    if run_completed.returncode == 0:
        return IsolatedTaskRun(True, True, True, ("solve",), None)
    detail = run_completed.stderr.strip() or run_completed.stdout.strip() or f"exit_code:{run_completed.returncode}"
    return IsolatedTaskRun(True, True, False, ("solve",), detail[:240])


def _execute_go_io_task(code: str, cases: list[dict[str, Any]], timeout_seconds: int) -> IsolatedTaskRun:
    string_cases = _string_cases(cases)
    rows = ",\n".join(
        "    {input: " + _json_string(arg) + ", expected: " + _json_string(expected) + "}" for arg, expected in string_cases
    )
    if rows:
        rows += ","
    runner = (
        code
        + "\nfunc main() {\n"
        + "  cases := []struct { input string; expected string }{\n"
        + rows
        + "\n  }\n"
        + "  for _, item := range cases {\n"
        + "    if solve(item.input) != item.expected { panic(\"assertion_mismatch\") }\n"
        + "  }\n"
        + "}\n"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        source = root / "main.go"
        source.write_text(runner, encoding="utf-8")
        try:
            completed = _run_completed(["go", "run", str(source)], timeout_seconds=timeout_seconds)
        except subprocess.TimeoutExpired:
            return IsolatedTaskRun(False, False, False, (), "timeout")
        except RuntimeError as exc:
            return IsolatedTaskRun(False, False, False, (), str(exc))
    if completed.returncode == 0:
        return IsolatedTaskRun(True, True, True, ("solve",), None)
    detail = completed.stderr.strip() or completed.stdout.strip() or f"exit_code:{completed.returncode}"
    compile_ok = "syntax error" not in detail.lower()
    return IsolatedTaskRun(compile_ok, compile_ok, False, ("solve",), detail[:240])


def execute_io_task(
    code: str,
    language: str,
    tests: tuple[str, ...] | list[str],
    *,
    timeout_seconds: int = 8,
) -> IsolatedTaskRun:
    try:
        cases = _parse_io_cases(tests)
    except Exception as exc:
        return IsolatedTaskRun(False, False, False, (), f"io_case_parse_error:{type(exc).__name__}:{exc}")
    normalized_language = language.lower()
    if normalized_language == "python":
        return _execute_python_io_task(code, cases, timeout_seconds)
    if normalized_language in {"typescript", "javascript"}:
        return _execute_typescript_io_task(code, cases, timeout_seconds)
    if normalized_language == "java":
        return _execute_java_io_task(code, cases, timeout_seconds)
    if normalized_language in {"cpp", "c++", "cxx"}:
        return _execute_cpp_io_task(code, cases, timeout_seconds)
    if normalized_language == "go":
        return _execute_go_io_task(code, cases, timeout_seconds)
    return IsolatedTaskRun(False, False, False, (), f"unsupported_io_language:{language}")
