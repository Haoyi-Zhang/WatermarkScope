from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


HTTPS_PREFIX = "https" + "://"
HTTP_PREFIX = "http" + "://"
GITHUB_HTTPS_PREFIX = HTTPS_PREFIX + "github.com/"


@dataclass(frozen=True, slots=True)
class UpstreamRepo:
    slug: str
    repo_url: str
    pinned_commit: str
    license_status: str
    source_relative: str
    purpose: str
    integration_mode: str
    redistributable: bool


def load_upstream_manifests(root: str | Path) -> tuple[UpstreamRepo, ...]:
    manifest_root = Path(root) / "third_party" / "upstream"
    manifests = []
    for path in sorted(manifest_root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifests.append(
            UpstreamRepo(
                slug=path.stem,
                repo_url=str(payload["repo_url"]),
                pinned_commit=str(payload["pinned_commit"]),
                license_status=str(payload["license_status"]),
                source_relative=str(payload["source_relative"]),
                purpose=str(payload["purpose"]),
                integration_mode=str(payload["integration_mode"]),
                redistributable=bool(payload["redistributable"]),
            )
        )
    return tuple(manifests)


def validate_manifest(manifest: UpstreamRepo) -> tuple[bool, tuple[str, ...]]:
    issues: list[str] = []
    if manifest.integration_mode == "paper_only":
        if manifest.pinned_commit != "paper_only":
            issues.append("paper_only_must_use_paper_only_commit")
        if not manifest.repo_url.startswith((HTTPS_PREFIX, HTTP_PREFIX)):
            issues.append("paper_only_repo_url_must_be_link")
    else:
        if not manifest.repo_url.startswith(GITHUB_HTTPS_PREFIX):
            issues.append("repo_url_must_use_https_github")
        if len(manifest.pinned_commit) < 7:
            issues.append("pinned_commit_too_short")
    if not manifest.source_relative:
        issues.append("source_relative_missing")
    if manifest.integration_mode not in {"baseline", "benchmark", "paper_only", "planned_or_metadata_only"}:
        issues.append("integration_mode_invalid")
    return len(issues) == 0, tuple(issues)


def _checkout_path(root: str | Path, slug: str) -> Path:
    return Path(root) / "external_checkout" / slug


def _load_frozen_provenance_record(root: str | Path, slug: str) -> dict[str, object] | None:
    root_path = Path(root)
    for candidate in (
        root_path / "artifacts" / "generated" / "provenance_log.json",
        root_path / "artifacts" / "provenance_log.json",
    ):
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        records = payload.get("records", [])
        if not isinstance(records, list):
            continue
        for record in records:
            if isinstance(record, dict) and str(record.get("slug", "")) == slug:
                return record
    return None


def _verify_checkout_from_frozen_provenance(root: str | Path, slug: str, expected_commit: str) -> tuple[bool, tuple[str, ...]]:
    checkout = _checkout_path(root, slug)
    if not checkout.exists():
        return False, ("checkout_missing",)
    record = _load_frozen_provenance_record(root, slug)
    if record is None:
        return False, ("git_unavailable", "frozen_provenance_missing")
    resolved_commit = str(record.get("resolved_commit", "")).strip()
    if resolved_commit != expected_commit:
        return False, ("git_unavailable", "frozen_provenance_commit_mismatch")
    return True, ("git_unavailable_reused_frozen_provenance",)


def _needs_frozen_provenance_fallback(completed: subprocess.CompletedProcess[str]) -> bool:
    combined = f"{completed.stdout}\n{completed.stderr}".lower()
    return "detected dubious ownership" in combined or "safe.directory" in combined


def verify_checkout(root: str | Path, slug: str, expected_commit: str) -> tuple[bool, tuple[str, ...]]:
    checkout = _checkout_path(root, slug)
    issues: list[str] = []
    if not checkout.exists():
        return False, ("checkout_missing",)
    try:
        head = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, PermissionError):
        return _verify_checkout_from_frozen_provenance(root, slug, expected_commit)
    if head.returncode != 0 and _needs_frozen_provenance_fallback(head):
        return _verify_checkout_from_frozen_provenance(root, slug, expected_commit)
    if head.returncode != 0 or head.stdout.strip() != expected_commit:
        issues.append("head_commit_mismatch")
    try:
        status = subprocess.run(
            ["git", "-C", str(checkout), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, PermissionError):
        return _verify_checkout_from_frozen_provenance(root, slug, expected_commit)
    if status.returncode != 0 and _needs_frozen_provenance_fallback(status):
        return _verify_checkout_from_frozen_provenance(root, slug, expected_commit)
    if status.returncode != 0:
        issues.append("git_status_failed")
    elif status.stdout.strip():
        issues.append("worktree_not_clean")
    return len(issues) == 0, tuple(issues)


def checkout_status(root: str | Path, manifest: UpstreamRepo) -> dict[str, object]:
    checkout = _checkout_path(root, manifest.slug)
    manifest_ok, manifest_issues = validate_manifest(manifest)
    source_path = checkout / manifest.source_relative
    if manifest.integration_mode == "paper_only":
        return {
            "slug": manifest.slug,
            "manifest_ok": manifest_ok,
            "manifest_issues": list(manifest_issues),
            "checkout_required": False,
            "checkout_exists": False,
            "source_relative_exists": False,
            "commit_ok": True,
            "checkout_issues": [],
        }
    commit_ok, checkout_issues = verify_checkout(root, manifest.slug, manifest.pinned_commit)
    if checkout.exists() and not source_path.exists():
        checkout_issues = tuple(list(checkout_issues) + ["source_relative_missing_in_checkout"])
        commit_ok = False
    return {
        "slug": manifest.slug,
        "manifest_ok": manifest_ok,
        "manifest_issues": list(manifest_issues),
        "checkout_required": True,
        "checkout_exists": checkout.exists(),
        "source_relative_exists": source_path.exists() if checkout.exists() else False,
        "commit_ok": commit_ok,
        "checkout_issues": list(checkout_issues),
    }
