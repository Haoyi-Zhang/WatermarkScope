from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_DOCS = [
    "README.md",
    "CLAIM_BOUNDARIES.md",
    "docs/EXAMINER_GUIDE.md",
    "docs/METHOD_INDEX.md",
    "docs/RESULTS_SUMMARY.md",
    "docs/TRACEABILITY_MATRIX.md",
    "RESULT_MANIFEST.jsonl",
]


EXPECTED_MODULES = {
    "CodeMarkBench",
    "SemCodebook",
    "CodeDye",
    "ProbeTrace",
    "SealAudit",
}


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    print("WatermarkScope viva check")
    print("=" * 25)

    missing_docs = [path for path in REQUIRED_DOCS if not (ROOT / path).exists()]
    if missing_docs:
        fail("Missing viva-facing files:\n" + "\n".join(f"  - {path}" for path in missing_docs))
    print(f"[OK] Viva-facing documents present: {len(REQUIRED_DOCS)}")

    manifest_path = ROOT / "RESULT_MANIFEST.jsonl"
    rows = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    modules = {row.get("module") for row in rows if row.get("module") != "Dissertation"}
    if not EXPECTED_MODULES.issubset(modules):
        fail(f"Manifest missing modules: {sorted(EXPECTED_MODULES - modules)}")
    print(f"[OK] Result manifest covers modules: {', '.join(sorted(EXPECTED_MODULES))}")

    missing_fields = [
        index
        for index, row in enumerate(rows, start=1)
        if row.get("module") != "Dissertation" and not (row.get("path") and row.get("sha256"))
    ]
    if missing_fields:
        fail(f"Manifest rows missing path or sha256: {missing_fields[:8]}")
    print(f"[OK] Manifest rows are readable and hash-addressed: {len(rows)}")

    key_artifacts = [
        "README.md",
        "CLAIM_BOUNDARIES.md",
        "docs/TRACEABILITY_MATRIX.md",
        "docs/RESULTS_SUMMARY.md",
        "RESULT_MANIFEST.jsonl",
        "scripts/viva_check.py",
    ]
    missing_artifacts = [path for path in key_artifacts if not (ROOT / path).exists()]
    if missing_artifacts:
        fail("Missing key inspection artifacts:\n" + "\n".join(f"  - {path}" for path in missing_artifacts))
    print(f"[OK] Key inspection artifacts present: {len(key_artifacts)}")

    traceability = (ROOT / "docs/TRACEABILITY_MATRIX.md").read_text(encoding="utf-8")
    for term in ["CLAIM_BOUNDARIES.md", "ACTIVE_CLAIM_SURFACE.json", "manifest"]:
        if term not in traceability:
            fail(f"Traceability matrix does not mention {term}")
    print("[OK] Traceability matrix links claims, boundaries, manifests, and artifacts")

    boundaries = (ROOT / "CLAIM_BOUNDARIES.md").read_text(encoding="utf-8")
    for phrase in ["not", "boundary", "claim"]:
        if phrase.lower() not in boundaries.lower():
            fail(f"Claim boundary file lacks expected wording: {phrase}")
    print("[OK] Claim boundaries are present for viva interpretation")

    print("\n[OK] Viva check passed. This is a quick inspection check, not a full GPU/API rerun.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
