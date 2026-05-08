from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_zero_legacy_name
import capture_environment
import release_bundle_contract
import validate_setup
from codemarkbench.suite import CANONICAL_SUITE_MODELS


REQUIRED_BASELINES = ("stone", "sweet", "ewd", "kgw")
BASELINE_UPSTREAM_MANIFESTS = {
    "stone": "third_party/STONE-watermarking.UPSTREAM.json",
    "sweet": "third_party/SWEET-watermark.UPSTREAM.json",
    "ewd": "third_party/EWD.UPSTREAM.json",
    "kgw": "third_party/KGW-lm-watermarking.UPSTREAM.json",
}
REQUIRED_BUNDLE_FILES = (
    *release_bundle_contract.REQUIRED_TRACKED_BUNDLE_FILES,
    "baseline_provenance.json",
    "bundle.manifest.json",
    "SHA256SUMS.txt",
    "MANIFEST.txt",
    "EXCLUDED.txt",
)
CANONICAL_SUITE_MANIFEST = "configs/matrices/suite_all_models_methods.json"
CANONICAL_SUITE_PROFILE = "suite_all_models_methods"
REQUIRED_SUMMARY_EXPORT_TABLES = (
    "method_summary.json",
    "suite_all_models_methods_method_master_leaderboard.json",
    "suite_all_models_methods_method_model_leaderboard.json",
    "suite_all_models_methods_model_method_functional_quality.json",
)
REQUIRED_SUMMARY_FIGURE_STEMS = (
    "suite_all_models_methods_score_decomposition",
    "suite_all_models_methods_detection_vs_utility",
)
REQUIRED_SUMMARY_FIGURE_SUFFIXES = (".png", ".pdf", ".json", ".csv")
REQUIRED_SUMMARY_FIGURE_FILES = tuple(
    f"{stem}{suffix}"
    for stem in REQUIRED_SUMMARY_FIGURE_STEMS
    for suffix in REQUIRED_SUMMARY_FIGURE_SUFFIXES
)
ALLOWED_GENERATED_BUNDLE_FILES = release_bundle_contract.ALLOWED_GENERATED_BUNDLE_FILES
FORBIDDEN_BUNDLE_PREFIXES = release_bundle_contract.FORBIDDEN_BUNDLE_PREFIXES
REQUIRED_ENVIRONMENT_SECTION_KEYS = ("platform", "python", "packages", "tools", "gpu")
ALLOWED_BASELINE_PROVENANCE_KEYS = frozenset(
    {
        "origin",
        "source_path",
        "vendored_path",
        "external_path",
        "selected_checkout_path",
        "checkout_valid",
        "bundle_eligible",
        "repo_url",
        "pinned_commit",
        "upstream_commit",
        "license_status",
        "verification_issues",
        "vendored_exists",
        "external_exists",
        "redistributable",
        "vendored_files",
        "vendored_file_digests",
    }
)
ALLOWED_UPSTREAM_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "repo_url",
        "pinned_commit",
        "license_status",
        "checkout_root",
        "public_external_root",
        "external_root",
        "source_relative",
        "method_symbol",
        "notes",
        "bundle_sanitized",
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a staged release bundle.")
    parser.add_argument("--bundle", type=Path, required=True, help="Bundle root produced by scripts/package_zenodo.sh")
    parser.add_argument("--report", type=Path, default=None, help="Optional JSON report path")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _environment_capture_issues(bundle: Path) -> list[str]:
    issues: list[str] = []
    json_path = bundle / "results" / "environment" / "runtime_environment.json"
    md_path = bundle / "results" / "environment" / "runtime_environment.md"

    try:
        payload = _load_json(json_path)
    except Exception as exc:
        return [f"unable to parse runtime environment capture at {json_path}: {exc}"]

    if not isinstance(payload, dict):
        return [f"{json_path} must be a JSON object."]
    def _is_sha256(value: object) -> bool:
        text = str(value or "").strip().lower()
        return len(text) == 64 and all(character in "0123456789abcdef" for character in text)

    status = str(payload.get("status", "")).strip().lower()
    if "placeholder" in status:
        issues.append("runtime environment JSON still declares a placeholder status")

    missing_sections = [
        name for name in REQUIRED_ENVIRONMENT_SECTION_KEYS if not isinstance(payload.get(name), dict)
    ]
    if missing_sections:
        issues.append(
            "runtime environment JSON is missing structured capture sections: "
            + ", ".join(missing_sections)
        )

    execution = payload.get("execution", {})
    if "execution" not in payload or not isinstance(execution, dict) or not execution:
        issues.append("runtime environment JSON is missing structured execution metadata")
    else:
        if str(execution.get("execution_mode", "")).strip() != "single_host_canonical":
            issues.append("runtime environment JSON must record execution_mode=single_host_canonical")
        if str(execution.get("cuda_visible_devices", "")).strip() != "0,1,2,3,4,5,6,7":
            issues.append("runtime environment JSON must record cuda_visible_devices=0,1,2,3,4,5,6,7")
        if int(execution.get("visible_gpu_count", 0) or 0) != 8:
            issues.append("runtime environment JSON must record visible_gpu_count=8")
        if not _is_sha256(execution.get("code_snapshot_digest")):
            issues.append("runtime environment JSON must record a 64-hex code_snapshot_digest")
        if not _is_sha256(execution.get("execution_environment_fingerprint")):
            issues.append("runtime environment JSON must record a 64-hex execution_environment_fingerprint")
        else:
            expected_fingerprint = capture_environment.execution_environment_fingerprint_sha256(
                payload,
                cuda_visible_devices=str(execution.get("cuda_visible_devices", "")).strip(),
            )
            if str(execution.get("execution_environment_fingerprint", "")).strip() != expected_fingerprint:
                issues.append(
                    "runtime environment JSON execution_environment_fingerprint must match the structured capture"
                )

    gpu_payload = payload.get("gpu", {})
    if isinstance(gpu_payload, dict):
        if int(gpu_payload.get("visible_gpu_count", 0) or 0) != 8:
            issues.append("runtime environment JSON gpu.visible_gpu_count must equal 8 for the fixed release execution class")
        if str(gpu_payload.get("cuda_visible_devices", "")).strip() != "0,1,2,3,4,5,6,7":
            issues.append("runtime environment JSON gpu.cuda_visible_devices must equal 0,1,2,3,4,5,6,7 for the fixed release execution class")

    markdown_text = md_path.read_text(encoding="utf-8", errors="replace").lower()
    if "placeholder" in markdown_text:
        issues.append("runtime environment Markdown still advertises a placeholder capture")

    return issues


