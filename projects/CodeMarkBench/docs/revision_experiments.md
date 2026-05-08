# Revision And Follow-Up Experiments

This document is for authors or reviewers who want to extend `CodeMarkBench`
after the canonical release, for example during a revision cycle.

## Keep The Canonical Surface Frozen

The published `suite_all_models_methods` release surface is intentionally
frozen:

- do not overwrite `results/tables/suite_all_models_methods/`
- do not overwrite `results/figures/suite_all_models_methods/`
- do not reuse `results/matrix/suite_all_models_methods/` for exploratory runs
- do not change the canonical `5 x 4 x 7 = 140` matrix when adding a follow-up
  experiment

Use a new `--profile` and custom output paths for every revision experiment.

## Reviewer Subsets Within The Canonical Roster

For a smaller run that still uses only the published models, methods, and
sources:

```bash
python scripts/reviewer_workflow.py subset \
  --profile revision_subset_qwen14b_sweet \
  --models Qwen/Qwen2.5-Coder-14B-Instruct \
  --methods sweet_runtime \
  --sources crafted_original \
  --limit 32
```

The subset builder now rejects unknown model, method, or source filters with a
message listing the canonical values. That is deliberate: subset mode filters
the release roster; it is not a custom-method or custom-model registration API.

## Adding New Models, Methods, Or Sources

Non-canonical follow-up experiments are possible, but they currently require a
small code-and-config change rather than only a command-line flag.

Expected touch points:

- model roster and revisions: [`codemarkbench/suite.py`](../codemarkbench/suite.py)
- method registry/adapters: [`codemarkbench/watermarks/registry.py`](../codemarkbench/watermarks/registry.py),
  method-specific adapter code, and baseline provenance under [`third_party/`](../third_party)
- source definitions and release files: [`codemarkbench/suite.py`](../codemarkbench/suite.py),
  [`scripts/build_suite_manifests.py`](../scripts/build_suite_manifests.py),
  and [`data/release/sources/`](../data/release/sources)
- manifest generation: [`scripts/build_suite_manifests.py`](../scripts/build_suite_manifests.py)
- documentation and summary exports: `docs/`, `results/tables/`, and
  `results/figures/` under a new non-canonical profile

This explicit list is meant to prevent accidental partial updates. A later
engineering cleanup can move the roster to a single machine-readable spec, but
the current release keeps the canonical roster fixed in code so the archived
result identity remains stable.

## Fresh-Clone Smoke Checks

After a follow-up change, run at least:

```bash
python scripts/reviewer_workflow.py browse --summary-only
python scripts/verify_release_integrity.py
python scripts/build_suite_manifests.py \
  --output-manifest results/matrix/subsets/revision_smoke.json \
  --profile revision_smoke \
  --models Qwen/Qwen2.5-Coder-14B-Instruct \
  --methods sweet_runtime \
  --sources crafted_original \
  --limit 4 \
  --skip-refresh-prepared-inputs
```

On a GPU host, follow the readiness and rerun commands in
[`docs/reproducibility.md`](reproducibility.md) or
[`docs/remote_linux_gpu.md`](remote_linux_gpu.md).
