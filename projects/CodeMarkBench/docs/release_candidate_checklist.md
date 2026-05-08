# Manual Release Review Checklist

This document is the release-candidate checklist for the `CodeMarkBench` public surface. Use it to audit the GitHub companion repository and the Zenodo artifact boundary before public release.

## Locked Public Story

- release-facing result of record: single-host canonical execution
- visible-device contract: `CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7`
- target publication-facing completion state: one-shot `140/140 success`
- optional path only: identical-execution-class two-host sharded reproduction / throughput mode
- headline metric: `CodeMarkScore`
- efficiency semantics: generation-stage clean-vs-watermarked timing only

## GitHub Companion Surface

The companion repository review surface is expected to include:

- source code
- canonical release inputs
- reviewer workflow scripts
- release-facing documentation
- `docs/baseline_screening.md`
- `data/fixtures/benchmark.normalized.jsonl`
- `results/schema.json`
- `results/export_schema.json`
- dataset-statistics summary tables under `results/tables/dataset_statistics`
- dataset-statistics summary figures under `results/figures/dataset_statistics`
- tracked full-run summary tables under `results/tables/suite_all_models_methods`
- tracked full-run summary figures under `results/figures/suite_all_models_methods`

Validate this GitHub companion mirror with `scripts/export_publish_repo.py` plus the
repository residue scans in this checklist. `scripts/validate_release_bundle.py`
is intentionally reserved for the Zenodo sanitized bundle, because that archive
layer carries `baseline_provenance.json`, `bundle.manifest.json`, `SHA256SUMS.txt`,
`MANIFEST.txt`, and `EXCLUDED.txt`.

An archived companion payload must not include:

- `.git`
- `paper`
- `proposal.md`
- `configs/archive/**`
- `data/interim/**`
- `results/matrix/**`
- `results/matrix_shards/**`
- `results/audits/**`
- `results/certifications/**`
- `results/runs/**`
- `results/submission_preflight/**`
- `scripts/archive_suite_outputs.py`
- ad hoc validation harnesses, temporary controller scripts, relay scratch files, or intermediate export scratch directories
- duplicated, draft-only, or one-off temporary tests that do not protect the released public contract
- local control files, temporary residue, scratch outputs, or machine-specific state
- vendored runtime upstream checkouts

## Zenodo Release Surface

The archival Zenodo review surface has two distinct layers:

- a raw matrix artifact hosted separately from the sanitized companion bundle
- a sanitized release bundle that stays within the tracked companion boundary

The overall Zenodo deposition is expected to include:

- raw matrix artifact
- checksums
- environment-of-record capture
- exact model roster plus resolved revisions
- sanitized release bundle

The sanitized bundle must stay fail-closed:

- manifest-sourced `vendored_path` entries must stay under `third_party/`, and manifest-sourced `external_path` entries must stay under `external_checkout/`
- `results/audits/` must stay excluded
- `results/export_schema.json` must stay included
- `scripts/archive_suite_outputs.py` must stay excluded from the sanitized bundle
- copied `third_party/*.UPSTREAM.json` manifests must be bundle-sanitized and must not leak `.coordination` or other local checkout roots
- vendored baseline runtime checkouts must stay excluded unless redistribution status is explicitly cleared
- vendored baseline runtime checkouts, when allowed, must be staged from tracked git files only and must carry an exact staged-file roster in provenance
- tracked publishable files must not be symlinks
- staged bundle payload files must not be symlinks
- `bundle.manifest.json` counts and `SHA256SUMS.txt` self-check entries must stay internally consistent
- the staged bundle must include the generated release metadata files:
  - `baseline_provenance.json`
  - `bundle.manifest.json`
  - `SHA256SUMS.txt`
  - `MANIFEST.txt`
  - `EXCLUDED.txt`
- `results/environment/runtime_environment.{json,md}` must be refreshed on the execution host before the public review surface is finalized and must match the canonical single-host execution class

## Metrics And Wording Checks

