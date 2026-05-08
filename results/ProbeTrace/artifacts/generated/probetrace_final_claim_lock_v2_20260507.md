# ProbeTrace Final Claim Lock v2

This additive claim lock supersedes v1 for continuation planning. It does not overwrite v1 or any raw result.

- Gate pass: `True`
- Best-paper ready for scoped claim: `True`
- Allowed current claim: DeepSeek-only five-owner source-bound active-owner attribution with owner/task-heldout margin evidence
- Multi-owner claim allowed: `True`
- Provider-general claim allowed: `False`

Locked effect surface:
- APIS-300 attribution: `300/300`
- Transfer validation: `900/900`
- Multi-owner live rows: `6000`
- Multi-owner owners/languages: `5` / `3`
- Multi-owner positives/controls: `750` / `5250`
- Multi-owner margin AUC: `1.0`
- Multi-owner global TPR: `{'high': 1.0, 'k': 750, 'low': 0.9949041555412677, 'method': 'wilson', 'n': 750, 'rate': 1.0}`
- Multi-owner global FPR: `{'high': 0.0007311714391846915, 'k': 0, 'low': 5.421010862427522e-20, 'method': 'wilson', 'n': 5250, 'rate': 0.0}`

Forbidden claims:
- provider-general attribution
- cross-provider attribution without non-DeepSeek evidence
- unbounded student-transfer generalization beyond source-bound receipts
- claim that perfect single-owner results alone prove no shortcut
- multi-owner claim from input package without fresh live score vectors
- claim that controls prove zero false positives rather than an upper-bounded rate

Remaining blockers:
- None.
