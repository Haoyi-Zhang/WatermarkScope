# SemCodebook Final Claim Lock v1

This artifact locks the scoped white-box claim and required paper disclosures.

- Gate pass: `True`
- Allowed claim: structured provenance watermark over admitted white-box model cells
- Positive recovery: 23,342/24,000
- Negative controls: 0/48,000
- Ablation rows: 43200
- Mandatory miss disclosure: 10210/10210 misses are attributed to DeepSeek-Coder-6.7B-Instruct.

Mandatory component comparisons:
- `full_vs_ast_only`: delta `None`
- `full_vs_cfg_only`: delta `None`
- `full_vs_drop_ast`: delta `None`
- `full_vs_drop_cfg`: delta `None`
- `full_vs_drop_ssa`: delta `None`
- `full_vs_ecc_off`: delta `None`
- `full_vs_ssa_only`: delta `None`
- `full_vs_unkeyed_schedule`: delta `None`

Forbidden claims:
- universal code watermark
- first-sample/no-retry natural-generation guarantee
- validator-repair evidence as main result
- provider-general claim outside admitted white-box cells
- perfect-score language
