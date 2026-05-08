# Release Sources

This directory contains the exact normalized source files executed by the canonical public release suite.

The current release truth is:

- `suite_humaneval_plus_release.normalized.jsonl`
- `suite_mbpp_plus_release.normalized.jsonl`
- `suite_humanevalx_release.normalized.jsonl`
- `suite_mbxp_release.normalized.jsonl`
- `crafted_original_release.normalized.jsonl`
- `crafted_translation_release.normalized.jsonl`
- `crafted_stress_release.normalized.jsonl`

These files are the reviewer-facing execution truth for dataset statistics, subset manifests, and full-suite manifests.

Provenance is intentionally split:

- `suite_humaneval_plus_release`, `suite_mbpp_plus_release`, `suite_humanevalx_release`, and `suite_mbxp_release` are public benchmark execution slices
- `crafted_original_release`, `crafted_translation_release`, and `crafted_stress_release` are curated crafted benchmark families with manually finalized public release records

For the multilingual public execution layer, `HumanEval-X`, `MBXP-5lang`, and all three crafted families are interpreted through the same balanced five-language runtime set: `python`, `cpp`, `java`, `javascript`, and `go`. `MBXP-5lang` remains a deterministic five-language balanced slice with explicit smoke-overlay support in the release metadata.

For those multilingual public slices, the balanced five-language claim is defined at the source level. The normalized JSONL files are intentionally serialized one executed language per row, so reviewer-facing row metadata should be read as per-language execution records inside a fixed five-language release slice, not as a contradiction of the slice definition.

Naming is also layered on purpose:

- public labels: `HumanEval-X (5-language balanced slice)`, `MBXP-5lang (5-language balanced slice)`
- manifest keys: `humaneval_x`, `mbxp_5lang`
- release files: `suite_humanevalx_release.normalized.jsonl`, `suite_mbxp_release.normalized.jsonl`

Those aliases all refer to the same two public multilingual sources.

The normalized source files are frozen execution inputs for the completed run. Some task text may preserve generation-time wording from the canonical input snapshot; the release-facing claim is the documented curated/manual-review process for the three crafted families, not a credential claim about external certified experts.

Some public benchmark rows also retain upstream test-section wording such as `manually generated tests` or `automatically generated tests`. That wording belongs to the upstream executable benchmark assets and should not be read as a claim about how the crafted release families in this repository were constructed.

This source layer tracks release truth and finalized provenance. Execution-backed semantic-validation evidence is generated during benchmark runs and export regeneration rather than embedded as row-level runtime annotations in the pre-run public snapshot.

