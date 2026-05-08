from __future__ import annotations

from build_blackbox_final_claim_locks_v1 import build_sealaudit, write_json, write_md


def main() -> int:
    payload = build_sealaudit()
    write_json("results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v1_20260507.json", payload)
    write_md("results/SealAudit/artifacts/generated/sealaudit_final_claim_lock_v1_20260507.md", "SealAudit Final Claim Lock v1", payload)
    print("[OK] Wrote SealAudit final claim-lock v1.")
    return 0 if payload["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
