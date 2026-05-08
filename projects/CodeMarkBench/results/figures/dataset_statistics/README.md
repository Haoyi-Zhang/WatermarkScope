# Dataset Statistics Figures

This directory contains the release-facing dataset statistics figures for the canonical public suite.

Use the figures with the following contract:

- `release_slice_composition.*`: empirical release-slice composition for the seven executed source groups
- `evaluation_dimensions_overview.*`: conceptual scorecard overview, not empirical method performance. The radar panel
  uses full metric labels and a schematic structural wheel to make the scorecard hierarchy legible; it is not a radar
  score plot and does not encode additive weights, coefficients, measured values, or method scores. The PL-style
  derivation panel shows metric dependencies: `HeadlineGen` denotes the headline-transformed generalization term, and
  the `Stealth` / `Efficiency` nodes correspond to the conditioned headline-core factors. Exact values remain
  table-first.

For exact counts, the machine-readable tables under `results/tables/dataset_statistics/` remain the primary evidence surface. In particular, `release_slice_language_breakdown.*`, `dataset_task_category_breakdown.*`, and `dataset_family_breakdown.*` are table-first release artifacts rather than public figures.

In particular:

- `evaluation_dimensions_overview.*` is a structural explanation figure that should be read together with [`docs/metrics.md`](../../../docs/metrics.md)
- `release_slice_composition.*` is the only empirical dataset figure retained in the default public figure roster
