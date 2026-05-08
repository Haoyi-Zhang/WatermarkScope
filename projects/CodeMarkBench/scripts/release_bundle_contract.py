from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]

TRACKED_DATASET_STATISTICS_TABLE_FILES = (
    "results/tables/dataset_statistics/benchmark_definition_summary.csv",
    "results/tables/dataset_statistics/benchmark_definition_summary.json",
    "results/tables/dataset_statistics/dataset_family_breakdown.csv",
    "results/tables/dataset_statistics/dataset_family_breakdown.json",
    "results/tables/dataset_statistics/dataset_statistics_manifest.json",
    "results/tables/dataset_statistics/dataset_task_category_breakdown.csv",
    "results/tables/dataset_statistics/dataset_task_category_breakdown.json",
    "results/tables/dataset_statistics/release_slice_language_breakdown.csv",
    "results/tables/dataset_statistics/release_slice_language_breakdown.json",
    "results/tables/dataset_statistics/release_slice_summary.csv",
    "results/tables/dataset_statistics/release_slice_summary.json",
    "results/tables/dataset_statistics/release_source_manifest_index.csv",
    "results/tables/dataset_statistics/release_source_manifest_index.json",
)
TRACKED_DATASET_STATISTICS_FIGURE_FILES = (
    "results/figures/dataset_statistics/README.md",
    "results/figures/dataset_statistics/evaluation_dimensions_overview.pdf",
    "results/figures/dataset_statistics/evaluation_dimensions_overview.png",
    "results/figures/dataset_statistics/release_slice_composition.pdf",
    "results/figures/dataset_statistics/release_slice_composition.png",
)
TRACKED_SUITE_README_FILES = (
    "results/figures/suite_all_models_methods/README.md",
    "results/tables/suite_all_models_methods/README.md",
)
_TRACKED_SUITE_FIGURE_STEMS = (
    "suite_all_models_methods_score_decomposition",
    "suite_all_models_methods_detection_vs_utility",
)
_TRACKED_SUITE_FIGURE_SUFFIXES = (".png", ".pdf", ".json", ".csv")
_TRACKED_SUITE_EXPORT_ROWARRAY_STEMS = (
    "method_summary",
    "model_summary",
    "model_method_summary",
    "method_source_summary",
    "method_language_summary",
    "method_attack_summary",
    "suite_all_models_methods_run_inventory",
    "suite_all_models_methods_method_master_leaderboard",
    "suite_all_models_methods_method_model_leaderboard",
    "suite_all_models_methods_upstream_only_leaderboard",
    "suite_all_models_methods_model_method_functional_quality",
    "suite_all_models_methods_utility_robustness_summary",
    "timing_summary",
    "suite_all_models_methods_model_method_timing",
)
TRACKED_SUITE_EXPORT_FILES = (
    *(
        f"results/tables/suite_all_models_methods/{stem}{suffix}"
        for stem in _TRACKED_SUITE_EXPORT_ROWARRAY_STEMS
        for suffix in (".csv", ".json")
    ),
    "results/tables/suite_all_models_methods/suite_all_models_methods_export_identity.json",
    *(
        f"results/figures/suite_all_models_methods/{stem}{suffix}"
        for stem in _TRACKED_SUITE_FIGURE_STEMS
        for suffix in _TRACKED_SUITE_FIGURE_SUFFIXES
    ),
)

BUNDLE_ALLOWED_PATHS = (
    "README.md",
    "LICENSE",
    "ARTIFACTS.md",
    "artifacts",
    "docs",
    "docs/release_contract.md",
    "docs/release_provenance.md",
    "Makefile",
    ".env.example",
    "pyproject.toml",
    "requirements.txt",
    "requirements-remote.txt",
    "codemarkbench",
    "configs",
    "scripts",
    "scripts/reviewer_workflow.ps1",
    "scripts/reviewer_workflow.py",
    "scripts/reviewer_workflow.sh",
    "data/release",
    "data/fixtures",
    "results/schema.json",
    "results/export_schema.json",
    "results/environment/runtime_environment.json",
    "results/environment/runtime_environment.md",
    "model_cache/README.md",
    "third_party/README.md",
    "third_party/STONE-watermarking.UPSTREAM.json",
    "third_party/SWEET-watermark.UPSTREAM.json",
    "third_party/EWD.UPSTREAM.json",
    "third_party/KGW-lm-watermarking.UPSTREAM.json",
    *TRACKED_DATASET_STATISTICS_TABLE_FILES,
    *TRACKED_DATASET_STATISTICS_FIGURE_FILES,
    *TRACKED_SUITE_README_FILES,
    *TRACKED_SUITE_EXPORT_FILES,
)

