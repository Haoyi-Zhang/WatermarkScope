# Submission Notes

## Purpose

This repository is prepared as the WatermarkScope FYP submission and inspection artifact. It is not a raw experiment dump and it is not a provider-secret archive.

The FYP submission-facing state is defined by:

- `dissertation/WatermarkScope_FYP_Dissertation.pdf`
- `RESULT_MANIFEST.jsonl`
- `docs/EXAMINER_GUIDE.md`

Research-continuation evidence is retained in:

- `results/watermark_strict_reviewer_audit_v8_20260507.json`
- `results/watermark_submission_gap_diagnosis_v1_20260508.json`
- the four project final claim locks under `results/*/artifacts/generated/`

## What Is Included

- Project code snapshots for SemCodebook, CodeDye, ProbeTrace, and SealAudit.
- Result artifacts and final claim locks for the locked scoped claims.
- Reproducibility manifests, preservation manifests, and hash-bound evidence files.
- Reviewer runbook and results summary.
- Submitted dissertation PDF and LaTeX source for the FYP report.
- Research-continuation material retained for traceability, but kept separate from the submitted FYP denominators.

## What Is Excluded

- API keys or private credentials.
- Root-only provider environment files.
- Nonessential transient logs and caches.
- Provider-general results that have not passed their own gates.

## Reviewer Reading Path

1. Read `dissertation/WatermarkScope_FYP_Dissertation.pdf` for the submitted FYP report.
2. Read `README.md` and `docs/EXAMINER_GUIDE.md` for the inspection path.
3. Read `CLAIM_BOUNDARIES.md` for allowed and forbidden claims.
4. Read `docs/RESULTS_SUMMARY.md` for denominators and main result surfaces.
5. Inspect project code under `projects/`.
6. Inspect final claim locks under `results/*/artifacts/generated/`.
7. Run the quick verification commands in `docs/RUNBOOK.md`.

## Claim Discipline

Every main result is bound to:

- fixed denominator;
- project and protocol version;
- provider/backbone scope;
- negative-control status;
- support-only vs claim-bearing role;
- hash/schema completeness.

Support-only rows, diagnostics, canary rows, and stress rows do not change the main claim denominator.

The safest one-sentence summary is:

> The four papers study source-code watermark evidence under scoped, auditable conditions: structured white-box provenance, conservative black-box null-audit, active-owner attribution, and selective security triage.

## Current Execution Policy

Do not launch duplicate full runs only to reconfirm existing gates. The current result set already exceeds the minimal one-white-box-model plus DeepSeek-only black-box check.

Further experiments should be launched only if they add a frozen new claim surface:

- CodeDye v4 evidence enrichment must be preregistered before any new DeepSeek run.
- SemCodebook real-repo witness should be support-only unless a new formal claim is introduced.
- ProbeTrace non-DeepSeek replication requires new provider keys and separate claim locks.
- SealAudit should improve paper framing before new DeepSeek spending.
