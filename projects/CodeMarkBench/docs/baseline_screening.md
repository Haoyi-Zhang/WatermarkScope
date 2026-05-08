# Baseline Screening

This note records the reviewer-facing baseline-screening outcome for the current canonical release.

## Included Runtime Baselines

The active benchmark roster keeps four pinned runtime baselines:

- `STONE`
- `SWEET`
- `EWD`
- `KGW`

These four methods remain in scope because they can be executed through a shared runtime-generation contract for source-code watermarking in LLM-based code generation: the benchmark controls orchestration, local model loading, decoding policy, release inputs, and score computation while preserving the pinned upstream watermark logic.

The exact pinned repositories and commits for those four baselines live in [`third_party/`](../third_party/).

## Excluded White-Box Methods

Two white-box source-code watermarking methods for LLM-based code generation were screened for inclusion and then excluded from the active runtime roster.

Screening date for this release note: `2026-04-25`.

| Method | Public basis used for screening | Required assets for this benchmark | Why it is excluded from the active benchmark |
| --- | --- | --- | --- |
| `CodeIP` | ACL Anthology record: `https://aclanthology.org/2024.findings-emnlp.541/`; repository references were also checked through public project mentions. | A complete official-public runtime path with runnable embedding/detection code, reproducible assets, and a stable adapter contract for the same local-model generation loop used by the four active baselines. | The release did not identify a complete official-public artifact set that can be placed under the same runtime-generation contract without reconstructing missing method-specific assets. It is therefore documented as related work rather than listed on the active runtime leaderboard. |
| `Practical and Effective Code Watermarking for Large Language Models` / `ACW` | OpenReview record: `https://openreview.net/forum?id=RpE4HeuX69`; linked code: `https://github.com/TimeLovercc/code-watermark`. | A runtime-only watermarking adapter that can be executed without training or model modification under the benchmark-controlled generation policy. | The public method description and code path are centered on AST-guided learning/training and model-side watermark embedding. That is a valuable but different experimental contract, so it is outside the runtime-generation comparison surface used for `STONE`, `SWEET`, `EWD`, and `KGW`. |

These exclusions do not claim the methods are unimportant. They only state that the current benchmark release does not place them on the same active runtime leaderboard as `STONE`, `SWEET`, `EWD`, and `KGW`.

If future official artifacts expose a complete runtime-comparable path for
either method, the benchmark can add a new adapter and rerun the canonical
matrix as a new release rather than backfilling the current `140/140` result.

## Prior Work Outside The Active Roster

- `UIUC ICLR 2025 / llm-code-watermark` remains cited as prior robustness work.
- It is not treated as a redundant benchmark replacement or as an additional active baseline method in the canonical leaderboard.
