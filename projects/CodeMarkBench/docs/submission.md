# Submission Notes

`CodeMarkBench` should be presented first as a benchmark for measuring the reliability of source-code watermarking for LLM-based code generation.

The repository and release-facing wording should emphasize:

- benchmark
- evaluation
- reliability
- robustness gaps
- failure surfaces
- reproducibility

Avoid treating the repository as a survey, product pitch, or packaging-first artifact.

## Formal Release Order

1. Build canonical manifests.
2. Run benchmark and matrix audits.
3. Run standalone formal preflight.
4. Launch the detached canonical single-host full rerun.
5. After `140/140 success`, regenerate release-facing tables and figures.
6. Export and validate the GitHub companion mirror.
7. Separately validate the Zenodo sanitized bundle when the archive metadata
   files have been staged.

Formal commands:

```bash
python scripts/build_suite_manifests.py
python scripts/audit_benchmarks.py --profile suite
python scripts/audit_full_matrix.py --manifest configs/matrices/suite_all_models_methods.json --profile suite_all_models_methods --strict-hf-cache --model-load-smoke --runtime-smoke --skip-provider-credentials
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 bash scripts/remote/run_preflight.sh --formal-full-only
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 bash scripts/remote/run_formal_single_host_full.sh --command-timeout-seconds 259200
python scripts/reviewer_workflow.py regenerate --matrix-index results/matrix/suite_all_models_methods/matrix_index.json --figure-dir results/figures/suite_all_models_methods --table-dir results/tables/suite_all_models_methods
```

The older `run_suite_matrix.sh --run-full` wrapper remains engineering smoke only.

## Public Story

The public result-of-record contract is:

- the single-host execution environment
- single host
- `8` visible GPUs
- A/B-free standalone preflight
- direct canonical full `140/140`

The optional two-host `8+8` identical-execution-class sharded path remains reviewer-safe reproduction / throughput only. It is not the formal public result source.

The result narrative is failure-revealing rather than victory-claiming:
CodeMarkBench shows that current source-code watermarking methods can preserve
some detection and utility while still exposing limited robustness under
reviewer-safe program transformations. Low public robustness and strict zero
diagnostics are therefore expected evidence surfaces, not failed runs, when the
canonical matrix itself reports `140/140` success. Keep this reading aligned
with [`result_interpretation.md`](result_interpretation.md).

## Score Story

The paper and repo should use the same score definition:

\[
\mathrm{CodeMarkScore}=
\mathrm{Gate}\cdot
\mathrm{GM}\left(\mathrm{headline\_core\_score}, \mathrm{headline\_generalization}\right)
\]

with these interpretation rules:

- `CodeMarkScore` is a secondary summary
- exact-value tables and decomposition tables are the primary evidence surface
- public `robustness` uses the core reviewer-safe attack tier only
- stress attacks remain descriptive only
- strict/raw diagnostics remain exported for reviewer audit
- constant support fields such as `utility_support_rate = 1.0` and
  `semantic_validation_rate = 1.0` describe coverage/status, not perfect
  performance

## Figures And Tables

Keep the public figure surface narrow:

- `suite_all_models_methods_score_decomposition`
- `suite_all_models_methods_detection_vs_utility`
- `release_slice_composition`
- `evaluation_dimensions_overview`

Prefer table-first evidence for:

- per-attack robustness
- core-vs-stress robustness
- robustness factor decomposition
- utility factor decomposition
- generalization axis breakdown
- gate decomposition

## Packaging Split

- GitHub: code, docs, reviewer workflow, canonical inputs, tracked summary exports
- Zenodo: raw rerun-backed artifact, sanitized release bundle, environment capture, model roster, provenance metadata

Before upload, re-run the release mirror cleanliness gate and confirm that GitHub carries only the companion surface while Zenodo carries the raw rerun-backed artifact.
