from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_PATHS = [
    "README.md",
    "CLAIM_BOUNDARIES.md",
    "RESULT_MANIFEST.jsonl",
    "docs/EXAMINER_GUIDE.md",
    "docs/ENVIRONMENT.md",
    "docs/METHOD_INDEX.md",
    "docs/RESULT_PRESERVATION_POLICY.md",
    "docs/RESULTS_SUMMARY.md",
    "docs/RUNBOOK.md",
    "docs/TRACEABILITY_MATRIX.md",
    "dissertation/WatermarkScope_FYP_Dissertation.pdf",
    "dissertation/latex/report.tex",
    "dissertation/latex/reference.bib",
    "projects/CodeMarkBench/README.md",
    "projects/SemCodebook/README.md",
    "projects/SemCodebook/src",
    "projects/SemCodebook/scripts",
    "projects/SemCodebook/tests",
    "projects/CodeDye/README.md",
    "projects/CodeDye/scripts",
    "projects/CodeDye/tests",
    "projects/ProbeTrace/README.md",
    "projects/ProbeTrace/scripts",
    "projects/SealAudit/README.md",
    "projects/SealAudit/src",
    "projects/SealAudit/scripts",
    "projects/SealAudit/tests",
    "results/SemCodebook/REPRODUCIBILITY_MANIFEST.json",
    "results/CodeDye/REPRODUCIBILITY_MANIFEST.json",
    "results/ProbeTrace/REPRODUCIBILITY_MANIFEST.json",
    "results/SealAudit/REPRODUCIBILITY_MANIFEST.json",
    "PRESERVED_RESULT_MANIFEST.jsonl",
    "PRESERVATION_SUMMARY.json",
    "scripts/build_result_manifest.py",
    "scripts/build_preserved_result_manifest.py",
    "scripts/check_project_snapshots.py",
    "scripts/check_preserved_results.py",
    "scripts/run_semcodebook_p1_miss_attribution.py",
    "scripts/examiner_check.py",
    "scripts/summarize_all.py",
]


KEY_ARTIFACTS = [
    "results/SemCodebook/artifacts/generated/semcodebook_whitebox_main_denominator_source_manifest_20260505.json",
    "results/SemCodebook/artifacts/generated/semcodebook_whitebox_model_sufficiency_gate_20260505.json",
    "results/CodeDye/artifacts/generated/codedye_positive_contamination_control_300_gate_20260505.json",
    "results/CodeDye/artifacts/generated/codedye_negative_control_300plus_gate_20260505.json",
    "results/ProbeTrace/artifacts/generated/apis300_live_attribution_evidence.json",
    "results/ProbeTrace/artifacts/generated/probetrace_abstain_aware_attribution_gate_20260506.json",
    "results/SealAudit/artifacts/generated/canonical_claim_surface_results.json",
    "results/SealAudit/artifacts/generated/sealaudit_coverage_risk_frontier_gate_20260505.json",
]

FORBIDDEN_TEXT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"private repository",
        r"progress mirror",
        r"MODEL_AND_KEY",
        r"cloud_server_authoritative",
        r"cloud_authority_root",
        r"blocked_pre_claim",
        r"review_ready=false",
        r"experiment_entry_allowed=false",
        r"remaining models / keys",
        r"expected final scale",
    ]
]

SECRET_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r"ghp_[A-Za-z0-9_]{20,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    ]
]

SCAN_EXCLUDE = {
    Path("scripts/repro_check.py"),
}


