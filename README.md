# WatermarkScope FYP Dissertation Repository

**WatermarkScope: A Benchmark-to-Audit Framework for Source-Code Watermarking in Code Generation Models**

This repository contains the dissertation, implementation snapshots, reproducibility scripts, and result artifacts for Haoyi Zhang's Final Year Project.

The project is organized as one evidence lifecycle rather than five unrelated experiments:

1. **CodeMarkBench** establishes the executable benchmark foundation.
2. **SemCodebook** studies structured white-box provenance watermarking.
3. **CodeDye** studies conservative black-box contamination null-audit.
4. **ProbeTrace** studies active-owner, source-bound attribution.
5. **SealAudit** studies watermark-as-security-object selective triage.

The central argument is that reliable source-code watermarking cannot be evaluated with one detector score. It requires executable benchmarks, structured provenance recovery, raw evidence retention, negative controls, scoped attribution, security triage, and explicit abstention boundaries.

## Repository Layout

```text
.
|-- dissertation/
|   |-- WatermarkScope_FYP_Dissertation.pdf
|   `-- latex/
|-- projects/
|   |-- CodeMarkBench/
|   |-- SemCodebook/
|   |-- CodeDye/
|   |-- ProbeTrace/
|   `-- SealAudit/
|-- results/
|   |-- SemCodebook/
|   |-- CodeDye/
|   |-- ProbeTrace/
|   `-- SealAudit/
|-- docs/
|   |-- EXAMINER_GUIDE.md
|   |-- ENVIRONMENT.md
|   |-- METHOD_INDEX.md
|   |-- RESULT_PRESERVATION_POLICY.md
|   |-- RESULTS_SUMMARY.md
|   |-- RUBRIC_ALIGNMENT.md
|   |-- RUNBOOK.md
|   |-- TRACEABILITY_MATRIX.md
|   |-- VIVA_PREPARATION.md
|   `-- SUBMISSION_NOTES.md
|-- CLAIM_BOUNDARIES.md
|-- PRESERVED_RESULT_MANIFEST.jsonl
|-- PRESERVATION_SUMMARY.json
|-- RESULT_MANIFEST.jsonl
`-- scripts/
    |-- check_preserved_results.py
    |-- examiner_check.py
    |-- repro_check.py
    `-- summarize_all.py
```

## Headline Results

| Module | Main role | Current result surface |
|---|---|---|
| CodeMarkBench | Executable benchmark foundation | 140/140 canonical run-completion inventory over 4 baselines, 5 local models, and 7 source groups |
| SemCodebook | White-box structured provenance | 23,342/24,000 positive recoveries; 0/48,000 negative-control hits, Wilson 95% upper bound 0.008%; 43,200 generation-changing ablation support rows |
| CodeDye | Black-box null-audit | 6/300 sparse DeepSeek signals, Wilson 95% CI 0.92%-4.29%; 170/300 positive-control hits; 0/300 negative-control hits, upper bound 1.26% |
| ProbeTrace | Active-owner attribution | 300/300 APIS successes, Wilson 95% lower bound 98.74%; 0/1,200 false-owner controls, upper bound 0.32%; 900 transfer support rows over the scoped source-bound setting |
| SealAudit | Security triage | 81/960 decisive marker-hidden rows; 879/960 needs-review rows; 0/960 observed unsafe-pass outcomes, upper bound 0.40% |

These results are intentionally scoped. The repository does not claim universal watermarking, contamination prevalence, provider-general authorship attribution, or automatic safety certification.

## Quick Checks

For a supervisor or examiner, start with:

```text
docs/EXAMINER_GUIDE.md
```

For a compact map from each method to its formulas, algorithms, result denominator, and artifact paths, see:

```text
docs/METHOD_INDEX.md
```

Run the repository integrity check:

```bash
python scripts/examiner_check.py
```

Or run the underlying checks separately:

```bash
python scripts/repro_check.py
python scripts/check_project_snapshots.py
python scripts/check_preserved_results.py
```

Print a compact table of result artifacts and verify their hashes:

```bash
python scripts/summarize_all.py
```

These commands verify that the dissertation PDF, code snapshots, result manifests, preserved-result hashes, claim-boundary files, and key artifact summaries are present. They are repository integrity checks, not full GPU/API reruns.

Existing result artifacts are protected by `PRESERVED_RESULT_MANIFEST.jsonl`. Continuation work should add versioned artifacts instead of overwriting prior outputs. See `docs/RESULT_PRESERVATION_POLICY.md`.

Continuation artifacts are kept outside the main FYP claim surface. They document how later experiments can add new denominators without changing the submitted dissertation results.

For environment and rerun boundaries, see:

- `docs/ENVIRONMENT.md`
- `docs/RUNBOOK.md`

For marking-oriented review, see:

- `docs/RUBRIC_ALIGNMENT.md`
- `docs/TRACEABILITY_MATRIX.md`
- `docs/VIVA_PREPARATION.md`

## Dissertation Build

The current PDF is included at:

```text
dissertation/WatermarkScope_FYP_Dissertation.pdf
```

To rebuild from LaTeX:

```bash
cd dissertation/latex
pdflatex report.tex
bibtex report
pdflatex report.tex
pdflatex report.tex
```

The dissertation uses IEEE references through `IEEEtran.bst`.

## Result Interpretation

The `RESULT_MANIFEST.jsonl` file binds key dissertation claims to concrete result files and SHA-256 hashes. The `CLAIM_BOUNDARIES.md` file records the allowed interpretation and forbidden interpretation for each module.

The dissertation and repository use the following rule:

> A result supports a main claim only if its denominator, detector version, threshold version, control status, and claim-bearing role are fixed before interpretation.

Diagnostic, support-only, canary, and stress rows are preserved when useful, but they do not change the main result denominators.
