# Reproducing `CodeMarkBench`

Start with **Level 1** unless you explicitly need regenerated full-run summaries or an end-to-end GPU rerun. If the original execution server is no longer available and you are rebuilding on a fresh cloud machine, use [`reproducibility.md`](reproducibility.md) as the operational checklist.

## Download The Companion Repository

Use current GitHub `main` for the latest reviewer-facing docs, validation
script, summary tables, and companion-surface updates:

```bash
git clone https://github.com/Haoyi-Zhang/CodeMarkBench.git
cd CodeMarkBench
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/verify_release_integrity.py
python scripts/reviewer_workflow.py browse --summary-only
```

If `git` is unavailable, download the public source archive instead:

```bash
curl -L -o CodeMarkBench-main.zip \
  https://github.com/Haoyi-Zhang/CodeMarkBench/archive/refs/heads/main.zip
unzip CodeMarkBench-main.zip
cd CodeMarkBench-main
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/verify_release_integrity.py
python scripts/reviewer_workflow.py browse --summary-only
```

The GitHub companion repository is enough for Level 1 inspection. Download the
Zenodo raw artifact only when you need Level 2 regeneration from the archived
raw matrix tree. A full Level 3 rerun also needs a fresh GPU host, model
snapshots, and pinned upstream baseline checkouts.

## Excluded White-Box Methods

The reproduction workflow mirrors the active canonical benchmark only:

- `CodeIP` is excluded because the public code exists but the official public artifact set is incomplete, so it cannot satisfy the official-public, runtime-comparable, reproducible benchmark standard used by this repository
- `Practical and Effective Code Watermarking for Large Language Models` is excluded because the official implementation follows a training/model-modifying path rather than the shared runtime-generation contract used here

Those two methods are documented as screened exclusions rather than runnable lanes in the workflow below.

## Level 1: Browse Summary Artifacts

No GPU is required.

Use the repository-tracked dataset statistics, documentation, and materialized full-run summary exports shipped with this companion repository:

- [`results/figures`](../results/figures)
- [`results/tables`](../results/tables)

This is the default reviewer path. It is the fastest way to inspect the benchmark design, dataset statistics, scoring rules, and the repository-tracked summary outputs that ship with the public companion repo.

If you already have rerun-backed summary JSON/tables in place and only want to refresh the full-run figure files without restoring the raw matrix tree, run:

```bash
python scripts/render_materialized_summary_figures.py --table-dir results/tables/suite_all_models_methods --output-dir results/figures/suite_all_models_methods --export-identity results/tables/suite_all_models_methods/suite_all_models_methods_export_identity.json
```

This redraw path is figure-only and publication-facing. It expects the canonical summary tables plus `suite_all_models_methods_export_identity.json`, which records the canonical matrix identity, the exact five-model pinned revision roster, and the required table hashes from the same rerun-backed export pass. Use it only when those summary tables and the export-identity sidecar already exist and were exported together from the same rerun-backed matrix.

## Level 2: Regenerate Figures And Tables From The External Raw Artifact

No GPU is required.

Use this path with the raw-results artifact described in [`docs/artifacts.md`](artifacts.md). Level 2 is the documented regeneration workflow for that external raw artifact; the GitHub companion repo does not ship the raw result tree by itself.