FORBIDDEN_PARTS = {"__pycache__", ".git"}
FORBIDDEN_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".bak",
    ".aux",
    ".log",
    ".out",
    ".toc",
    ".blg",
    ".bbl",
    ".idx",
    ".fls",
    ".fdb_latexmk",
    ".synctex.gz",
    ".zip",
    ".7z",
    ".rar",
}


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - human-facing check
        fail(f"Invalid JSON: {path.relative_to(ROOT)} ({exc})")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    missing = [p for p in REQUIRED_PATHS if not (ROOT / p).exists()]
    if missing:
        fail("Missing required paths:\n" + "\n".join(f"  - {p}" for p in missing))

    missing_artifacts = [p for p in KEY_ARTIFACTS if not (ROOT / p).exists()]
    if missing_artifacts:
        fail("Missing key result artifacts:\n" + "\n".join(f"  - {p}" for p in missing_artifacts))

    bad_files = []
    for path in ROOT.rglob("*"):
        rel_parts = set(path.relative_to(ROOT).parts)
        if rel_parts & FORBIDDEN_PARTS:
            bad_files.append(path)
        elif path.is_file() and path.suffix in FORBIDDEN_SUFFIXES:
            bad_files.append(path)
    if bad_files:
        formatted = "\n".join(f"  - {p.relative_to(ROOT)}" for p in bad_files[:40])
        fail(f"Repository contains generated/cache files:\n{formatted}")

    for manifest in [
        ROOT / "results/SemCodebook/REPRODUCIBILITY_MANIFEST.json",
        ROOT / "results/CodeDye/REPRODUCIBILITY_MANIFEST.json",
        ROOT / "results/ProbeTrace/REPRODUCIBILITY_MANIFEST.json",
        ROOT / "results/SealAudit/REPRODUCIBILITY_MANIFEST.json",
    ]:
        load_json(manifest)

    result_rows = []
    for line in (ROOT / "RESULT_MANIFEST.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            result_rows.append(json.loads(line))
    if len(result_rows) < 15:
        fail("RESULT_MANIFEST.jsonl has too few entries for the five-module dissertation.")
    for row in result_rows:
        path = ROOT / row["path"]
        if not path.exists():
            fail(f"Manifest artifact missing: {row['path']}")
        if row.get("module") != "Dissertation" and sha256(path) != row["sha256"]:
            fail(f"Manifest hash mismatch: {row['path']}")
        if isinstance(row.get("numerator"), int) and isinstance(row.get("denominator"), int) and row["denominator"] > 0:
            if "independence_unit" not in row:
                fail(f"Manifest row lacks independence unit: {row['module']} / {row['claim']}")
        if row.get("ci_required"):
            for field in ("rate", "ci95_low", "ci95_high", "ci_method"):
                if field not in row:
                    fail(f"Manifest row lacks statistical metadata '{field}': {row['module']} / {row['claim']}")

    expected_rates = {
        ("CodeMarkBench", "Canonical executable run inventory"): (140, 140),
        ("SemCodebook", "Positive recovery"): (23342, 24000),
        ("SemCodebook", "Negative-control hits"): (0, 48000),
        ("CodeDye", "Sparse null-audit signal boundary"): (6, 300),
        ("CodeDye", "Positive contamination control"): (170, 300),
        ("CodeDye", "Negative control"): (0, 300),
        ("ProbeTrace", "APIS-300 attribution evidence"): (300, 300),
        ("ProbeTrace", "False-owner and abstain-aware controls"): (0, 1200),
        ("SealAudit", "Marker-hidden canonical triage surface"): (81, 960),
        ("SealAudit", "Coverage-risk frontier"): (81, 960),
    }
    by_key = {(row["module"], row["claim"]): row for row in result_rows}
    for key, (numerator, denominator) in expected_rates.items():
        row = by_key.get(key)
        if row is None:
            fail(f"Missing manifest claim: {key}")
        if row.get("numerator") != numerator or row.get("denominator") != denominator:
            fail(f"Unexpected manifest numerator/denominator for {key}: {row.get('numerator')}/{row.get('denominator')}")

    sem_row = by_key.get(("SemCodebook", "White-box denominator and source manifest"))
    if not sem_row or sem_row.get("denominator") != 72000:
        fail("SemCodebook 72,000-row denominator is not bound in RESULT_MANIFEST.jsonl.")

    transfer_row = by_key.get(("ProbeTrace", "Transfer validation results"))
    if not transfer_row or transfer_row.get("primary_independence_unit") != "task_cluster":
        fail("ProbeTrace transfer support row must record task-cluster primary independence unit.")
    if not transfer_row.get("support_only") or transfer_row.get("claim_bearing") is not False:
        fail("ProbeTrace transfer rows must be support-only and non-claim-bearing.")
    codedye_support = by_key.get(("CodeDye", "Support row exclusion inventory"))
    if not codedye_support or not codedye_support.get("support_only") or codedye_support.get("claim_bearing") is not False:
        fail("CodeDye support inventory must be support-only and non-claim-bearing.")

    text_files = [
        p
        for p in ROOT.rglob("*")
        if p.is_file()
        and p.relative_to(ROOT) not in SCAN_EXCLUDE
        and p.stat().st_size < 5_000_000
        and p.suffix.lower() in {".md", ".py", ".json", ".jsonl", ".yaml", ".yml", ".tex", ".bib", ".txt"}
    ]
    for path in text_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in FORBIDDEN_TEXT_PATTERNS:
            if pattern.search(text):
                fail(f"Forbidden stale/internal wording in {path.relative_to(ROOT)}: {pattern.pattern}")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                fail(f"Secret-like token found in {path.relative_to(ROOT)}")

    pdf = ROOT / "dissertation/WatermarkScope_FYP_Dissertation.pdf"
    if pdf.stat().st_size < 100_000:
        fail("Dissertation PDF is unexpectedly small.")

    print("[OK] Repository integrity check passed.")
    print(f"[OK] Root: {ROOT}")
    print(f"[OK] Required paths: {len(REQUIRED_PATHS)}")
    print(f"[OK] Key artifacts: {len(KEY_ARTIFACTS)}")


if __name__ == "__main__":
    main()
