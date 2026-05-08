# Metrics And `CodeMarkScore`

`CodeMarkBench` releases two score layers on purpose:

- **strict/raw diagnostics**: coverage-explicit, useful for auditing failure modes; unsupported top-level strict
  generalization and the strict composite remain fail-closed
- **public/release-facing summaries**: support-aware, used for tables, figures, and headline interpretation

The benchmark is designed so reviewers can inspect both layers. The public summaries are not meant to hide failures; they are meant to avoid misleading collapses where one special `0` or one unsupported slice wipes out the entire headline surface.
The public summary separates measured supported evidence from coverage/status diagnostics so unsupported slices and true zero outcomes remain visible in exact-value tables instead of being conflated into one opaque scalar.

Primary evidence is always:

- exact-value tables
- per-attack and per-tier breakdowns
- factor decompositions
- gate diagnostics

`CodeMarkScore` is a **secondary summary**, not the only result surface.
It is not a weighted average of the displayed dimensions. The score is a
gated, non-compensatory roll-up whose components remain visible in tables so
reviewers can audit whether a method is limited by detection, robustness,
utility, stealth, efficiency, or stability.

## Released Public Fields

The release-facing scorecard centers on:

- `gate`
- `detection_separability`
- `robustness`
- `utility`
- `stealth`
- `efficiency`
- `stealth_conditioned`
- `efficiency_conditioned`
- `core_score`
- `headline_core_score`
- `generalization`
- `headline_generalization`
- `generalization_status`
- `CodeMarkScore`

The scorecard also releases strict/raw diagnostics:

- `raw_robustness_strict`
- `raw_utility_strict`
- `raw_core_score_strict`
- `raw_generalization_strict`
- `raw_composite_strict`
- `scale_consistency`

The release surface also exports support/status fields:

- `robustness_status`
- `robustness_support_rate`
- `stress_robustness`
- `utility_status`
- `utility_support_rate`
- `generalization_available_axes`

Table-first diagnostics additionally export:

- `attack_tier`
- `attack_robustness`

## Attack Tiers

`CodeMarkBench` does not use one mixed attack pool as the public robustness definition.

### Core reviewer-safe tier

The public `robustness` metric uses only:

- `whitespace_normalize`
- `comment_strip`
- `identifier_rename`
- `noise_insert`

These are the release-facing edit attacks used for the main robustness claim.

### Stress tier

The benchmark also executes:

- `control_flow_flatten`
- `block_shuffle`
- `budgeted_adaptive`

These remain part of the benchmark, but they are released as a **stress surface**, not as the ordinary-edit definition of public robustness.

## Gate

`Gate` remains intentionally fail-closed:

\[
\mathrm{Gate}=\min\left(
\mathrm{watermarked\_pass\_preservation},
1-\mathrm{negative\_control\_fpr},
\mathrm{negative\_control\_support\_rate}
\right)
\]

This part is not softened. It is a relative pass-preservation gate with a
negative-control penalty, not a standalone absolute usability certificate. If a
method does not preserve executable behavior relative to its own clean
generation baseline, the headline should be heavily penalized; absolute clean
and watermarked pass rates remain in the functional-quality tables.

## Public Robustness

Public robustness is computed in two steps.

### Step 1: per-attack public robustness

For each supported **core-tier** attack \(a\):

\[
\mathrm{attack\_robustness}_a =
\mathrm{AM}\left(
\mathrm{attack\_retention}_a,
\mathrm{attack\_attacked\_detected\_semantic\_rate}_a,
\mathrm{attack\_attacked\_pass\_preservation}_a
\right)
\]

where:

- `attack_retention`
- `attack_attacked_detected_semantic_rate`
- `attack_attacked_pass_preservation`

are the three public attack factors.

Coverage is exported separately as:

\[
\mathrm{attack\_support\_rate}_a=\frac{\text{supported attack factors}}{3}
\]

### Step 2: aggregate across core attacks

\[
\mathrm{robustness}=
\mathrm{AM}\left(\mathrm{attack\_robustness}_a\right)
\]

with:

\[
\mathrm{robustness\_support\_rate}=
\frac{\text{supported core attacks}}{\text{total core attacks}}
\]

This design means:

- one failed attack still hurts
- coverage gaps stay visible through `attack_support_rate` and `robustness_support_rate`
- but one special `0` no longer forces the public aggregate to `0` when other supported attacks remain non-zero

