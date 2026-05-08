# CodeDye Final Claim Lock v1

This artifact is non-claim-bearing. It locks the currently admissible paper claim and the claims that remain forbidden until fresh postrun evidence passes.

- Gate pass: `True`
- Best-paper ready: `False`
- Allowed current claim: DeepSeek-only curator-side sparse null-audit with hash-bound transcript retention
- Upgrade claim allowed: `False`

Effect surface:
- `claim_rows`: `300`
- `final_signal`: `6`
- `final_signal_ci95`: `{'k': 6, 'n': 300, 'rate': 0.02, 'low': 0.009197631557703617, 'high': 0.042939620817860576, 'method': 'wilson'}`
- `statistics_artifact_positive_count`: `4`
- `support_rows_excluded`: `806`
- `missing_payload_or_transcript_hash`: `0`
- `positive_control_detected`: `170`
- `positive_control_denominator`: `300`
- `positive_control_sensitivity_ci95`: `{'k': 170, 'n': 300, 'rate': 0.5666666666666667, 'low': 0.5100989219821965, 'high': 0.6215486818545306, 'method': 'wilson'}`
- `positive_control_missed`: `130`
- `positive_miss_taxonomy`: `{'witness_ablation_did_not_collapse': 130}`
- `negative_control_false_positive`: `0`
- `negative_control_rows`: `300`
- `negative_control_fp_ci95`: `{'k': 0, 'n': 300, 'rate': 0.0, 'low': 8.673617379884035e-19, 'high': 0.012642971224546034, 'method': 'wilson'}`

Forbidden claims:
- high-recall contamination detector
- contamination prevalence estimate
- provider accusation
- evidence that non-signals prove absence of contamination
- support/public rows as main-denominator evidence
- v3 live claim before the postrun promotion gate passes

Remaining blockers:
- fresh_v3_live_result_missing
- positive_control_sensitivity_only_170_of_300
- live_signal_only_6_of_300

Required next evidence:
- Fresh frozen v3 DeepSeek live run with exactly 300 claim rows.
- Complete raw transcript, structured payload, prompt, task, and record hashes.
- Utility admissibility and support-row exclusion pass.
- Sensitivity improvement must come from preregistered protocol invariants, not threshold tuning.
