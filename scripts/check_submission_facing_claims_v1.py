from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCAN_PATHS = [
    ROOT / "README.md",
    ROOT / "CLAIM_BOUNDARIES.md",
    ROOT / "docs" / "RESULTS_SUMMARY.md",
    ROOT / "docs" / "SUBMISSION_NOTES.md",
    ROOT / "docs" / "RUNBOOK.md",
]

FORBIDDEN = [
    re.compile(r"\b6/300\b"),
    re.compile(r"\b81/960\b"),
    re.compile(r"\b879/960\b"),
    re.compile(r"not multi-owner", re.IGNORECASE),
    re.compile(r"provider-general authorship", re.IGNORECASE),
    re.compile(r"FYP examination", re.IGNORECASE),
    re.compile(r"Final Year Project", re.IGNORECASE),
    re.compile(r"dissertation-level claims", re.IGNORECASE),
]

REQUIRED = {
    "README.md": [
        "bestpaper_ready_by_strict_artifact_gate",
        "ProbeTrace",
        "6,000 multi-owner rows",
        "4/300 sparse audit signals",
    ],
    "CLAIM_BOUNDARIES.md": [
        "DeepSeek-only five-owner",
        "no high-recall detector claim",
        "no security certificate",
    ],
    "docs/RESULTS_SUMMARY.md": [
        "4 sparse signals",
        "320 decisive rows",
        "0/5,250 false-attribution controls",
    ],
}


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    for path in SCAN_PATHS:
        if not path.exists():
            fail(f"Missing submission-facing file: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN:
            if pattern.search(text):
                fail(f"Stale or unsafe submission-facing wording in {path.relative_to(ROOT)}: {pattern.pattern}")
    for rel, needles in REQUIRED.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                fail(f"Required current-claim wording missing from {rel}: {needle}")
    print("[OK] Submission-facing claim wording verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
