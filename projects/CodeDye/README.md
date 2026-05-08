# CodeDye

CodeDye is the black-box contamination null-audit module in the WatermarkScope FYP lifecycle. This packaged snapshot contains the audit implementation code used by the dissertation and the result artifacts referenced from `../../results/CodeDye/`.

## Role In The FYP

CodeDye studies how a benchmark curator can preserve black-box audit evidence without turning sparse signals into unsupported contamination claims. The protocol records prompt hashes, raw response hashes, structured payload hashes, detector versions, threshold versions, and explicit control roles.

## Current Dissertation Result Surface

- DeepSeek live audit rows: 300.
- Sparse audit signals: 6/300 = 2.00%.
- Positive contamination controls: 170/300.
- Negative controls: 0/300.
- Support/public/stress rows excluded from the main denominator: 806.

## Code Layout

- `scripts/`: audit, aggregation, evidence-sync, baseline/control, and attack-matrix utilities.
- `tests/`: regression tests for attack matrix and claim-promotion scaffolds.
- `../../RESULT_MANIFEST.jsonl`: FYP-facing claim-to-evidence summary with artifact hashes.

## Result Artifacts

Primary artifacts are stored outside this code snapshot at:

```text
../../results/CodeDye/artifacts/generated/
```

The top-level `RESULT_MANIFEST.jsonl` records the exact files and SHA-256 hashes used by the dissertation.

## Claim Boundary

Allowed claim: conservative curator-side null-audit with sparse evidence and calibrated controls.

Forbidden claim: contamination accusation, contamination prevalence estimate, or high-recall detection.
