# Results Summary

This file summarizes the result surfaces used by the dissertation. It is intended for quick examiner review. The dissertation gives the full interpretation and limitations.

## Cross-Project Story

The five stages form a source-code watermarking lifecycle:

1. **Evaluate** existing code-watermarking methods under executable stress conditions.
2. **Embed and recover** structured provenance in admitted white-box cells.
3. **Audit** black-box provider outputs without turning sparse evidence into prevalence claims.
4. **Attribute** outputs to a scoped active owner and source split.
5. **Triage** watermark mechanisms as security-relevant objects with explicit abstention.

## Main Result Table

| Project | Claim-bearing denominator | Observed result | Exclusion / caveat | Safe interpretation |
|---|---:|---:|---|---|
| CodeMarkBench | 140 canonical runs | 140/140 run-complete | Run completion is not task-level detector success | Benchmark foundation; exposes reliability tradeoffs rather than watermark success rate |
| SemCodebook positive recovery | 24,000 positives | 23,342 recovered | 658 misses/abstains/rejects remain in denominator; 43,200 ablation rows support-only | Reported structured provenance rate in admitted white-box cells |
| SemCodebook negatives | 48,000 controls | 0 hits; Wilson 95% upper bound 0.008% | Zero observed is not zero mathematical risk | Clean negative-control surface in current denominator |
| CodeDye live audit | 300 DeepSeek rows | 6 sparse signals; Wilson 95% CI 0.92%-4.29% | 806 support rows excluded; 4/300 stats sub-gate separate | Conservative null-audit, not contamination prevalence |
| CodeDye positive controls | 300 controls | 170 hits; Wilson 95% CI 51.01%-62.15% | Control sensitivity is not live prevalence | Moderate known-control sensitivity, not high-recall detection |
| CodeDye negative controls | 300 controls | 0 hits; Wilson 95% upper bound 1.26% | Control surface only for current denominator | Current false-positive control surface |
| ProbeTrace APIS | 300 records | 300 successes; Wilson 95% lower bound 98.74% | Single active owner; not multi-owner/provider-general | Single-active-owner/source-bound attribution |
| ProbeTrace false-owner controls | 1,200 controls | 0 false attributions; Wilson 95% upper bound 0.32% | Wrong/null/random owner controls only | Scoped false-owner control evidence |
| ProbeTrace transfer support | 900 rows | receipt-complete | 900 transfer rows over 300 task clusters, not independent attribution denominator | Source-bound transfer support |
| SealAudit marker-hidden | 960 rows | 81 decisive; Wilson 95% CI 6.84%-10.37% | 320 marker-visible rows diagnostic-only | Selective triage coverage |
| SealAudit needs-review | 960 rows | 879 needs review | Needs-review is designed abstention | Explicit abstention, not hidden failure |
| SealAudit unsafe pass | 960 rows | 0 observed; Wilson 95% upper bound 0.40% | Bound is within marker-hidden protocol only | Conservative unsafe-pass audit observation, not a safety certificate |

CodeDye also stores a separate 4/300 statistics-artifact sub-gate. That count is a reproducibility sub-gate under a narrower definition; it is not added to or substituted for the final 6/300 reporting signal.

## Result Boundaries

The following claims are deliberately not made:

- No universal source-code watermarking claim.
- No claim that all existing watermarking fails.
- No contamination accusation or provider prevalence estimate.
- No provider-general or multi-owner authorship claim.
- No automatic safety classifier or security certificate claim.

## Where To Inspect Artifacts

| Project | Code | Results |
|---|---|---|
| CodeMarkBench | `projects/CodeMarkBench/` | `projects/CodeMarkBench/results/` |
| SemCodebook | `projects/SemCodebook/` | `results/SemCodebook/` |
| CodeDye | `projects/CodeDye/` | `results/CodeDye/` |
| ProbeTrace | `projects/ProbeTrace/` | `results/ProbeTrace/` |
| SealAudit | `projects/SealAudit/` | `results/SealAudit/` |
