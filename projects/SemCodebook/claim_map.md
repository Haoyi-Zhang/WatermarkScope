# SemCodebook Claim Map

| Dissertation claim | Evidence path | Boundary |
|---|---|---|
| SemCodebook implements typed AST/CFG/SSA carrier extraction, keyed scheduling, and ECC-style recovery. | `src/semcodebook/`, `tests/` | Method implementation claim. |
| SemCodebook achieves 23,342/24,000 positive recoveries and 0/48,000 negative-control hits in the packaged white-box surface. | `../../results/SemCodebook/artifacts/generated/semcodebook_whitebox_effect_authenticity_gate_20260505.json`, `../../results/SemCodebook/artifacts/generated/semcodebook_whitebox_main_denominator_source_manifest_20260505.json` | Admitted white-box cells only. |
| Family/scale sufficiency is recorded for the FYP result surface. | `../../results/SemCodebook/artifacts/generated/semcodebook_whitebox_model_sufficiency_gate_20260505.json` | Does not imply provider-general coverage. |
| Generation-changing ablation support covers 43,200 rows. | `../../results/SemCodebook/artifacts/generated/semcodebook_generation_changing_ablation_promotion_gate_20260505.json` | Method evidence; not a first-sample/no-retry claim. |
