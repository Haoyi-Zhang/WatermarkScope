from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"

REQUIRED = [
    "results/SemCodebook/artifacts/generated/semcodebook_family_scale_sufficiency_table_v1_20260507.json",
    "results/CodeDye/artifacts/generated/codedye_audit_utility_second_pass_v1_20260507.json",
    "results/ProbeTrace/artifacts/generated/probetrace_margin_second_pass_audit_v1_20260507.json",
    "results/SealAudit/artifacts/generated/sealaudit_needs_review_second_pass_taxonomy_v1_20260507.json",
    "results/bestpaper_second_pass_summary_v1_20260507.json",
]


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def main() -> int:
    missing = [path for path in REQUIRED if not (ROOT / path).exists()]
    if missing:
        fail("Missing second-pass artifacts:\n" + "\n".join(f"  - {path}" for path in missing))

    sem = load(REQUIRED[0])
    if len(sem.get("family_table", {})) < 5 or len(sem.get("scale_table", {})) < 4:
        fail("SemCodebook family/scale table does not cover the required breadth.")

    code = load(REQUIRED[1])
    if code.get("claim_bearing") is not False:
        fail("CodeDye second-pass utility must remain non-claim-bearing.")
    if code["utility_surface"]["final_signal_count"] != 6:
        fail("CodeDye second-pass utility must preserve the 6/300 signal boundary.")

    probe = load(REQUIRED[2])
    if probe["row_count"] != 300:
        fail("ProbeTrace second-pass audit must cover 300 row-level records.")
    for name, summary in probe["control_score_summaries"].items():
        if summary["owner_id_emitted"] != 0 or summary["false_attribution"] != 0:
            fail(f"ProbeTrace control emitted owner or false attribution: {name}")

    seal = load(REQUIRED[3])
    if seal["needs_review_count"] != 879:
        fail("SealAudit second-pass taxonomy must preserve 879 needs-review rows.")

    summary = load(REQUIRED[4])
    if summary.get("claim_bearing") is not False or len(summary.get("remaining_p1", [])) != 4:
        fail("Second-pass summary must remain non-claim-bearing and list four remaining P1 items.")

    print("[OK] Best-paper second-pass artifacts verified.")
    print("[OK] Real computable closure added without promoting unfinished claims.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
