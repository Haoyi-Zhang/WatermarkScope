# Strict Reviewer Audit v2

This audit is non-claim-bearing and supersedes v1 for planning. It does not overwrite any result artifact.

Portfolio verdict: `not_bestpaper_ready_p1_blocked`
Best-paper ready: `False`
Remaining P1/P2: `6` / `5`

## SemCodebook

- Verdict: `strong_submission_but_not_bestpaper_locked`
- Mean strict score: `4.5`
- Allowed claim: structured provenance watermark over admitted white-box model cells
- Ready: `False`
- Reason: Evidence is strong enough for a best-paper-level scoped white-box claim, but final paper wording and paired-delta presentation still need lock-in.

P1:
- None.

P2:
- Paper text must foreground that DeepSeek-Coder-6.7B accounts for the row-level positive misses rather than hide it.
- Component contribution table should be shown with paired deltas in the main paper or appendix.

## CodeDye

- Verdict: `not_bestpaper_ready_p1_blocked`
- Mean strict score: `4.0`
- Allowed claim: DeepSeek-only curator-side sparse null-audit
- Ready: `False`
- Reason: The protocol is clean, but current effect is weak; best-paper case requires v3 sensitivity improvement or an unusually compelling sparse-audit framing.

P1:
- Effect is still too weak for any detection claim: live yield is 6/300 and positive-control sensitivity is 170/300.
- A fresh frozen v3 control/live run is required before any claim upgrade beyond conservative null-audit.

P2:
- If v3 does not improve sensitivity, the paper must explicitly argue sparse-audit utility rather than detection power.

## ProbeTrace

- Verdict: `not_bestpaper_ready_p1_blocked`
- Mean strict score: `4.0`
- Allowed claim: single-active-owner/source-bound DeepSeek attribution
- Ready: `False`
- Reason: Single-owner claim is strong; best-paper-level generality requires fresh multi-owner live score-vector evidence.

P1:
- Broad multi-owner attribution is not claim-bearing until fresh score-vector outputs exist.
- Perfect 300/300 result remains vulnerable to shortcut/leakage critique without multi-owner heldout evidence.

P2:
- Latency/query frontier should be visible in main text.

## SealAudit

- Verdict: `not_bestpaper_ready_p1_blocked`
- Mean strict score: `4.0`
- Allowed claim: marker-hidden DeepSeek selective audit/triage
- Ready: `False`
- Reason: Protocol is honest and useful, but coverage is too low until v5 increases decisive routing without unsafe-pass inflation.

P1:
- Decisive coverage is only 81/960; current result is selective triage, not a strong audit classifier.
- v5 final evidence is not claim-bearing yet, so coverage cannot be upgraded.

P2:
- Expert review support must remain role-based and row-confirmation based.
