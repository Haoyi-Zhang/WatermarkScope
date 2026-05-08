from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_zero_legacy_name
import release_bundle_contract
import validate_release_bundle
import validate_setup

DEFAULT_OUTPUT = ROOT.parent / "CodeMarkBench_release"
EXCLUDED_PREFIXES = (
    ".git",
    ".coordination",
    ".pytest_cache",
    "results/runs",
    "results/matrix",
    "results/certifications",
    "results/launchers",
    "results/release_bundle",
    "results/archive",
    "results/test_release_bundle",
    "results/fetched_suite",
    "results/tmp",
    "results/.tmp",
    "results/figures/suite_precheck",
    "results/submission_preflight",
)
EXCLUDED_NAMES = {"__pycache__"}
REQUIRED_PUBLIC_FILES = tuple(Path(relative) for relative in release_bundle_contract.REQUIRED_TRACKED_BUNDLE_FILES)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a publishable CodeMarkBench repository with fresh git history.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output directory for the publishable repo")
    parser.add_argument("--author-name", default="CodeMarkBench Release", help="Git author name for the initial commit")
    parser.add_argument(
        "--author-email",
        default="codemarkbench-release",
        help="Anonymous git author identity string for the initial commit.",
    )
    return parser.parse_args()


def _is_excluded(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    if any(relative == prefix or relative.startswith(prefix + "/") for prefix in EXCLUDED_PREFIXES):
        return True
    parts = path.relative_to(ROOT).parts
    if any(part in EXCLUDED_NAMES for part in parts):
        return True
    return any(str(part).startswith(".tmp") for part in parts)


def _git_lines(*args: str) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _ensure_clean_tree() -> None:
    status_lines = _git_lines("status", "--short", "--untracked-files=all")
    if status_lines:
        raise SystemExit("publish export requires a clean tracked working tree with no untracked files")


def _tracked_files() -> list[Path]:
    tracked: list[Path] = []
    for relative in sorted(release_bundle_contract.tracked_bundle_surface(ROOT)):
        candidate = ROOT / relative
        if candidate.exists() and candidate.is_file():
            tracked.append(candidate)
    return tracked


def _copy_tracked_files(output: Path) -> None:
    for source in _tracked_files():
        relative = source.relative_to(ROOT)
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _validate_required_public_assets(root: Path) -> None:
    missing = [path.as_posix() for path in REQUIRED_PUBLIC_FILES if not (root / path).exists()]
    if missing:
        raise SystemExit(f"publish export is missing required public assets: {missing}")


def _validate_public_snapshot_identity_markers(root: Path) -> None:
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).parts[:1] != ("tests",)
    )
    findings = validate_setup.scan_for_identity_markers(files, labels=set(validate_setup.IDENTITY_PATTERNS))
    if findings:
        preview = ", ".join(findings[:8])
        if len(findings) > 8:
            preview += ", ..."
        raise SystemExit(f"publish export contains identity-marker findings: {preview}")


def _ensure_real_environment_capture(root: Path) -> None:
    issues = validate_release_bundle._environment_capture_issues(root)
    if issues:
        preview = ", ".join(issues[:6])
        if len(issues) > 6:
            preview += ", ..."
        raise SystemExit(f"publish export requires validated environment capture: {preview}")


def _ensure_release_summary_provenance(root: Path) -> None:
    issues = validate_release_bundle._summary_export_identity_issues(root)
    if issues:
        preview = ", ".join(issues[:6])
        if len(issues) > 6:
            preview += ", ..."
        raise SystemExit(f"publish export requires validated release summary provenance: {preview}")


def _init_git(output: Path, *, author_name: str, author_email: str) -> None:
    subprocess.run(["git", "init"], cwd=str(output), check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=str(output), check=True)
    subprocess.run(["git", "config", "user.name", author_name], cwd=str(output), check=True)
    subprocess.run(["git", "config", "user.email", author_email], cwd=str(output), check=True)
    subprocess.run(["git", "add", "."], cwd=str(output), check=True)
    subprocess.run(["git", "commit", "-m", "Initialize CodeMarkBench"], cwd=str(output), check=True)


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    output_name_findings = validate_setup.legacy_project_findings_for_text(
        output.name,
        context="publish export root name",
    )
    if output_name_findings:
        raise SystemExit("refusing to export publish repo with legacy names in the output directory name")
    if output == ROOT or ROOT in output.parents:
        raise SystemExit("publish export output must be outside the active repository root")
    if output.exists():
        raise SystemExit("publish export requires --output to point to a fresh nonexistent directory")
    output.mkdir(parents=True, exist_ok=True)

    _ensure_clean_tree()
    _validate_required_public_assets(ROOT)
    _ensure_real_environment_capture(ROOT)
    _ensure_release_summary_provenance(ROOT)
    _copy_tracked_files(output)
    _validate_required_public_assets(output)
    _ensure_release_summary_provenance(output)
    _validate_public_snapshot_identity_markers(output)
    findings = check_zero_legacy_name.scan_tree(output)
    if findings:
        raise SystemExit("refusing to export publish repo with legacy names still present")
    _init_git(output, author_name=args.author_name, author_email=args.author_email)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
