# Baseline Provenance

This repository treats the runtime methods used in the release as pinned upstream baseline implementations with explicit per-method provenance. Each runtime method is pinned to its upstream repository, then executed through project-native adapters that keep the watermark algorithm logic intact while routing orchestration, local model loading, and decoding policy through the shared benchmark layer:

- `stone_runtime` -> `third_party/STONE-watermarking.UPSTREAM.json`
- `sweet_runtime` -> `third_party/SWEET-watermark.UPSTREAM.json`
- `ewd_runtime` -> `third_party/EWD.UPSTREAM.json`
- `kgw_runtime` -> `third_party/KGW-lm-watermarking.UPSTREAM.json`

## Baseline Matrix

| Method | Upstream repository | Pinned commit | Source subpath | License status |
| --- | --- | --- | --- | --- |
| `stone_runtime` | `https://github.com/inistory/STONE-watermarking.git` | `bb5d809c0c494a219411e861f2313cca2b9fd7b4` | `stone_implementation` | `unverified` |
| `sweet_runtime` | `https://github.com/hongcheki/sweet-watermark.git` | `853b47eb064c180beebd383302d09491fc98a565` | `.` | `unverified` |
| `ewd_runtime` | `https://github.com/luyijian3/EWD.git` | `605756acf802528a3df89d95a4661a031eafc79b` | `.` | `unverified` |
| `kgw_runtime` | `https://github.com/jwkirchenbauer/lm-watermarking.git` | `82922516930c02f8aa322765defdb5863d07a00e` | `.` | `redistributable` |

## Auxiliary Provenance Helpers

- `bash scripts/fetch_runtime_upstreams.sh all` fetches the pinned upstream checkouts for the canonical runtime baselines, refuses remote-url or dirty-tree mismatches, and re-pins a clean checkout whose `HEAD` drifted away from the recorded commit.
- `python scripts/run_runtime_family.py --family runtime_official ...` is a low-level diagnostic helper for adapter debugging; it is not the primary active workflow.
- `python scripts/evaluate_baseline_family.py --input results/runs/<run_id>` is a low-level analysis helper for imported baseline diagnostics; it is not the primary active workflow.
- `stone_runtime` uses the upstream `stone_implementation` subpath recorded in `third_party/STONE-watermarking.UPSTREAM.json`.
- `kgw_runtime` is pinned to the upstream repository named `lm-watermarking`, recorded in `third_party/KGW-lm-watermarking.UPSTREAM.json`.

## Primary Active Workflow

- `make suite-precheck` remains an engineering smoke gate on the current active benchmark.
- The formal release-facing rerun path is the single-host 8-GPU workflow documented in [`docs/remote_linux_gpu.md`](remote_linux_gpu.md).
- `bash scripts/remote/run_formal_single_host_full.sh` is the canonical single-host full-suite entrypoint.
- The identical-execution-class two-host sharded path remains available only as an optional reviewer-safe reproduction and throughput mode.

## Packaging Rule

- `scripts/package_zenodo.sh` always records a per-method `baseline_provenance.json` entry for `stone`, `sweet`, `ewd`, and `kgw`.
- the staged public release bundle is expected to include the refreshed `results/environment/runtime_environment.json` and `results/environment/runtime_environment.md` files alongside that provenance map
- Only redistributable vendored snapshots are bundled into the public release artifact. In the current release, `STONE`, `SWEET`, and `EWD` remain `license_status: unverified`, so both the GitHub companion repo and the Zenodo sanitized bundle keep those runtime checkouts out of the published payload and expose only provenance manifests plus fetch workflow.
- `KGW` remains the redistributable baseline in the current roster, but the default public release still uses provenance manifests plus fetch workflow instead of shipping the vendored checkout by default.
- The raw archival artifact is also not a fallback source-code mirror for `STONE`, `SWEET`, or `EWD`: it carries benchmark outputs, checksums, and provenance records, while source retrieval for those baselines remains a reviewer-side pinned fetch step.
- The bundle never includes `.git`, `paper/`, `proposal.md`, cached artifacts, or generated run outputs.

## Reviewer-Facing Contract

For the active public release:

- the four baseline implementations are pinned to explicit upstream commits with recorded provenance
- the project adapts orchestration, local model loading, and decoding interfaces around them
- the repository does **not** edit the baseline watermark algorithm logic itself
- runtime baseline comparisons use the same benchmark-layer generation policy and the same canonical release-suite source definitions across methods
- redistribution and license status are tracked per upstream manifest rather than assumed to be uniform across all four baselines
- upstream provenance does not imply uniform redistribution permission across all four methods
- detector-internal runtime failures are surfaced as benchmark metadata instead of crashing the entire run, and negative-control coverage excludes those unavailable detector outcomes instead of counting them as clean evidence

