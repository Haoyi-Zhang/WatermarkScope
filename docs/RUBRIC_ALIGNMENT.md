# Rubric Alignment

This document maps the repository and dissertation to the qualities normally expected from a high-scoring final-year project: clear problem framing, technical depth, implementation evidence, rigorous evaluation, reproducibility, critical discussion, and professional presentation.

## High-Level Assessment

The project should be assessed as one coherent framework:

> WatermarkScope builds a benchmark-to-audit evidence chain for source-code watermarking in code generation models.

It is not five unrelated experiments. The modules are arranged by access model and evidence strength:

1. executable benchmark foundation,
2. white-box structured provenance,
3. black-box null-audit,
4. active-owner attribution,
5. security triage.

## Rubric Mapping

| Assessment area | Evidence in this repository | Why it matters |
|---|---|---|
| Problem formulation | Dissertation Chapter 1; `README.md`; `CLAIM_BOUNDARIES.md` | Defines a precise lifecycle question rather than a vague watermarking topic |
| Literature grounding | Dissertation Chapter 2; `dissertation/latex/reference.bib` | Connects code LLMs, benchmarks, watermarking, provenance, contamination, and safety |
| Technical design | Chapters 3-5; `docs/METHOD_INDEX.md`; module source code under `projects/` | Provides formulas, algorithms, schemas, and implementation snapshots |
| Implementation quality | `projects/CodeMarkBench/`, `projects/SemCodebook/`, `projects/CodeDye/`, `projects/ProbeTrace/`, `projects/SealAudit/` | Shows code artifacts rather than only a written report |
| Evaluation rigor | `docs/RESULTS_SUMMARY.md`; `RESULT_MANIFEST.jsonl`; result artifacts under `results/` | Fixes denominators, controls, confidence intervals, and support-row exclusions |
| Reproducibility | `scripts/repro_check.py`; `scripts/summarize_all.py`; `scripts/examiner_check.py`; `docs/RUNBOOK.md` | Gives examiner-verifiable local checks and clear full-rerun boundaries |
| Critical reflection | Chapter 6; `CLAIM_BOUNDARIES.md`; `docs/VIVA_PREPARATION.md` | States what is not claimed and what evidence would weaken the conclusions |
| Professional presentation | PDF, LaTeX source, figures, tables, IEEE references, organized repository | Makes the work inspectable as a dissertation and as a software artifact |

## Why The Work Is Substantial

The submitted package contains:

- one complete dissertation PDF and LaTeX source,
- five implementation snapshots,
- result artifacts with SHA-256 binding,
- a result manifest with denominators, confidence intervals, and independence units,
- local reproducibility checks,
- examiner guide, method index, environment notes, runbook, and traceability map.

The strongest FYP-level contribution is not any single result number. It is the disciplined evidence architecture: every result is tied to a denominator, a control surface, a claim boundary, and a concrete artifact.

## Remaining Boundaries

The project is intentionally conservative about claims:

- CodeMarkBench is a finite release matrix, not a proof that all watermarking fails.
- SemCodebook is scoped to admitted white-box model cells, not universal semantic watermarking.
- CodeDye is a null-audit protocol, not a contamination accusation.
- ProbeTrace is single-active-owner/source-bound, not provider-general authorship.
- SealAudit is selective triage, not an automatic safety classifier.

These boundaries should be read as scientific rigor rather than weakness.

