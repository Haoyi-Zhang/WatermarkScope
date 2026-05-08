from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = {
    "SemCodebook": ROOT / "docs/papers/SemCodebook.md",
    "CodeDye": ROOT / "docs/papers/CodeDye.md",
    "ProbeTrace": ROOT / "docs/papers/ProbeTrace.md",
    "SealAudit": ROOT / "docs/papers/SealAudit.md",
}
INDEX = ROOT / "docs/papers/README.md"

REQUIRED = {
    "SemCodebook": ["23342/24000", "0/48000", "72,000", "no-retry"],
    "CodeDye": ["4/300", "170/300", "0/300", "not a high-recall"],
    "ProbeTrace": ["6,000", "750/750", "0/5,250", "AUC 1.0", "DeepSeek-only"],
    "SealAudit": ["320/960", "0/960", "diagnostic-only", "not an automatic safety classifier"],
}

FORBIDDEN = [
    re.compile(r"provider-general attribution[^.\n]*(is|are) supported", re.IGNORECASE),
    re.compile(r"(is|as|supports|proves|provides)\s+(a\s+)?high-recall contamination detector", re.IGNORECASE),
    re.compile(r"(is|as|supports|proves|provides)\s+(a\s+)?security certificate", re.IGNORECASE),
    re.compile(r"(is|as|supports|proves|provides)\s+(a\s+)?harmlessness guarantee", re.IGNORECASE),
    re.compile(r"(is|as|supports|proves|provides)\s+(a\s+)?universal semantic watermark", re.IGNORECASE),
]


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not INDEX.exists():
        fail("Paper brief index missing.")
    for project, path in DOCS.items():
        if not path.exists():
            fail(f"Paper brief missing: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        for needle in REQUIRED[project]:
            if needle not in text:
                fail(f"{project} brief missing required phrase: {needle}")
        for pattern in FORBIDDEN:
            matches = [m.group(0) for m in pattern.finditer(text)]
            if matches:
                for match in matches:
                    fail(f"{project} brief has unsafe overclaim phrase: {match}")
    print("[OK] Submission paper briefs verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
