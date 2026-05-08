# Release Story And Canonical Execution Surface

This document summarizes the release-facing identity of `CodeMarkBench`, the canonical execution surface behind the public result-of-record, and the repository/artifact split used for the formal public release.

## Canonical Result Surface

The formal public result-of-record contract is:

- one canonical `suite_all_models_methods` matrix index
- materialized on one Linux execution host
- executed under the fixed visible-device contract `CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7`
- scheduled under `--gpu-slots 8 --gpu-pool-mode shared --cpu-workers 9 --retry-count 1 --command-timeout-seconds 259200`
- publication-facing only after the one-shot canonical rerun reports `140/140 success`

The formal public story is the one-shot single-host rerun only. Earlier segmented, recovery, or exploratory runs are engineering history, not part of the formal release-facing provenance story.

The only publication-facing matrix identity is:

- `results/matrix/suite_all_models_methods/matrix_index.json`

## Metrics Contract

The public headline metric remains `CodeMarkScore`.

The release-facing efficiency semantics are fixed to generation-stage timing only:

- `clean_generation_seconds`
- `watermarked_generation_seconds`
- their token-normalized derived surfaces

Full-pipeline runtime, queue wait, detached-launch latency, audit time, and other end-to-end campaign timing surfaces are descriptive systems outputs only. They are not headline-score inputs.

## Public Repository Split

The public distribution is intentionally split across two surfaces:

- GitHub companion repository:
  - source code
  - canonical release inputs
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

GitHub is the release-facing companion surface. Zenodo is the archival host for large rerun-backed artifacts.

## Reproduction Contract

The default public rerun contract is the formal single-host path:

- the single Linux execution host
- eight visible GPUs
- each run stays on one GPU end-to-end
- one one-shot canonical rerun of the full `140`-run suite
- canonical release-facing output materialized into one `suite_all_models_methods` matrix index

The repository also supports an optional reviewer-safe two-host identical-execution-class sharded mode for throughput and reproduction. That sharded mode is not the release-facing result source. It is an optional execution mode that can be merged into one reviewer-local inspection-only matrix index.

## Release Closure Checklist

Before public release, verify:

- the canonical `suite_all_models_methods` matrix index is materialized and reports `140/140 success`
- README and docs uniformly describe the single-host 8-GPU formal release plus optional two-host 8+8 reproduction
- tracked full-run summary exports are populated under `results/figures/suite_all_models_methods/` and `results/tables/suite_all_models_methods/`
- GitHub excludes raw matrix trees, local residues, tokens, caches, and runtime upstream checkouts
- Zenodo metadata, checksums, environment capture, and model revision provenance are complete