In the suite-level master leaderboard, this aggregate is first computed within
each source group and then source-balanced. Therefore the master `robustness`
value is not expected to equal a naive arithmetic mean over the descriptive
per-attack rows.

The two support fields intentionally have different denominators:

- `robustness_support_rate` is method-level core-attack coverage
- `attack_support_rate` is factor-level coverage within one attack row

A method can therefore show `robustness_support_rate = 1.0` while a specific
attack row has lower factor-level support. That combination means the core-tier
attack family is represented, not that every lower-level factor is perfect.

### Strict robustness diagnostic

The strict/raw release keeps a supported-factor diagnostic:

\[
\mathrm{raw\_attack\_robustness\_strict}_a =
\mathrm{GM}\left(\text{supported attack factors}\right)
\]

and:

\[
\mathrm{raw\_robustness\_strict}=
\mathrm{GM}\left(\mathrm{raw\_attack\_robustness\_strict}_a\right)
\]

This strict surface is still useful for failure auditing, but it is not the public headline definition. Coverage gaps are
reported through the support-rate fields rather than silently treated as evidence.

### Stress robustness

Stress attacks are aggregated separately:

\[
\mathrm{stress\_robustness}=
\mathrm{AM}\left(\mathrm{stress\ attack\_robustness}_a\right)
\]

Stress-attack coverage remains visible through per-attack support rates and the table-first breakdowns, and `stress_robustness` is descriptive only. It does **not** enter `CodeMarkScore`.
The `per_attack_robustness_breakdown` table is an attack-level descriptive
sidecar from the master score coverage; use
`core_vs_stress_robustness_summary` for the source-balanced master robustness
value that enters the headline path.

## Public Utility

Public utility is support-aware.

The public utility factors are:

- `quality_score_mean`
- `semantic_preservation_rate`
- `semantic_validation_rate`

The released public utility is:

\[
\mathrm{utility}=
\mathrm{AM}\left(\text{supported utility factors}\right)
\]

with:

\[
\mathrm{utility\_support\_rate}=
\frac{\text{supported utility factors}}{3}
\]

The public scalar and its support rate are intentionally separated: the scalar summarizes supported evidence, while `utility_support_rate` exposes coverage without double-penalizing the main value.

The strict/raw diagnostic remains:

\[
\mathrm{raw\_utility\_strict}=
\mathrm{GM}\left(\text{supported utility factors}\right)
\]

## Strict And Public Core Views

The released public unsmoothed core view is:

\[
\mathrm{core\_score}=
\mathrm{GM}\left(
\mathrm{detection\_separability},
\mathrm{robustness},
\mathrm{utility},
\mathrm{stealth\_conditioned},
\mathrm{efficiency\_conditioned}
\right)
\]

The strict/raw diagnostic counterpart is:

\[
\mathrm{raw\_core\_score\_strict}=
\mathrm{GM}\left(
\mathrm{detection\_separability},
\mathrm{raw\_robustness\_strict},
\mathrm{raw\_utility\_strict},
\mathrm{raw\_stealth\_conditioned\_strict},
\mathrm{raw\_efficiency\_conditioned\_strict}
\right)
\]

`raw_core_score_strict` is not the headline score. It exists so strict transfer and scale diagnostics can be computed from a genuinely strict core surface rather than from the softened public summary.
When the strict top-level path reaches zero, that is a real diagnostic signal,
not a crashed-run marker. The canonical release matrix itself remains complete
only when `run_count = 140`, `success_count = 140`, and `failed_count = 0`.

## Conditioned Stealth And Efficiency

`stealth` and `efficiency` remain standalone released diagnostics.

Their public conditioned variants use public utility:

\[
\mathrm{stealth\_conditioned}=\sqrt{\mathrm{stealth}\cdot \mathrm{utility}}
\]

\[
\mathrm{efficiency\_conditioned}=\sqrt{\mathrm{efficiency}\cdot \mathrm{utility}}
\]

`efficiency` uses only generation-stage clean-vs-watermarked token-normalized timing. Attack, validation, detection, and full pipeline wall-clock remain descriptive timing surfaces and are not direct headline-score inputs.

## Headline Core

The headline layer applies the same soft floor to all five public core pillars:

\[
\mathrm{headline}(x)=0.05 + 0.95x
\]

Then:

\[
\mathrm{headline\_core\_score}=
\mathrm{GM}\left(
\mathrm{headline\_detection},
\mathrm{headline\_robustness},
\mathrm{headline\_utility},
\mathrm{headline\_stealth\_conditioned},
\mathrm{headline\_efficiency\_conditioned}
\right)
\]