The redistribution boundary is summarized in
[`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md). In short, `STONE`,
`SWEET`, and `EWD` are pinned and fetchable but remain `license_status:
unverified`, so the public artifact records provenance rather than bundling
their source trees. `KGW` is marked redistributable but is fetched through the
same pinned workflow for consistency.

Adapter-boundary claim: `CodeMarkBench` owns the orchestration layer, local model
loading, decoding policy, run metadata, and error handling. The benchmark does
not intentionally alter the upstream watermark/detector algorithm logic for the
four active runtime comparisons; reviewer-side audits should compare the pinned
upstream commits above with the project adapter code rather than expecting the
GitHub companion repository to vendor every upstream file.

## Adapter Audit Table

The release treats the four watermark baselines as pinned upstream
implementations executed under a common benchmark contract. The table below is
the reviewer-facing adapter map for the public release:

| Method | Upstream manifest | Adapter boundary | Upstream files checked by readiness | Benchmark-controlled policy |
| --- | --- | --- | --- | --- |
| STONE | `third_party/STONE-watermarking.UPSTREAM.json` @ `bb5d809c0c494a219411e861f2313cca2b9fd7b4` | `codemarkbench/baselines/stone_family/official_runtime.py` loads the pinned checkout and wraps generation/detection calls. | `watermark/auto_watermark.py`, `utils/transformers_config.py` under `stone_implementation/` | pinned local HF model snapshot, shared decoding interface, benchmark prompt/execution metadata, common detector error reporting |
| SWEET | `third_party/SWEET-watermark.UPSTREAM.json` @ `853b47eb064c180beebd383302d09491fc98a565` | The same runtime adapter loads SWEET from the pinned checkout and routes calls through the shared runner. | `sweet.py`, `watermark.py` | pinned local HF model snapshot, shared decoding interface, benchmark prompt/execution metadata, common detector error reporting |
| EWD | `third_party/EWD.UPSTREAM.json` @ `605756acf802528a3df89d95a4661a031eafc79b` | The same runtime adapter loads EWD from the pinned checkout and routes calls through the shared runner. | `watermark.py` | pinned local HF model snapshot, shared decoding interface, benchmark prompt/execution metadata, common detector error reporting |
| KGW | `third_party/KGW-lm-watermarking.UPSTREAM.json` @ `82922516930c02f8aa322765defdb5863d07a00e` | The same runtime adapter loads KGW from the pinned checkout and routes calls through the shared runner. | `extended_watermark_processor.py`, `alternative_prf_schemes.py`, `normalizers.py` | pinned local HF model snapshot, shared decoding interface, benchmark prompt/execution metadata, common detector error reporting |

The table is not a claim that upstream projects expose identical APIs or
licenses. It documents the parts CodeMarkBench controls uniformly and the
minimal upstream files the readiness checks use to verify that the expected
pinned implementation is present.

## Screening Notes

The public paper/repo wording keeps the baseline-screening story explicit. See [`docs/baseline_screening.md`](baseline_screening.md) for the reviewer-facing screening note.

- the canonical main leaderboard retains the four pinned runtime baselines because they share the same runtime-generation comparison contract
- `CodeIP` is excluded after baseline screening because the public code exists but the official public artifact set is incomplete, so it cannot satisfy the official-public, runtime-comparable, reproducible benchmark standard used by this repository
- `Practical and Effective Code Watermarking for Large Language Models` is excluded after baseline screening because the official implementation follows a training/model-modifying path rather than the shared runtime-generation contract
- `UIUC ICLR 2025 / llm-code-watermark` is cited as a prior robustness study, not as a redundant benchmark/tool baseline

## Public Release Behavior

- The main CLI and configs stay project-native.
- Baseline source and licensing stay visible in the GitHub companion repository under `docs/`, `third_party/`, and the generated provenance manifest; the Zenodo artifact carries archival provenance metadata rather than acting as a second source-code host.
- Runtime baselines require a local Hugging Face model, a GPU, and a valid upstream checkout whose `origin` remote matches the lock manifest, whose `HEAD` commit matches the pinned SHA, and whose worktree is clean.
- `validate_setup.py` fails if any imported runtime method declares a missing or mismatched pinned upstream checkout.
- Runtime baseline comparisons keep the shared runtime generation policy aligned at the benchmark layer: `max_new_tokens=256`, `do_sample=true`, `temperature=0.2`, `top_p=0.95`, and `no_repeat_ngram_size=4`.
- Release-facing comparisons therefore rely on pinned provenance plus a common benchmark-layer execution contract, not on redistributing all upstream runtime trees inside the public artifact.
