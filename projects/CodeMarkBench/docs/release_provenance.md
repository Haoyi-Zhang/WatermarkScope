# Canonical Matrix Provenance

`results/schema.json` documents the machine-readable report and scorecard serialization used by per-run `report.json` payloads. `results/export_schema.json` documents the tracked summary-export contract for the release-facing `suite_all_models_methods` figure/table surface. This document records the canonical matrix identity and the provenance contract for the materialized formal result of record.

## Canonical Matrix Identity

The public release is intended to anchor on one canonical matrix identity:

- profile: `suite_all_models_methods`
- matrix index: `results/matrix/suite_all_models_methods/matrix_index.json`
- matrix index sha256: `7bf4cc0a125b0a9bf9e1cb8efb8cdfd089a3521c4f58b7daf399edc862d35c0b`
- result of record: single Linux execution host
- visible device contract: `CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7`
- scheduler contract: `--gpu-slots 8 --gpu-pool-mode shared --cpu-workers 9 --retry-count 1 --command-timeout-seconds 259200`
- completion state: `run_count = 140`, `success_count = 140`, `failed_count = 0`
- execution mode: `single_host_canonical`

The materialized canonical matrix index is the only release-facing source of truth for:

- full-suite regenerate/export flows
- release-facing summary figures and tables
- archival artifact checksums and matrix identity

The corrected archival Zenodo record is [10.5281/zenodo.19740954](https://doi.org/10.5281/zenodo.19740954).
It records the same matrix index SHA-256, the GitHub companion commit used for
the archived bundle, and the raw/sanitized-bundle checksums. The byte-identical
source commit for the deposited sanitized bundle is
`3252ca48e15416eee5259967aa735c969f7eb150`.

Two code identities can appear in release notes:

- the **archived sanitized-bundle source commit**, recorded in the Zenodo
  manifest, identifies the GitHub tree used to assemble that deposited bundle
- the **current GitHub `main` commit** may be newer when it contains
  documentation, validation, recovery, or companion-surface publication updates
  after the archival bundle was assembled

Both identities point to the same canonical matrix index SHA-256 above. Result
claims must follow the matrix identity, not a later documentation-only commit.

## Formal Provenance Story

The formal provenance story is one clean one-shot single-host rerun. Earlier segmented, recovery, or sharded engineering attempts are not part of the formal public result identity and do not define the release-facing provenance story.

Reviewer-facing interpretation is:

- the release-facing matrix is the canonical single-host benchmark result
- historical segmented runs may exist in engineering notes, but they are not publication-facing provenance inputs
- only the one-shot canonical matrix index is the public result identity used for regenerate/export and archival packaging

## Release Provenance Fields

Publication and archival metadata must preserve at least:

- `canonical_manifest`
- `canonical_manifest_digest`
- `canonical_model_revisions`
- `execution_mode`
- `gpu_pool_mode`
- `code_snapshot_digest`
- `execution_environment_fingerprint`
- environment-of-record capture paths

For the public release, `code_snapshot_digest` and `execution_environment_fingerprint` must be recorded in the refreshed `results/environment/runtime_environment.json` execution block for the release-facing host capture, together with `execution_mode`, `cuda_visible_devices`, and `visible_gpu_count`. Release packaging must keep the refreshed environment-of-record artifact linked to the canonical matrix identity, and the tracked summary exports inherit that same matrix identity through `results/export_schema.json`.

## Metrics Semantics

The named compact score field remains `CodeMarkScore`, but release interpretation treats it as a secondary rollup. Exact-value tables, released submetrics, strict diagnostics, and decompositions are the primary evidence surface.

Efficiency semantics are fixed to generation-stage timing only:

- `clean_generation_seconds`
- `watermarked_generation_seconds`
- their token-normalized derivatives

Descriptive pipeline timing remains public, but it is not a headline-score input. In release-facing tables and figures, make the distinction explicit:

- generation-stage timing supports the public efficiency metric
- full-pipeline timing is descriptive systems output

## GitHub And Zenodo Split

The public release is intentionally split:

- GitHub companion repository:
  - source code
  - canonical manifests and release inputs
  - reviewer workflow scripts
  - release-facing documentation
  - tracked summary figures and tables
  - machine-readable provenance manifests
- Zenodo archival artifact:
  - raw matrix artifact
  - checksums
  - environment-of-record capture
  - exact model roster plus resolved revisions
  - sanitized release bundle

GitHub is the release-facing companion surface. Zenodo is the archival surface for large rerun-backed artifacts.
