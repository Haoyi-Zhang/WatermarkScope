# Interpreting the Released Results

This document is the reviewer-facing reading guide for the materialized
`suite_all_models_methods` release. It explains how to read the low robustness
values, strict zero diagnostics, and constant support fields without treating
them as run failures or hidden post-processing.

The release result is a completed canonical matrix: `run_count = 140`,
`success_count = 140`, `failed_count = 0`, and
`execution_mode = single_host_canonical`. The result should be read as evidence
that current source-code watermarking methods expose reliability gaps under a
common executable benchmark, not as evidence that the methods are uniformly
robust.

## Main Method-Level Reading

The method-level table below is copied from the tracked
`suite_all_models_methods_method_master_leaderboard.*` export. `CodeMarkScore`
is a compact secondary summary; the component columns and exact-value tables
are the primary evidence surface.

| Method | CodeMarkScore | Gate | HeadlineCore | HeadlineGeneralization | Detection | Robustness | Utility | Stealth | Efficiency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SWEET | 0.3827 | 0.4984 | 0.5904 | 0.9984 | 0.7220 | 0.3361 | 0.6467 | 0.4765 | 0.6988 |
| EWD | 0.3761 | 0.5000 | 0.5687 | 0.9948 | 0.7706 | 0.2645 | 0.6467 | 0.4649 | 0.6502 |
| STONE | 0.3504 | 0.5266 | 0.5843 | 0.7579 | 0.5312 | 0.3536 | 0.6509 | 0.4942 | 0.9809 |
| KGW | 0.3498 | 0.4920 | 0.5062 | 0.9985 | 0.6045 | 0.4439 | 0.6476 | 0.4721 | 0.1028 |

The key scientific reading is that detection can be nontrivial while
robustness remains limited. This is the intended failure-revealing behavior of
the benchmark. The public robustness values are not caused by crashed runs:
the canonical matrix is complete, and the method-level `robustness_support_rate`
is `1.0` for the four public method rows.

## Recommended Reviewer Reading Order

1. Start with
   `results/tables/suite_all_models_methods/suite_all_models_methods_method_master_leaderboard.*`
   for the method-level summary.
2. Read
   `suite_all_models_methods_utility_robustness_summary.*`,
   `per_attack_robustness_breakdown.*`, and
   `core_vs_stress_robustness_summary.*` before using
   the headline score.
3. Use
   `robustness_factor_decomposition.*`,
   `utility_factor_decomposition.*`,
   `generalization_axis_breakdown.*`, and
   `gate_decomposition.*` to audit why a score is
   high, low, zero, or unsupported.
4. Use the figures only as compact structure and trend views. Exact values
   live in the tables.

## Expected Zero and Constant Diagnostics

Some zero or constant fields are expected by the metric contract:

| Field pattern | Observed release behavior | Interpretation |
| --- | --- | --- |
| `raw_generalization_strict` | `0.0000` in the model-by-method scan | Strict fail-closed diagnostic. It falls to zero when a required raw stability axis is zero; it is not the public headline generalization value. |
| `raw_composite_strict` | `0.0000` in method-level rows | Strict top-level diagnostic using `Gate * raw_core_score_strict * raw_generalization_strict`; it is intentionally harsher than `CodeMarkScore`. |
| `utility_support_rate` | `1.0000` in the model-by-method scan | Coverage/status field: the public utility factors are available. It is not a claim that utility performance is perfect. |
| `semantic_validation_rate` | `1.0000` in the model-by-method scan | The released rows satisfy the semantic-validation predicate used by the utility factor. It is one exact-value utility component, not a claim that overall utility or model quality is perfect. |
| method-level `robustness_support_rate` | `1.0000` for the four public methods | Every core-tier attack row needed for the method-level public robustness aggregate is represented. This is not the same field as per-attack factor coverage. |
| per-attack `attack_support_rate` | may be below `1.0000` | Factor-level support within an attack row. It can be lower than method-level `robustness_support_rate` because it measures a narrower denominator. |
| model-by-method `cross_family_transfer` | blank/NA | Cross-family transfer is not evaluated at the per-model slice, because a single model row does not contain a cross-family model comparison. |
| model-by-method `scale_consistency` | blank/NA | Scale consistency is a diagnostic requiring a family-scale comparison, so it is not meaningful in isolated model rows. |

