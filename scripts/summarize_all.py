from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "RESULT_MANIFEST.jsonl"
MUTABLE_PRESENTATION_MODULES = {"Dissertation"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if not MANIFEST.exists():
        raise SystemExit("RESULT_MANIFEST.jsonl is missing. Run scripts/build_result_manifest.py first.")

    rows = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    print("WatermarkScope FYP result manifest")
    print("=" * 30)
    current_module = None
    for row in rows:
        module = row["module"]
        if module != current_module:
            current_module = module
            print(f"\n[{module}]")
        path = ROOT / row["path"]
        mutable_presentation = module in MUTABLE_PRESENTATION_MODULES
        ok = path.exists() and (mutable_presentation or sha256(path) == row["sha256"])
        denom = row.get("denominator")
        numer = row.get("numerator")
        rate = ""
        support_only = row.get("support_only") or row.get("claim_bearing") is False
        if support_only:
            support_n = row.get("support_denominator", denom)
            if isinstance(support_n, int):
                if row["module"] == "ProbeTrace" and row.get("primary_independence_unit"):
                    rate = (
                        f" ({support_n} support rows; "
                        f"primary unit {row['primary_independence_unit']}, "
                        f"{row.get('primary_task_clusters')} clusters; not main denominator)"
                    )
                else:
                    rate = f" ({support_n} support rows excluded from main denominator)"
        elif isinstance(denom, int) and isinstance(numer, int) and denom:
            rate = f" ({numer}/{denom} = {numer / denom:.2%})"
            if "ci95_low" in row and "ci95_high" in row:
                rate += f"; 95% CI {row['ci95_low']:.2%}-{row['ci95_high']:.2%}"
        elif isinstance(denom, int):
            rate = f" (denominator {denom})"
        status = "OK" if ok and not mutable_presentation else "PRESENTATION-DRIFT" if ok else "MISMATCH"
        print(f"- {status}: {row['claim']}{rate}")
        if row.get("primary_independence_unit"):
            print(f"  independence: {row['primary_independence_unit']} ({row.get('primary_task_clusters')} clusters)")
        print(f"  {row['path']}")

    if any(
        not (
            (ROOT / row["path"]).exists()
            and (row.get("module") in MUTABLE_PRESENTATION_MODULES or sha256(ROOT / row["path"]) == row["sha256"])
        )
        for row in rows
    ):
        raise SystemExit("One or more manifest entries failed hash verification.")

    print(f"\nVerified {len(rows)} manifest entries.")


if __name__ == "__main__":
    main()