This keeps the headline non-compensatory while avoiding pathological "everything collapses to zero because one public pillar hit zero" behavior.

## Generalization

The axis definitions stay the same:

- `source_stability`
- `task_stability`
- `language_stability`
- `cross_family_transfer`

The strict/raw diagnostic remains:

\[
\mathrm{raw\_generalization\_strict}=
\mathrm{GM}\left(\text{available axes}\right)
\]

The public release-facing summary is:

\[
\mathrm{generalization}=
\mathrm{AM}\left(\text{available axes}\right)
\]

For the public axes, slice-level `core_score` values are only treated as available observations when their underlying public `robustness` and `utility` are supported. Unsupported slices are excluded from public stability/generalization rather than coerced to real zero observations.

If no axis is available:

- `generalization = null`
- `generalization_status = unsupported`
- `headline_generalization = 0.5`

Otherwise:

\[
\mathrm{headline\_generalization}=0.05 + 0.95\cdot \mathrm{generalization}
\]

This makes unsupported generalization neutral rather than misleadingly perfect, while still letting supported-zero slices remain visibly weak.
`headline_generalization` is therefore a released cross-slice stability
summary. It must not be described as absolute deployment robustness across all
models, languages, tasks, or future watermarking methods.

Descriptive rollups can also emit:

- `robustness_status = descriptive_mixed`
- `utility_status = descriptive_mixed`
- `generalization_status = descriptive_mixed`

to indicate a table row is averaging already-exported grouped scorecards rather than issuing a fresh grouped verdict.

## Final `CodeMarkScore`

The public headline formula is:

\[
\mathrm{CodeMarkScore}=
\mathrm{Gate}\cdot
\mathrm{GM}\left(
\mathrm{headline\_core\_score},
\mathrm{headline\_generalization}
\right)
\]

This replaces the old three-way direct product.

Why:

- `Gate` stays as the hard trust/usability filter
- `HeadlineCore` and `HeadlineGeneralization` still combine non-compensatorily
- but the final score is no longer over-compressed by multiplying three already-compressed terms directly

The strict top-level diagnostic is preserved as:

- `raw_composite_strict`

where:

\[
\mathrm{raw\_composite\_strict}=
\mathrm{Gate}\cdot
\mathrm{raw\_core\_score\_strict}\cdot
\mathrm{raw\_generalization\_strict}
\]

with unsupported strict generalization treated fail-closed as `0` rather than neutralized. This field is diagnostic only.

## How To Read Zero Values

A released public zero does **not** automatically mean every lower-level item is zero.

In particular:

- `robustness = 0` does **not** mean every attack is `0`
- it means the public core-tier robustness aggregate is `0`
- you must read it together with:
  - `attack_robustness`
  - `robustness_status`
  - `robustness_support_rate`
  - `raw_robustness_strict`
  - the per-attack tables

Likewise:

- `CodeMarkScore = 0` does not mean every submetric is `0`
- it can also happen because `Gate = 0`
- or because a headline layer is heavily penalized

That is why `CodeMarkBench` treats:

- exact-value tables
- factor decomposition
- per-attack and per-tier breakdowns

as the primary evidence surface.

## Table-First Evidence Surfaces

The release-facing export contract explicitly expects table-first evidence for:

- `per_attack_robustness_breakdown`
- `core_vs_stress_robustness_summary`
- `robustness_factor_decomposition`
- `utility_factor_decomposition`
- `generalization_axis_breakdown`
- `gate_decomposition`

These should be read before the headline score.
Rows with `aggregation_view = suite_method_master_leaderboard` use the same
source-balanced master-leaderboard contract as the method table. Rows tagged as
descriptive attack breakdowns expose attack-level factors and support rates,
but they are not a recipe for reconstructing the source-balanced headline by a
single unweighted mean.
In `gate_decomposition.*`, `gate`, `watermarked_pass_preservation`, and
negative-control fields follow the master-leaderboard contract; the
`descriptive_*_test_pass_rate` columns are absolute method-rollup context fields
included only to keep the relative gate interpretable.

## Diagnostic-Only Scale Consistency

`scale_consistency` remains released, but it is diagnostic-only in this iteration. It does not enter the current headline score. This keeps within-family scale variation visible without giving one family disproportionate influence over the final public headline.
