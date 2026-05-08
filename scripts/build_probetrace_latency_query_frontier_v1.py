from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
APIS = ROOT / "results/ProbeTrace/artifacts/generated/apis300_live_attribution_evidence.json"
OUT = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_latency_query_frontier_v1_{DATE}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "count": len(values),
        "mean": round(mean(values), 4),
        "median": round(median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def main() -> int:
    payload = json.loads(APIS.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    records = records if isinstance(records, list) else []
    query_values = [float(row.get("provider_trace_request_count", row.get("query_count", 0)) or 0) for row in records if isinstance(row, dict)]
    latency_values = [float(row.get("latency_seconds", row.get("latency_overhead", 0)) or 0) for row in records if isinstance(row, dict)]
    missing_query = sum(1 for row in records if isinstance(row, dict) and row.get("provider_trace_request_count", row.get("query_count")) in (None, ""))
    missing_latency = sum(1 for row in records if isinstance(row, dict) and row.get("latency_seconds", row.get("latency_overhead")) in (None, ""))
    out = {
        "schema_version": "probetrace_latency_query_frontier_v1",
        "generated_at_utc": utc_now(),
        "claim_bearing": False,
        "gate_pass": len(records) == 300,
        "source_artifact": str(APIS.relative_to(ROOT)),
        "record_count": len(records),
        "query_summary": summary(query_values),
        "latency_summary": summary(latency_values),
        "missing_query_count": missing_query,
        "missing_latency_count": missing_latency,
        "paper_requirement": "Main text must report query/latency overhead as a cost frontier. Missing latency fields are a disclosure item, not a reason to infer zero cost.",
        "formal_multi_owner_claim_allowed": False,
        "blockers": [] if len(records) == 300 else ["apis300_record_count_drift"],
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {OUT.relative_to(ROOT)}")
    return 0 if out["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