1. Download the raw result artifact described in [`docs/artifacts.md`](artifacts.md)
2. Restore the raw result tree under `results/matrix/`
3. Regenerate figures and tables:

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
```

```bash
python scripts/refresh_report_metadata.py --matrix-index results/matrix/suite_all_models_methods/matrix_index.json
python scripts/reviewer_workflow.py regenerate --matrix-index results/matrix/suite_all_models_methods/matrix_index.json --figure-dir results/figures/suite_all_models_methods --table-dir results/tables/suite_all_models_methods
python scripts/export_dataset_statistics.py
```

This path reproduces the summary outputs without rerunning models. The regeneration commands above are the authoritative Level 2 path for the external raw-results artifact.

If you specifically need a figure-only rerender after the canonical summary tables and JSON sidecars already exist, use:

```bash
python scripts/render_materialized_summary_figures.py --table-dir results/tables/suite_all_models_methods --output-dir results/figures/suite_all_models_methods --export-identity results/tables/suite_all_models_methods/suite_all_models_methods_export_identity.json --require-times-new-roman
```

If Times New Roman is unavailable on the machine, you can use `--allow-font-fallback` for a quick inspection pass. Final release figures should still be rendered with `--require-times-new-roman`.

For a one-click wrapper, use:

```bash
python scripts/reviewer_workflow.py regenerate --matrix-index results/matrix/suite_all_models_methods/matrix_index.json --figure-dir results/figures/suite_all_models_methods --table-dir results/tables/suite_all_models_methods
```

This wrapper now fails fast with a clear message if the requested matrix index does not exist yet. Canonical `suite_all_models_methods` figure/table output paths are reserved for the canonical full-suite matrix index; custom matrices must use custom output directories.
Treat `regenerate` as the canonical full-suite summary regeneration path. It is meant for the tracked `suite_all_models_methods` summary surface rather than an arbitrary unrelated matrix layout.
Use the redraw-only script above instead when you already have the materialized canonical summary tables and their export-identity sidecar and only need to redraw the retained suite publication-facing figures.

## Level 3: Rerun The Canonical Release Suite

GPU access is required.

### Prerequisites

- Python `3.10+`
- CUDA-capable Linux GPU host
- local toolchains for executable validation
- access to the following exact model identifiers:
  - `Qwen/Qwen2.5-Coder-1.5B-Instruct`
  - `Qwen/Qwen2.5-Coder-14B-Instruct`
  - `Qwen/Qwen2.5-Coder-7B-Instruct`
  - `bigcode/starcoder2-7b`
  - `deepseek-ai/deepseek-coder-6.7b-instruct`

For the rerun-backed public release, those identifiers are not enough by themselves. The release metadata should also pin the resolved local Hugging Face snapshot revision for each roster entry, using the cache's `refs/main -> snapshots/<revision>` mapping that was actually used during the run.

To anchor the Python side of a fresh rerun to the recorded CUDA 12.4 release
environment, install the project requirements with the release anchor
requirements:

```bash
python -m pip install --extra-index-url https://download.pytorch.org/whl/cu124 \
  -r requirements.txt -r requirements-remote.txt -r constraints-release-cu124.txt
