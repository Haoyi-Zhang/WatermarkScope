# Artifacts And Large Result Files

This document explains how the public `CodeMarkBench` release is split between the repository-facing summary surface and the archival raw-result surface.

Status for the final public split:

- the publication-facing result-of-record contract is the completed canonical single-host one-shot matrix with `140/140` successful runs and `failed_count = 0`
- raw full-run results are **not** stored in git
- archival raw-results metadata is published with the external Zenodo deposition rather than stored as raw results in git
- the repository-tracked `results/figures/suite_all_models_methods/` and `results/tables/suite_all_models_methods/` directories now contain the materialized publication-facing summary surface for the canonical `140/140` run, with tables as the primary exact-value evidence and a deliberately narrow relation/structure figure set
- Level 2 regeneration remains the documented path for rebuilding those summaries from the external raw artifact

The public GitHub repository is intentionally small and release-facing:

- code
- canonical release manifests with embedded public-benchmark provenance
- canonical crafted release inputs
- documentation
- repository-tracked dataset statistics figures and tables
- materialized summary figures, summary tables, lightweight result inventories, and manifests

Large raw full-run outputs are **not** stored in git.
Local working copies may contain ignored engineering residues such as
`_PROJECT_CONTEXT/`, `_review_outputs/`, `results/matrix/`, or
`results/certifications/`; those paths are outside the public companion mirror
and outside the sanitized Zenodo bundle. The release-facing surface is the
tracked GitHub tree plus the published Zenodo files listed below.

The public GitHub repository alone is therefore sufficient for code inspection, dataset statistics, formulas, canonical release-suite definitions, and the materialized tracked full-run summary exports, but **not** for reconstructing the rerun-backed raw artifact for the single-host full-suite result without restoring the external raw artifact locally.

## Excluded White-Box Methods

The public artifact scope matches the active canonical benchmark only:

- `CodeIP` is excluded because the public code exists but the official public artifact set is incomplete, so it cannot satisfy the official-public, runtime-comparable, reproducible benchmark standard used by this repository
- `Practical and Effective Code Watermarking for Large Language Models` is excluded because the official implementation follows a training/model-modifying path rather than the shared runtime-generation contract used here

The GitHub and Zenodo release surfaces therefore track only the four active runtime baselines in the canonical benchmark.

## What Stays Out Of Git

The following are not intended for GitHub storage:

- raw `results/matrix/**` per-run trees
- certification and audit outputs
- local caches and model weights
- runtime upstream checkouts
- machine-specific logs

## Distribution Strategy

- **GitHub**: code, docs, canonical release inputs, summary figures/tables, and lightweight inventories
- **Zenodo**: raw full-run result artifact and sanitized release bundle

The public release story is stable:

- GitHub is the canonical companion repository for code, docs, and tracked summary exports
- Zenodo is the archival home for the rerun-backed raw result tree
- the corrected archival Zenodo record is [10.5281/zenodo.19740954](https://doi.org/10.5281/zenodo.19740954)

Published Zenodo files for the result-of-record release:

| File | Role | SHA-256 |
| --- | --- | --- |
| `CodeMarkBench-canonical-raw-results-suite_all_models_methods-20260424T183928.tar.zst` | Raw `140/140` matrix evidence and per-run reports. | `29d0c20a5f5e99cc24d61e7479e4d788565161c78c3660e560412eb502d38a2d` |
| `CodeMarkBench-sanitized-release-bundle-20260425T181337.tar.zst` | Compact release-surface snapshot for archival recovery. | `471c14eaa2d3f3fddbbf197715ee75549540639b95f13c9d1456875a98f78111` |
| `raw_results_manifest.json` | Machine-readable artifact identity and GitHub companion commit. | recorded in `SHA256SUMS.txt` |
| `SHA256SUMS.txt` | Download verification file. | archived with the Zenodo record |

## Raw Result Artifact Layout

The archival raw artifact restores the finished full-run tree under:

```text
results/matrix/suite_all_models_methods/
```

and the formal execution environment capture under:

```text
results/environment/
```

Machine-specific preflight/audit residues such as `results/certifications/`
and `results/audits/` are intentionally not part of the public raw-results
archive. They are local process evidence, may contain execution-host paths, and
are replaced in the public release contract by the archived matrix tree,
environment capture, checksums, manifest identity, and reviewer-facing
validation scripts.

## Published Artifact Metadata

The archival release metadata includes:

- a raw artifact manifest
- a checksum file
- the exact model identifiers used
- the exact resolved local Hugging Face snapshot revision for each released model identifier
- the exact upstream provenance manifests used for the four pinned baseline implementations in this release
- the exact execution environment capture used for the rerun

The helper templates under `artifacts/` are packaging inputs used to generate the deposited manifest and checksum files. Published release metadata contains no unset placeholder values; the repository templates are packaging inputs rather than the archival record itself. Level 2 reproduction is the documented regeneration path from the external raw-results artifact rather than a self-contained raw-results download from this repository alone.

In other words:

- GitHub ships code, canonical release inputs, docs, dataset statistics, and the materialized repository-tracked full-run summary exports in this companion repository
- GitHub does **not** guarantee the raw full-run matrix tree needed to regenerate those exports from scratch
- Zenodo is the canonical home for the raw full-run result tree

Repository templates for the first two files live under:

- [`artifacts/raw_results_manifest.template.json`](../artifacts/raw_results_manifest.template.json)
- [`artifacts/SHA256SUMS.template.txt`](../artifacts/SHA256SUMS.template.txt)

The templates are intentionally placeholders. The published manifest and
checksum file are the Zenodo files, not the repository templates.

The exact environment capture is refreshed by remote preflight for the formal rerun and travels with the public archival artifact and sanitized release bundle. Any helper files left in the repository are packaging inputs rather than the archival record itself.

## Rebuilding Summary Outputs

After downloading the raw artifact, regenerate the summary outputs locally:

```bash
curl -L -o CodeMarkBench-canonical-raw-results-suite_all_models_methods-20260424T183928.tar.zst \
  'https://zenodo.org/records/19740954/files/CodeMarkBench-canonical-raw-results-suite_all_models_methods-20260424T183928.tar.zst?download=1'
curl -L -o CodeMarkBench-sanitized-release-bundle-20260425T181337.tar.zst \
  'https://zenodo.org/records/19740954/files/CodeMarkBench-sanitized-release-bundle-20260425T181337.tar.zst?download=1'
curl -L -o raw_results_manifest.json \
  'https://zenodo.org/records/19740954/files/raw_results_manifest.json?download=1'
curl -L -o SHA256SUMS.txt \
  'https://zenodo.org/records/19740954/files/SHA256SUMS.txt?download=1'
sha256sum -c SHA256SUMS.txt
tar --use-compress-program=zstd -xf CodeMarkBench-canonical-raw-results-suite_all_models_methods-20260424T183928.tar.zst -C .
python scripts/refresh_report_metadata.py --matrix-index results/matrix/suite_all_models_methods/matrix_index.json
python scripts/reviewer_workflow.py regenerate --matrix-index results/matrix/suite_all_models_methods/matrix_index.json --figure-dir results/figures/suite_all_models_methods --table-dir results/tables/suite_all_models_methods
python scripts/export_dataset_statistics.py
```

If you specifically need a figure-only rerender after the canonical summary tables and JSON sidecars already exist, run:

```bash
python scripts/render_materialized_summary_figures.py --table-dir results/tables/suite_all_models_methods --output-dir results/figures/suite_all_models_methods --export-identity results/tables/suite_all_models_methods/suite_all_models_methods_export_identity.json --require-times-new-roman
```

The repository does not distribute model weights or runtime baseline checkouts. Those are fetched on demand from the exact model IDs and pinned upstream manifests.
