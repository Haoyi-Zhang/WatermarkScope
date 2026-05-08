from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _hf_readiness import (
    HFModelRequirement,
    smoke_load_local_hf_evaluator,
    smoke_load_local_hf_model,
    validate_local_hf_cache,
)
from codemarkbench.config import build_experiment_config
from codemarkbench.attacks.registry import available_attacks
from codemarkbench.baselines.stone_family.common import (
    stone_family_checkout_metadata,
    validate_checkout as validate_runtime_checkout,
)
from codemarkbench.toolchains import inspect_local_toolchain
from codemarkbench.watermarks.registry import available_watermarks
from codemarkbench.watermarks.upstream_runtime import is_runtime_watermark
from evaluate_baseline_family import (
    baseline_eval_requirement,
    canonical_baseline_eval_requirement,
    derived_baseline_eval_requirement,
)

validate_stone_checkout = validate_runtime_checkout

from _shared import (
    CONFIG_DIR,
    DATA_DIR,
    DEFAULT_ATTACKS,
    DEFAULT_FIXTURE,
    DEFAULT_NORMALIZED_BENCHMARK,
    MODEL_CACHE_DIR,
    RESULTS_DIR,
    dump_json,
    load_config,
    load_json,
    read_jsonl,
)


IDENTITY_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "author": re.compile(r"(?im)^\s*author\s*:\s*.+$"),
    "affiliation": re.compile(r"(?im)^\s*affiliation\s*:\s*.+$"),
    "institution": re.compile(r"(?im)^\s*institution\s*:\s*.+$"),
    "personal_path": re.compile(r"(?i)c:\\users\\[a-z0-9._-]+"),
    "coordination_path": re.compile(r"(?i)(?:^|[\\/])\.coordination(?:[\\/]|$)"),
}

_LEGACY_TITLE = "".join(["Code", "WM", "Bench"])
_LEGACY_SLUG = "".join(["code", "wm", "bench"])
_LEGACY_ENV_PREFIX = "".join(["CODE", "WMBENCH", "_"])

LEGACY_PROJECT_PATTERNS = {
    "legacy_project_title": re.compile(rf"\b{re.escape(_LEGACY_TITLE)}\b", re.IGNORECASE),
    "legacy_project_slug": re.compile(rf"\b{re.escape(_LEGACY_SLUG)}\b", re.IGNORECASE),
    "legacy_env_prefix": re.compile(rf"\b{re.escape(_LEGACY_ENV_PREFIX)}[A-Z0-9_]*\b", re.IGNORECASE),
}

PUBLIC_BENCHMARK_CONTENT_PATTERN_LABELS = {
    "author",
    "affiliation",
    "institution",
    "personal_path",
    "coordination_path",
}

BENCHMARK_CONTENT_FIELDS = {
    "prompt",
    "reference_solution",
    "canonical_solution",
    "completion",
    "test",
    "execution_tests",
    "reference_tests",
    "contract",
    "expected_behavior",
    "semantic_contract",
    "stress_tests",
    "metamorphic_tests",
    "functional_cases",
    "stress_cases",
    "base_cases",
    "prompt_prefix",
}

BENCHMARK_METADATA_FIELDS = {
    "task_id",
    "dataset",
    "language",
    "source",
    "source_path",
    "source_url",
    "source_revision",
    "source_sha256",
    "source_digest",
    "prompt_digest",
    "solution_digest",
    "split",
    "license_note",
    "adapter_name",
    "validation_scope",
    "public_source",
    "record_kind",
    "source_group",
    "origin_type",
    "family_id",
    "difficulty",
    "evaluation_backend",
    "runner_image",
    "official_problem_file",
    "language_version",
    "reference_kind",
    "smoke_completion_available",
    "canonical_available",
    "notes",
    "description",
    "translation_anchor_language",
    "entry_point",
}

_COORDINATION_LITERAL_EXEMPT_SUFFIXES = {
    ".py",
    ".sh",
    ".ps1",
    ".md",
    ".txt",
    ".rst",
    ".toml",
    ".ini",
    ".cfg",
}

_BINARY_IDENTITY_SCAN_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
}

