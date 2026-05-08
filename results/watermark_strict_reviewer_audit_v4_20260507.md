# Strict Reviewer Audit v4

This additive audit incorporates the v5 reviewer manifest and the new black-box claim-lock/traceability artifacts. It does not overwrite v3.

Portfolio verdict: `not_bestpaper_ready_p1_blocked`
Best-paper ready: `False`
Remaining P1/P2: `5` / `0`

## SemCodebook

- Verdict: `bestpaper_ready_by_strict_artifact_gate`
- Mean strict score: `4.62`
- Allowed claim: structured provenance watermark over admitted white-box model cells
- Ready: `True`
- Delta: unchanged_from_v3

P1:
- None.

P2:
- None.

## CodeDye

- Verdict: `not_bestpaper_ready_p1_blocked`
- Mean strict score: `4.0`
- Allowed claim: DeepSeek-only curator-side sparse null-audit with hash-bound transcript retention
- Ready: `False`
- Delta: Closed the reviewer-facing row-traceability P2; effect and fresh-v3 evidence remain P1.

P1:
- Effect is still too weak for any detection/prevalence claim: final boundary is 6/300 and positive-control sensitivity is 170/300.
- A fresh frozen v3 DeepSeek run with full prompt/raw/structured/task/record hashes is still required before any claim upgrade.

P2:
- None.

## ProbeTrace

- Verdict: `not_bestpaper_ready_p1_blocked`
- Mean strict score: `4.12`
- Allowed claim: DeepSeek-only single-active-owner/source-bound attribution protocol
- Ready: `False`
- Delta: Closed leakage-scan and latency/query P2s for scoped single-owner claim.

P1:
- Broad multi-owner attribution remains non-claim-bearing until fresh 6,000-row DeepSeek score vectors, margin AUC, and owner/task-heldout postrun gates pass.

P2:
- None.

## SealAudit

- Verdict: `not_bestpaper_ready_p1_blocked`
- Mean strict score: `4.0`
- Allowed claim: DeepSeek-only marker-hidden selective audit/triage protocol
- Ready: `False`
- Delta: Closed abstention taxonomy and expert-wording P2s; low coverage/v5 evidence remain P1.

P1:
- Decisive coverage is still only 81/960, so current evidence supports selective triage rather than a strong audit classifier.
- Fresh v5 final evidence, coverage-risk frontier, threshold sensitivity, and visible-marker boundary are still missing.

P2:
- None.