- `CodeMarkScore` remains a multiplicative fail-closed headline:
  - `CodeMarkScore = Gate * GM(HeadlineCore, HeadlineGeneralization)`
- `CodeMarkScore` is presented as a secondary summary, while exact-value tables and raw submetrics remain the primary evidence surface
- reviewers must be able to see that a headline score of `0.0` can coexist with non-zero diagnostics such as `gate`, `efficiency`, `detection_separability`, or `utility`
- `generalization_supported = false` with empty available axes must be explained separately from supported axes that evaluate to `0.0`, and `generalization_status` must make that distinction explicit
- unsupported generalization must not appear as a misleading raw `1.0`; the release-facing contract is `generalization = null/N.A.` plus neutral `headline_generalization = 0.5`
- generation-stage timing remains the only efficiency input
- full-pipeline timing remains descriptive only

## English-Only And Provenance Checks

- release-facing docs are English-only
- no Chinese residue remains in release-facing text
- no AI-authorship framing appears
- benchmark construction and release-facing review are described as checklist-driven manual review
- public wording may use:
  - `curated benchmark`
  - `manual release review`
  - `checklist-driven release review`
- public wording must not use:
  - unsourced endorsement quotes
  - inflated claims that are not documented elsewhere

## Data And Baseline Provenance Checks

- `HumanEval+` and `MBPP+` manifests carry explicit `license_note` fields
- multilingual public-slice manifests keep explicit source-level provenance
- `STONE`, `SWEET`, and `EWD` remain `license_status: unverified`
- GitHub and the Zenodo sanitized bundle rely on provenance manifests plus pinned fetch workflow rather than vendored upstream runtime checkouts
- the raw archival artifact must not be described as a surrogate source-code mirror for `STONE`, `SWEET`, or `EWD`; for those baselines it publishes results plus provenance, and reviewers fetch source from the recorded upstream pins

## Summary Export Inventory

The companion repository is expected to ship:

- full-run leaderboards
- functional-quality tables
- descriptive timing tables
- score-decomposition figures
- detection-vs-utility figures
- release-slice composition and evaluation-overview figures
- source / model / language / attack breakdown tables instead of redundant breakdown figures
- utility-versus-robustness exact-value tables instead of a redundant tradeoff figure

## Final Cleanliness Gate

- the release-review working tree must not depend on `.tmp_*`, `_cmb_*`, relay tarballs, manual scratch directories, or temporary export workspaces
- only public-contract regression tests should remain in the shipped repository; temporary closure/debug/test harnesses must be removed before publication
- no staged bundle or GitHub surface may include intermediate artifacts that exist only to bootstrap local review
- final public-facing paths must be understandable without private local context or unpublished controller state

## Environment Capture Status

The repository carries the formal execution-host capture under:

- `results/environment/runtime_environment.json`
- `results/environment/runtime_environment.md`

Before publication, verify those two files were refreshed on the execution host and reflect the publication-facing single-host execution class. In particular, the release review should verify that the environment surface exposes the same visible execution class used by the formal run of record, including the reviewer-facing `CUDA_VISIBLE_DEVICES` setting, the visible GPU count, `execution_mode`, `code_snapshot_digest`, and `execution_environment_fingerprint`. The automated staging gate remains fail-closed: it requires both files to exist, requires `runtime_environment.json` to parse as a JSON object, requires structured `platform`, `python`, `packages`, `tools`, `gpu`, and `execution` sections, and rejects stale or nonfinal status wording in both release-facing environment files.

## Final Release Decision Gate

Before any public release, manually confirm:

- the GitHub file surface above is acceptable
- the Zenodo upload surface above is acceptable
- the README / artifacts / reproduce wording is final
- the metrics wording is final
- the shipped table/figure inventory is final
- the environment capture has been refreshed on the formal execution host
- the final public file surface is clean and free of redundant temporary files, one-off harnesses, and intermediate artifacts

Release only after the checks in this document are complete and the public surface is ready.
