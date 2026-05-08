# SealAudit

SealAudit is the watermark-as-security-object triage module in the WatermarkScope FYP lifecycle. This packaged snapshot contains the audit implementation code used by the dissertation and the result artifacts referenced from `../../results/SealAudit/`.

## Role In The FYP

SealAudit studies whether watermark mechanisms should be audited as security-relevant objects. The dissertation reports marker-hidden selective triage with explicit needs-review and unsafe-pass boundaries.

## Current Dissertation Result Surface

- Canonical cases: 320.
- Marker-hidden claim rows: 960.
- Decisive outcomes: 81/960 = 8.44%.
- Needs-review outcomes: 879/960.
- Unsafe-pass outcomes: 0/960.
- Marker-visible rows: 320 diagnostic-only rows excluded from the main denominator.

## Code Layout

- `src/sealaudit/`: benchmark and audit helpers.
- `scripts/`: rubric, adjudication, baseline, attack/statistics, and benchmark builders.
- `tests/`: benchmark and audit logic tests.
- `../../RESULT_MANIFEST.jsonl`: FYP-facing claim-to-evidence summary with artifact hashes.

## Result Artifacts

Primary artifacts are stored outside this code snapshot at:

```text
../../results/SealAudit/artifacts/generated/
```

The top-level `RESULT_MANIFEST.jsonl` records the exact files and SHA-256 hashes used by the dissertation.

## Claim Boundary

Allowed claim: conservative marker-hidden selective triage with explicit abstention and unsafe-pass tracking.

Forbidden claim: automatic safety classifier, harmlessness certificate, or security certificate for all watermarking mechanisms.
