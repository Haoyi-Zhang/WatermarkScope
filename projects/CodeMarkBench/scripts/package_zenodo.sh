#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-$ROOT/results/release_bundle}"
PYTHON_BIN="${PYTHON_BIN:-}"
export PYTHONDONTWRITEBYTECODE=1

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT/.venv/bin/python"
  else
    echo "Missing Python interpreter. Set PYTHON_BIN or create $ROOT/.venv/bin/python." >&2
    exit 1
  fi
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Missing Python interpreter: $PYTHON_BIN" >&2
  exit 1
fi

"$PYTHON_BIN" - "$ROOT" "$OUT_DIR" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

root = Path(sys.argv[1]).resolve()
results_root = (root / "results").resolve()


def _resolve_safe_output_dir(raw_value: str) -> Path:
    results_anchor = root / "results"
    if release_bundle_contract.first_symlink_component(root, results_anchor) is not None:
        raise SystemExit(
            f"release bundle output root cannot use a symlinked results directory: {results_anchor}"
        )
    candidate = Path(raw_value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        candidate.relative_to(root)
    except ValueError:
        pass
    else:
        if release_bundle_contract.first_symlink_component(root, candidate) is not None:
            raise SystemExit(
                f"release bundle output root must not contain symlinked path components: {candidate}"
            )
    candidate = candidate.resolve()
    try:
        candidate.relative_to(results_root)
    except ValueError as exc:
        raise SystemExit(
            f"release bundle output root must stay under {results_root}"
        ) from exc
    bundle_relative = candidate.relative_to(root).as_posix()
    if not release_bundle_contract.is_allowed_bundle_output_root(bundle_relative):
        raise SystemExit(
            "release bundle output root must stay under an allowed staging subtree "
            f"(results/release_bundle*, results/test_release_bundle*, or results/tmp), not {bundle_relative}"
        )
    if candidate == results_root:
        raise SystemExit(
            f"release bundle output root must be a child of {results_root}, not the results root itself"
        )
    return candidate

scripts_dir = root / "scripts"
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from codemarkbench.baselines.stone_family.common import load_upstream_manifest, stone_family_checkout_metadata
import release_bundle_contract
import validate_release_bundle
import validate_setup
out = _resolve_safe_output_dir(sys.argv[2])
REQUIRED_TRACKED_PATHS = list(release_bundle_contract.REQUIRED_TRACKED_BUNDLE_FILES)

BASELINES = {
    "stone": "stone_runtime",
    "sweet": "sweet_runtime",
    "ewd": "ewd_runtime",
    "kgw": "kgw_runtime",
}

policy_exclusions = [root / Path(relative) for relative in release_bundle_contract.POLICY_EXCLUSIONS]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_available() -> bool:
    probe = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.returncode == 0


def _windows_git_dirty_entries() -> list[str] | None:
    if os.name == "nt":
        return None
    if not str(root).startswith("/mnt/"):
        return None
    if shutil.which("powershell.exe") is None or shutil.which("wslpath") is None:
        return None
    try:
        win_root = subprocess.run(
            ["wslpath", "-w", str(root)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return None
    if not win_root:
        return None
    command = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        f"git -C '{win_root}' status --porcelain"
    )
    probe = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return None
    return [line.strip() for line in (probe.stdout or "").splitlines() if line.strip()]


def _ensure_publishable_workspace() -> None:
    missing_required = [relative for relative in REQUIRED_TRACKED_PATHS if not (root / relative).exists()]
    if missing_required:
        raise SystemExit(
            "release bundle prerequisites missing from the working tree: "
            + ", ".join(missing_required)
        )
    legacy_scan_paths: list[Path] = []
    for relative in release_bundle_contract.BUNDLE_ALLOWED_PATHS:
        candidate = root / relative
        if candidate.is_file():
            legacy_scan_paths.append(candidate)
            continue
        if candidate.is_dir():
            legacy_scan_paths.extend(path for path in candidate.rglob("*") if path.is_file())
    legacy_findings = validate_setup.scan_for_legacy_project_markers(sorted(set(legacy_scan_paths)), root=root)
    if legacy_findings:
        preview = ", ".join(legacy_findings[:8])
        if len(legacy_findings) > 8:
            preview += ", ..."
        raise SystemExit(
            "refusing to stage a release bundle while legacy project naming remains in publishable files: "
            + preview
        )
    if not _git_available():
        return
    for relative in REQUIRED_TRACKED_PATHS:
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", relative],
            capture_output=True,
            text=True,
            check=False,
        )
        if tracked.returncode != 0:
            raise SystemExit(f"release bundle prerequisite must be tracked in git: {relative}")
    allow_dirty = str(os.environ.get("CODEMARKBENCH_ALLOW_DIRTY_BUNDLE", "")).strip().lower() in {"1", "true", "yes", "on"}
    if allow_dirty:
        return
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    dirty_entries = [line.strip() for line in (status.stdout or "").splitlines() if line.strip()]
    windows_entries = _windows_git_dirty_entries()
    if windows_entries is not None:
        dirty_entries = windows_entries
    if dirty_entries:
        preview = ", ".join(dirty_entries[:8])
        if len(dirty_entries) > 8:
            preview += ", ..."
        raise SystemExit(
            "refusing to stage a release bundle from a dirty git worktree; "
            "commit or stash the current changes first, or set CODEMARKBENCH_ALLOW_DIRTY_BUNDLE=1 for an explicit override. "
            f"Dirty entries: {preview}"
        )


def _ensure_real_environment_capture() -> None:
    runtime_environment_json = root / "results" / "environment" / "runtime_environment.json"
    runtime_environment_md = root / "results" / "environment" / "runtime_environment.md"
    if not runtime_environment_json.exists() or not runtime_environment_md.exists():
        raise SystemExit(
            "release bundle requires results/environment/runtime_environment.json and "
            "results/environment/runtime_environment.md to exist."
        )
    try:
        payload = json.loads(runtime_environment_json.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"unable to parse runtime environment capture at {runtime_environment_json}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{runtime_environment_json} must be a JSON object.")
    def _is_sha256(value: object) -> bool:
        text = str(value or "").strip().lower()
        return len(text) == 64 and all(character in "0123456789abcdef" for character in text)
    required_sections = ("platform", "python", "packages", "tools", "gpu")
    missing_sections = [name for name in required_sections if not isinstance(payload.get(name), dict)]
    if missing_sections:
        raise SystemExit(
            "refusing to stage a release bundle without a refreshed runtime environment capture; "
            f"missing structured environment sections: {', '.join(missing_sections)}"
        )
    status = str(payload.get("status", "")).strip().lower()
    if "placeholder" in status:
        raise SystemExit(
            "refusing to stage a release bundle with a placeholder runtime environment capture; "
            "refresh results/environment/runtime_environment.{json,md} on the formal execution host first."
        )
    execution = payload.get("execution", {})
    if "execution" not in payload or not isinstance(execution, dict) or not execution:
        raise SystemExit(
            "refusing to stage a release bundle without release-facing execution metadata in runtime_environment.json."
        )
    if str(execution.get("execution_mode", "")).strip() != "single_host_canonical":
        raise SystemExit(
            "refusing to stage a release bundle without execution_mode=single_host_canonical in runtime_environment.json."
        )
    if str(execution.get("cuda_visible_devices", "")).strip() != "0,1,2,3,4,5,6,7":
        raise SystemExit(
            "refusing to stage a release bundle without the fixed CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 release contract in runtime_environment.json."
        )
    if int(execution.get("visible_gpu_count", 0) or 0) != 8:
        raise SystemExit(
            "refusing to stage a release bundle without visible_gpu_count=8 in runtime_environment.json."
        )
    if not _is_sha256(execution.get("code_snapshot_digest")):
        raise SystemExit(
            "refusing to stage a release bundle without a 64-hex code_snapshot_digest in runtime_environment.json."
        )
    if not _is_sha256(execution.get("execution_environment_fingerprint")):
        raise SystemExit(
            "refusing to stage a release bundle without a 64-hex execution_environment_fingerprint in runtime_environment.json."
        )
    gpu_payload = payload.get("gpu", {})
    if int(gpu_payload.get("visible_gpu_count", 0) or 0) != 8:
        raise SystemExit(
            "refusing to stage a release bundle when gpu.visible_gpu_count does not match the fixed eight-GPU release contract."
        )
    if str(gpu_payload.get("cuda_visible_devices", "")).strip() != "0,1,2,3,4,5,6,7":
        raise SystemExit(
            "refusing to stage a release bundle when gpu.cuda_visible_devices does not match the fixed release contract."
        )
    markdown_text = runtime_environment_md.read_text(encoding="utf-8", errors="replace")
    if "placeholder" in markdown_text.lower():
        raise SystemExit(
            "refusing to stage a release bundle while results/environment/runtime_environment.md still advertises a placeholder capture; "
            "refresh the environment-of-record capture first."
        )


def is_excluded(path: Path) -> str | None:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        return "outside_repo_root"
    if release_bundle_contract.is_policy_excluded(relative):
        return relative
    for forbidden in release_bundle_contract.FORBIDDEN_BUNDLE_PREFIXES:
        if relative == forbidden or relative.startswith(forbidden + "/"):
            return forbidden
    return None


def _resolve_bundle_source(entry: str | Path) -> tuple[Path, str]:
    raw = Path(entry)
    source = raw if raw.is_absolute() else (root / raw)
    source = source.resolve()
    try:
        relative = source.relative_to(root)
    except ValueError as exc:
        raise SystemExit(
            f"release bundle allowlist entry escapes repository root: {entry}"
        ) from exc
    return source, relative.as_posix()


def _copy_bundle_file(source: Path, relative: str) -> str:
    if source.is_symlink():
        raise SystemExit(f"tracked publishable file must not be a symlink in the release bundle surface: {relative}")
    destination = out / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    _sanitize_upstream_manifest_for_bundle(destination)
    return relative


def _tracked_checkout_files(repo_root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise SystemExit(
            f"unable to enumerate tracked files for vendored checkout {repo_root}: {stderr or 'git ls-files failed'}"
        )
    tracked_files: list[str] = []
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
            raise SystemExit(
                f"vendored checkout {repo_root} contains a non-sanitizable tracked path: {entry}"
            )
        if release_bundle_contract.is_policy_excluded(normalized) or any(
            release_bundle_contract.path_matches_prefix(normalized, prefix)
            for prefix in release_bundle_contract.FORBIDDEN_BUNDLE_PREFIXES
        ):
            raise SystemExit(
                f"vendored checkout {repo_root} contains a forbidden tracked path for the sanitized bundle: {normalized}"
            )
        if release_bundle_contract.is_allowed_bundle_output_root(normalized):
            raise SystemExit(
                f"vendored checkout {repo_root} contains a forbidden tracked bundle-output residue path: {normalized}"
            )
        artifact_issue = release_bundle_contract.forbidden_bundle_artifact_issue(normalized)
        if artifact_issue is not None:
            raise SystemExit(
                f"vendored checkout {repo_root} contains a machine-specific tracked artifact for the sanitized bundle: {artifact_issue}"
            )
        tracked_files.append(normalized)
    tracked_files = sorted(set(tracked_files))
    if not tracked_files:
        raise SystemExit(f"vendored checkout {repo_root} has no tracked files to bundle")
    return tracked_files


def _stage_vendored_checkout(repo_root: Path, bundle_prefix: str, tracked_files: list[str]) -> list[str]:
    resolved_repo_root = repo_root.resolve()
    copied: list[str] = []
    for relative in tracked_files:
        source = repo_root / Path(relative)
        if not source.exists():
            raise SystemExit(
                f"vendored checkout {repo_root} is missing tracked file required for the release bundle: {relative}"
            )
        if source.is_symlink():
            raise SystemExit(
                f"vendored checkout {repo_root} contains a symlinked tracked file that cannot be bundled fail-closed: {relative}"
            )
        resolved_source = source.resolve()
        try:
            resolved_source.relative_to(resolved_repo_root)
        except ValueError as exc:
            raise SystemExit(
                f"vendored checkout {repo_root} contains a tracked path that escapes the checkout root: {relative}"
            ) from exc
        if not resolved_source.is_file():
            raise SystemExit(
                f"vendored checkout {repo_root} contains a tracked entry that is not a regular file: {relative}"
            )
        destination = out / bundle_prefix / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved_source, destination)
        _sanitize_upstream_manifest_for_bundle(destination)
        copied.append(destination.relative_to(out).as_posix())
    return copied


def _sanitize_upstream_manifest_for_bundle(path: Path) -> None:
    if not path.name.endswith(".UPSTREAM.json") or "third_party" not in path.parts:
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"unable to parse upstream manifest for bundle sanitization: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"upstream manifest must be a JSON object before bundling: {path}")
    if "schema_version" not in payload:
        raise SystemExit(f"upstream manifest is missing schema_version: {path}")
    schema_version = payload.get("schema_version")
    if not isinstance(schema_version, int) or schema_version != 1:
        raise SystemExit(f"upstream manifest schema_version must be integer 1: {path}")
    repo_url = str(payload.get("repo_url", "")).strip()
    pinned_commit = str(payload.get("pinned_commit", "")).strip()
    license_status = str(payload.get("license_status", "")).strip()
    if not repo_url or not pinned_commit or not license_status:
        raise SystemExit(f"upstream manifest is missing repo_url, pinned_commit, or license_status: {path}")
    checkout_root = str(payload.get("checkout_root", "")).strip()
    normalized_checkout_root = release_bundle_contract.vendored_bundle_prefix(checkout_root)
    if normalized_checkout_root is None:
        raise SystemExit(
            f"upstream manifest must declare a bundle-safe checkout_root under third_party/: {path}"
        )
    public_external_root = str(payload.get("public_external_root", "")).strip()
    normalized_public_external_root = release_bundle_contract.external_bundle_prefix(public_external_root)
    if normalized_public_external_root is None:
        raise SystemExit(
            f"upstream manifest must declare a bundle-safe public_external_root under external_checkout/: {path}"
        )
    source_relative = str(payload.get("source_relative", "")).strip()
    if source_relative == ".":
        normalized_source_relative = "."
    else:
        normalized_source_relative = release_bundle_contract.normalize_bundle_relative_path(
            source_relative,
            forbid_hidden_components=True,
            allow_hidden_leaf=True,
        )
        if normalized_source_relative is None:
            raise SystemExit(
                f"upstream manifest must declare a sanitized source_relative without parent traversal or hidden directories: {path}"
            )
    method_symbol = str(payload.get("method_symbol", "")).strip()
    notes = str(payload.get("notes", "")).strip()
    sanitized_payload = {
        "schema_version": schema_version,
        "repo_url": repo_url,
        "pinned_commit": pinned_commit,
        "license_status": license_status,
        "checkout_root": normalized_checkout_root,
        "external_root": normalized_public_external_root,
        "source_relative": normalized_source_relative,
        "public_external_root": normalized_public_external_root,
        "bundle_sanitized": True,
    }
    if method_symbol:
        sanitized_payload["method_symbol"] = method_symbol
    if notes:
        sanitized_payload["notes"] = notes
    path.write_text(
        json.dumps(sanitized_payload, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def remove_tree(path: Path) -> None:
    last_error: Exception | None = None
    for _ in range(5):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            last_error = exc
            time.sleep(0.2)
    if last_error is not None:
        raise last_error


def _public_baseline_payload(method: str) -> dict[str, object]:
    manifest = load_upstream_manifest(method)
    metadata = dict(stone_family_checkout_metadata(method))
    checkout_root = release_bundle_contract.vendored_bundle_prefix(str(manifest.get("checkout_root", "")).strip()) or ""
    public_external_root = release_bundle_contract.external_bundle_prefix(
        str(manifest.get("public_external_root", "")).strip()
    ) or ""
    metadata_origin = str(metadata.get("origin", "")).strip()
    metadata_source_path = release_bundle_contract.normalize_bundle_relative_path(
        str(metadata.get("source_path", "")).strip()
    ) or ""
    metadata_repo_root_text = str(metadata.get("repo_root", "") or "").strip()
    metadata_repo_root = Path(metadata_repo_root_text).resolve() if metadata_repo_root_text else None
    external_path = public_external_root
    vendored_root = root / checkout_root if checkout_root else None
    vendored_symlink_component = (
        release_bundle_contract.first_symlink_component(root, vendored_root)
        if vendored_root is not None
        else None
    )
    vendored_exists = (
        bool(checkout_root)
        and vendored_root is not None
        and vendored_root.exists()
        and vendored_symlink_component is None
    )
    expected_vendored_root = vendored_root.resolve() if vendored_exists and vendored_root is not None else None
    vendored_metadata_matches = (
        vendored_exists
        and metadata_origin == "vendored_snapshot"
        and metadata_source_path == checkout_root
        and metadata_repo_root is not None
        and expected_vendored_root is not None
        and metadata_repo_root == expected_vendored_root
    )
    external_exists = (
        bool(metadata.get("checkout_present", False))
        and metadata_origin == "external_checkout"
        and metadata_source_path == public_external_root
    )
    metadata_issues = [str(item) for item in metadata.get("checkout_issues", [])]
    vendored_verification_issues = [
        item
        for item in metadata_issues
        if not item.startswith("missing local checkout for ")
    ]
    manifest_repo_url = str(manifest.get("repo_url", "")).strip()
    manifest_pinned_commit = str(manifest.get("pinned_commit", "")).strip()
    manifest_license_status = str(manifest.get("license_status", "")).strip()
    metadata_repo_url = str(metadata.get("repo_url", "")).strip()
    metadata_pinned_commit = str(metadata.get("pinned_commit", "")).strip()
    metadata_upstream_commit = str(metadata.get("upstream_commit", "")).strip()
    metadata_license_status = str(metadata.get("license_status", "")).strip()
    consistency_issues: list[str] = []
    if metadata_repo_url and manifest_repo_url and metadata_repo_url != manifest_repo_url:
        consistency_issues.append(
            f"repo_url mismatch between manifest and checkout metadata: {metadata_repo_url} != {manifest_repo_url}"
        )
    if metadata_pinned_commit and manifest_pinned_commit and metadata_pinned_commit != manifest_pinned_commit:
        consistency_issues.append(
            "pinned_commit mismatch between manifest and checkout metadata"
        )
    if metadata_license_status and manifest_license_status and metadata_license_status != manifest_license_status:
        consistency_issues.append(
            f"license_status mismatch between manifest and checkout metadata: {metadata_license_status} != {manifest_license_status}"
        )
    if metadata_upstream_commit and manifest_pinned_commit and metadata_upstream_commit != manifest_pinned_commit:
        consistency_issues.append(
            "upstream_commit mismatch between checkout metadata and pinned manifest commit"
        )
    metadata_issues.extend(consistency_issues)
    vendored_verification_issues.extend(consistency_issues)
    repo_url = manifest_repo_url or metadata_repo_url
    pinned_commit = manifest_pinned_commit or metadata_pinned_commit
    upstream_commit = metadata_upstream_commit or manifest_pinned_commit
    license_status = manifest_license_status or metadata_license_status
    public_manifest_valid = bool(repo_url) and bool(pinned_commit) and bool(upstream_commit) and bool(license_status)
    redistributable = bool(metadata.get("redistributable", False))
    if str(manifest.get("checkout_root", "")).strip() and not checkout_root:
        vendored_verification_issues.append("vendored checkout_root must stay under third_party/")
    if vendored_symlink_component is not None:
        symlink_issue = f"vendored checkout_root must not contain symlinked path components: {checkout_root}"
        vendored_verification_issues.append(symlink_issue)
        metadata_issues.append(symlink_issue)
    if str(manifest.get("public_external_root", "")).strip() and not public_external_root:
        metadata_issues.append("public_external_root must stay under external_checkout/")
    if external_exists and not public_external_root:
        metadata_issues.append("external checkout requires a sanitized public_external_root")
    if vendored_exists and not vendored_metadata_matches:
        vendored_verification_issues.append(
            "vendored checkout was not the verified checkout selected by stone_family_checkout_metadata"
        )
    if vendored_exists:
        verification_issues = list(dict.fromkeys(vendored_verification_issues))
        checkout_valid = public_manifest_valid and not verification_issues
        if redistributable and checkout_valid:
            origin = "vendored_snapshot"
            bundle_eligible = True
            source_path = checkout_root
        else:
            origin = "vendored_unverified"
            bundle_eligible = False
            source_path = ""
    else:
        verification_issues = list(dict.fromkeys(metadata_issues))
        checkout_valid = public_manifest_valid and not verification_issues
        bundle_eligible = False
        if checkout_valid:
            origin = "external_checkout"
            source_path = external_path
        else:
            origin = "external_unverified"
            source_path = ""
    return {
        "origin": origin,
        "source_path": source_path,
        "vendored_path": checkout_root,
        "external_path": external_path,
        "selected_checkout_path": source_path,
        "checkout_valid": checkout_valid,
        "bundle_eligible": bundle_eligible,
        "repo_url": repo_url,
        "pinned_commit": pinned_commit,
        "upstream_commit": upstream_commit,
        "license_status": license_status,
        "verification_issues": verification_issues,
        "vendored_exists": vendored_exists,
        "external_exists": external_exists,
        "redistributable": redistributable,
        "vendored_files": [],
        "vendored_file_digests": {},
    }


if out.exists():
    remove_tree(out)

_ensure_publishable_workspace()
_ensure_real_environment_capture()

included_files: list[str] = []
excluded: list[str] = []
checksums: list[str] = []
baseline_provenance_map: dict[str, dict[str, object]] = {}
tracked_bundle_files = sorted(release_bundle_contract.tracked_bundle_surface(root))
dynamic_bundle_roots: list[tuple[str, Path, str, list[str]]] = []

fail_closed_issues: list[str] = []
for public_name, method in BASELINES.items():
    payload = _public_baseline_payload(method)
    baseline_provenance_map[public_name] = payload
    origin = str(payload.get("origin", "")).strip()
    if origin in {"vendored_unverified", "external_unverified"}:
        details = [str(item) for item in payload.get("verification_issues", [])]
        suffix = f" ({'; '.join(details)})" if details else ""
        fail_closed_issues.append(
            f"{public_name}: refusing to stage a release bundle with provenance origin '{origin}'{suffix}"
        )
    if payload["origin"] == "vendored_snapshot" and bool(payload.get("bundle_eligible", False)):
        vendored_path = str(payload["vendored_path"]).strip()
        vendored_source_root = root / vendored_path
        tracked_files = _tracked_checkout_files(vendored_source_root)
        vendored_files = [
            f"{vendored_path}/{relative}".replace("\\", "/")
            for relative in tracked_files
        ]
        payload["vendored_files"] = vendored_files
        payload["vendored_file_digests"] = {
            relative: sha256(vendored_source_root / Path(relative.removeprefix(vendored_path + "/")))
            for relative in vendored_files
        }
        dynamic_bundle_roots.append((public_name, vendored_source_root, vendored_path, tracked_files))

if fail_closed_issues:
    for issue in fail_closed_issues:
        print(issue, file=sys.stderr)
    raise SystemExit(1)

try:
    out.mkdir(parents=True, exist_ok=True)

    for path in policy_exclusions:
        if not path.exists():
            continue
        excluded.append(f"policy\t{path.relative_to(root).as_posix()}")

    for public_name, payload in baseline_provenance_map.items():
        vendored_path = str(payload.get("vendored_path", "")).strip()
        external_path = str(payload.get("external_path", "")).strip()
        if bool(payload.get("vendored_exists")) and not bool(payload.get("bundle_eligible", False)):
            excluded.append(
                f"policy\t{vendored_path}\t{public_name} vendored checkout is not bundled without a verified git checkout and redistributable license"
            )
        if bool(payload.get("external_exists")):
            excluded.append(
                f"policy\t{external_path}\t{public_name} external checkout is runtime-only and not bundled"
            )

    for relative in tracked_bundle_files:
        source, relative = _resolve_bundle_source(relative)
        if not source.exists():
            excluded.append(f"missing\t{relative}")
            continue
        included_files.append(_copy_bundle_file(source, relative))
        checksums.append(f"{sha256(out / relative)}  {relative}")

    for _public_name, source_root, bundle_prefix, tracked_files in dynamic_bundle_roots:
        reason = is_excluded(root / bundle_prefix)
        if reason is not None:
            excluded.append(f"policy\t{bundle_prefix}\t{reason}")
            continue
        for copied_relative in _stage_vendored_checkout(source_root, bundle_prefix, tracked_files):
            included_files.append(copied_relative)
            checksums.append(f"{sha256(out / copied_relative)}  {copied_relative}")

    provenance_path = out / "baseline_provenance.json"
    provenance_path.write_text(
        json.dumps(baseline_provenance_map, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    checksums.append(f"{sha256(provenance_path)}  baseline_provenance.json")
    included_files.append("baseline_provenance.json")

    try:
        bundle_root = out.relative_to(root).as_posix()
    except ValueError:
        bundle_root = out.name
    canonical_matrix_index = root / "results" / "matrix" / "suite_all_models_methods" / "matrix_index.json"
    if not canonical_matrix_index.exists():
        raise SystemExit(
            "release bundle requires results/matrix/suite_all_models_methods/matrix_index.json "
            "to exist so the staged summary exports stay anchored to the canonical rerun."
        )
    canonical_matrix_index_sha256 = sha256(canonical_matrix_index)

    generated_entries = {
        "baseline_provenance.json",
        "MANIFEST.txt",
        "SHA256SUMS.txt",
        "EXCLUDED.txt",
        "bundle.manifest.json",
    }
    included = sorted(set(included_files).union(generated_entries))

    (out / "MANIFEST.txt").write_text("\n".join(included) + "\n", encoding="utf-8", newline="\n")
    (out / "EXCLUDED.txt").write_text("\n".join(sorted(excluded)) + "\n", encoding="utf-8", newline="\n")
    checksums.append(f"{sha256(out / 'MANIFEST.txt')}  MANIFEST.txt")
    checksums.append(f"{sha256(out / 'EXCLUDED.txt')}  EXCLUDED.txt")

    bundle_manifest = {
        "bundle_root": bundle_root,
        "included": included,
        "excluded": sorted(excluded),
        "file_count": len(included),
        "included_count": len(included),
        "baseline_provenance_map": baseline_provenance_map,
        "canonical_matrix_index_sha256": canonical_matrix_index_sha256,
    }
    (out / "bundle.manifest.json").write_text(
        json.dumps(bundle_manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    checksums.append(f"{sha256(out / 'bundle.manifest.json')}  bundle.manifest.json")
    checksums.append(f"{'0' * 64}  SHA256SUMS.txt")
    (out / "SHA256SUMS.txt").write_text("\n".join(sorted(checksums)) + "\n", encoding="utf-8", newline="\n")
    validation_report = validate_release_bundle.validate_bundle(out, require_live_vendored_checkout=True)
    if validation_report["status"] != "passed":
        for issue in validation_report["issues"]:
            print(f"- {issue}", file=sys.stderr)
        raise SystemExit(1)
except BaseException:
    if out.exists():
        remove_tree(out)
    raise

print(f"Anonymous release bundle staged at {out}")
print("Before publishing, verify that paper/, proposal.md, caches, and local run outputs are absent.")
print(f"Included entries: {len(included)}; files hashed: {len(checksums)}")
PY
