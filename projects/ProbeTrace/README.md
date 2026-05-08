# ProbeTrace

ProbeTrace is the active-owner attribution module in the WatermarkScope FYP lifecycle. This packaged snapshot contains the attribution implementation code used by the dissertation and the result artifacts referenced from `../../results/ProbeTrace/`.

## Role In The FYP

ProbeTrace studies source-bound attribution under a fixed active owner registry. The protocol uses owner-bound witnesses, control owners, commitment evidence, and transfer receipts. It is not a universal authorship detector.

## Current Dissertation Result Surface

- APIS attribution records: 300/300 observed successes in the scoped active-owner setting.
- False-owner controls: 0/1,200 false attributions.
- Transfer validation rows: 900 receipt-complete rows across SFT, LoRA, and quantized students.
- Scope: single active owner and source-bound split.

## Code Layout

- `scripts/`: attribution, baseline, transfer, and aggregation utilities.
- `../../RESULT_MANIFEST.jsonl`: FYP-facing claim-to-evidence summary with artifact hashes.
- `external_sources_manifest.json`: third-party/source provenance metadata.

## Result Artifacts

Primary artifacts are stored outside this code snapshot at:

```text
../../results/ProbeTrace/artifacts/generated/
```

The top-level `RESULT_MANIFEST.jsonl` records the exact files and SHA-256 hashes used by the dissertation.

## Examiner Check

From the repository root, run:

```bash
python scripts/examiner_check.py
```

This verifies the ProbeTrace artifact bindings together with the other WatermarkScope lifecycle modules. It is an integrity check, not a full provider/API rerun.

## Claim Boundary

Allowed claim: scoped active-owner/source-bound attribution under the evaluated protocol.

Forbidden claim: provider-general authorship, multi-owner attribution, or unbounded transfer generalization.
