# Reproducibility Guide For A Fresh Cloud Host

This guide is the reviewer-facing recovery path for reproducing `CodeMarkBench`
after the original execution server is no longer available. The public release
is intentionally split into two durable pieces:

- GitHub companion repository: code, documentation, canonical inputs, reviewer
  workflow scripts, environment capture, and materialized summary tables/figures
- Zenodo archival artifact: raw rerun-backed matrix tree, checksums, and the
  sanitized release bundle used to rebuild the GitHub summary surface

The archived result of record is the completed canonical single-host run:
`run_count = 140`, `success_count = 140`, `failed_count = 0`, and
`execution_mode = single_host_canonical`.

The corrected published archival record is [10.5281/zenodo.19740954](https://doi.org/10.5281/zenodo.19740954).
It contains the raw matrix artifact, `raw_results_manifest.json`, `SHA256SUMS.txt`,
and the sanitized release bundle.

The exact file names in the archival record are:

- `CodeMarkBench-canonical-raw-results-suite_all_models_methods-20260424T183928.tar.zst`
- `CodeMarkBench-sanitized-release-bundle-20260425T181337.tar.zst`
- `raw_results_manifest.json`
- `SHA256SUMS.txt`

The raw archive is the matrix evidence layer. The sanitized bundle is a compact
repository-style snapshot of the release surface; GitHub `main` may contain
documentation, validation, or companion-surface publication updates after that
archived bundle was created.
For byte-identical restoration of the archived sanitized bundle, use the
GitHub commit recorded in `raw_results_manifest.json`
(`3252ca48e15416eee5259967aa735c969f7eb150` for the corrected deposition).
For the latest reviewer-facing companion tables, validation script, and
documentation updates, use current GitHub `main`; those later
companion-surface updates do not change the Zenodo raw matrix identity.

## What Can Be Reproduced

Use the three levels below depending on the review need.

| Level | Requires GPU | Requires Zenodo raw artifact | Purpose |
| --- | --- | --- | --- |
| Level 1 | No | No | Inspect the shipped benchmark definition, docs, summary tables, and figures. |
| Level 2 | No | Yes | Rebuild the tracked summary tables and figures from the archived raw matrix. |
| Level 3 | Yes | No | Re-execute the full benchmark on a fresh Linux GPU host. |

Level 2 is the exact archival regeneration path for the released tables and
figures. Level 3 is the end-to-end rerun path; it should match the benchmark
contract and completed-run invariants, while wall-clock timing, host metadata,
and cache-local details may differ from the archived server.

## Level 1: Inspect The Companion Repository

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/reviewer_workflow.py browse
python scripts/verify_release_integrity.py
```

This path is enough to inspect the benchmark, result interpretation, exported
tables, and retained publication-style figures without downloading model weights
or raw matrix files.
`verify_release_integrity.py` also checks the canonical manifest digest,
summary artifact hashes, run inventory, release-source row counts, and a small
public-surface token-marker scan. On a Windows working tree with CRLF line
endings, it reports the canonical manifest as valid if the LF-normalized bytes
match the published digest and warns about the line-ending difference.

Primary review files:

- `docs/result_interpretation.md`
- `docs/metrics.md`
- `docs/artifacts.md`
- `results/tables/suite_all_models_methods/`
- `results/figures/suite_all_models_methods/`
- `results/environment/runtime_environment.json`

## Level 2: Rebuild Summary Exports From Zenodo

Install the decompressor and download the Zenodo files:

```bash
sudo apt-get update
sudo apt-get install -y zstd ca-certificates curl
curl -L -o CodeMarkBench-canonical-raw-results-suite_all_models_methods-20260424T183928.tar.zst \
  'https://zenodo.org/records/19740954/files/CodeMarkBench-canonical-raw-results-suite_all_models_methods-20260424T183928.tar.zst?download=1'
curl -L -o CodeMarkBench-sanitized-release-bundle-20260425T181337.tar.zst \
  'https://zenodo.org/records/19740954/files/CodeMarkBench-sanitized-release-bundle-20260425T181337.tar.zst?download=1'
curl -L -o raw_results_manifest.json \
  'https://zenodo.org/records/19740954/files/raw_results_manifest.json?download=1'
curl -L -o SHA256SUMS.txt \
  'https://zenodo.org/records/19740954/files/SHA256SUMS.txt?download=1'
sha256sum -c SHA256SUMS.txt
```

Restore the raw matrix tree from the raw-results artifact so that the canonical
index exists at:

```text
results/matrix/suite_all_models_methods/matrix_index.json
```

The archive stores repo-relative paths, so extraction from the repository root
restores the expected layout:

```bash
tar --use-compress-program=zstd -xf CodeMarkBench-canonical-raw-results-suite_all_models_methods-20260424T183928.tar.zst -C .
```

Then regenerate the summary surface:

```bash
python scripts/refresh_report_metadata.py --matrix-index results/matrix/suite_all_models_methods/matrix_index.json
python scripts/reviewer_workflow.py regenerate \
  --matrix-index results/matrix/suite_all_models_methods/matrix_index.json \
  --figure-dir results/figures/suite_all_models_methods \
  --table-dir results/tables/suite_all_models_methods
python scripts/export_dataset_statistics.py
python scripts/reviewer_workflow.py browse
```

Expected archived-run invariants:

- `run_count = 140`
- `success_count = 140`
- `failed_count = 0`
- `execution_mode = single_host_canonical`

The companion repository intentionally does not store `results/matrix/**` in
git. The raw matrix is restored only from the archival artifact.

## Level 3: Full Rerun On A Fresh 8-GPU Linux Host

Recommended execution class:

- one Linux host
- eight visible CUDA devices; the released run used eight A800 40GB-class GPUs
- at least 32 CPU cores, 128 GB RAM, and 1.5 TB free disk are recommended for model caches, upstream checkouts, raw matrix outputs, and temporary archives
- Python `3.10+`
- C/C++, Java, Node.js, and Go toolchains for executable validation
- Hugging Face access for the exact pinned model identifiers in `README.md`

Fresh-host setup:

```bash
git clone https://github.com/Haoyi-Zhang/CodeMarkBench.git
cd CodeMarkBench
sudo apt-get update
sudo apt-get install -y build-essential git curl ca-certificates zstd nodejs npm openjdk-21-jdk golang-go
bash scripts/remote/bootstrap_linux_gpu.sh --install --venv .venv/tosem_release
source .venv/tosem_release/bin/activate
python -m pip install --extra-index-url https://download.pytorch.org/whl/cu124 \
  -r requirements.txt -r requirements-remote.txt -r constraints-release-cu124.txt
bash scripts/fetch_runtime_upstreams.sh all
python scripts/build_suite_manifests.py
```

Install `constraints-release-cu124.txt` as an additional requirements file, not
only as a resolver constraint. It pins the recorded release anchors
(`torch 2.6.0+cu124`, `transformers 4.57.6`, and `numpy 2.2.6`) from
`results/environment/runtime_environment.json`. The companion repository also
ships `results/environment/release_pip_freeze.txt`, captured from the formal
Linux release environment with `python -m pip freeze --all`, so reviewers can
audit the resolved package set used by the published single-host run. Level 3
still depends on
external availability of the pinned Hugging Face model snapshots and pinned
upstream baseline repositories; the GitHub plus Zenodo release is self-contained
for Level 1 inspection and Level 2 regeneration from the archived raw matrix,
not for redistributing model weights or all third-party baseline source trees.

Model-cache readiness is explicit. The release configs use local snapshot
loading for the formal run, so either pre-download the exact model revisions
listed in `README.md` into `model_cache/huggingface`, or run readiness with
token-backed probing before switching to strict cache-only execution:

```bash
python - <<'PY'
import os
from huggingface_hub import snapshot_download
from codemarkbench.suite import CANONICAL_SUITE_MODELS

token = os.environ.get("HF_ACCESS_TOKEN") or None
for spec in CANONICAL_SUITE_MODELS:
    snapshot_download(
        repo_id=spec.name,
        revision=spec.revision,
        cache_dir="model_cache/huggingface",
        token=token,
    )
PY
python scripts/check_model_access.py --token-env HF_ACCESS_TOKEN
python scripts/audit_full_matrix.py \
  --manifest configs/matrices/suite_all_models_methods.json \
  --profile suite_all_models_methods \
  --probe-hf-access \
  --model-load-smoke \
  --runtime-smoke \
  --skip-provider-credentials
```

Readiness gates:

```bash
make suite-validate
python scripts/audit_benchmarks.py --profile suite
python scripts/audit_full_matrix.py \
  --manifest configs/matrices/suite_all_models_methods.json \
  --profile suite_all_models_methods \
  --strict-hf-cache \
  --model-load-smoke \
  --runtime-smoke \
  --skip-provider-credentials
```

Formal single-host rerun:

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
  bash scripts/remote/run_preflight.sh --formal-full-only

CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
  bash scripts/remote/run_formal_single_host_full.sh --command-timeout-seconds 259200
```

After completion, regenerate the publication-facing summaries:

```bash
python scripts/reviewer_workflow.py regenerate \
  --matrix-index results/matrix/suite_all_models_methods/matrix_index.json \
  --figure-dir results/figures/suite_all_models_methods \
  --table-dir results/tables/suite_all_models_methods
python scripts/export_dataset_statistics.py
python scripts/reviewer_workflow.py browse
```

Final release figures are rendered with Times New Roman available and
`--require-times-new-roman`. If a fresh cloud host lacks that font, install it
or use `--allow-font-fallback` only for inspection, not for the final release
surface.

Monitor a long-running full matrix with:

```bash
python scripts/monitor_matrix.py --matrix-index results/matrix/suite_all_models_methods/matrix_index.json
tail -f results/launchers/suite_all_models_methods/latest.log
```

For custom experiments, use a different `--profile`, matrix output root, figure
directory, and table directory. Do not overwrite the canonical
`suite_all_models_methods` release surface unless intentionally rebuilding that
formal release.

## Validation Checklist

Use these checks before relying on a restored or rerun result:

```bash
python scripts/reviewer_workflow.py browse
python -m pytest \
  tests/test_export_full_run_tables.py \
  tests/test_render_materialized_summary_figures.py \
  tests/test_reviewer_workflow.py \
  tests/test_release_bundle_contract.py \
  tests/test_validate_release_bundle.py
```

For a restored raw artifact or a fresh full rerun, also verify:

- the canonical matrix index exists under `results/matrix/suite_all_models_methods/`
- the matrix reports `140/140` successful runs with `failed_count = 0`
- `results/tables/suite_all_models_methods/suite_all_models_methods_export_identity.json`
  records the canonical manifest/profile and `single_host_canonical`
- the figure and table directories contain the materialized summary exports
- the result interpretation remains table-first: low robustness and strict zero
  diagnostics are empirical findings, not failed executions
