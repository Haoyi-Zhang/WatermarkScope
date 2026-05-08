from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "results/watermark_submission_main_table_manifest_v1_20260508.json"
ARTIFACT_MD = ROOT / "results/watermark_submission_main_table_manifest_v1_20260508.md"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists() or not ARTIFACT_MD.exists():
        fail("Submission main-table manifest artifacts are missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "watermark_submission_main_table_manifest_v1":
        fail("Unexpected main-table manifest schema.")
    if payload.get("claim_bearing") is not False:
        fail("Main-table manifest must be non-claim-bearing.")
    rows = payload.get("rows", [])
    projects = {row.get("project") for row in rows}
    if projects != {"SemCodebook", "CodeDye", "ProbeTrace", "SealAudit"}:
        fail(f"Unexpected projects in main-table manifest: {sorted(projects)}")
    expected_fragments = {
        "SemCodebook": "23342/24000",
        "CodeDye": "4/300",
        "ProbeTrace": "6000 multi-owner",
        "SealAudit": "320/960",
    }
    for row in rows:
        project = row["project"]
        if expected_fragments[project] not in row.get("primary_result", ""):
            fail(f"{project} primary result missing expected current result fragment.")
        if not row.get("claim_bearing"):
            fail(f"{project} row should identify the table role as claim-bearing.")
        if not row.get("forbidden_table_uses"):
            fail(f"{project} lacks forbidden table uses.")
        for item in row.get("artifacts", []):
            path = ROOT / item["path"]
            if not path.exists():
                fail(f"Referenced table artifact missing: {item['path']}")
            if item.get("bytes") != path.stat().st_size or item.get("sha256") != sha256(path):
                fail(f"Referenced table artifact hash/size drifted: {item['path']}")
    print("[OK] Watermark submission main-table manifest verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
