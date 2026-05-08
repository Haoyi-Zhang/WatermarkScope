# Submission Notes

## Purpose

This repository is designed for FYP examination and supervisor review. It includes the dissertation, implementation snapshots, result summaries, and reproducibility metadata.

It is not a full raw-experiment dump. Some raw artifacts are intentionally excluded because they are large, provider-specific, or not needed for an examiner to verify the dissertation-level claims.

## What Is Included

- Dissertation PDF and LaTeX source.
- CodeMarkBench official repository snapshot.
- SemCodebook, CodeDye, ProbeTrace, and SealAudit code snapshots.
- Scripts and tests that document the implementation and gate logic.
- Key JSON/MD result artifacts used by the dissertation.
- Reproducibility manifests and anonymization/claim-boundary summaries.
- A repository integrity check in `scripts/repro_check.py`.

## What Is Excluded

- API keys or private credentials.
- Provider secrets and root-only environment files.
- Large raw run dumps that are not needed for the main dissertation tables.
- Python bytecode caches and local build artifacts.
- Stale failed-run drafts and temporary debugging files.

## Examiner Reading Path

1. Read `README.md` for the unified story.
2. Open `dissertation/WatermarkScope_FYP_Dissertation.pdf`.
3. Check `docs/RESULTS_SUMMARY.md` for headline denominators.
4. Inspect code in `projects/`.
5. Inspect result manifests in `results/`.
6. Run `python scripts/repro_check.py`.

## Claim Discipline

Every main result should be read with its denominator and boundary. Support-only rows, diagnostics, canary rows, and stress rows do not change the main claim denominator.

The safest one-sentence summary is:

> WatermarkScope builds a benchmark-to-audit framework showing that source-code watermarking requires executable evaluation, structured provenance, black-box evidence retention, scoped attribution, and conservative security triage.

