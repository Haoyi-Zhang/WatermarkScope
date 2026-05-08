# ProbeTrace Final Claim Lock v1

This artifact is non-claim-bearing. It locks the currently admissible paper claim and the claims that remain forbidden until fresh postrun evidence passes.

- Gate pass: `True`
- Best-paper ready: `False`
- Allowed current claim: DeepSeek-only single-active-owner/source-bound attribution protocol
- Upgrade claim allowed: `False`

Effect surface:
- `apis300_attribution`: `{'k': 300, 'n': 300, 'rate': 1.0, 'low': 0.9873570287754538, 'high': 0.9999999999999998, 'method': 'wilson'}`
- `negative_control_false_attribution`: `{'k': 0, 'n': 1200, 'rate': 0.0, 'low': 2.168404344971009e-19, 'high': 0.003191000602734924, 'method': 'wilson'}`
- `transfer_validation`: `{'k': 900, 'n': 900, 'rate': 1.0, 'low': 0.9957498532699458, 'high': 1.0, 'method': 'wilson'}`
- `transfer_rows`: `900`
- `transfer_dataset_sha256`: `0adefeff0da33219c4a94565e6073392a69d4a46b56ef184e7fb501191c87073`
- `transfer_primary_independence_unit`: `task_cluster`
- `unique_transfer_task_count`: `300`
- `multi_owner_input_rows`: `6000`
- `multi_owner_owner_count`: `5`
- `multi_owner_language_count`: `3`
- `multi_owner_control_role_counts`: `{'null_owner': 750, 'random_owner': 750, 'same_provider_unwrap': 750, 'true_owner': 750, 'wrong_owner': 3000}`
- `multi_owner_split_counts`: `{'owner_heldout': 1200, 'task_heldout': 1200, 'train_dev': 3600}`

Forbidden claims:
- provider-general attribution
- multi-owner attribution from input package alone
- shortcut-free or leakage-free claim without fresh owner/task-heldout score vectors
- student-transfer generalization outside source-bound receipts
- perfect-score language without the anti-leakage caveat

Remaining blockers:
- fresh_multi_owner_live_score_vectors_missing
- owner_task_heldout_margin_auc_missing
- perfect_single_owner_result_requires_anti_leakage_confirmation

Required next evidence:
- Fresh 6000-row DeepSeek score-vector output over 5 owners and 3 languages.
- True/wrong/null/random/same-provider owner margins and threshold-free AUC.
- Owner-heldout and task-heldout splits with all raw/structured/prompt/output/source hashes.
- Per-owner TPR/FPR CI and near-boundary rows retained.
