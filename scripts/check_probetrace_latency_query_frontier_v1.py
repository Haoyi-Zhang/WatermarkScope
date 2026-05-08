from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260507"
ARTIFACT = ROOT / f"results/ProbeTrace/artifacts/generated/probetrace_latency_query_frontier_v1_{DATE}.json"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def main() -> int:
    if not ARTIFACT.exists():
        fail("ProbeTrace latency/query frontier is missing.")
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "probetrace_latency_query_frontier_v1":
        fail("Unexpected ProbeTrace latency/query schema.")
    if payload.get("claim_bearing") is not False:
        fail("ProbeTrace latency/query frontier must be non-claim-bearing.")
    if payload.get("gate_pass") is not True or payload.get("record_count") != 300:
        fail("ProbeTrace latency/query frontier must bind APIS-300.")
    if payload.get("formal_multi_owner_claim_allowed") is not False:
        fail("ProbeTrace latency/query frontier must not allow multi-owner claim.")
    print("[OK] ProbeTrace latency/query frontier verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
