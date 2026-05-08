# Threats To Validity

This document records release-facing limitations that reviewers should consider when interpreting the `CodeMarkBench` result surface.

## Construct Validity

`CodeMarkBench` evaluates source-code watermarking under executable generation, attack, validation, and detection workflows. The released metrics intentionally separate detection, robustness, utility, stealth, efficiency, gates, support rates, and generalization diagnostics. `CodeMarkScore` is a secondary roll-up, not a replacement for the exact-value tables.

Unsupported attack outcomes are not hidden failures. They mark cases where a transformation is not applicable to a language, source form, or attack contract. The summary tables expose support-rate and status fields so reviewers can distinguish unavailable attacks from supported attacks that fail.

The benchmark deliberately reports low robustness and strict zero diagnostics
when the data support that reading. These values are not polished away because
they are part of the empirical contribution: they show that detectable
watermarks can still be fragile under executable code transformations.

## Internal Validity

The formal result of record is the single-host canonical matrix with `140/140` successful runs. The companion repository includes summary figures, summary tables, environment capture, model revisions, and matrix identity metadata; raw per-run reports remain in the external archival artifact so that the GitHub surface stays small and reviewable.

The repository uses fail-closed release gates for the summary identity, environment capture, model roster, matrix identity, and required table/figure hashes. These gates reduce accidental drift between code, documentation, and result exports, but they do not replace independent review of the raw artifact.

The public `CodeMarkScore` is a compact secondary roll-up. It should not be
used as the sole internal-validity argument. The release keeps exact-value
leaderboards, per-attack robustness, core-vs-stress robustness, utility
decomposition, gate decomposition, strict diagnostics, and support rates so
reviewers can audit whether an apparent trend is driven by one component.

## External Validity

The canonical model roster is intentionally fixed to five local code generation models and exact snapshot revisions. Results should therefore be read as evidence for this release roster and not as a universal claim about all LLMs, all model scales, or all watermark implementations.

The multilingual comparison uses a balanced five-language execution slice. That choice improves comparability across methods and sources, but it does not exhaust every programming language, task style, or deployment setting.

The active baseline roster is restricted to four pinned runtime baselines that
can share one generation-time comparison contract. Excluded training or
model-modifying methods are not judged inferior; they are outside the current
runtime-only leaderboard and should be evaluated with their own compatible
contract in a future release.

## Reproducibility Validity

Level 1 review requires no GPU and uses the shipped summary artifacts. Level 2 regenerates the summary surface from the external raw artifact. Level 3 reruns the canonical suite on a GPU host with the documented eight-device execution class. These levels are intentionally separated because the raw full-run matrix and model weights are too large for the GitHub companion repository.

The formal GPU rerun depends on local model snapshots, upstream runtime checkouts, CUDA-compatible PyTorch, and toolchains for executable validation. The release docs and remote bootstrap scripts document these dependencies, but reviewers should expect full reruns to require substantial GPU time and storage.

The raw artifact and sanitized bundle are preserved in Zenodo so that the
original cloud server does not need to remain online. A fresh host must still
recover model snapshots, pinned upstream checkouts, compilers/runtimes, and a
CUDA-capable PyTorch environment before running the Level 3 full rerun.

## Artifact Validity

GitHub intentionally excludes raw `results/matrix/**`, launcher logs, caches,
certification scratch files, and external checkouts. This keeps the companion
repository reviewable and avoids publishing machine-specific state, but it also
means Level 2 regeneration requires the Zenodo raw artifact. The release split
is therefore part of the artifact contract rather than an omission.

Environment captures use public-safe host and interpreter labels in the
published companion surface. Hardware class, CUDA visibility, package
versions, code snapshot digest, and execution fingerprint remain available for
audit, while private host aliases and absolute virtualenv paths are not needed
for scientific reproducibility.
