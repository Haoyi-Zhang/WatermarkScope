# Local Model Matrix

The canonical release suite compares the same four pinned upstream baseline implementations, executed through CodeMarkBench adapters, on each of the following local backbones:

- `Qwen/Qwen2.5-Coder-1.5B-Instruct` @ `2e1fd397ee46e1388853d2af2c993145b0f1098a`
- `Qwen/Qwen2.5-Coder-14B-Instruct` @ `aedcc2d42b622764e023cf882b6652e646b95671`
- `Qwen/Qwen2.5-Coder-7B-Instruct` @ `c03e6d358207e414f1eca0bb1891e29f1db0e242`
- `bigcode/starcoder2-7b` @ `bb9afde76d7945da5745592525db122d4d729eb1`
- `deepseek-ai/deepseek-coder-6.7b-instruct` @ `e5d64addd26a6a1db0f9b863abf6ee3141936807`

This gives the release suite a clean within-family scale comparison for Qwen plus two independent backbone families.

The roster is pinned at two levels for a rerun-backed public release:

- the public-facing identifier must be exactly one of the five `model_name + model_revision` pairs above
- the rerun-backed metadata must record the same resolved local Hugging Face snapshot revision actually used for each ID

GitHub documents the canonical pinned roster and workflow, but it does not vendor weights. The rerun-backed raw artifact metadata or release bundle must preserve the exact same resolved snapshot revisions shown above. For the tracked release-facing summary surface, `results/tables/suite_all_models_methods/suite_all_models_methods_export_identity.json` carries the same five `model_name + model_revision` pairs as machine-readable companion-surface metadata.

## Environment Variables

- `HF_ACCESS_TOKEN` (optional for the canonical public roster; required only when you explicitly want a token-backed probe or access to gated/private models)
- `HF_ACCESS_TOKEN_FALLBACK` (optional fallback when the primary token is not populated on the current host)

## Active Baseline Roster

- `stone_runtime`
- `sweet_runtime`
- `ewd_runtime`
- `kgw_runtime`

Within each matched model slice, these four baseline implementations are compared on the same benchmark rows. Cross-model execution may run in parallel, but ranking and score aggregation remain aligned to matched `model x method x source` slices.

For multilingual suite sources, the active official-runtime execution path uses the canonical five-language runtime set shared by the four imported methods: `python`, `cpp`, `java`, `javascript`, and `go`. In this release, `HumanEval-X`, `MBXP-5lang`, and the crafted sources are always presented through that five-language balanced execution slice.

## Active Suite Manifests

- `configs/matrices/suite_all_models_methods.json`
- `configs/matrices/suite_canary_heavy.json`
- `configs/matrices/model_invocation_smoke.json`

`suite_canary_heavy` is the heavy representative-model precheck. `model_invocation_smoke` verifies that the remaining four backbones can complete the same imported-baseline call path across the bounded seven-source release roster, including the five-language multilingual slice.

## Runtime Expectations

The pinned upstream baseline implementations load local Hugging Face weights through the project runtime adapters. The active public workflow is local-model-only; API-backed execution is not part of the canonical release suite.

For a 40 GB GPU card, the safe defaults remain:

- `device = cuda`
- `dtype = float16`
- `max_new_tokens = 256`

Before starting a large run, validate model access against the exact canonical pinned revisions with:

```bash
python scripts/check_model_access.py --require-all
```

By default, this command probes the five canonical `model_name + model_revision` pairs listed above and can do so anonymously for public models. Add `--require-token` when you explicitly want the readiness gate to fail on a missing Hugging Face token. For the canonical roster entries, an explicit mismatched `--revision` is rejected. For any custom `--model` override outside the benchmark roster, provide an explicit matching `--revision`; unpinned custom models are rejected.
