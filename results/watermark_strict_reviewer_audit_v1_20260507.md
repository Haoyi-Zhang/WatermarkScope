# Strict Reviewer Audit v1

This audit is non-claim-bearing. It evaluates current evidence, claim discipline, and remaining reviewer attack surface.

Portfolio verdict: `not_bestpaper_ready_p1_blocked`
Best-paper ready: `False`

## SemCodebook

- Verdict: `strong_submission_but_not_bestpaper_locked`
- Mean strict score: `4.38`
- Main claim allowed: structured provenance watermark over admitted white-box model cells
- Best-paper ready: `False`
- Reason: Strongest project, but still requires careful paper claim locking and full miss taxonomy to remove residual reviewer attack surface.

Remaining P1:
- None.

Remaining P2:
- Finish row-level positive-miss taxonomy for all 658 headline misses before using miss-analysis as a main-paper argument.
- In the paper, explicitly separate supported structural provenance recovery from unsupported natural first-sample generation.

## CodeDye

- Verdict: `not_bestpaper_ready_p1_blocked`
- Mean strict score: `3.88`
- Main claim allowed: DeepSeek-only curator-side sparse null-audit
- Best-paper ready: `False`
- Reason: Method is defensible as a conservative null-audit, but effect yield is too sparse for best-paper unless the protocol contribution is framed narrowly or v3 improves sensitivity.

Remaining P1:
- Effect is weak for any detection claim: live yield is 6/300 and positive-control sensitivity is 170/300.
- A fresh frozen v3 control/live run is required before any claim upgrade beyond conservative null-audit.

Remaining P2:
- Positive-control misses should be split into canary, provenance, chronology, retrieval, budget, and payload buckets.

## ProbeTrace

- Verdict: `not_bestpaper_ready_p1_blocked`
- Mean strict score: `4.0`
- Main claim allowed: single-active-owner/source-bound DeepSeek attribution
- Best-paper ready: `False`
- Reason: Single-owner claim is strong; best-paper-level generality requires fresh multi-owner live score-vector evidence.

Remaining P1:
- Broad multi-owner attribution is not claim-bearing until fresh score-vector outputs exist.
- Perfect 300/300 result remains vulnerable to shortcut/leakage critique without multi-owner heldout evidence.

Remaining P2:
- Latency/query frontier should be visible in main text, not only appendix.

## SealAudit

- Verdict: `not_bestpaper_ready_p1_blocked`
- Mean strict score: `4.0`
- Main claim allowed: marker-hidden DeepSeek selective audit/triage
- Best-paper ready: `False`
- Reason: The protocol is honest and useful, but coverage is too low until v5 increases decisive routing without unsafe-pass inflation.

Remaining P1:
- Decisive coverage is only 81/960; the current result is a selective triage surface, not a strong audit classifier.
- v5 final evidence is not claim-bearing yet, so coverage cannot be upgraded.

Remaining P2:
- Expert review support should stay role-based and row-confirmation based without implying signatures or identity disclosure.
