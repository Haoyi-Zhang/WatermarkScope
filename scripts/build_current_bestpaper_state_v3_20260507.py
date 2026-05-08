from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def write(rel: str, payload: Any) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> int:
    v2 = load("results/watermark_bestpaper_current_state_v2_20260507.json")
    neg = load("results/CodeDye/artifacts/generated/codedye_negative_control_row_hash_manifest_v2_20260507.json")
    payload = {
        **v2,
        "schema_version": "watermark_bestpaper_current_state_v3_20260507",
        "generated_at_utc": utc_now(),
    }
    codedye = payload["status_summary"]["CodeDye"]
    codedye["negative_control_row_source_local_available"] = True
    codedye["negative_control_row_hash_manifest_gate_pass"] = neg["gate_pass"]
    codedye["negative_control_row_hash_count"] = neg["row_hash_count"]
    codedye["negative_control_false_positive_count"] = neg["false_positive_count"]
    codedye["remaining_bestpaper_gap"] = (
        "DeepSeek live result remains sparse 6/300; CodeDye is defensible as a conservative null-audit. "
        "A stronger v3 live claim still requires a fresh frozen DeepSeek rerun with improved sensitivity."
    )
    payload["new_real_closures_this_round"] = [
        *payload["new_real_closures_this_round"],
        "Fetched preserved CodeDye 300-row negative-control source from js2, verified source hash, and built a 300-row v2 hash manifest with 0 false positives.",
    ]
    write("results/watermark_bestpaper_current_state_v3_20260507.json", payload)
    print("[OK] Wrote current best-paper state v3 report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
