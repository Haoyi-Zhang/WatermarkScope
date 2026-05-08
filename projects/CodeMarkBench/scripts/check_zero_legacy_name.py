from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_setup


DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".coordination",
    "__pycache__",
    ".pytest_cache",
    "model_cache",
    "external_checkout",
}
DEFAULT_EXCLUDED_PATH_PREFIXES = (
    "results/matrix/",
    "results/matrix_shards/",
    "results/audits/",
    "results/certifications/",
    "results/launchers/",
    "results/archive/",
    "results/release_bundle/",
    "results/fetched_suite/",
)
DEFAULT_EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".gz", ".zip", ".tar", ".tgz", ".bz2", ".7z"}
BINARY_SCAN_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".woff", ".woff2"}
LEGACY_BINARY_TOKENS = tuple(
    {
        validate_setup._LEGACY_TITLE.encode("utf-8").lower(),
        validate_setup._LEGACY_SLUG.encode("utf-8").lower(),
        validate_setup._LEGACY_ENV_PREFIX.encode("utf-8").lower(),
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail if the tree still contains legacy project naming.")
    parser.add_argument("--root", type=Path, required=True, help="Tree root to scan.")
    parser.add_argument("--report", type=Path, default=None, help="Optional JSON report path.")
    return parser.parse_args()


def _is_excluded_dir(path: Path, *, root: Path) -> bool:
    relative = path.relative_to(root)
    relative_str = relative.as_posix()
    if any(part in DEFAULT_EXCLUDED_DIRS for part in relative.parts):
        return True
    for prefix in DEFAULT_EXCLUDED_PATH_PREFIXES:
        normalized_prefix = prefix.rstrip("/")
        if relative_str == normalized_prefix or relative_str.startswith(prefix):
            return True
    return False


def _should_skip_content(path: Path, *, root: Path) -> bool:
    if _is_excluded_dir(path, root=root):
        return True
    return path.suffix.lower() in DEFAULT_EXCLUDED_SUFFIXES


def _scan_binary_for_legacy_markers(path: Path, *, root: Path) -> list[str]:
    findings: list[str] = []
    relative = path.relative_to(root).as_posix()
    payload = path.read_bytes().lower()
    for token in LEGACY_BINARY_TOKENS:
        if token in payload:
            findings.append(f"{relative}: matched legacy project marker in binary content")
            break
    return findings


def scan_tree(root: Path) -> list[str]:
    root = root.resolve()
    if not root.exists():
        return [f"missing root: {root}"]
    findings = validate_setup.legacy_project_findings_for_text(root.name, context=".: root name")
    for current_dir, dir_names, file_names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current_dir)
        retained_dir_names: list[str] = []
        for dir_name in dir_names:
            child_dir = current_path / dir_name
            if child_dir.is_symlink() or _is_excluded_dir(child_dir, root=root):
                continue
            retained_dir_names.append(dir_name)
        dir_names[:] = retained_dir_names
        for file_name in file_names:
            path = current_path / file_name
            if path.is_symlink() or _is_excluded_dir(path, root=root):
                continue
            relative = path.relative_to(root).as_posix()
            for label, pattern in validate_setup.LEGACY_PROJECT_PATTERNS.items():
                if pattern.search(relative):
                    findings.append(f"{relative}: matched {label} in path")
            if _should_skip_content(path, root=root):
                continue
            if path.suffix.lower() in BINARY_SCAN_SUFFIXES:
                findings.extend(_scan_binary_for_legacy_markers(path, root=root))
                continue
            findings.extend(validate_setup.scan_for_legacy_project_markers([path], root=root))
    return sorted(set(findings))


def main() -> int:
    args = parse_args()
    findings = scan_tree(args.root)
    report = {
        "root": str(args.root.resolve()),
        "status": "failed" if findings else "passed",
        "findings": findings,
    }
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if findings:
        print("Legacy-name scan failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Legacy-name scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
