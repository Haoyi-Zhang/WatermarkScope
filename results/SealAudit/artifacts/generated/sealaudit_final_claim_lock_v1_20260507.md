# SealAudit Final Claim Lock v1

This artifact is non-claim-bearing. It locks the currently admissible paper claim and the claims that remain forbidden until fresh postrun evidence passes.

- Gate pass: `True`
- Best-paper ready: `False`
- Allowed current claim: DeepSeek-only marker-hidden selective audit/triage protocol
- Upgrade claim allowed: `False`

Effect surface:
- `case_count`: `320`
- `marker_hidden_claim_rows`: `960`
- `marker_visible_diagnostic_rows`: `320`
- `decisive_count`: `81`
- `decisive_coverage_ci95`: `{'k': 81, 'n': 960, 'rate': 0.084375, 'low': 0.06840615950150586, 'high': 0.10365684661114782, 'method': 'wilson'}`
- `needs_review_count`: `879`
- `needs_review_ci95`: `{'k': 879, 'n': 960, 'rate': 0.915625, 'low': 0.8963431533888522, 'high': 0.9315938404984943, 'method': 'wilson'}`
- `unsafe_pass_count`: `0`
- `unsafe_pass_ci95`: `{'k': 0, 'n': 960, 'rate': 0.0, 'low': 0.0, 'high': 0.003985571263342763, 'method': 'wilson'}`
- `decision_distribution`: `{'benign': 80, 'latent_trojan': 1, 'needs_review': 879}`
- `expert_review_role_support_only`: `True`
- `v5_final_evidence_ready`: `False`
- `v5_postrun_gate_pass`: `False`

Forbidden claims:
- security certificate
- harmlessness guarantee
- automatic latent-trojan classifier
- visible-marker rows as main evidence
- expert-signed gold labels or named/institutional expert certification
- v5 coverage upgrade before final v5 postrun promotion passes

Remaining blockers:
- decisive_coverage_only_81_of_960
- v5_final_evidence_not_claim_bearing
- v5_coverage_risk_frontier_missing
- v5_threshold_sensitivity_missing
- v5_visible_marker_boundary_missing

Required next evidence:
- Fresh v5 second-stage DeepSeek evidence with 960 hidden claim rows.
- Coverage-risk frontier showing improved decisive coverage without unsafe-pass inflation.
- Threshold sensitivity and visible-marker diagnostic boundary artifacts.
- Hard ambiguity retained rather than forced labels.