_LEGACY_BINARY_TOKENS = (
    _LEGACY_TITLE.encode("utf-8"),
    _LEGACY_SLUG.encode("utf-8"),
    _LEGACY_ENV_PREFIX.encode("utf-8"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the CodeMarkBench setup.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/default.yaml"),
        help="Config file to validate. Defaults to the canonical public runtime configuration.",
    )
    parser.add_argument("--benchmark", type=Path, default=None, help="Canonical normalized benchmark fixture path.")
    parser.add_argument("--attack-matrix", type=Path, default=DEFAULT_ATTACKS, help="Attack matrix path.")
    parser.add_argument("--check-anonymity", action="store_true", help="Scan release-facing files for identity markers.")
    parser.add_argument("--report", type=Path, default=None, help="Optional JSON report path.")
    return parser.parse_args()


def ensure_paths_exist(paths: list[Path]) -> list[str]:
    issues: list[str] = []
    for path in paths:
        if not path.exists():
            issues.append(f"missing: {path}")
    return issues


def scan_for_identity_markers(paths: list[Path], *, labels: set[str] | None = None) -> list[str]:
    findings: list[str] = []
    active_labels = labels or set(IDENTITY_PATTERNS)
    for path in paths:
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or "_cache" in path.parts or path.suffix.lower() in {".pyc", ".pyo", ".gz"}:
            continue
        if path.suffix.lower() in {".jsonl", ".json"} and "data" in path.parts:
            findings.extend(scan_for_identity_markers_in_benchmark(path))
            continue
        if _is_probably_binary(path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        path_labels = set(active_labels)
        if path.name == "Makefile" or path.suffix.lower() in _COORDINATION_LITERAL_EXEMPT_SUFFIXES:
            path_labels.discard("coordination_path")
        findings.extend(_scan_text(text, path=path, labels=path_labels))
    return findings


def _scan_text(text: str, *, path: Path, labels: set[str] | None = None) -> list[str]:
    findings: list[str] = []
    active_labels = labels or set(IDENTITY_PATTERNS)
    for label, pattern in IDENTITY_PATTERNS.items():
        if label not in active_labels:
            continue
        if pattern.search(text):
            findings.append(f"{path}: matched {label}")
    return findings


def scan_for_legacy_project_markers(paths: list[Path], *, root: Path | None = None) -> list[str]:
    findings: list[str] = []
    normalized_root = root.resolve() if root is not None else None
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        relative = path
        if normalized_root is not None:
            try:
                relative = path.resolve().relative_to(normalized_root)
            except ValueError:
                relative = path.name
        relative_str = Path(relative).as_posix()
        for label, pattern in LEGACY_PROJECT_PATTERNS.items():
            if pattern.search(relative_str):
                findings.append(f"{relative_str}: matched {label} in path")
        if _is_probably_binary(path):
            payload = path.read_bytes()
            if _LEGACY_BINARY_TOKENS[0] in payload:
                findings.append(f"{relative_str}: matched legacy_project_title in binary content")
            if _LEGACY_BINARY_TOKENS[1] in payload:
                findings.append(f"{relative_str}: matched legacy_project_slug in binary content")
            if _LEGACY_BINARY_TOKENS[2] in payload:
                findings.append(f"{relative_str}: matched legacy_env_prefix in binary content")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in LEGACY_PROJECT_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{relative_str}: matched {label}")
    return findings


def legacy_project_findings_for_text(text: str, *, context: str) -> list[str]:
    findings: list[str] = []
    for label, pattern in LEGACY_PROJECT_PATTERNS.items():
        if pattern.search(text):
            findings.append(f"{context}: matched {label}")
    return findings


def _collect_strings(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        parts: list[str] = []
        for nested in value.values():
            parts.extend(_collect_strings(nested))
        return parts
    if isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for item in value:
            parts.extend(_collect_strings(item))
        return parts
    return [str(value)]


def _is_probably_binary(path: Path) -> bool:
    if path.suffix.lower() in _BINARY_IDENTITY_SCAN_SUFFIXES:
        return True
    try:
        payload = path.read_bytes()
    except OSError:
        return False
    return b"\x00" in payload


def scan_for_identity_markers_in_benchmark(path: Path) -> list[str]:
    findings: list[str] = []
    is_public_snapshot = "public" in path.parts
    if path.suffix.lower() == ".jsonl":
        rows = read_jsonl(path)
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            metadata_payload: list[str] = []
            content_payload: list[str] = []
            for key, value in row.items():
                key_str = str(key)
                if key_str in BENCHMARK_CONTENT_FIELDS:
                    content_payload.extend(_collect_strings(value))
                    continue
                if key_str not in BENCHMARK_METADATA_FIELDS and key_str not in {"notes", "description"}:
                    continue
                metadata_payload.extend(_collect_strings(value))
            if metadata_payload:
                findings.extend(_scan_text("\n".join(metadata_payload), path=Path(f"{path}#{index}")))
            if content_payload:
                labels = PUBLIC_BENCHMARK_CONTENT_PATTERN_LABELS if is_public_snapshot else None
                findings.extend(_scan_text("\n".join(content_payload), path=Path(f"{path}#{index}:content"), labels=labels))
        return findings
    text = path.read_text(encoding="utf-8", errors="ignore")
    return _scan_text(text, path=path)


def release_candidate_files() -> list[Path]:
    candidates = [
        CONFIG_DIR,
        DATA_DIR / "fixtures",
        DATA_DIR / "release",
        DATA_DIR / "public",
        Path("codemarkbench"),
        MODEL_CACHE_DIR / "README.md",
        RESULTS_DIR / "schema.json",
        Path("docs"),
        Path("submission"),
        Path("README.md"),
        Path("LICENSE"),
        Path("Makefile"),
        Path("pyproject.toml"),
        Path("requirements.txt"),
        Path(".env.example"),
        Path(".gitignore"),
        Path("scripts"),
        Path("third_party"),
    ]
    return candidates


def _strict_local_hf_requirement(config: dict[str, Any], *, config_path: Path) -> HFModelRequirement | None:
    provider = dict(config.get("provider", {}))
    watermark = dict(config.get("watermark", {}))
    provider_mode = str(provider.get("mode", "")).strip().lower()
    provider_parameters = dict(provider.get("parameters", {}))
    watermark_scheme = str(watermark.get("scheme", "")).strip().lower()

    if provider_mode == "local_hf" and bool(provider_parameters.get("local_files_only", False)):
        model_name = str(provider_parameters.get("model", "")).strip()
        if not model_name:
            return None
        return HFModelRequirement(
            model=model_name,
            cache_dir=str(provider_parameters.get("cache_dir", "")).strip(),
            local_files_only=True,
            trust_remote_code=bool(provider_parameters.get("trust_remote_code", False)),
            device=str(provider_parameters.get("device", "cuda")).strip() or "cuda",
            dtype=str(provider_parameters.get("dtype", "float16")).strip() or "float16",
            token_env=str(provider_parameters.get("token_env", "HF_ACCESS_TOKEN")).strip() or "HF_ACCESS_TOKEN",
            usage=("local_hf",),
            config_paths=(str(config_path),),
        )

    if is_runtime_watermark(watermark_scheme) and bool(watermark.get("local_files_only", False)):
        model_name = str(watermark.get("model_name", "")).strip()
        if not model_name:
            return None
        return HFModelRequirement(
            model=model_name,
            cache_dir=str(watermark.get("cache_dir", "")).strip(),
            local_files_only=True,
            trust_remote_code=bool(watermark.get("trust_remote_code", False)),
            device=str(watermark.get("device", "cuda")).strip() or "cuda",
            dtype=str(watermark.get("dtype", "float16")).strip() or "float16",
            token_env=str(watermark.get("token_env", "HF_ACCESS_TOKEN")).strip() or "HF_ACCESS_TOKEN",
            usage=("runtime",),
            config_paths=(str(config_path),),
        )

    return None


def _strict_local_hf_requirements(config: dict[str, Any], *, config_path: Path) -> list[HFModelRequirement]:
    primary = _strict_local_hf_requirement(config, config_path=config_path)
    if primary is None:
        return []
    requirements = [primary]
    config_metadata = dict(build_experiment_config(config).metadata or {})
    baseline_requirement = derived_baseline_eval_requirement(
        metadata=config_metadata,
        device=str(primary.device or "cuda"),
        token_env=str(primary.token_env or "HF_ACCESS_TOKEN"),
        cache_dir=str(primary.cache_dir),
        local_files_only=bool(primary.local_files_only),
        trust_remote_code=bool(primary.trust_remote_code),
        usage=("baseline_eval", "evaluator"),
    )
    if (
        baseline_requirement.model != primary.model
        or baseline_requirement.revision != primary.revision
        or baseline_requirement.cache_dir != primary.cache_dir
    ):
        requirements.append(baseline_requirement)
    return requirements


def _validate_requirement_with_smoke(requirement: HFModelRequirement) -> dict[str, Any]:
    validation = validate_local_hf_cache(requirement, require_root_entry=True)
    issues = list(str(item) for item in validation.get("issues", []))
    if validation["status"] == "ok":
        model_smoke = smoke_load_local_hf_model(requirement)
        evaluator_smoke = smoke_load_local_hf_evaluator(requirement)
        if model_smoke.get("status") != "ok":
            issues.extend(f"{requirement.model}: offline model smoke {item}" for item in model_smoke.get("issues", []))
        if evaluator_smoke.get("status") != "ok":
            issues.extend(
                f"{requirement.model}: offline evaluator smoke {item}"
                for item in evaluator_smoke.get("issues", [])
            )
    else:
        model_smoke = {
            "model": requirement.model,
            "status": "skipped",
            "issues": ["cache_validation_failed"],
        }
        evaluator_smoke = {
            "model": requirement.model,
            "status": "skipped",
            "issues": ["cache_validation_failed"],
        }
    return {
        **validation,
        "cache_status": validation["status"],
        "model_smoke": model_smoke,
        "evaluator_smoke": evaluator_smoke,
        "status": "ok" if not issues else "failed",
        "issues": issues,
    }


def _as_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    benchmark_path = args.benchmark
    if benchmark_path is None:
        benchmark_cfg = config.get("benchmark", {})
        path_cfg = config.get("paths", {})
        benchmark_path = Path(
            benchmark_cfg.get("prepared_output")
            or path_cfg.get("prepared_benchmark")
            or DEFAULT_NORMALIZED_BENCHMARK
        )
    benchmark_rows = read_jsonl(benchmark_path)
    attack_matrix = load_json(args.attack_matrix)
    benchmark_manifest_path = benchmark_path.with_suffix(".manifest.json")
    benchmark_manifest = load_json(benchmark_manifest_path) if benchmark_manifest_path.exists() else {}
    known_attacks = set(available_attacks())
    known_watermarks = set(available_watermarks())
    runtime_requirements: dict[str, object] = {}
    hf_cache_validation: dict[str, object] | None = None
    baseline_provenance: dict[str, Any] = {}
    toolchain_validation: dict[str, Any] = {}

    issues = []
    issues.extend(ensure_paths_exist([args.config, benchmark_path, args.attack_matrix, CONFIG_DIR, RESULTS_DIR]))
    if not benchmark_manifest:
        issues.append(f"missing benchmark manifest: {benchmark_manifest_path}")
    if not benchmark_rows:
        issues.append("benchmark fixture is empty")
    if benchmark_manifest and benchmark_manifest.get("record_count") not in {None, len(benchmark_rows)}:
        issues.append(
            f"benchmark manifest count mismatch: manifest={benchmark_manifest.get('record_count')} rows={len(benchmark_rows)}"
        )
    if not isinstance(attack_matrix.get("attacks"), list) or not attack_matrix["attacks"]:
        issues.append("attack matrix is empty")
    watermark_config = config.get("watermark", {})
    watermark_scheme = str(watermark_config.get("scheme", "")).lower()
    if watermark_scheme not in known_watermarks:
        issues.append(
            f"unknown watermark scheme: {watermark_config.get('scheme', '')}"
        )
    if is_runtime_watermark(watermark_scheme):
        model_name = str(watermark_config.get("model_name", "")).strip()
        baseline_provenance = stone_family_checkout_metadata(watermark_scheme)
        upstream_root = Path(str(baseline_provenance["repo_root"])) if baseline_provenance.get("repo_root") else None
        runtime_requirements = {
            "scheme": watermark_scheme,
            "model_name": model_name,
            "upstream_root": str(upstream_root) if upstream_root is not None else None,
            "token_env": str(watermark_config.get("token_env", "HF_ACCESS_TOKEN")),
            "device": str(watermark_config.get("device", "auto")),
            "baseline_provenance": baseline_provenance,
        }
        if not model_name:
            issues.append(f"runtime watermark '{watermark_scheme}' requires watermark.model_name")
        checkout_issues = validate_runtime_checkout(watermark_scheme)
        issues.extend(checkout_issues)
        if not checkout_issues and upstream_root is None:
            issues.append(
                f"runtime watermark '{watermark_scheme}' requires a valid official upstream checkout"
            )
    configured_attacks = [str(name).lower() for name in config.get("attacks", {}).get("include", [])]
    unknown_attacks = sorted(set(configured_attacks) - known_attacks)
    if unknown_attacks:
        issues.append(f"unknown configured attacks: {unknown_attacks}")
    matrix_names = [str(item.get("name", "")).lower() for item in attack_matrix.get("attacks", []) if isinstance(item, dict)]
    unknown_matrix_names = sorted(set(matrix_names) - known_attacks)
    if unknown_matrix_names:
        issues.append(f"attack matrix contains unknown attacks: {unknown_matrix_names}")
    benchmark_languages = [str(language).lower() for language in config.get("benchmark", {}).get("languages", [])]
    if benchmark_manifest:
        observed_languages = [str(language).lower() for language in benchmark_manifest.get("observed_languages", [])]
        missing_claimed_languages = [language for language in benchmark_languages if language not in observed_languages]
        if missing_claimed_languages:
            issues.append(f"claimed benchmark languages missing from fixture: {missing_claimed_languages}")
    runtime_validation_languages = sorted(
        {
            str(row.get("language", "")).strip().lower()
            for row in benchmark_rows
            if str(row.get("evaluation_backend", "")).strip().lower() == "docker_remote"
            and bool(row.get("validation_supported"))
        }
    )
    if runtime_validation_languages:
        toolchain_entries: list[dict[str, Any]] = []
        for language in runtime_validation_languages:
            inspection = inspect_local_toolchain(language)
            toolchain_entries.append(inspection)
            if inspection.get("status") != "ok":
                issues.extend(
                    f"toolchain[{language}] {item}"
                    for item in inspection.get("issues", [])
                )
        toolchain_validation = {
            "languages": runtime_validation_languages,
            "entries": toolchain_entries,
        }

    strict_hf_requirements = _strict_local_hf_requirements(config, config_path=args.config)
    if strict_hf_requirements:
        requirement_entries = []
        requirement_checks = []
        requirement_issues: list[str] = []
        for requirement in strict_hf_requirements:
            requirement_entries.append(
                {
                    "model": requirement.model,
                    "revision": requirement.revision,
                    "cache_dir": requirement.cache_dir,
                    "local_files_only": requirement.local_files_only,
                    "usage": list(requirement.usage),
                    "config_paths": list(requirement.config_paths),
                }
            )
            validation = _validate_requirement_with_smoke(requirement)
            validation["usage"] = list(requirement.usage)
            validation["config_paths"] = list(requirement.config_paths)
            requirement_checks.append(validation)
            if validation["status"] != "ok":
                requirement_issues.extend(str(item) for item in validation.get("issues", []))
        runtime_requirements["hf_model_requirement"] = requirement_entries[0]
        if len(requirement_entries) > 1:
            runtime_requirements["baseline_eval_hf_model_requirement"] = requirement_entries[1]
        hf_cache_validation = {
            "status": "ok" if not requirement_issues else "failed",
            "issues": requirement_issues,
            "requirements": requirement_entries,
            "checks": requirement_checks,
        }
        if requirement_issues:
            issues.extend(requirement_issues)

    if args.check_anonymity:
        paths = []
        for candidate in release_candidate_files():
            if candidate.is_dir():
                paths.extend(sorted(candidate.rglob("*")))
            else:
                paths.append(candidate)
        findings = scan_for_identity_markers(paths, labels=set(IDENTITY_PATTERNS) - {"coordination_path"})
        issues.extend(findings)

    report = {
        "config_path": str(args.config),
        "benchmark_path": str(benchmark_path),
        "attack_matrix_path": str(args.attack_matrix),
        "config_keys": sorted(config.keys()),
        "benchmark_count": len(benchmark_rows),
        "attack_count": len(attack_matrix.get("attacks", [])),
        "benchmark_manifest": benchmark_manifest,
        "baseline_provenance": baseline_provenance,
        "runtime_requirements": runtime_requirements,
        "hf_cache_validation": hf_cache_validation,
        "toolchain_validation": toolchain_validation,
        "issues": issues,
    }

    if args.report is not None:
        dump_json(args.report, report)

    if issues:
        print("Validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("Validation passed: setup is ready for local reproduction and public release.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
