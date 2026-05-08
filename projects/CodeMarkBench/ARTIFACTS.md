# Artifacts

See [docs/artifacts.md](docs/artifacts.md) for the canonical artifact-status, raw-results distribution, environment capture, and regeneration instructions.
See [docs/reproducibility.md](docs/reproducibility.md) for the fresh-cloud recovery path used when the original execution server is no longer available.

Published archival record:

- Zenodo DOI: [10.5281/zenodo.19740954](https://doi.org/10.5281/zenodo.19740954)
- Raw artifact: `CodeMarkBench-canonical-raw-results-suite_all_models_methods-20260424T183928.tar.zst`
- Raw artifact SHA-256: `29d0c20a5f5e99cc24d61e7479e4d788565161c78c3660e560412eb502d38a2d`

In the public companion repository:

- the publication-facing result-of-record contract is the completed single-host canonical matrix with `140/140` successful runs and `failed_count = 0`
- large raw full-run artifacts are not stored in git
- the helper templates under [artifacts/](artifacts) are release-engineering inputs, not the archival metadata itself
- the repository-tracked `results/figures/suite_all_models_methods/` and `results/tables/suite_all_models_methods/` directories now contain the materialized publication-facing summary exports for the canonical `140/140` single-host run
- [`docs/result_interpretation.md`](docs/result_interpretation.md) documents the intended failure-revealing reading of low robustness values, strict zero diagnostics, and constant support fields
- Level 2 regeneration is the documented path for rebuilding those summaries from the external raw artifact
- the publication split is GitHub for the lightweight companion repo and Zenodo for the rerun-backed raw artifact and sanitized release bundle