REQUIRED_TRACKED_BUNDLE_FILES = (
    "README.md",
    "LICENSE",
    "ARTIFACTS.md",
    "docs/baseline_screening.md",
    "docs/release_contract.md",
    "docs/release_provenance.md",
    "data/fixtures/benchmark.normalized.jsonl",
    "results/schema.json",
    "results/export_schema.json",
    "results/environment/runtime_environment.json",
    "results/environment/runtime_environment.md",
    "results/tables/dataset_statistics/benchmark_definition_summary.csv",
    "results/tables/dataset_statistics/release_slice_language_breakdown.csv",
    "results/tables/dataset_statistics/dataset_task_category_breakdown.csv",
    "results/tables/dataset_statistics/dataset_family_breakdown.csv",
    "results/tables/dataset_statistics/release_source_manifest_index.csv",
    *(
        f"results/tables/suite_all_models_methods/{stem}{suffix}"
        for stem in _TRACKED_SUITE_EXPORT_ROWARRAY_STEMS
        for suffix in (".csv", ".json")
    ),
    "results/tables/suite_all_models_methods/suite_all_models_methods_export_identity.json",
    "results/figures/dataset_statistics/release_slice_composition.png",
    "results/figures/dataset_statistics/evaluation_dimensions_overview.png",
    *(
        f"results/figures/suite_all_models_methods/{stem}{suffix}"
        for stem in _TRACKED_SUITE_FIGURE_STEMS
        for suffix in _TRACKED_SUITE_FIGURE_SUFFIXES
    ),
)

POLICY_EXCLUSIONS = (
    ".git",
    "paper",
    "proposal.md",
    "configs/archive",
    "data/interim",
    "results/runs",
    "results/submission_preflight",
    "scripts/archive_suite_outputs.py",
)

FORBIDDEN_BUNDLE_PREFIXES = (
    ".coordination",
    "configs/archive",
    "data/public",
    "results/audits",
    "results/archive",
    "results/runs",
    "results/matrix",
    "results/matrix_shards",
    "results/figures/suite_precheck",
    "results/certifications",
    "results/release_bundle",
    "results/fetched_suite",
    "results/test_release_bundle",
    "results/tmp",
    "results/submission_preflight",
    "scripts/archive_suite_outputs.py",
)

ALLOWED_GENERATED_BUNDLE_FILES = {
    "baseline_provenance.json",
    "bundle.manifest.json",
    "SHA256SUMS.txt",
    "MANIFEST.txt",
    "EXCLUDED.txt",
}
ALLOWED_BUNDLE_OUTPUT_ROOT_NAMES = (
    "release_bundle",
    "test_release_bundle",
    "tmp",
)
FORBIDDEN_BUNDLE_PATH_COMPONENTS = {
    "__pycache__",
    ".pytest_cache",
}
FORBIDDEN_BUNDLE_FILE_SUFFIXES = (
    ".pyc",
    ".pyo",
)


def path_matches_prefix(relative: str | Path, prefix: str) -> bool:
    candidate = str(relative).strip().replace("\\", "/")
    normalized_prefix = str(prefix).strip().replace("\\", "/").rstrip("/")
    if not candidate or not normalized_prefix:
        return False
    return candidate == normalized_prefix or candidate.startswith(normalized_prefix + "/")


def has_hidden_path_component(
    value: str | Path,
    *,
    allow_root_hidden_leaf: bool = False,
) -> bool:
    normalized = normalize_bundle_relative_path(value)
    if normalized is None:
        return False
    parts = PurePosixPath(normalized).parts
    for index, part in enumerate(parts):
        if not part.startswith("."):
            continue
        if allow_root_hidden_leaf and len(parts) == 1 and index == 0:
            continue
        return True
    return False


def first_symlink_component(root: Path, candidate: Path) -> Path | None:
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return candidate if candidate.is_symlink() else None
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return current
    return None


