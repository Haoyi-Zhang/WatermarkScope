from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/watermark_submission_main_table_manifest_v1_20260508.json"
OUT_MD = ROOT / "results/watermark_submission_main_table_manifest_v1_20260508.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact(rel: str) -> dict:
    path = ROOT / rel
    if not path.exists():
        raise FileNotFoundError(rel)
    return {"path": rel, "sha256": sha256(path), "bytes": path.stat().st_size}


def main() -> int:
    if OUT.exists() or OUT_MD.exists():
        raise FileExistsError("refusing_to_overwrite_submission_main_table_manifest_v1")
    rows = [
        {
            "project": "SemCodebook",
            "table_role": "whitebox_main_and_ablation",
            "claim_bearing": True,
            "primary_result": "23342/24000 positive recoveries; 0/48000 negative-control hits; 72000 admitted records",
            "artifacts": [
                artifact("results/SemCodebook/artifacts/generated/semcodebook_final_claim_lock_v1_20260507.json"),
                artifact("results/SemCodebook/artifacts/generated/semcodebook_whitebox_model_sufficiency_gate_20260505.json"),
                artifact("results/SemCodebook/artifacts/generated/semcodebook_generation_changing_ablation_promotion_gate_20260505.json"),
            ],
            "forbidden_table_uses": ["no-retry natural-generation guarantee", "validator-repair main claim"],
        },
        {
            "project": "CodeDye",
            "table_role": "deepseek_sparse_null_audit",
            "claim_bearing": True,
            "primary_result": "4/300 sparse DeepSeek audit signals; 170/300 positive-control hits; 0/300 negative-control hits",
            "artifacts": [
                artifact("results/CodeDye/artifacts/generated/codedye_final_claim_lock_v2_20260507.json"),
                artifact("results/CodeDye/artifacts/generated/codedye_v3_postrun_promotion_gate_v1_20260507_deepseek300_topup_v5_postrun.json"),
                artifact("results/CodeDye/artifacts/generated/codedye_positive_miss_taxonomy_v2_20260507.json"),
                artifact("results/CodeDye/artifacts/generated/codedye_negative_control_row_hash_manifest_v2_20260507.json"),
            ],
            "forbidden_table_uses": ["high-recall detection", "provider accusation", "contamination prevalence"],
        },
        {
            "project": "ProbeTrace",
            "table_role": "deepseek_multi_owner_attribution",
            "claim_bearing": True,
            "primary_result": "6000 multi-owner rows; 750/750 positives; 0/5250 false-attribution controls; AUC 1.0",
            "artifacts": [
                artifact("results/ProbeTrace/artifacts/generated/probetrace_final_claim_lock_v2_20260507.json"),
                artifact("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_postrun_promotion_gate_v2_20260507.json"),
                artifact("results/ProbeTrace/artifacts/generated/probetrace_multi_owner_deepseek_live_score_vectors_20260507_merged_v1_manifest.json"),
                artifact("results/ProbeTrace/artifacts/generated/probetrace_latency_query_frontier_v1_20260507.json"),
                artifact("results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_scan_v1_20260507.json"),
            ],
            "forbidden_table_uses": ["provider-general attribution", "cross-provider attribution", "unbounded transfer"],
        },
        {
            "project": "SealAudit",
            "table_role": "deepseek_marker_hidden_selective_triage",
            "claim_bearing": True,
            "primary_result": "320/960 decisive marker-hidden rows; 0/960 unsafe-pass rows; 320 visible-marker rows diagnostic-only",
            "artifacts": [
                artifact("results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v2_20260507.json"),
                artifact("results/SealAudit/artifacts/generated/sealaudit_v5_postrun_promotion_gate_v2_20260507.json"),
                artifact("results/SealAudit/artifacts/generated/sealaudit_v5_coverage_risk_frontier_v2_20260507.json"),
                artifact("results/SealAudit/artifacts/generated/sealaudit_v5_threshold_sensitivity_v2_20260507.json"),
                artifact("results/SealAudit/artifacts/generated/sealaudit_v5_visible_marker_diagnostic_boundary_v2_20260507.json"),
            ],
            "forbidden_table_uses": ["security certificate", "harmlessness guarantee", "automatic safety classifier"],
        },
    ]
    payload = {
        "schema_version": "watermark_submission_main_table_manifest_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "purpose": "Bind current submission-facing main tables to final claim-lock artifacts and prevent stale result reuse.",
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Watermark Submission Main Table Manifest v1", ""]
    for row in rows:
        lines.extend(
            [
                f"## {row['project']}",
                f"- Table role: `{row['table_role']}`",
                f"- Primary result: {row['primary_result']}",
                "- Artifacts:",
            ]
        )
        lines.extend(f"  - `{item['path']}`" for item in row["artifacts"])
        lines.extend(["- Forbidden table uses:"])
        lines.extend(f"  - {item}" for item in row["forbidden_table_uses"])
        lines.append("")
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    print(f"[OK] Wrote {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
