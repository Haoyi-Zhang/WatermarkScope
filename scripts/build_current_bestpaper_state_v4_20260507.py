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
    v3 = load("results/watermark_bestpaper_current_state_v3_20260507.json")
    probe_pkg = load("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_canonical_input_package_20260507.json")
    probe_gate = load("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_prerun_gate_20260507.json")
    payload = {
        **v3,
        "schema_version": "watermark_bestpaper_current_state_v4_20260507",
        "generated_at_utc": utc_now(),
    }
    probe = payload["status_summary"]["ProbeTrace"]
    probe["status"] = "single_owner_claim_safe_and_multi_owner_deepseek_input_package_ready"
    probe["multi_owner_deepseek_prerun_gate_pass"] = probe_gate["gate_pass"]
    probe["multi_owner_canonical_input_rows"] = probe_pkg["row_count"]
    probe["multi_owner_target_counts"] = probe_pkg["control_role_counts"]
    probe["multi_owner_split_counts"] = probe_pkg["split_counts"]
    probe["remaining_bestpaper_gap"] = (
        "Multi-owner generalization still requires fresh DeepSeek provider outputs and postrun promotion. "
        "The 6000-row canonical input package and prerun gate are ready and preserve the single-owner floor."
    )
    payload["new_real_closures_this_round"] = [
        *payload["new_real_closures_this_round"],
        "Built ProbeTrace 6000-row DeepSeek multi-owner canonical input package with 5 owners, 3 languages, 750 positives, 3000 wrong-owner controls, and 2250 null/random/same-provider controls.",
    ]
    write("results/watermark_bestpaper_current_state_v4_20260507.json", payload)
    print("[OK] Wrote current best-paper state v4 report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
