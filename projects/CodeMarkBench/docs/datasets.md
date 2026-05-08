# Datasets And Active Slice

`CodeMarkBench` combines four public executable benchmark slices and three curated crafted multilingual benchmark families under one normalized schema. The repository presents one canonical public release suite with a stable, deterministic execution slice for the released benchmark.

Reviewer-facing execution truth lives under `data/release/sources/`.

## Active Execution Slice

The active aggregate suite score uses the following seven atomic source groups:

- `HumanEval+`
- `MBPP+`
- `HumanEval-X (5-language balanced slice)`
- `MBXP-5lang (5-language balanced slice)`
- `Crafted Original`
- `Crafted Translation`
- `Crafted Stress`

One sentence should be read as normative across the public repo:

> `HumanEval-X`, `MBXP-5lang`, and all three crafted sources are executed through the same five-language balanced runtime set: `python`, `cpp`, `java`, `javascript`, and `go`.

For the multilingual public slices, "five-language balanced slice" is a **source-level** statement, not a row-level one. The release JSONL files serialize one executed language per row, while the slice definition, release counts, and benchmark accounting remain fixed at the source level.

## Canonical Benchmark Definition Table

The machine-readable benchmark-definition table is exported to:

- [`results/tables/dataset_statistics/benchmark_definition_summary.csv`](../results/tables/dataset_statistics/benchmark_definition_summary.csv)
- [`results/tables/dataset_statistics/benchmark_definition_summary.json`](../results/tables/dataset_statistics/benchmark_definition_summary.json)

For quick review, the canonical release suite is summarized as:

| Source | Active release size | Scored in aggregate | Execution slice | Languages | Sampling rule | Type |
| --- | ---: | --- | --- | --- | --- | --- |
| `HumanEval+` | `164` | `Yes` | `python` | `python` | full retained | public |
| `MBPP+` | `378` | `Yes` | `python` | `python` | full retained | public |
| `HumanEval-X (5-language balanced slice)` | `200` | `Yes` | `python/cpp/java/javascript/go` | `python/cpp/java/javascript/go` | deterministic five-language balanced slice | public |
| `MBXP-5lang (5-language balanced slice)` | `200` | `Yes` | `python/cpp/java/javascript/go` | `python/cpp/java/javascript/go` | deterministic five-language balanced slice with smoke-overlay support | public |
| `Crafted Original` | `240` | `Yes` | `python/cpp/java/javascript/go` | `python/cpp/java/javascript/go` | curated five-language family/category-balanced crafted release family | crafted |
| `Crafted Translation` | `240` | `Yes` | `python/cpp/java/javascript/go` | `python/cpp/java/javascript/go` | curated five-language family/category-balanced crafted release family | crafted |
| `Crafted Stress` | `240` | `Yes` | `python/cpp/java/javascript/go` | `python/cpp/java/javascript/go` | curated five-language family/category-balanced crafted release family | crafted |

`release_slice_composition` is the README-facing figure because it shows exactly what the active release executes.

For source-level provenance, the single-language `HumanEval+` and `MBPP+` manifests now carry the same explicit `license_note` field style already used by the multilingual public slices:

- `HumanEval+`: `Apache-2.0; EvalPlus HumanEval+ release`
- `MBPP+`: `Apache-2.0; EvalPlus MBPP+ release`
- `HumanEval-X (5-language balanced slice)`: `Apache-2.0; CodeGeeX HumanEval-X benchmark`
- `MBXP-5lang (5-language balanced slice)`: `Apache-2.0; MXEval MBXP release`

## Crafted Benchmarks

The three crafted benchmark families serve distinct roles:

- `crafted_original`: native multilingual benchmark tasks
- `crafted_translation`: cross-language translation-oriented tasks
- `crafted_stress`: harder or more adversarial task structures intended to stress watermark robustness and utility

The crafted sources are released as curated benchmark families finalized under manual release review. In this repository, that means:

- task-family design plus manually reviewed task wording and contract wording at release time
- cross-language record checking, manual revision, and release finalization before publication
- deterministic manifest, parity, and release-consistency checks over the finalized release sources
- rerun-backed runtime validation is produced during execution workflows and is not embedded as row-level runtime annotations inside this public source snapshot

These crafted slices are intentionally part of the canonical benchmark rather than post hoc challenge extras. They are meant to expose reliability limits under harder multilingual benchmark conditions, and the public release keeps source-level exact-value tables so reviewers can separate public-slice behavior from crafted-slice failure surfaces instead of treating the crafted contribution as a hidden hardness confound.

Release-facing benchmark construction and review are checklist-driven. The public wording for the crafted benchmark families and the benchmark-level release packet is reviewed against the dataset schema, executable contract, and release-source manifests, and those crafted release sources should be described as curated release content.

Some frozen prompt, semantic-contract, or note strings inside the executed
crafted JSONL records still contain earlier release-family wording from the
result-of-record run. That wording is part of the archived benchmark input text
and is preserved so a fresh rerun uses the same prompts as the Zenodo raw
matrix; it should be interpreted as project-authored, manually reviewed curated
content rather than a claim about external expert credentials or a separate
expert-panel study.

`math/bit ops` belongs to the same curated crafted family inventory. It is reviewed and finalized under the same release process and should not be described as a separate auto-constructed public benchmark slice.

Reviewers should read the crafted rows as belonging only to the three crafted
release families listed above, not as separate public benchmark lanes, external
expert-panel datasets, or independent generated datasets.

For semantic-validation semantics, keep the source records and execution reports distinct:

- the release sources declare validation support at the manifest level through the benchmark metadata
- executed report summaries later separate `declared_*` semantic-support fields from `runtime_*` semantic-support fields
- the release source files should not be read as already containing rerun-backed runtime semantic annotations

For the public executable slices, some retained upstream test assets still contain phrases such as `manually generated tests` or `automatically generated tests`. Those phrases are preserved as part of the upstream benchmark content and do not describe the provenance of the crafted benchmark families or the release-layer contribution made by this repository.

For the public multilingual sources, the repository keeps the release truth explicit at the manifest level. `HumanEval-X` remains fully canonical across all five executed languages. `MBXP-5lang` uses a deterministic five-language balanced slice, and the manifest index makes two things explicit at the same time:

- the executed release size stays fixed at `200`
- the reference-support split is disclosed as `canonical` versus `smoke_overlay`

That means reviewers can audit where overlay-backed execution support is needed without confusing the executed release size with the reference-kind accounting.

The canonical naming layers are also intentionally split but stable:

- public display labels: `HumanEval-X (5-language balanced slice)` and `MBXP-5lang (5-language balanced slice)`
- manifest source keys: `humaneval_x` and `mbxp_5lang`
- release filenames: `suite_humanevalx_release.normalized.jsonl` and `suite_mbxp_release.normalized.jsonl`

The suite manifests now carry both the release-size map and the source-alias map so provenance joins do not have to infer those relationships from filenames alone.

## Statistics Files

Dataset statistics are exported under [`results/tables/dataset_statistics`](../results/tables/dataset_statistics) and [`results/figures/dataset_statistics`](../results/figures/dataset_statistics) using:

```bash
python scripts/export_dataset_statistics.py
```

Use the outputs with the following scope:

- `release_slice_composition`: README-facing figure for the active execution slice
- `release_slice_language_breakdown`: active execution-slice language coverage across all seven sources as the release-facing exact-value table
- `dataset_task_category_breakdown`: crafted-only category coverage as a release-facing exact-value table
- `dataset_family_breakdown`: crafted-only family coverage as a release-facing exact-value table
- `evaluation_dimensions_overview`: structural scorecard overview used alongside [`docs/metrics.md`](../docs/metrics.md)

The exported machine-readable tables include:

- `release_slice_summary.{csv,json}`
- `benchmark_definition_summary.{csv,json}`
- `release_slice_language_breakdown.{csv,json}`
- `release_source_manifest_index.{csv,json}`
- `dataset_task_category_breakdown.{csv,json}`
- `dataset_family_breakdown.{csv,json}`