def normalize_bundle_relative_path(
    value: str | Path,
    *,
    required_prefix: str | None = None,
    forbid_hidden_components: bool = False,
    allow_hidden_leaf: bool = False,
) -> str | None:
    stripped = str(value).strip().replace("\\", "/")
    if not stripped:
        return None
    candidate = PurePosixPath(stripped)
    if candidate.is_absolute():
        return None
    if any(part in {"", ".", ".."} for part in candidate.parts):
        return None
    if forbid_hidden_components:
        hidden_parts = candidate.parts[:-1] if allow_hidden_leaf else candidate.parts
        if any(part.startswith(".") for part in hidden_parts):
            return None
    normalized = candidate.as_posix().strip()
    if not normalized:
        return None
    if required_prefix:
        prefix = required_prefix.rstrip("/")
        if normalized != prefix and not normalized.startswith(prefix + "/"):
            return None
    return normalized


def is_bundle_path_allowed(relative: str) -> bool:
    candidate = relative.strip().replace("\\", "/")
    return any(path_matches_prefix(candidate, prefix) for prefix in BUNDLE_ALLOWED_PATHS)


def is_policy_excluded(relative: str) -> bool:
    candidate = relative.strip().replace("\\", "/")
    return any(path_matches_prefix(candidate, prefix) for prefix in POLICY_EXCLUSIONS)


def is_allowed_bundle_output_root(relative: str | Path) -> bool:
    normalized = normalize_bundle_relative_path(relative)
    if normalized is None:
        return False
    parts = PurePosixPath(normalized).parts
    if len(parts) < 2 or parts[0] != "results":
        return False
    root_name = parts[1]
    if root_name == "tmp":
        return len(parts) > 2
    return any(
        root_name == prefix or root_name.startswith(prefix + "_")
        for prefix in ALLOWED_BUNDLE_OUTPUT_ROOT_NAMES
        if prefix != "tmp"
    )


def forbidden_bundle_artifact_issue(relative: str | Path) -> str | None:
    normalized = normalize_bundle_relative_path(relative)
    if normalized is None:
        return None
    parts = PurePosixPath(normalized).parts
    if any(part.startswith(".") for part in parts[:-1]):
        return normalized
    if any(part in FORBIDDEN_BUNDLE_PATH_COMPONENTS for part in parts):
        return normalized
    leaf = parts[-1] if parts else ""
    if any(leaf.endswith(suffix) for suffix in FORBIDDEN_BUNDLE_FILE_SUFFIXES):
        return normalized
    return None


def tracked_bundle_surface(root: Path) -> set[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "tracked publishable surface requires git metadata; create a clean git staging mirror before export or validation."
        ) from exc
    if completed.returncode != 0:
        raise RuntimeError(
            "tracked publishable surface requires git metadata; create a clean git staging mirror before export or validation."
        )
    surface: set[str] = set()
    for raw in completed.stdout.splitlines():
        relative = raw.strip().replace("\\", "/")
        if not relative:
            continue
        candidate = root / Path(relative)
        if is_policy_excluded(relative):
            continue
        if not is_bundle_path_allowed(relative):
            continue
        if first_symlink_component(root, candidate) is not None:
            raise RuntimeError(
                f"tracked publishable path must not contain symlinked path components: {relative}"
            )
        if not candidate.exists():
            raise RuntimeError(
                f"tracked publishable path is missing from the working tree: {relative}"
            )
        if not candidate.is_file():
            raise RuntimeError(f"tracked publishable path must resolve to a regular file: {relative}")
        if has_hidden_path_component(relative, allow_root_hidden_leaf=True):
            raise RuntimeError(
                f"tracked publishable path must not contain hidden path components: {relative}"
            )
        artifact_issue = forbidden_bundle_artifact_issue(relative)
        if artifact_issue is not None:
            raise RuntimeError(
                f"tracked publishable path must not contain machine-specific residue: {artifact_issue}"
            )
        surface.add(relative)
    return surface


def vendored_bundle_prefix(path: str) -> str | None:
    return normalize_bundle_relative_path(
        path,
        required_prefix="third_party",
        forbid_hidden_components=True,
    )


def external_bundle_prefix(path: str) -> str | None:
    return normalize_bundle_relative_path(
        path,
        required_prefix="external_checkout",
        forbid_hidden_components=True,
    )


def vendored_bundle_file(path: str) -> str | None:
    return normalize_bundle_relative_path(
        path,
        required_prefix="third_party",
        forbid_hidden_components=True,
        allow_hidden_leaf=True,
    )