def _bundle_files(bundle: Path) -> tuple[list[Path], list[Path]]:
    files: list[Path] = []
    symlinks: list[Path] = []
    for path in bundle.rglob("*"):
        if path.is_symlink():
            symlinks.append(path)
            continue
        if path.is_file():
            files.append(path)
    return sorted(files), sorted(symlinks)


def _load_checksums(path: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    if not path.exists():
        return payload
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = str(line).strip()
        if not stripped:
            continue
        parts = stripped.split(None, 1)
        if len(parts) != 2:
            continue
        digest, relpath = parts
        payload[relpath.strip()] = digest.strip()
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256_hexdigest(value: str) -> bool:
    text = str(value).strip().lower()
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def _publishable_tracked_files() -> set[str]:
    return release_bundle_contract.tracked_bundle_surface(ROOT)


def _normalize_bundle_relative_path(value: str) -> str | None:
    return release_bundle_contract.normalize_bundle_relative_path(value)


def _bundle_contains_path(actual_files: set[str], relative_path: str) -> bool:
    normalized = relative_path.rstrip("/")
    prefix = normalized + "/"
    return any(entry == normalized or entry.startswith(prefix) for entry in actual_files)


def _summary_export_identity_issues(bundle: Path) -> list[str]:
    issues: list[str] = []
    identity_path = (
        bundle
        / "results"
        / "tables"
        / "suite_all_models_methods"
        / "suite_all_models_methods_export_identity.json"
    )
    try:
        payload = _load_json(identity_path)
    except Exception as exc:
        return [f"unable to parse summary export identity at {identity_path}: {exc}"]
    if not isinstance(payload, dict):
        return [f"{identity_path} must be a JSON object."]

    if str(payload.get("artifact_role", "")).strip() != "suite_all_models_methods_release_summary_export_identity":
        issues.append("summary export identity must record the canonical artifact_role")
    if str(payload.get("manifest", "")).strip() != CANONICAL_SUITE_MANIFEST:
        issues.append(
            "summary export identity must record manifest=configs/matrices/suite_all_models_methods.json"
        )
    if str(payload.get("profile", "")).strip() != CANONICAL_SUITE_PROFILE:
        issues.append("summary export identity must record profile=suite_all_models_methods")
    if str(payload.get("execution_mode", "")).strip() != "single_host_canonical":
        issues.append("summary export identity must record execution_mode=single_host_canonical")
    matrix_code_snapshot_digest = str(payload.get("matrix_code_snapshot_digest", "")).strip().lower()
    if not _is_sha256_hexdigest(matrix_code_snapshot_digest):
        issues.append("summary export identity must record a 64-hex matrix_code_snapshot_digest")
    if int(payload.get("run_count", 0) or 0) != 140:
        issues.append("summary export identity must record run_count=140")
    if int(payload.get("success_count", 0) or 0) != 140:
        issues.append("summary export identity must record success_count=140")
    if int(payload.get("failed_count", 0) or 0) != 0:
        issues.append("summary export identity must record failed_count=0")
    score_version = str(payload.get("score_version", "")).strip()
    if not score_version:
        issues.append("summary export identity must record a non-empty score_version")
    matrix_index_relpath = str(payload.get("matrix_index", "")).strip()
    if matrix_index_relpath != "results/matrix/suite_all_models_methods/matrix_index.json":
        issues.append(
            "summary export identity must record matrix_index=results/matrix/suite_all_models_methods/matrix_index.json"
        )
    matrix_index_sha256 = str(payload.get("matrix_index_sha256", "")).strip().lower()
    if not _is_sha256_hexdigest(matrix_index_sha256):
        issues.append("summary export identity must record a 64-hex matrix_index_sha256")
    else:
        bundle_manifest_path = bundle / "bundle.manifest.json"
        if bundle_manifest_path.exists():
            try:
                bundle_manifest_payload = _load_json(bundle_manifest_path)
            except Exception as exc:
                issues.append(f"unable to parse bundle.manifest.json while validating matrix_index_sha256: {exc}")
            else:
                manifest_matrix_sha256 = str(
                    bundle_manifest_payload.get("canonical_matrix_index_sha256", "")
                ).strip().lower()
                if not _is_sha256_hexdigest(manifest_matrix_sha256):
                    issues.append("bundle.manifest.json must record a 64-hex canonical_matrix_index_sha256")
                elif matrix_index_sha256 != manifest_matrix_sha256:
                    issues.append(
                        "summary export identity matrix_index_sha256 must match "
                        "bundle.manifest.json canonical_matrix_index_sha256"
                    )
    canonical_manifest_digest = str(payload.get("canonical_manifest_digest", "")).strip().lower()
    if not _is_sha256_hexdigest(canonical_manifest_digest):
        issues.append("summary export identity must record a 64-hex canonical_manifest_digest")
    else:
        manifest_path = bundle / Path(CANONICAL_SUITE_MANIFEST)
        if manifest_path.exists():
            actual_manifest_digest = _sha256(manifest_path)
            if canonical_manifest_digest != actual_manifest_digest:
                issues.append("summary export identity canonical_manifest_digest must match the staged canonical manifest")

    expected_models = [spec.name for spec in CANONICAL_SUITE_MODELS]
    roster = payload.get("model_roster", [])
    if not isinstance(roster, list) or not roster:
        issues.append("summary export identity must record the canonical five-model release roster")
    else:
        observed_models: list[str] = []
        for index, entry in enumerate(roster, start=1):
            if not isinstance(entry, dict):
                issues.append(f"summary export identity model_roster[{index}] is not an object")
                continue
            model_name = str(entry.get("model", "")).strip()
            model_revision = str(entry.get("model_revision", "")).strip()
            observed_models.append(model_name)
            spec = next((candidate for candidate in CANONICAL_SUITE_MODELS if candidate.name == model_name), None)
            if spec is None:
                issues.append(f"summary export identity model_roster[{index}] names a non-canonical model: {model_name}")
                continue
            if model_revision != spec.revision:
                issues.append(
                    f"summary export identity model_roster[{index}] revision mismatch for {model_name}: "
                    f"expected {spec.revision}, observed {model_revision or '<missing>'}"
                )
        if observed_models != expected_models:
            issues.append(
                "summary export identity must record the canonical five-model roster in release order: "
                f"expected {expected_models}, observed {observed_models}"
            )

    source_modes = payload.get("assembly_source_execution_modes", [])
    if not isinstance(source_modes, list) or not source_modes:
        issues.append("summary export identity must record non-empty assembly_source_execution_modes")
    else:
        normalized_modes = sorted({str(mode).strip() for mode in source_modes if str(mode).strip()})
        if normalized_modes != ["single_host_canonical"]:
            issues.append(
                "summary export identity must be backed only by single_host_canonical source indexes; "
                f"observed {normalized_modes}"
            )
    if int(payload.get("assembly_source_index_count", 0) or 0) != 1:
        issues.append(
            "summary export identity must record assembly_source_index_count=1 for the formal one-shot release path"
        )

    recorded_hashes = payload.get("required_table_hashes", {})
    if not isinstance(recorded_hashes, dict):
        issues.append("summary export identity must record required_table_hashes")
    else:
        for table_name in REQUIRED_SUMMARY_EXPORT_TABLES:
            recorded_hash = str(recorded_hashes.get(table_name, "")).strip().lower()
            table_path = bundle / "results" / "tables" / "suite_all_models_methods" / table_name
            if not recorded_hash:
                issues.append(f"summary export identity is missing required_table_hashes[{table_name}]")
                continue
            if not _is_sha256_hexdigest(recorded_hash):
                issues.append(f"summary export identity {table_name} hash must be a 64-hex sha256")
                continue
            if not table_path.exists():
                issues.append(f"summary export identity points at a missing summary table: {table_name}")
                continue
            actual_hash = _sha256(table_path)
            if actual_hash != recorded_hash:
                issues.append(f"summary export identity hash mismatch for {table_name}")

    figure_stems = payload.get("figure_stems", [])
    if not isinstance(figure_stems, list):
        issues.append("summary export identity must record figure_stems")
    else:
        observed_figure_stems = sorted({str(stem).strip() for stem in figure_stems if str(stem).strip()})
        if observed_figure_stems != sorted(REQUIRED_SUMMARY_FIGURE_STEMS):
            issues.append(
                "summary export identity must record the narrowed publication-facing figure roster "
                f"{list(REQUIRED_SUMMARY_FIGURE_STEMS)}; observed {observed_figure_stems}"
            )
    recorded_figure_hashes = payload.get("required_figure_hashes", {})
    if not isinstance(recorded_figure_hashes, dict):
        issues.append("summary export identity must record required_figure_hashes")
    else:
        for figure_name in REQUIRED_SUMMARY_FIGURE_FILES:
            recorded_hash = str(recorded_figure_hashes.get(figure_name, "")).strip().lower()
            figure_path = bundle / "results" / "figures" / "suite_all_models_methods" / figure_name
            if not recorded_hash:
                issues.append(f"summary export identity is missing required_figure_hashes[{figure_name}]")
                continue
            if not _is_sha256_hexdigest(recorded_hash):
                issues.append(f"summary export identity {figure_name} hash must be a 64-hex sha256")
                continue
            if not figure_path.exists():
                issues.append(f"summary export identity points at a missing summary figure: {figure_name}")
                continue
            actual_hash = _sha256(figure_path)
            if actual_hash != recorded_hash:
                issues.append(f"summary export identity hash mismatch for {figure_name}")

    runtime_json = bundle / "results" / "environment" / "runtime_environment.json"
    try:
        runtime_payload = _load_json(runtime_json)
    except Exception:
        runtime_payload = {}
    execution = runtime_payload.get("execution", {}) if isinstance(runtime_payload, dict) else {}
    if isinstance(execution, dict):
        if str(payload.get("execution_mode", "")).strip() != str(execution.get("execution_mode", "")).strip():
            issues.append("summary export identity execution_mode must match runtime_environment.json")
        if str(payload.get("code_snapshot_digest", "")).strip() != str(execution.get("code_snapshot_digest", "")).strip():
            issues.append("summary export identity code_snapshot_digest must match runtime_environment.json")
        if str(payload.get("execution_environment_fingerprint", "")).strip() != str(
            execution.get("execution_environment_fingerprint", "")
        ).strip():
            issues.append("summary export identity execution_environment_fingerprint must match runtime_environment.json")

    method_summary_path = bundle / "results" / "tables" / "suite_all_models_methods" / "method_summary.json"
    try:
        method_summary_rows = json.loads(method_summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(f"unable to parse method_summary.json while validating summary export identity: {exc}")
    else:
        if not isinstance(method_summary_rows, list) or not method_summary_rows:
            issues.append("method_summary.json must be a non-empty row array in the release bundle")
        else:
            summary_versions = {
                str(row.get("score_version", "")).strip()
                for row in method_summary_rows
                if isinstance(row, dict) and str(row.get("score_version", "")).strip()
            }
            if len(summary_versions) != 1 or score_version not in summary_versions:
                issues.append("summary export identity score_version must match method_summary.json")

    method_master_path = (
        bundle
        / "results"
        / "tables"
        / "suite_all_models_methods"
        / "suite_all_models_methods_method_master_leaderboard.json"
    )
    try:
        method_master_rows = json.loads(method_master_path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(
            "unable to parse suite_all_models_methods_method_master_leaderboard.json while validating summary export identity: "
            f"{exc}"
        )
    else:
        if not isinstance(method_master_rows, list) or not method_master_rows:
            issues.append(
                "suite_all_models_methods_method_master_leaderboard.json must be a non-empty row array in the release bundle"
            )
        else:
            master_versions = {
                str(row.get("score_version", "")).strip()
                for row in method_master_rows
                if isinstance(row, dict) and str(row.get("score_version", "")).strip()
            }
            if len(master_versions) != 1 or score_version not in master_versions:
                issues.append(
                    "summary export identity score_version must match suite_all_models_methods_method_master_leaderboard.json"
                )
    return issues


def _looks_like_local_checkout_path(value: str) -> bool:
    candidate = str(value).strip()
    if not candidate:
        return False
    if ".coordination/" in candidate or "\\.coordination\\" in candidate:
        return True
    if candidate.startswith(("/", "\\")):
        return True
    return len(candidate) > 2 and candidate[1] == ":" and candidate[2] in {"\\", "/"}


def _normalize_source_relative(value: str) -> str | None:
    stripped = str(value).strip()
    if stripped == ".":
        return "."
    return release_bundle_contract.normalize_bundle_relative_path(
        stripped,
        forbid_hidden_components=True,
        allow_hidden_leaf=True,
    )


def _live_vendored_checkout_manifest(vendored_root: str) -> tuple[set[str], dict[str, str], list[str]]:
    issues: list[str] = []
    vendored_prefix = release_bundle_contract.vendored_bundle_prefix(vendored_root)
    if vendored_prefix is None:
        return set(), {}, [f"vendored checkout root is not bundle-safe: {vendored_root}"]
    repo_root = ROOT / Path(vendored_prefix)
    symlink_component = release_bundle_contract.first_symlink_component(ROOT, repo_root)
    if symlink_component is not None:
        relative_component = symlink_component.relative_to(ROOT).as_posix()
        return set(), {}, [f"live vendored checkout must not use symlinked path components: {relative_component}"]
    if not repo_root.exists():
        return set(), {}, [f"live vendored checkout is missing: {vendored_prefix}"]
    resolved_repo_root = repo_root.resolve()
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        return set(), {}, [f"unable to enumerate live vendored checkout {vendored_prefix}: {stderr or 'git ls-files failed'}"]

    tracked_files: set[str] = set()
    tracked_digests: dict[str, str] = {}
    for raw_entry in completed.stdout.decode("utf-8", errors="surrogateescape").split("\0"):
        entry = raw_entry.strip().replace("\\", "/")
        if not entry:
            continue
        normalized = release_bundle_contract.normalize_bundle_relative_path(
            entry,
            forbid_hidden_components=True,
            allow_hidden_leaf=True,
        )
        if normalized is None:
            issues.append(f"live vendored checkout contains a non-sanitizable tracked path: {entry}")
            continue
        if release_bundle_contract.is_policy_excluded(normalized) or any(
            release_bundle_contract.path_matches_prefix(normalized, prefix)
            for prefix in release_bundle_contract.FORBIDDEN_BUNDLE_PREFIXES
        ):
            issues.append(f"live vendored checkout contains a forbidden tracked path: {normalized}")
            continue
        if release_bundle_contract.is_allowed_bundle_output_root(normalized):
            issues.append(f"live vendored checkout contains a forbidden bundle-output residue path: {normalized}")
            continue
        artifact_issue = release_bundle_contract.forbidden_bundle_artifact_issue(normalized)
        if artifact_issue is not None:
            issues.append(f"live vendored checkout contains a machine-specific tracked artifact: {artifact_issue}")
            continue
        source = repo_root / Path(normalized)
        if not source.exists():
            issues.append(f"live vendored checkout is missing tracked file: {normalized}")
            continue
        if source.is_symlink():
            issues.append(f"live vendored checkout contains a symlinked tracked file: {normalized}")
            continue
        resolved_source = source.resolve()
        try:
            resolved_source.relative_to(resolved_repo_root)
        except ValueError:
            issues.append(f"live vendored checkout contains a tracked path that escapes the checkout root: {normalized}")
            continue
        if not source.is_file():
            issues.append(f"live vendored checkout contains a tracked entry that is not a regular file: {normalized}")
            continue
        bundle_relative = f"{vendored_prefix}/{normalized}".replace("\\", "/")
        tracked_files.add(bundle_relative)
        tracked_digests[bundle_relative] = _sha256(source)
    if not tracked_files:
        issues.append(f"live vendored checkout has no tracked files: {vendored_prefix}")
    return tracked_files, tracked_digests, issues


def _vendored_nested_policy_issue(entry: str, bundle_root: str | None) -> str | None:
    if not bundle_root:
        return None
    try:
        nested_relative = PurePosixPath(entry).relative_to(PurePosixPath(bundle_root)).as_posix()
    except Exception:
        return None
    if release_bundle_contract.is_policy_excluded(nested_relative):
        return nested_relative
    if release_bundle_contract.is_allowed_bundle_output_root(nested_relative):
        return nested_relative
    for prefix in release_bundle_contract.FORBIDDEN_BUNDLE_PREFIXES:
        if release_bundle_contract.path_matches_prefix(nested_relative, prefix):
            return nested_relative
    artifact_issue = release_bundle_contract.forbidden_bundle_artifact_issue(nested_relative)
    if artifact_issue is not None:
        return nested_relative
    return None


def _provenance_issues(name: str, payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    origin = str(payload.get("origin", "")).strip()
    source_path = str(payload.get("source_path", "")).strip()
    vendored_path = str(payload.get("vendored_path", "")).strip()
    checkout_valid_value = payload.get("checkout_valid", False)
    checkout_valid = checkout_valid_value if isinstance(checkout_valid_value, bool) else False
    bundle_eligible_value = payload.get("bundle_eligible", False)
    bundle_eligible = bundle_eligible_value if isinstance(bundle_eligible_value, bool) else False
    verification_issues = [str(item) for item in payload.get("verification_issues", [])]
    pinned_commit = str(payload.get("pinned_commit", "")).strip()
    upstream_commit = str(payload.get("upstream_commit", "")).strip()
    license_status = str(payload.get("license_status", "")).strip()
    redistributable = payload.get("redistributable", None)
    unexpected_keys = sorted(set(payload) - ALLOWED_BASELINE_PROVENANCE_KEYS)
    if unexpected_keys:
        issues.append(
            f"{name}: unexpected provenance keys are not allowed in a release bundle: {', '.join(unexpected_keys)}"
        )

    for key, raw_value in payload.items():
        if not isinstance(raw_value, str):
            continue
        value = raw_value.strip()
        if not value:
            continue
        if key in {"source_path", "vendored_path", "external_path", "selected_checkout_path"}:
            if ".coordination/" in value or "\\.coordination\\" in value:
                issues.append(f"{name}: {key} leaks internal checkout path: {value}")
            continue
        if key.endswith(("_path", "_root")) and _looks_like_local_checkout_path(value):
            issues.append(f"{name}: {key} leaks local checkout path: {value}")

    if not isinstance(checkout_valid_value, bool):
        issues.append(f"{name}: checkout_valid must be a boolean")
    if not isinstance(bundle_eligible_value, bool):
        issues.append(f"{name}: bundle_eligible must be a boolean")
    if origin in {"vendored_snapshot", "external_checkout"} and not checkout_valid:
        issues.append(f"{name}: {origin} selected without a valid checkout")
    if origin in {"vendored_unverified", "external_unverified"}:
        issues.append(f"{name}: unverified provenance origin '{origin}' is not allowed in a release bundle")
    if origin == "vendored_snapshot" and not bundle_eligible:
        issues.append(f"{name}: vendored snapshot selected but bundle_eligible is false")
    if origin == "missing":
        issues.append(f"{name}: baseline provenance is missing from the staged bundle")
    if origin == "external_checkout" and not source_path:
        issues.append(f"{name}: external checkout selected without sanitized source_path")
    if origin == "vendored_snapshot" and not source_path:
        issues.append(f"{name}: vendored snapshot selected without publishable source_path")
    if origin == "missing" and verification_issues:
        issues.extend(f"{name}: {item}" for item in verification_issues)
    if origin not in {"missing", "vendored_snapshot", "external_checkout", "vendored_unverified", "external_unverified"}:
        issues.append(f"{name}: unexpected provenance origin '{origin}'")
    if str(payload.get("repo_url", "")).strip() == "":
        issues.append(f"{name}: missing repo_url in provenance payload")
    if origin != "missing" and not pinned_commit:
        issues.append(f"{name}: missing pinned_commit in provenance payload")
    if origin != "missing" and not upstream_commit:
        issues.append(f"{name}: missing upstream_commit in provenance payload")
    if origin != "missing" and not license_status:
        issues.append(f"{name}: missing license_status in provenance payload")
    if origin != "missing" and not isinstance(redistributable, bool):
        issues.append(f"{name}: missing boolean redistributable flag in provenance payload")
    if origin == "vendored_snapshot" and license_status.lower() != "redistributable":
        issues.append(f"{name}: vendored snapshot selected without redistributable license_status")
    if origin == "vendored_snapshot" and redistributable is not True:
        issues.append(f"{name}: vendored snapshot selected without redistributable=true")
    vendored_files = payload.get("vendored_files", [])
    vendored_file_digests = payload.get("vendored_file_digests", {})
    if origin == "vendored_snapshot":
        vendored_root = release_bundle_contract.vendored_bundle_prefix(vendored_path) if vendored_path else None
        if not isinstance(vendored_files, list) or not vendored_files:
            issues.append(f"{name}: vendored snapshot is missing a non-empty vendored_files roster")
        else:
            normalized_files: list[str] = []
            for raw_entry in vendored_files:
                if not isinstance(raw_entry, str):
                    issues.append(f"{name}: vendored_files entries must be strings")
                    continue
                normalized_entry = release_bundle_contract.vendored_bundle_file(raw_entry)
                if normalized_entry is None:
                    issues.append(
                        f"{name}: vendored_files entry must stay under third_party/ without hidden path components: {raw_entry!r}"
                    )
                    continue
                if vendored_root and not release_bundle_contract.path_matches_prefix(normalized_entry, vendored_root):
                    issues.append(
                        f"{name}: vendored_files entry must stay inside vendored_path {vendored_root}: {normalized_entry}"
                    )
                    continue
                forbidden_nested = _vendored_nested_policy_issue(normalized_entry, vendored_root)
                if forbidden_nested is not None:
                    issues.append(
                        f"{name}: vendored_files entry must not include forbidden nested bundle path: {forbidden_nested}"
                    )
                    continue
                normalized_files.append(normalized_entry)
            if len(set(normalized_files)) != len(normalized_files):
                issues.append(f"{name}: vendored_files contains duplicate staged paths")
        if not isinstance(vendored_file_digests, dict) or not vendored_file_digests:
            issues.append(f"{name}: vendored snapshot is missing a non-empty vendored_file_digests map")
        else:
            normalized_digest_paths: set[str] = set()
            for raw_path, raw_digest in vendored_file_digests.items():
                if not isinstance(raw_path, str):
                    issues.append(f"{name}: vendored_file_digests keys must be strings")
                    continue
                normalized_path = release_bundle_contract.vendored_bundle_file(raw_path)
                if normalized_path is None:
                    issues.append(
                        f"{name}: vendored_file_digests path must stay under third_party/ without hidden path components: {raw_path!r}"
                    )
                    continue
                if vendored_root and not release_bundle_contract.path_matches_prefix(normalized_path, vendored_root):
                    issues.append(
                        f"{name}: vendored_file_digests path must stay inside vendored_path {vendored_root}: {normalized_path}"
                    )
                    continue
                forbidden_nested = _vendored_nested_policy_issue(normalized_path, vendored_root)
                if forbidden_nested is not None:
                    issues.append(
                        f"{name}: vendored_file_digests path must not include forbidden nested bundle path: {forbidden_nested}"
                    )
                    continue
                if not _is_sha256_hexdigest(str(raw_digest)):
                    issues.append(
                        f"{name}: vendored_file_digests entry for {normalized_path} must be a 64-hex sha256"
                    )
                    continue
                normalized_digest_paths.add(normalized_path)
            if isinstance(vendored_files, list):
                normalized_file_paths = {
                    release_bundle_contract.vendored_bundle_file(raw_entry)
                    for raw_entry in vendored_files
                    if isinstance(raw_entry, str)
                }
                normalized_file_paths.discard(None)
                if normalized_digest_paths != normalized_file_paths:
                    issues.append(f"{name}: vendored_file_digests keys must exactly match vendored_files")
    return issues


def _provenance_bundle_issues(
    name: str,
    payload: dict[str, Any],
    bundle: Path,
    actual_files: set[str],
    *,
    require_live_vendored_checkout: bool,
) -> list[str]:
    issues: list[str] = []
    origin = str(payload.get("origin", "")).strip()
    source_path = str(payload.get("source_path", "")).strip()
    vendored_path = str(payload.get("vendored_path", "")).strip()
    external_path = str(payload.get("external_path", "")).strip()
    selected_checkout_path = str(payload.get("selected_checkout_path", "")).strip()

    source_norm = _normalize_bundle_relative_path(source_path)
    vendored_norm = release_bundle_contract.vendored_bundle_prefix(vendored_path) if vendored_path else None
    external_norm = release_bundle_contract.external_bundle_prefix(external_path) if external_path else None
    selected_norm = _normalize_bundle_relative_path(selected_checkout_path)
    vendored_files = payload.get("vendored_files", [])
    vendored_file_digests = payload.get("vendored_file_digests", {})

    def _vendored_nested_policy_issue(entry: str, bundle_root: str | None) -> str | None:
        if not bundle_root:
            return None
        try:
            nested_relative = PurePosixPath(entry).relative_to(PurePosixPath(bundle_root)).as_posix()
        except Exception:
            return None
        if release_bundle_contract.is_policy_excluded(nested_relative):
            return nested_relative
        if release_bundle_contract.is_allowed_bundle_output_root(nested_relative):
            return nested_relative
        for prefix in release_bundle_contract.FORBIDDEN_BUNDLE_PREFIXES:
            if release_bundle_contract.path_matches_prefix(nested_relative, prefix):
                return nested_relative
        artifact_issue = release_bundle_contract.forbidden_bundle_artifact_issue(nested_relative)
        if artifact_issue is not None:
            return nested_relative
        return None

    def _require_sanitized_path(key: str, raw_value: str, normalized_value: str | None) -> None:
        if normalized_value is None:
            issues.append(f"{name}: {key} must be a sanitized relative path, found '{raw_value}'")

    if vendored_path and vendored_norm is None:
        issues.append(f"{name}: vendored_path must stay under third_party/, found '{vendored_path}'")
    if external_path and external_norm is None:
        issues.append(f"{name}: external_path must stay under external_checkout/, found '{external_path}'")

    if origin == "vendored_snapshot":
        source_norm = release_bundle_contract.vendored_bundle_prefix(source_path) if source_path else None
        selected_norm = release_bundle_contract.vendored_bundle_prefix(selected_checkout_path) if selected_checkout_path else None
        _require_sanitized_path("source_path", source_path, source_norm)
        _require_sanitized_path("vendored_path", vendored_path, vendored_norm)
        _require_sanitized_path("selected_checkout_path", selected_checkout_path, selected_norm)
        if source_norm and vendored_norm and source_norm != vendored_norm:
            issues.append(f"{name}: vendored snapshot source_path and vendored_path must match")
        if source_norm and selected_norm and source_norm != selected_norm:
            issues.append(f"{name}: vendored snapshot selected_checkout_path must match source_path")
        bundle_root = vendored_norm or source_norm or selected_norm
        if bundle_root and not _bundle_contains_path(actual_files, bundle_root):
            issues.append(f"{name}: vendored snapshot path '{bundle_root}' is not present in the staged bundle")
        expected_vendored_files: set[str] = set()
        expected_vendored_digests: dict[str, str] = {}
        if isinstance(vendored_file_digests, dict):
            for raw_entry, raw_digest in vendored_file_digests.items():
                if not isinstance(raw_entry, str):
                    continue
                normalized_entry = release_bundle_contract.vendored_bundle_file(raw_entry)
                if normalized_entry is not None and _is_sha256_hexdigest(str(raw_digest)):
                    expected_vendored_files.add(normalized_entry)
                    expected_vendored_digests[normalized_entry] = str(raw_digest).strip().lower()
        elif isinstance(vendored_files, list):
            for raw_entry in vendored_files:
                if not isinstance(raw_entry, str):
                    continue
                normalized_entry = release_bundle_contract.vendored_bundle_file(raw_entry)
                if normalized_entry is not None:
                    expected_vendored_files.add(normalized_entry)
        if bundle_root and expected_vendored_files:
            actual_vendored_files = {
                entry
                for entry in actual_files
                if release_bundle_contract.path_matches_prefix(entry, bundle_root)
            }
            live_vendored_files: set[str] = set()
            live_vendored_digests: dict[str, str] = {}
            if require_live_vendored_checkout:
                live_vendored_files, live_vendored_digests, live_vendored_issues = _live_vendored_checkout_manifest(
                    bundle_root
                )
                issues.extend(f"{name}: {issue}" for issue in live_vendored_issues)
                if live_vendored_files and expected_vendored_files != live_vendored_files:
                    issues.append(f"{name}: vendored snapshot roster does not match the live vendored checkout")
            for entry in sorted(expected_vendored_files):
                forbidden_nested = _vendored_nested_policy_issue(entry, bundle_root)
                if forbidden_nested is not None:
                    issues.append(
                        f"{name}: vendored snapshot roster includes forbidden nested bundle path: {forbidden_nested}"
                    )
            for entry in sorted(actual_vendored_files):
                forbidden_nested = _vendored_nested_policy_issue(entry, bundle_root)
                if forbidden_nested is not None:
                    issues.append(
                        f"{name}: vendored snapshot staged content includes forbidden nested bundle path: {forbidden_nested}"
                    )
            missing_files = sorted(expected_vendored_files - actual_vendored_files)
            unexpected_files = sorted(actual_vendored_files - expected_vendored_files)
            issues.extend(
                f"{name}: vendored snapshot is missing bundled file: {entry}"
                for entry in missing_files
            )
            issues.extend(
                f"{name}: vendored snapshot includes unexpected bundled file: {entry}"
                for entry in unexpected_files
            )
            for relative_path, expected_digest in expected_vendored_digests.items():
                if relative_path not in actual_vendored_files:
                    continue
                observed_digest = _sha256(bundle / relative_path)
                if observed_digest != expected_digest:
                    issues.append(
                        f"{name}: vendored snapshot digest mismatch for {relative_path}: expected {expected_digest}, observed {observed_digest}"
                    )
                live_digest = live_vendored_digests.get(relative_path)
                if require_live_vendored_checkout and live_digest is not None and expected_digest != live_digest:
                    issues.append(
                        f"{name}: vendored snapshot digest map does not match the live vendored checkout for {relative_path}"
                    )

    if origin == "external_checkout":
        source_norm = release_bundle_contract.external_bundle_prefix(source_path) if source_path else None
        selected_norm = release_bundle_contract.external_bundle_prefix(selected_checkout_path) if selected_checkout_path else None
        _require_sanitized_path("source_path", source_path, source_norm)
        _require_sanitized_path("external_path", external_path, external_norm)
        _require_sanitized_path("selected_checkout_path", selected_checkout_path, selected_norm)
        if source_norm and external_norm and source_norm != external_norm:
            issues.append(f"{name}: external checkout source_path and external_path must match")
        if source_norm and selected_norm and source_norm != selected_norm:
            issues.append(f"{name}: external checkout selected_checkout_path must match source_path")

    return issues


def _staged_upstream_manifest_issues(
    bundle: Path,
    actual_files: set[str],
    baseline_payload: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    parsed_manifests: dict[str, dict[str, Any]] = {}
    manifest_paths = sorted(
        entry
        for entry in actual_files
        if release_bundle_contract.path_matches_prefix(entry, "third_party")
        and entry.endswith(".UPSTREAM.json")
    )
    for relative_path in manifest_paths:
        manifest_path = bundle / relative_path
        try:
            payload = _load_json(manifest_path)
        except Exception as exc:
            issues.append(f"{relative_path}: unable to parse copied upstream manifest: {exc}")
            continue
        if not isinstance(payload, dict):
            issues.append(f"{relative_path}: copied upstream manifest must be a JSON object")
            continue
        parsed_manifests[relative_path] = payload
        extras = sorted(set(payload) - ALLOWED_UPSTREAM_MANIFEST_KEYS)
        if extras:
            issues.append(
                f"{relative_path}: copied upstream manifest contains unexpected keys: {', '.join(extras)}"
            )
        if "schema_version" not in payload:
            issues.append(f"{relative_path}: copied upstream manifest is missing schema_version")
        else:
            schema_version = payload.get("schema_version")
            if not isinstance(schema_version, int) or schema_version != 1:
                issues.append(f"{relative_path}: copied upstream manifest schema_version must be integer 1")
        if payload.get("bundle_sanitized") is not True:
            issues.append(f"{relative_path}: copied upstream manifest must set bundle_sanitized=true")
        for key in ("repo_url", "pinned_commit", "license_status"):
            if not str(payload.get(key, "")).strip():
                issues.append(f"{relative_path}: copied upstream manifest is missing {key}")
        source_relative = str(payload.get("source_relative", "")).strip()
        if not source_relative:
            issues.append(f"{relative_path}: copied upstream manifest is missing source_relative")
        else:
            normalized_source_relative = _normalize_source_relative(source_relative)
            if normalized_source_relative is None:
                issues.append(
                    f"{relative_path}: copied upstream manifest source_relative must be a sanitized relative path or '.'"
                )
        checkout_root = str(payload.get("checkout_root", "")).strip()
        if not checkout_root:
            issues.append(f"{relative_path}: copied upstream manifest is missing checkout_root")
        elif release_bundle_contract.vendored_bundle_prefix(checkout_root) is None:
            issues.append(
                f"{relative_path}: copied upstream manifest checkout_root must stay under third_party/"
            )
        public_external_root = str(payload.get("public_external_root", "")).strip()
        external_root = str(payload.get("external_root", "")).strip()
        local_external_root = str(payload.get("local_external_root", "")).strip()
        if local_external_root:
            issues.append(
                f"{relative_path}: copied upstream manifest must not expose local_external_root"
            )
        normalized_public_external_root = None
        if not public_external_root:
            issues.append(f"{relative_path}: copied upstream manifest is missing public_external_root")
        else:
            normalized_public_external_root = release_bundle_contract.external_bundle_prefix(
                public_external_root
            )
            if normalized_public_external_root is None:
                issues.append(
                    f"{relative_path}: copied upstream manifest public_external_root must stay under external_checkout/"
                )
        normalized_external_root = None
        if not external_root:
            issues.append(f"{relative_path}: copied upstream manifest is missing external_root")
        else:
            normalized_external_root = release_bundle_contract.external_bundle_prefix(external_root)
            if normalized_external_root is None:
                issues.append(
                    f"{relative_path}: copied upstream manifest external_root must stay under external_checkout/"
                )
        if (
            normalized_public_external_root is not None
            and normalized_external_root is not None
            and normalized_public_external_root != normalized_external_root
        ):
            issues.append(
                f"{relative_path}: copied upstream manifest external_root must match public_external_root"
            )
    for baseline_name, manifest_relative in BASELINE_UPSTREAM_MANIFESTS.items():
        baseline_entry = baseline_payload.get(baseline_name)
        if not isinstance(baseline_entry, dict):
            continue
        manifest_payload = parsed_manifests.get(manifest_relative)
        if manifest_payload is None:
            issues.append(
                f"{baseline_name}: copied upstream manifest missing from the staged bundle: {manifest_relative}"
            )
            continue
        live_manifest_path = ROOT / manifest_relative
        if live_manifest_path.exists():
            try:
                live_manifest_payload = _load_json(live_manifest_path)
            except Exception as exc:
                issues.append(f"{manifest_relative}: unable to parse live upstream manifest for comparison: {exc}")
            else:
                live_source_relative = str(live_manifest_payload.get("source_relative", "")).strip()
                manifest_source_relative = str(manifest_payload.get("source_relative", "")).strip()
                if live_source_relative and manifest_source_relative != live_source_relative:
                    issues.append(
                        f"{baseline_name}: copied upstream manifest source_relative does not match the tracked upstream manifest"
                    )
        for key in ("repo_url", "pinned_commit", "license_status"):
            baseline_value = str(baseline_entry.get(key, "")).strip()
            manifest_value = str(manifest_payload.get(key, "")).strip()
            if baseline_value and manifest_value != baseline_value:
                issues.append(
                    f"{baseline_name}: copied upstream manifest {key} does not match baseline provenance"
                )
        manifest_checkout_root = str(manifest_payload.get("checkout_root", "")).strip()
        manifest_external_root = str(
            manifest_payload.get("public_external_root", manifest_payload.get("external_root", ""))
        ).strip()
        baseline_vendored_path = str(baseline_entry.get("vendored_path", "")).strip()
        baseline_external_path = str(baseline_entry.get("external_path", "")).strip()
        if baseline_vendored_path and manifest_checkout_root and baseline_vendored_path != manifest_checkout_root:
            issues.append(
                f"{baseline_name}: copied upstream manifest checkout_root does not match baseline vendored_path"
            )
        if baseline_external_path and manifest_external_root and baseline_external_path != manifest_external_root:
            issues.append(
                f"{baseline_name}: copied upstream manifest external root does not match baseline external_path"
            )
        origin = str(baseline_entry.get("origin", "")).strip()
        source_path = str(baseline_entry.get("source_path", "")).strip()
        if origin == "vendored_snapshot" and manifest_checkout_root and source_path != manifest_checkout_root:
            issues.append(
                f"{baseline_name}: vendored snapshot source_path does not match copied upstream manifest checkout_root"
            )
        if origin == "external_checkout" and manifest_external_root and source_path != manifest_external_root:
            issues.append(
                f"{baseline_name}: external checkout source_path does not match copied upstream manifest external root"
            )
    return issues


def validate_bundle(bundle: Path, *, require_live_vendored_checkout: bool = False) -> dict[str, Any]:
    bundle = bundle.resolve()
    issues: list[str] = []
    bundle_name_findings = validate_setup.legacy_project_findings_for_text(bundle.name, context="bundle root name")
    issues.extend(bundle_name_findings)

    if not bundle.exists():
        issues.append(f"missing bundle root: {bundle}")
    baseline_path = bundle / "baseline_provenance.json"
    manifest_path = bundle / "bundle.manifest.json"
    checksums_path = bundle / "SHA256SUMS.txt"
    if not baseline_path.exists():
        issues.append(f"missing bundle artifact: {baseline_path}")
    if not manifest_path.exists():
        issues.append(f"missing bundle artifact: {manifest_path}")
    if not checksums_path.exists():
        issues.append(f"missing bundle artifact: {checksums_path}")

    anonymity_findings: list[str] = []
    legacy_name_findings: list[str] = list(bundle_name_findings)
    provenance_report: dict[str, Any] = {}
    if not issues:
        baseline_payload = _load_json(baseline_path)
        manifest_payload = _load_json(manifest_path)
        bundle_files, symlink_entries = _bundle_files(bundle)
        actual_files = {file.relative_to(bundle).as_posix() for file in bundle_files}
        issues.extend(
            f"bundle contains symlinked entry: {entry.relative_to(bundle).as_posix()}"
            for entry in symlink_entries
        )
        try:
            tracked_publishable_files = _publishable_tracked_files()
        except Exception as exc:
            tracked_publishable_files = set()
            issues.append(f"unable to resolve tracked publishable surface: {exc}")
        publishable_files = set(tracked_publishable_files) | ALLOWED_GENERATED_BUNDLE_FILES
        observed_keys = set(baseline_payload)
        if observed_keys != set(REQUIRED_BASELINES):
            missing = sorted(set(REQUIRED_BASELINES) - observed_keys)
            extras = sorted(observed_keys - set(REQUIRED_BASELINES))
            if missing:
                issues.append(f"baseline_provenance.json missing required entries: {missing}")
            if extras:
                issues.append(f"baseline_provenance.json contains unexpected entries: {extras}")
        manifest_provenance = manifest_payload.get("baseline_provenance_map", {})
        if manifest_provenance != baseline_payload:
            issues.append("bundle.manifest.json baseline_provenance_map does not exactly match baseline_provenance.json")
        for required_key in REQUIRED_BASELINES:
            if required_key not in baseline_payload:
                continue
            payload = baseline_payload[required_key]
            if not isinstance(payload, dict):
                issues.append(f"{required_key}: provenance entry must be a JSON object")
                continue
            issues.extend(_provenance_issues(required_key, payload))
            issues.extend(
                _provenance_bundle_issues(
                    required_key,
                    payload,
                    bundle,
                    actual_files,
                    require_live_vendored_checkout=require_live_vendored_checkout,
                )
            )
            if str(payload.get("origin", "")).strip() == "vendored_snapshot":
                vendored_file_digests = payload.get("vendored_file_digests", {})
                if isinstance(vendored_file_digests, dict):
                    for raw_entry in vendored_file_digests:
                        if not isinstance(raw_entry, str):
                            continue
                        normalized_entry = release_bundle_contract.vendored_bundle_file(raw_entry)
                        if normalized_entry is not None:
                            publishable_files.add(normalized_entry)
            provenance_report[required_key] = {
                "origin": payload.get("origin"),
                "checkout_valid": payload.get("checkout_valid"),
                "bundle_eligible": payload.get("bundle_eligible"),
                "verification_issues": payload.get("verification_issues", []),
            }
        issues.extend(_staged_upstream_manifest_issues(bundle, actual_files, baseline_payload))
        included = set(manifest_payload.get("included", []))
        try:
            expected_bundle_root = bundle.relative_to(ROOT).as_posix()
        except ValueError:
            expected_bundle_root = bundle.name
        if str(manifest_payload.get("bundle_root", "")).strip() != expected_bundle_root:
            issues.append(
                f"bundle.manifest.json bundle_root mismatch: expected {expected_bundle_root}, "
                f"found {manifest_payload.get('bundle_root')!r}"
            )
        included_count = manifest_payload.get("included_count", None)
        if included_count != len(included):
            issues.append(
                f"bundle.manifest.json included_count mismatch: expected {len(included)}, found {included_count!r}"
            )
        file_count = manifest_payload.get("file_count", None)
        if file_count != len(actual_files):
            issues.append(
                f"bundle.manifest.json file_count mismatch: expected {len(actual_files)}, found {file_count!r}"
            )
        for required_path in REQUIRED_BUNDLE_FILES:
            if required_path not in actual_files:
                issues.append(f"bundle is missing required file: {required_path}")
        missing_publishable = sorted(tracked_publishable_files - actual_files)
        issues.extend(f"bundle is missing tracked publishable file: {entry}" for entry in missing_publishable)
        if all(
            required_path in actual_files
            for required_path in (
                "results/environment/runtime_environment.json",
                "results/environment/runtime_environment.md",
            )
        ):
            issues.extend(_environment_capture_issues(bundle))
            issues.extend(_summary_export_identity_issues(bundle))
        for required_path in ("baseline_provenance.json", "bundle.manifest.json"):
            if required_path not in included:
                issues.append(f"bundle.manifest.json missing included entry for {required_path}")
        if set(manifest_payload.get("baseline_provenance_map", {})) != set(REQUIRED_BASELINES):
            issues.append("bundle.manifest.json baseline_provenance_map does not match the required four-baseline roster")
        missing_from_manifest = sorted(actual_files - included)
        missing_from_bundle = sorted(included - actual_files)
        issues.extend(f"bundle.manifest.json is missing actual file: {entry}" for entry in missing_from_manifest)
        issues.extend(f"bundle.manifest.json references missing file: {entry}" for entry in missing_from_bundle)
        unexpected_payload = sorted(actual_files - publishable_files)
        issues.extend(f"bundle contains unpublished file: {entry}" for entry in unexpected_payload)
        checksums = _load_checksums(checksums_path)
        checksum_files = set(checksums)
        issues.extend(f"SHA256SUMS.txt is missing actual file: {entry}" for entry in sorted(actual_files - checksum_files))
        issues.extend(f"SHA256SUMS.txt references missing file: {entry}" for entry in sorted(checksum_files - actual_files))
        if checksums.get("SHA256SUMS.txt") != "0" * 64:
            issues.append("SHA256SUMS.txt must carry the zero-digest self-check placeholder for SHA256SUMS.txt")
        for relative_path, expected_digest in checksums.items():
            if relative_path == "SHA256SUMS.txt":
                continue
            file_path = bundle / relative_path
            if not file_path.exists():
                continue
            observed_digest = _sha256(file_path)
            if observed_digest != expected_digest:
                issues.append(
                    f"SHA256SUMS.txt digest mismatch for {relative_path}: expected {expected_digest}, observed {observed_digest}"
                )
        forbidden_entries = sorted(
            {
                file.relative_to(bundle).as_posix()
                for file in bundle_files
                if any(
                    release_bundle_contract.path_matches_prefix(
                        file.relative_to(bundle).as_posix(),
                        prefix,
                    )
                    for prefix in FORBIDDEN_BUNDLE_PREFIXES
                )
            }
        )
        issues.extend(f"bundle contains forbidden path: {entry}" for entry in forbidden_entries)
        anonymity_findings = validate_setup.scan_for_identity_markers(
            bundle_files,
            labels=set(validate_setup.IDENTITY_PATTERNS),
        )
        issues.extend(anonymity_findings)
        legacy_name_findings = check_zero_legacy_name.scan_tree(bundle)
        issues.extend(legacy_name_findings)

    return {
        "bundle": str(bundle),
        "status": "failed" if issues else "passed",
        "issues": issues,
        "anonymity_findings": anonymity_findings,
        "legacy_name_findings": legacy_name_findings,
        "provenance": provenance_report,
    }


def main() -> int:
    args = parse_args()
    report = validate_bundle(args.bundle)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if report["issues"]:
        print("Bundle validation failed:")
        for issue in report["issues"]:
            print(f"- {issue}")
        return 1

    print("Bundle validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
