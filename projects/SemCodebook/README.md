# SemCodebook

SemCodebook is the white-box provenance-watermark module in the WatermarkScope FYP lifecycle. This packaged snapshot contains the implementation code used by the dissertation and the result artifacts referenced from `../../results/SemCodebook/`.

## Role In The FYP

SemCodebook studies whether structured program carriers can preserve recoverable provenance under code rewrites. It uses typed AST, CFG, and SSA carrier families, keyed scheduling, schedule commitments, and ECC-style recovery. The module answers the white-box part of the thesis: when local model access and admitted model cells are available, a provenance watermark can be evaluated with structured recovery rather than only token-level detection.

## Current Dissertation Result Surface

- White-box workload: 72,000 records.
- Positive recovery: 23,342/24,000 = 97.26%.
- Negative controls: 0/48,000 hits.
- Generation-changing ablation: 43,200 rows.
- Scope: admitted white-box model family and scale cells only.

## Code Layout

- `src/semcodebook/`: detector, carriers, protocol, ECC, commitments, negative controls, and evaluation helpers.
- `scripts/`: gate builders, baseline admission scripts, and analysis utilities retained for examiner inspection.
- `tests/`: unit and regression tests for detector, schema, negative controls, and readiness logic.
- `../../RESULT_MANIFEST.jsonl`: FYP-facing claim-to-evidence summary with artifact hashes.

## Result Artifacts

Primary artifacts are stored outside this code snapshot at:

```text
../../results/SemCodebook/artifacts/generated/
```

The top-level `RESULT_MANIFEST.jsonl` records the exact files and SHA-256 hashes used by the dissertation.

## Claim Boundary

Allowed claim: structured provenance recovery in admitted white-box cells.

Forbidden claim: universal source-code watermarking, natural first-sample/no-retry success, validator-repair success, or claims outside the admitted model/source cells.
