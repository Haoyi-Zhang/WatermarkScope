# Citation

If you use `CodeMarkBench`, cite both the GitHub companion repository and the
archival Zenodo record that stores the raw matrix artifact and release bundle:

```bibtex
@software{zhang_codemarkbench_2026,
  author = {Zhang, Haoyi},
  title = {{CodeMarkBench}: Corrected Canonical Raw Results and Release Bundle for Source-Code Watermarking Reliability Evaluation},
  year = {2026},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.19740954},
  url = {https://doi.org/10.5281/zenodo.19740954}
}
```

The repository-level citation metadata is also available in
[`CITATION.cff`](../CITATION.cff).

## Third-Party Components

The release uses public benchmark slices, local model snapshots, and pinned
upstream watermarking baselines. When reporting derived experiments, cite the
corresponding upstream projects or papers in addition to `CodeMarkBench`.

Baseline provenance for the four active runtime methods is recorded in
[`third_party/`](../third_party) and summarized in
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md). Those notices distinguish
between runtime provenance and redistribution status; three baseline upstream
licenses remain marked `unverified`, so the public release records fetchable
commit identities instead of redistributing those source trees.

The model roster and exact Hugging Face snapshot revisions are listed in the
root [`README.md`](../README.md) and in
[`results/tables/suite_all_models_methods/suite_all_models_methods_export_identity.json`](../results/tables/suite_all_models_methods/suite_all_models_methods_export_identity.json).
