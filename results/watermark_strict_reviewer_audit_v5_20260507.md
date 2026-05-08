# Strict Reviewer Audit v5

This additive audit incorporates fresh-run contracts, naming consistency, and provider readiness v2. It does not overwrite earlier audits.

Portfolio verdict: `not_bestpaper_ready_p1_blocked`
Best-paper ready: `False`
Remaining P1/P2: `5` / `0`
Provider execution ready now: `True`

## SemCodebook

- Verdict: `bestpaper_ready_by_strict_artifact_gate`
- Mean strict score: `4.62`
- Allowed claim: structured provenance watermark over admitted white-box model cells
- Ready: `True`
- Delta: unchanged_from_v4; reviewer manifest v6 now indexes fresh-run hardening for black-box projects

P1:
- None.

P2:
- None.

## CodeDye

- Verdict: `not_bestpaper_ready_p1_blocked`
- Mean strict score: `4.12`
- Allowed claim: DeepSeek-only curator-side sparse null-audit with hash-bound transcript retention
- Ready: `False`
- Delta: Fresh-run contract and provider-readiness v2 close launch-schema risk; effect/fresh-output P1 remains.

P1:
- Effect is still too weak for any detection/prevalence claim: final boundary is 6/300 and positive-control sensitivity is 170/300.
- A fresh frozen v3 DeepSeek run with full prompt/raw/structured/task/record hashes is still required before any claim upgrade; the execution contract is ready, provider execution is not.

P2:
- None.

## ProbeTrace

- Verdict: `not_bestpaper_ready_p1_blocked`
- Mean strict score: `4.25`
- Allowed claim: DeepSeek-only single-active-owner/source-bound attribution protocol
- Ready: `False`
- Delta: Multi-owner launch contract now closes schema/naming risk; fresh score-vector evidence P1 remains.

P1:
- Broad multi-owner attribution remains non-claim-bearing until fresh 6,000-row DeepSeek score vectors, margin AUC, and owner/task-heldout postrun gates pass; the input/output contract is ready, provider execution is not.

P2:
- None.

## SealAudit

- Verdict: `not_bestpaper_ready_p1_blocked`
- Mean strict score: `4.12`
- Allowed claim: DeepSeek-only marker-hidden selective audit/triage protocol
- Ready: `False`
- Delta: v5 launch/output contract closes final-evidence naming risk; low coverage/fresh-v5 evidence P1 remains.

P1:
- Decisive coverage is still only 81/960, so current evidence supports selective triage rather than a strong audit classifier.
- Fresh v5 final evidence, coverage-risk frontier, threshold sensitivity, and visible-marker boundary are still missing; the v5 input/output contract is ready, provider execution is not.

P2:
- None.
