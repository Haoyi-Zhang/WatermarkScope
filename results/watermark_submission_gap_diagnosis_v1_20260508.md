# Watermark Submission Gap Diagnosis v1

Portfolio: `bestpaper_ready_by_strict_artifact_gate`; score `4.78/5`; P1/P2 `0/0`.

This is a non-claim-bearing planning artifact. It distinguishes scoped gate readiness from best-paper-award competitiveness.

## SemCodebook
- Strict score: `4.62/5`
- Current status: `strong_submission_ready_for_scoped_whitebox_claim`
- Locked claim: structured provenance watermark over admitted white-box model cells
- Next execution: Do not rerun whitebox until paper/theory tables are aligned; if adding evidence, run support-only real-repo witness, not another broad sweep.

Best-paper gaps:
- `method_theory` (medium): The mechanism is strong, but the paper must make AST/CFG/SSA/ECC/keyed schedule read as a compact theory of structured provenance rather than an artifact-heavy system. Fix: Add formal definitions, recovery sufficient conditions, and component necessity lemmas tied directly to the generation-changing ablation.
- `baseline_positioning` (medium): Reviewers may question whether official watermark baselines are fully comparable to structured provenance under semantic rewrite. Fix: Add a baseline-role table and a fairness paragraph that separates runnable official baselines, citation-only baselines, and non-equivalent comparators.
- `external_validity` (low_medium): 72k records cover model/family/scale breadth, but real-repo workflow examples would make the claim more memorable. Fix: Add one non-main-table real-repo walkthrough with compile/test witness and failure-boundary discussion.

## CodeDye
- Strict score: `4.75/5`
- Current status: `strong_submission_ready_only_for_sparse_null_audit`
- Locked claim: DeepSeek-only curator-side sparse null-audit with frozen v3 protocol and hash-complete 300-task live evidence
- Next execution: No immediate rerun. First write the sparse-audit narrative and tables; then decide whether a preregistered v4 support run is worth the API cost.

Best-paper gaps:
- `effect_size` (high_for_award_low_for_scoped_acceptance): Main DeepSeek signal is sparse: 4/300. This is acceptable for a conservative null-audit paper but weak for a best-paper-style detection narrative. Fix: Frame sparse yield as the point of a low-false-positive audit protocol; add utility and query-budget curves instead of inflating recall.
- `positive_control_sensitivity` (medium): Positive-control sensitivity is 170/300, with 130 witness-ablation misses. Reviewers will ask whether the protocol misses known contamination too often. Fix: Add miss taxonomy examples and a frozen v4 evidence-enrichment design; rerun only if thresholds are preregistered before execution.
- `claim_boundary` (medium): The paper can be rejected if it sounds like a provider contamination accusation or high-recall detector. Fix: Keep the title/abstract as curator-side null-audit; report non-signals as non-accusatory outcomes, not absence proof.

## ProbeTrace
- Strict score: `5.0/5`
- Current status: `closest_to_best_paper_ready_for_scoped_deepseek_claim`
- Locked claim: DeepSeek-only five-owner source-bound active-owner attribution with owner/task-heldout margin evidence
- Next execution: No new DeepSeek run needed. Next work is writing: anti-leakage section, near-boundary rows, and cost frontier in the main text.

Best-paper gaps:
- `too_perfect_result_risk` (medium_high): AUC=1.0, APIS=300/300, transfer=900/900 are strong but invite leakage/shortcut skepticism. Fix: Make anti-leakage evidence prominent: hidden owner IDs, wrong/null/random/same-provider controls, owner/task-heldout splits, and near-boundary examples.
- `provider_scope` (medium_for_best_paper): The locked claim is DeepSeek-only. This is acceptable for a scoped paper but weaker than a provider-general award narrative. Fix: Do not claim provider-general. If future keys are available, prioritize GPT/Claude replication for this project first.
- `cost_usability` (low_medium): Latency/query overhead can become a practical objection even when attribution is accurate. Fix: Move latency/query frontier into main results instead of appendix.

## SealAudit
- Strict score: `4.75/5`
- Current status: `strong_submission_ready_only_for_selective_triage`
- Locked claim: DeepSeek-only marker-hidden v5 selective audit/triage with support-evidence binding
- Next execution: No new DeepSeek run needed. Next work is paper framing: coverage-risk frontier, unsafe-pass bound, and failure taxonomy.

Best-paper gaps:
- `coverage` (medium_high): Decisive coverage is 320/960. This is a selective triage result, not a full classifier. Fix: Make coverage-risk frontier the core contribution; explicitly treat retained ambiguity as safety-preserving abstention.
- `human_support_boundary` (medium): Expert review can help credibility but becomes a liability if described as signed/named gold labels. Fix: Use only anonymous role-based support and row-level packet confirmation wording.
- `security_overclaim` (high_if_written_wrong): Reviewers will reject any harmlessness guarantee or security certificate claim. Fix: Write watermark-as-security-object audit/triage, not automatic safety classification.
