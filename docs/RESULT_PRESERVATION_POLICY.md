# Result Preservation Policy

This repository now treats existing experiment outputs as immutable evidence.

## Non-Destructive Continuation Rule

Continuation work must not delete, rename, or overwrite prior result artifacts. New experiments, stronger gates, revised summaries, or dissertation refinements must be written as additive, versioned artifacts.

Allowed:

- Add a new result file with a new date, version, model, gate, or run identifier.
- Add a new summary that cites the preserved artifact and explains a revised boundary.
- Add a superseding artifact while keeping the earlier file intact.
- Add reviewer-facing documentation that clarifies why a prior result is support-only, diagnostic, or claim-bearing.

Not allowed:

- Delete prior JSON, JSONL, CSV, PDF, figure, or manifest files.
- Rewrite a prior result file to improve a metric or hide a failed boundary.
- Change a denominator after inspecting results.
- Replace support-only rows with claim-bearing rows without a new preregistered gate artifact.

## Machine Check

The current result state is locked by:

```bash
python scripts/build_preserved_result_manifest.py
```

The preservation manifest can be checked by:

```bash
python scripts/check_preserved_results.py
```

The check requires every preserved file to remain present with the same byte size and SHA-256 hash. It permits additional files, because future work should be additive.

## Interpretation

Preservation does not mean every prior artifact is a main claim. It means the evidence chain remains auditable. Claim-bearing status is still controlled by `RESULT_MANIFEST.jsonl`, `CLAIM_BOUNDARIES.md`, and the project-specific reproducibility manifests.