These fields are kept because they make reviewer auditing stricter. Removing
them would make the release look cleaner but less honest.

## Robustness Interpretation

The low public robustness values are the main empirical warning. For example,
the method-level public robustness values range from `0.2645` to `0.4439`, even
though detection and utility remain nonzero. This means the benchmark is
surfacing attacks and transformations that weaken watermark retention under the
published core tier.

The stress tier is exported separately through table-first evidence. It should
not be silently folded into the headline score or hidden behind a single
optimistic scalar. Reviewers should inspect both core-tier and stress-tier
tables when judging whether a method is robust enough for deployment.

`headline_generalization` should be read as a cross-slice stability summary
under the released matrix, not as a universal deployment-robustness guarantee.
The strict counterpart, `raw_generalization_strict`, is intentionally harsher
and can be zero when a required strict axis is unavailable or zero. Keeping both
fields is deliberate: the public headline avoids collapsing a table into one
special unsupported case, while the strict diagnostic preserves a fail-closed
audit trail.

Utility also remains table-first. `utility` summarizes supported quality,
semantic-preservation, and semantic-validation factors. It does not certify
that every generated program is optimal, and it should be checked alongside
`raw_utility_strict`, functional-quality tables, and timing tables.

For paper wording, avoid reducing the release to phrases such as "high utility"
or "strong generalization" without the accompanying strict diagnostics. The
public utility scalar is a support-aware arithmetic summary over supported
factors; low semantic-preservation or pass-preservation components remain
visible in the functional-quality and utility-factor tables. Likewise, headline
generalization is a released cross-slice stability summary under supported
axes, while `raw_generalization_strict` preserves the fail-closed diagnostic.
`Gate` should be described as a relative pass-preservation gate with a
negative-control penalty; it must be interpreted beside absolute clean and
watermarked pass rates, not as an absolute usability certificate.
In `gate_decomposition.*`, the `descriptive_*_test_pass_rate` columns are
absolute method-rollup context fields from the descriptive method summary, while
`gate` and `watermarked_pass_preservation` remain the source-balanced
master-leaderboard values used by the public scorecard.

Some frozen crafted-source prompt strings still contain the legacy phrase
`expert-constructed` because changing those strings after execution would change
the result-of-record input text. Treat that phrase as legacy benchmark wording,
not as a claim that an external expert panel authored or certified the tasks.

## Row-Count Semantics

Three row counts appear in the release and should not be conflated:

- release-source tasks: the seven source JSONL files contain the canonical
  task inputs (`164`, `378`, `200`, `200`, `240`, `240`, and `240` rows)
- per-run report rows: a run expands those source tasks through benchmark,
  language, watermark, attack, and evaluation records
- scored rows: leaderboard exports may remove duplicate or non-scoring rows
  before grouped scorecard evaluation

The exported `raw_row_count`, `row_count`, and `duplicate_rows_removed` columns
document that transition. They are bookkeeping fields, not evidence that the
canonical `5 x 4 x 7 = 140` run matrix changed.

## Repository and Artifact Split

GitHub is the lightweight companion surface: code, documentation, canonical
inputs, environment capture, and tracked summary tables/figures. The raw
`results/matrix/**` tree is intentionally not committed to git because it is a
large rerun-backed artifact. Zenodo or the external artifact channel carries
the raw matrix tree and the sanitized release bundle.

This split is designed to make the code repository clean while preserving the
complete raw evidence path for artifact evaluation.
