from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "PRESERVED_RESULT_MANIFEST.jsonl"
SUMMARY = ROOT / "PRESERVATION_SUMMARY.json"

PRESERVED_ROOTS = [
    ROOT / "results",
    ROOT / "projects" / "CodeMarkBench" / "results",
]

ADDITIONAL_PRESERVED_FILES = [
    ROOT / "RESULT_MANIFEST.jsonl",
    ROOT / "CLAIM_BOUNDARIES.md",
    ROOT / "docs" / "RESULTS_SUMMARY.md",
    ROOT / "dissertation" / "WatermarkScope_FYP_Dissertation.pdf",
]

EXCLUDE_PARTS = {".git", "__pycache__"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".tmp"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def should_preserve(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE_PARTS for part in rel.parts):
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    return path.is_file()


def preservation_scope(path: Path) -> str:
    rel = path.relative_to(ROOT)
    parts = rel.parts
    if parts[:1] == ("results",):
        return f"project_result:{parts[1]}" if len(parts) > 1 else "project_result"
    if parts[:3] == ("projects", "CodeMarkBench", "results"):
        return "benchmark_result:CodeMarkBench"
    if parts[:1] == ("dissertation",):
        return "dissertation_output"
    if parts[:1] == ("docs",):
        return "examiner_documentation"
    return "repository_claim_binding"


def iter_preserved_files() -> list[Path]:
    files: dict[Path, None] = {}
    for root in PRESERVED_ROOTS:
        if root.exists():
            for path in root.rglob("*"):
                if should_preserve(path):
                    files[path] = None
    for path in ADDITIONAL_PRESERVED_FILES:
        if path.exists() and should_preserve(path):
            files[path] = None
    return sorted(files)


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for path in iter_preserved_files():
        stat = path.stat()
        rows.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "bytes": stat.st_size,
                "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "suffix": path.suffix.lower(),
                "preservation_scope": preservation_scope(path),
                "policy": "do_not_delete_or_overwrite; future refinements must create additive versioned artifacts",
            }
        )

    OUT.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )

    by_scope: dict[str, int] = {}
    by_suffix: dict[str, int] = {}
    total_bytes = 0
    for row in rows:
        by_scope[row["preservation_scope"]] = by_scope.get(row["preservation_scope"], 0) + 1
        by_suffix[row["suffix"] or "<none>"] = by_suffix.get(row["suffix"] or "<none>", 0) + 1
        total_bytes += int(row["bytes"])

    SUMMARY.write_text(
        json.dumps(
            {
                "created_at_utc": created_at,
                "manifest": OUT.name,
                "preserved_file_count": len(rows),
                "total_bytes": total_bytes,
                "policy": "Existing result artifacts are immutable for continuation work. Add new artifacts instead of overwriting old evidence.",
                "by_scope": dict(sorted(by_scope.items())),
                "by_suffix": dict(sorted(by_suffix.items())),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[OK] Wrote {OUT.relative_to(ROOT)} with {len(rows)} preserved files.")
    print(f"[OK] Wrote {SUMMARY.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
