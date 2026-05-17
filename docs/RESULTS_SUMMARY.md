# Results Summary

This document summarizes the submitted FYP evidence surface used for the viva. Later continuation repositories and post-submission experiments are useful future work, but they do not rewrite the dissertation-facing denominators.

## Submitted Evidence Surface

| Project | Claim-bearing denominator | Observed result | Safe interpretation |
|---|---:|---:|---|
| CodeMarkBench | 140 canonical benchmark runs | 140/140 runs completed | Executable benchmark support, not watermark success |
| SemCodebook positive recovery | 24,000 positive rows | 23,342 recovered; misses remain inside the denominator | Structured provenance recovery in admitted white-box cells |
| SemCodebook negative controls | 48,000 negative-control rows | 0/48,000 hits | Negative controls support authenticity within the finite submitted surface |
| CodeDye live audit | 300 live audit samples | 6/300 sparse live signals | Conservative black-box null-audit evidence, not prevalence |
| CodeDye controls | 300 positive controls and 300 negative controls | 170/300 positive controls; 0/300 negative controls | Control evidence for the sparse audit signal |
| ProbeTrace scoped attribution | 300 scoped active-owner decisions | 300/300 scoped decisions | Scoped owner attribution under the evaluated registry |
| ProbeTrace false-owner controls | 1,200 false-owner controls | 0/1,200 false-owner hits | Control evidence against the submitted false-owner surface |
| SealAudit marker-hidden triage | 960 marker-hidden triage rows | 81/960 decisive outcomes | Selective triage with explicit abstention |
| SealAudit unsafe-pass tracking | 960 marker-hidden triage rows | 0 observed unsafe passes | Observed finite-sample safety signal, not a safety certificate |

## Reading Rule

The results should be read in this order: denominator, controls, artifact, access model, and boundary. A broader claim needs a new admitted evidence surface.

## High-Risk Misreadings To Avoid

- CodeDye's sparse signal must not be described as high recall or contamination prevalence.
- ProbeTrace's scoped attribution result must not be described as provider-general authorship proof.
- SealAudit's unsafe-pass result must not be described as a harmlessness guarantee.
- SemCodebook's admitted white-box cells must not be described as universal natural-generation watermarking.

## Primary Artifact Paths

| Artifact | Path |
|---|---|
| Traceability matrix | `docs/TRACEABILITY_MATRIX.md` |
| Claim boundaries | `CLAIM_BOUNDARIES.md` |
| Result manifest | `RESULT_MANIFEST.jsonl` |
| Viva integrity check | `scripts/viva_check.py` |
