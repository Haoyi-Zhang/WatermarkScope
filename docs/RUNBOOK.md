# Runbook

This runbook gives the practical commands for checking, rebuilding, and inspecting the FYP repository.

## 1. Repository Integrity Check

From the repository root:

```bash
python scripts/examiner_check.py
```

This one-command check validates the examiner-facing documents, manifest shape, repository integrity, and result summary.

The underlying integrity check can also be run directly:

```bash
python scripts/repro_check.py
```

Expected result:

```text
[OK] Repository integrity check passed.
```

This validates required files, key artifacts, manifest hashes, headline denominators, stale wording, generated/cache files, and secret-like token patterns.

## 2. Project Snapshot Check

Verify that the five code/result snapshots advertised to examiners are present:

```bash
python scripts/check_project_snapshots.py
```

Expected result:

```text
[OK] Project evidence snapshots are present.
```

This is a packaged evidence-snapshot check. It is intentionally not a full unit-test or GPU/API rerun for SemCodebook, CodeDye, ProbeTrace, or SealAudit.

## 3. Preserved Result Check

Before adding new experiments or revised gates, verify that earlier results have not been deleted or overwritten:

```bash
python scripts/check_preserved_results.py
```

Expected result:

```text
[OK] Preserved result manifest verified: <N> files unchanged.
```

If a preserved file changed, do not regenerate the preservation manifest to hide the change. Restore the original file and write the new result as a versioned artifact. The policy is documented in `docs/RESULT_PRESERVATION_POLICY.md`.

## 4. Result Manifest Summary

From the repository root:

```bash
python scripts/summarize_all.py
```

Expected result:

```text
Verified <N> manifest entries.
```

The printed table is the fastest way to connect dissertation result numbers to exact artifacts.

## 5. Rebuild Result Manifest

Only run this if result artifacts have intentionally changed:

```bash
python scripts/build_result_manifest.py
python scripts/repro_check.py
```

The manifest should not be regenerated just to hide a mismatch. A mismatch means either the artifact changed and the dissertation should be checked, or the wrong artifact is being packaged.

## 6. Rebuild Dissertation PDF

```bash
cd dissertation/latex
pdflatex report.tex
bibtex report
pdflatex report.tex
pdflatex report.tex
```

After rebuilding, copy or compare `report.pdf` with `../WatermarkScope_FYP_Dissertation.pdf` as needed. The submitted PDF is already present in `dissertation/`.

## 7. Inspect Module Code

| Module | Primary code path | Primary result path |
|---|---|---|
| CodeMarkBench | `projects/CodeMarkBench/` | `projects/CodeMarkBench/results/` |
| SemCodebook | `projects/SemCodebook/` | `results/SemCodebook/` |
| CodeDye | `projects/CodeDye/` | `results/CodeDye/` |
| ProbeTrace | `projects/ProbeTrace/` | `results/ProbeTrace/` |
| SealAudit | `projects/SealAudit/` | `results/SealAudit/` |

Each module README gives the local role, current result surface, code layout, artifact path, and claim boundary.

## 8. Full Rerun Boundary

The FYP repository supports examiner verification and code inspection. Full reruns of the complete experiments are intentionally separated from local integrity checks because they require GPUs, model weights, or live provider APIs.

For dissertation marking, the expected default is:

1. run local integrity checks,
2. inspect implementation snapshots,
3. inspect result artifacts and hashes,
4. read claim boundaries and dissertation limitations.

For research continuation, use the project-specific scripts and reconstruct the full GPU/API environment described in `docs/ENVIRONMENT.md`.

## 9. Additive Continuation Boundary

Further watermark refinement should follow this sequence:

1. Run `python scripts/check_preserved_results.py`.
2. Create new dated or versioned result artifacts under the appropriate project result directory.
3. Keep prior artifacts unchanged even if a newer result supersedes them.
4. Update claim-boundary documentation only after the new artifact passes its own gate.
5. Run `python scripts/examiner_check.py` before sharing the repository.
