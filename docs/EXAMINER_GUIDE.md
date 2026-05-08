# Examiner Guide

This guide is a short verification path for supervisors or examiners who need to inspect the dissertation evidence quickly. It separates fast local checks from full GPU/API reruns.

## Five-Minute Review Path

1. Open `dissertation/WatermarkScope_FYP_Dissertation.pdf`.
2. Read the repository overview in `README.md`.
3. Check the headline denominators in `docs/RESULTS_SUMMARY.md`.
4. Check the claim boundaries in `CLAIM_BOUNDARIES.md`.
5. Run:

```bash
python scripts/examiner_check.py
```

Or run the underlying checks separately:

```bash
python scripts/repro_check.py
python scripts/check_project_snapshots.py
python scripts/check_preserved_results.py
python scripts/summarize_all.py
```

The first command verifies required files, key artifacts, result hashes, numerator/denominator values, stale wording, cache files, and secret-like tokens. The second command verifies that advertised project snapshots are present. The third command verifies that earlier result files have not been deleted or overwritten. The fourth command prints the result manifest with hash status and rates.

If the repository is inspected through GitHub rather than the local submission folder, one raw SemCodebook ablation file may be represented by `EXTERNAL_LARGE_ARTIFACTS.json` because it exceeds the ordinary GitHub single-file limit. This does not affect the dissertation claim surface: the compact ablation gate and summary remain in the repository and are the files used for examiner-facing verification.

## Thirty-Minute Review Path

Inspect the five implementation snapshots:

| Module | Code path | What to inspect |
|---|---|---|
| CodeMarkBench | `projects/CodeMarkBench/` | benchmark harness, baseline adapters, canonical result tables |
| SemCodebook | `projects/SemCodebook/` | carriers, detector, ECC recovery, method gates, tests |
| CodeDye | `projects/CodeDye/` | audit records, evidence hashing, controls, threshold discipline |
| ProbeTrace | `projects/ProbeTrace/` | active-owner attribution scripts, transfer receipts, control gates |
| SealAudit | `projects/SealAudit/` | triage rubric, benchmark builders, adjudication and risk gates |

Then inspect the result artifacts bound in `RESULT_MANIFEST.jsonl`. Each row contains:

- module name,
- dissertation claim,
- numerator and denominator where applicable,
- artifact path,
- artifact byte size,
- SHA-256 hash,
- interpretation boundary.

For a marking-oriented view, also inspect `docs/TRACEABILITY_MATRIX.md`, which maps the written claims to code and result artifacts.

## What The Local Checks Prove

The local checks prove that the submitted repository is internally consistent:

- the dissertation PDF and LaTeX source are present,
- the code snapshots are present,
- the result artifacts referenced by the dissertation are present,
- the result hashes match the manifest,
- preserved result artifacts remain byte-identical to the locked continuation manifest,
- the headline denominators match the written result surface,
- no obvious secret-like tokens or stale internal wording remain in reviewer-facing text files.

Research-continuation artifacts, where present, are outside the default FYP examiner path. They do not change the submitted dissertation claims.

## What Requires GPU Or API Access

The local checks are not full reruns of every experiment. Full reruns require resources outside a normal examiner laptop:

| Module | Full rerun requirement |
|---|---|
| CodeMarkBench | local model weights, benchmark dependencies, and GPU runtime |
| SemCodebook | local white-box code models and 72,000-row evaluation workload |
| CodeDye | provider API access for live black-box audit rows |
| ProbeTrace | provider API access plus owner-registry and transfer validation workloads |
| SealAudit | provider/API judging where configured, benchmark generation, and triage evaluation |

The repository therefore provides two layers: local integrity verification for dissertation marking, and implementation/result artifacts for deeper rerun inspection.

## Recommended Reading Order

1. Dissertation Abstract and Chapter 1 for the unified story.
2. Chapter 3 for the benchmark foundation.
3. Chapter 4 for SemCodebook and CodeDye.
4. Chapter 5 for ProbeTrace and SealAudit.
5. Chapter 6 for denominator, limitation, and publication-plan synthesis.
6. `CLAIM_BOUNDARIES.md` to verify that the written claims stay inside evaluated evidence.

## Main Claim Discipline

The dissertation should be read as a benchmark-to-audit framework, not as five independent universal claims. The safe one-sentence interpretation is:

> WatermarkScope shows that reliable source-code watermarking needs executable benchmarks, structured provenance recovery, black-box evidence retention, scoped attribution, selective security triage, and explicit abstention boundaries.