```

Level 3 remains an end-to-end rerun path, so it still depends on external
availability of the pinned Hugging Face model snapshots and the pinned upstream
baseline repositories. GitHub plus Zenodo are sufficient for Level 1 inspection
and Level 2 archival summary regeneration without the original execution server.

### Upstream Baselines

The four official runtime baselines are fetched by pinned upstream provenance:

```bash
bash scripts/fetch_runtime_upstreams.sh all
```

### Reviewer Workflow

The canonical one-click reviewer workflow uses manifest generation plus a thin orchestration layer:

```bash
python scripts/reviewer_workflow.py browse
python scripts/reviewer_workflow.py regenerate --matrix-index results/matrix/suite_all_models_methods/matrix_index.json --figure-dir results/figures/suite_all_models_methods --table-dir results/tables/suite_all_models_methods
python scripts/reviewer_workflow.py subset --models Qwen/Qwen2.5-Coder-14B-Instruct --methods sweet_runtime --sources crafted_original
python scripts/reviewer_workflow.py subset --profile reviewer_subset_all_sources --models Qwen/Qwen2.5-Coder-14B-Instruct --methods sweet_runtime
python scripts/reviewer_workflow.py subset --models Qwen/Qwen2.5-Coder-7B-Instruct --methods kgw_runtime --sources humaneval_plus --limit 8
bash scripts/remote/run_reviewer_subset_pair.sh
```

The `.sh` and `.ps1` wrappers under [`scripts/`](../scripts/) expose the same flows to shell-native users:

```bash
bash scripts/reviewer_workflow.sh browse
bash scripts/reviewer_workflow.sh regenerate --matrix-index results/matrix/suite_all_models_methods/matrix_index.json --figure-dir results/figures/suite_all_models_methods --table-dir results/tables/suite_all_models_methods
bash scripts/reviewer_workflow.sh subset --models Qwen/Qwen2.5-Coder-14B-Instruct --methods sweet_runtime --sources crafted_original
PYTHON_BIN=/path/to/tosem_release_env/bin/python bash scripts/reviewer_workflow.sh subset --models Qwen/Qwen2.5-Coder-7B-Instruct --methods kgw_runtime --sources humaneval_plus --limit 8
powershell -ExecutionPolicy Bypass -File scripts/reviewer_workflow.ps1 browse
powershell -ExecutionPolicy Bypass -File scripts/reviewer_workflow.ps1 regenerate --matrix-index results/matrix/suite_all_models_methods/matrix_index.json --figure-dir results/figures/suite_all_models_methods --table-dir results/tables/suite_all_models_methods
powershell -ExecutionPolicy Bypass -File scripts/reviewer_workflow.ps1 subset --models Qwen/Qwen2.5-Coder-14B-Instruct --methods sweet_runtime --sources crafted_original
```

Bare `regenerate` commands target the canonical `configs/matrices/suite_all_models_methods.json` / `suite_all_models_methods` rerun-backed matrix index and its tracked `suite_all_models_methods` figure/table surface. Custom matrices must pass custom output directories and must not reuse the canonical release paths.

For `subset`, the workflow performs manifest build, benchmark audit, matrix audit, and environment capture before matrix execution. It assumes the upstream runtime checkouts and local model snapshots are already available on the machine; on a fresh machine, use the remote preflight path first.
The shell-native wrappers resolve `--python` first, then `PYTHON_BIN`, then a repo-local `.venv`. If neither is present, they accept an already-active dedicated virtualenv/current interpreter under `.venv` or `tosem_release*`, and otherwise fail fast with a clear interpreter error instead of silently picking an arbitrary ambient Python.
After `subset` starts, the workflow prints the generated manifest path, matrix index path, per-run log/report globs, and a ready-to-copy monitor command for `scripts/monitor_matrix.py`. The same subset monitor path can also be watched with `make matrix-monitor MATRIX_INDEX=<printed matrix index path>`.
Use distinct `--profile` values for repeated reviewer subsets whenever you want isolated manifests, lock files, environment captures, and output roots.
The canonical parallel reviewer gate reserves `suite_reviewer_subset_a` and `suite_reviewer_subset_b`; `bash scripts/remote/run_reviewer_subset_pair.sh` uses those explicit profiles so the A/B pair does not collide on one shared `.matrix_runner.lock`.
`subset` accepts `--benchmark-source` as an alias for `--sources`.
`subset --no-run` is a build-only path that writes the subset manifest without environment capture or matrix execution.
Append `--limit <n>` when you want a true micro-smoke for one model, one watermark, and one source instead of the entire selected source-group slice.
Add `--probe-hf-access` to `subset` when you want the readiness gate to verify token-backed Hugging Face access instead of relying only on the local snapshot/cache checks.
The formal release-facing rerun path is the single-host 8-GPU workflow documented in [`docs/remote_linux_gpu.md`](remote_linux_gpu.md). The publication-facing result-of-record contract is the completed single-host one-shot materialization with `140/140` successful runs. The identical-execution-class two-host sharded path remains available only as an optional reviewer-safe reproduction or throughput mode; it is not the release-facing result source.

### Local/Dev Workflow

```bash
bash scripts/fetch_runtime_upstreams.sh all
python scripts/build_suite_manifests.py
make suite-validate
python scripts/audit_full_matrix.py --manifest configs/matrices/suite_all_models_methods.json --profile suite_all_models_methods --strict-hf-cache --model-load-smoke --runtime-smoke --skip-provider-credentials
python scripts/audit_benchmarks.py --profile suite
# if you need a fresh non-resume local launch tree before a full run:
python scripts/clean_suite_outputs.py --include-full-matrix --include-release-bundle
```

`make suite-validate` alone is not a rerun-readiness proof. For a real rerun gate, use the explicit `audit_full_matrix.py` command above or the wrapped remote flow in [`scripts/remote/run_preflight.sh`](remote_linux_gpu.md). That gate now includes the evaluator-side offline load required by the canonical baseline-eval contract, not just cache presence and runtime/model smoke. The canonical single-host rerun contract is `bash scripts/remote/run_formal_single_host_full.sh --command-timeout-seconds 259200` on one eight-GPU Linux host after `run_preflight.sh --formal-full-only`; publication-facing status applies only after the canonical matrix reports `140/140 success`, as in the single-host result of record. Use the sharded identical-execution-class path in [`docs/remote_linux_gpu.md`](remote_linux_gpu.md) only when you explicitly want optional two-host reproduction or throughput.

### Linux Remote Workflow

See [`docs/remote_linux_gpu.md`](remote_linux_gpu.md) for the recommended optional environment capture, upstream fetch, A/B-free standalone preflight, reviewer-subset smokes, and explicit direct-full sequence. Reviewer subsets are recommended smokes, not an enforced formal gate in the single-host launcher. For a fresh non-resume single-host launch, explicitly reset the active outputs with `python scripts/clean_suite_outputs.py --include-full-matrix --include-release-bundle` when you need a fresh tree, and then run the formal helper without reusing prior outputs. The formal single-host path must never preserve an old result tree and does not support `--resume`. In reviewer-facing documentation, `--no-clean` is reserved only for `--skip-readiness --no-clean` in the second phase of the optional two-host shard flow after readiness has already passed for that same shard profile; the shard wrapper rejects `--no-clean` outside that continuation path. In that shard flow, `--no-clean` keeps the readiness/certification state; the launch step still cleans shard-local output artifacts before execution.

## Notes

- model weights are not distributed with this repository
- pinned upstream baseline checkouts are not stored in git
- rerun-backed publication should disclose the resolved snapshot revision for each released model identifier
- the active multilingual official-runtime comparison slice is `python/cpp/java/javascript/go`
- exact environment capture and reviewer notes live in [`docs/environment.md`](environment.md)
