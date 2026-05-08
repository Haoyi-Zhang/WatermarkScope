# Runbook

This runbook gives the practical commands for checking, rebuilding, and inspecting the five-stage WatermarkScope FYP repository.

## 1. Current Submission Gate

From the repository root:

```bash
python -B scripts/check_watermark_submission_gap_diagnosis_v1.py
python -B scripts/check_watermark_submission_main_table_manifest_v1.py
python -B scripts/check_submission_facing_claims_v1.py
python -B scripts/check_strict_reviewer_audit_v8.py
python -B scripts/check_preserved_results.py
```

Expected result:

```text
[OK] Watermark submission gap diagnosis verified.
[OK] Watermark submission main-table manifest verified.
[OK] Submission-facing claim wording verified.
[OK] Strict reviewer audit v8 verified.
[OK] Preserved result manifest verified: <N> result files unchanged.
```

These checks validate the current submission-facing state. They are not GPU or provider reruns.

## 2. ProbeTrace Final Gate

ProbeTrace is the most recent closed blocker. Verify it directly:

```bash
python -B scripts/check_probetrace_multi_owner_postrun_promotion_gate_v2.py
python -B scripts/check_probetrace_final_claim_lock_v2.py
```

Expected result:

```text
[OK] ProbeTrace APIS-300 and control artifacts verified.
[OK] ProbeTrace transfer support rows remain support-only.
```

## 3. Legacy Integrity Check

The older repository integrity check is retained for traceability:

```bash
python -B scripts/repro_check.py
```

It validates required files, key artifacts, manifest hashes, generated/cache files, and secret-like token patterns. Some older manifest rows are retained for preservation and are not the current submission claim surface.

For GitHub inspection, `EXTERNAL_LARGE_ARTIFACTS.json` records any preserved raw result file that is too large for ordinary GitHub storage. The local submission folder may contain the full raw file; the GitHub repository keeps the compact claim-bearing artifact and the external digest record.

## 4. Project Snapshot Check

Verify that the five code/result snapshots advertised to examiners are present:

```bash
python -B scripts/check_project_snapshots.py
```

Expected result:

```text
[OK] Project evidence snapshots are present.
```

This is a packaged evidence-snapshot check. It is intentionally not a full unit-test or GPU/API rerun for SemCodebook, CodeDye, ProbeTrace, or SealAudit.

## 5. Preserved Result Check

Before adding new experiments or revised gates, verify that earlier results have not been deleted or overwritten:

```bash
python -B scripts/check_preserved_results.py
```

Expected result:

```text
[OK] Preserved result manifest verified: <N> files unchanged.
```

If a preserved file changed, do not regenerate the preservation manifest to hide the change. Restore the original file and write the new result as a versioned artifact. The policy is documented in `docs/RESULT_PRESERVATION_POLICY.md`.

## 6. Result Manifest Summary

From the repository root:

```bash
python -B scripts/summarize_all.py
```

Expected result:

```text
Verified <N> manifest entries.
```

The printed table is the fastest way to connect dissertation result numbers to exact artifacts.

## 7. Rebuild Result Manifest

Only run this if result artifacts have intentionally changed:

```bash
python scripts/build_result_manifest.py
python scripts/repro_check.py
```

The manifest should not be regenerated just to hide a mismatch. A mismatch means either the artifact changed and the dissertation should be checked, or the wrong artifact is being packaged.

## 8. Dissertation and Continuation Boundary

The `dissertation/` directory contains the authoritative FYP report and rebuildable LaTeX source. The FYP claim surface is the dissertation-level evidence surface recorded in the PDF and `RESULT_MANIFEST.jsonl`.

Some result locks and continuation notes target later paper submissions. Those artifacts are retained for traceability and future work, but they do not change the submitted FYP denominators unless a new admitted surface is explicitly documented.

## 9. Inspect Module Code

| Module | Primary code path | Primary result path |
|---|---|---|
| CodeMarkBench | `projects/CodeMarkBench/` | `projects/CodeMarkBench/results/` |
| SemCodebook | `projects/SemCodebook/` | `results/SemCodebook/` |
| CodeDye | `projects/CodeDye/` | `results/CodeDye/` |
| ProbeTrace | `projects/ProbeTrace/` | `results/ProbeTrace/` |
| SealAudit | `projects/SealAudit/` | `results/SealAudit/` |

Each module README gives the local role, current result surface, code layout, artifact path, and claim boundary.

## 10. Full Rerun Boundary

The repository supports reviewer verification and code inspection. Full reruns of complete experiments are intentionally separated from local integrity checks because they require GPUs, model weights, or live provider APIs.

For paper review, the expected default is:

1. run local integrity checks,
2. inspect implementation snapshots,
3. inspect result artifacts and hashes,
4. read claim boundaries and limitations.

For research continuation, use the project-specific scripts and reconstruct the full GPU/API environment described in `docs/ENVIRONMENT.md`.

## 11. Additive Continuation Boundary

Further watermark refinement should follow this sequence:

1. Run `python scripts/check_preserved_results.py`.
2. Create new dated or versioned result artifacts under the appropriate project result directory.
3. Keep prior artifacts unchanged even if a newer result supersedes them.
4. Update claim-boundary documentation only after the new artifact passes its own gate.
5. Run the current submission gate checks before sharing the repository.
