from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "PRESERVED_RESULT_MANIFEST.jsonl"
EXTERNAL_LARGE_ARTIFACTS = ROOT / "EXTERNAL_LARGE_ARTIFACTS.json"

MUTABLE_PRESENTATION_SCOPES = {
    "dissertation_output",
    "examiner_documentation",
    "repository_claim_binding",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not MANIFEST.exists():
        fail("PRESERVED_RESULT_MANIFEST.jsonl is missing. Run scripts/build_preserved_result_manifest.py once to lock current results.")

    rows = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        fail("PRESERVED_RESULT_MANIFEST.jsonl is empty.")
    external_rows = {}
    if EXTERNAL_LARGE_ARTIFACTS.exists():
        for row in json.loads(EXTERNAL_LARGE_ARTIFACTS.read_text(encoding="utf-8")):
            external_rows[row["path"]] = row

    missing: list[str] = []
    changed: list[str] = []
    checked = 0
    skipped = 0
    external_missing = 0
    for row in rows:
        if row.get("preservation_scope") in MUTABLE_PRESENTATION_SCOPES:
            skipped += 1
            continue
        rel = row["path"]
        path = ROOT / rel
        if not path.exists():
            external = external_rows.get(rel)
            if external and external.get("bytes") == row.get("bytes") and external.get("sha256") == row.get("sha256"):
                external_missing += 1
                continue
            missing.append(rel)
            continue
        checked += 1
        if path.stat().st_size != row["bytes"] or sha256(path) != row["sha256"]:
            changed.append(rel)

    if missing or changed:
        lines = []
        if missing:
            lines.append("Missing preserved files:")
            lines.extend(f"  - {p}" for p in missing[:40])
        if changed:
            lines.append("Changed preserved files:")
            lines.extend(f"  - {p}" for p in changed[:40])
        fail("\n".join(lines))

    print(f"[OK] Preserved result manifest verified: {checked} result files unchanged.")
    if external_missing:
        print(f"[OK] External large artifacts registered but not stored in this checkout: {external_missing}.")
    print(f"[OK] Presentation/documentation rows skipped: {skipped}.")
    print("[OK] New additive result files are allowed; existing preserved result files remain immutable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
