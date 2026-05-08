# ProbeTrace: Active-Owner Attribution with Source-Bound Semantic Witnesses

Generated: `2026-05-08T10:57:51+00:00`

## One-Sentence Claim

ProbeTrace studies active-owner source-bound attribution. Attribution should be tested as an owner-bound protocol with decoys, source witnesses, and heldout controls rather than as generic authorship classification.

## Abstract Draft

Source-code watermark evidence is fragile when claims are tied to surface tokens, unscoped provider behavior, or unverified safety assumptions. We present ProbeTrace, a scoped protocol for active-owner source-bound attribution. The method fixes its denominator, controls, and claim boundary before interpretation, then reports both positive evidence and failure/abstention surfaces. In the current FYP evaluation, the claim-bearing surface is APIS-300: 300/300 scoped attributions with 0/1,200 false-owner control hits. A separate 900-row source-bound transfer surface is retained as support-only receipt evidence over 300 task clusters. The result supports the scoped claim only; it does not license the forbidden claims listed below.

## Contributions

1. A scoped mechanism for active-owner source-bound attribution with explicit claim boundaries.
2. A fixed-denominator evaluation surface tied to hash-bound artifacts and final claim locks.
3. Negative-control, support-only, and failure-boundary reporting designed to prevent overclaiming.

## Method Framing

- The protocol binds candidate owners to semantic witnesses and commitment evidence while hiding owner labels from provider prompts.
- Wrong-owner, null-owner, random-owner, and same-provider unwrap controls are evaluated beside true-owner rows.
- Owner-heldout and task-heldout splits are reserved for a later multi-owner extension rather than the submitted FYP denominator.

## Main Result Surface

- 300 APIS attribution rows in the scoped single-active-owner setting.
- 300/300 APIS success events and 0/1,200 false-owner control hits.
- 900 source-bound transfer rows retained as support-only receipt/source-binding evidence over 300 task clusters.

Current main-table source artifacts:
- `results/ProbeTrace/artifacts/generated/apis300_live_attribution_evidence.json`
- `results/ProbeTrace/artifacts/generated/probetrace_abstain_aware_attribution_gate_20260506.json`
- `results/ProbeTrace/artifacts/generated/probetrace_transfer_row_binding_manifest_gate_20260505.json`
- `results/ProbeTrace/artifacts/generated/probetrace_latency_query_frontier_v1_20260507.json`
- `results/ProbeTrace/artifacts/generated/probetrace_anti_leakage_scan_v1_20260507.json`

## Publication Readiness Notes

- `too_perfect_result_risk` (medium_high): AUC=1.0, APIS=300/300, transfer=900/900 are strong but invite leakage/shortcut skepticism. Recommended revision: Make anti-leakage evidence prominent: hidden owner IDs, wrong/null/random/same-provider controls, owner/task-heldout splits, and near-boundary examples.
- `provider_scope` (medium_for_broader_claims): The locked FYP claim is scoped to APIS-300 and its controls. This is acceptable for a dissertation result but weaker than a provider-general broad-claim narrative. Recommended revision: Do not claim provider-general. If future keys are available, prioritize independent provider-specific surfaces.
- `cost_usability` (low_medium): Latency/query overhead can become a practical objection even when attribution is accurate. Recommended revision: Move latency/query frontier into main results instead of appendix.

## Limitations And Forbidden Claims

- The claim is DeepSeek-only and source-bound.
- The paper must foreground anti-leakage controls because the result is very strong.
- Multi-owner, provider-general, or cross-provider attribution requires new provider-specific gates.

Forbidden table uses:
- provider-general attribution
- cross-provider attribution
- unbounded transfer

## Reviewer Response Anchors

- The main denominator is fixed before interpretation and bound to versioned artifacts.
- Support-only rows do not enter the main denominator.
- Zero-event and perfect-event results must be reported with finite confidence bounds.
- Claims are scoped to the provider/model/cell conditions in the final lock.

