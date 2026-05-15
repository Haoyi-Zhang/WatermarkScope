# Claim Boundaries

This file records the interpretation boundary for each submitted FYP dissertation result. It is intended to make the repository auditable during the viva: a reader can inspect the code, inspect the result artifact, and verify whether the dissertation claim stays inside the evaluated denominator.

## Shared Benchmark Support: CodeMarkBench

- **Role in the submission:** shared benchmark foundation and support material for executable source-code watermark evaluation. It is not a fifth paper in the four-watermark package and does not create an additional main claim surface.
- **Primary denominator:** 140 canonical run-completion records over 4 watermark baselines, 5 local code models, and 7 source groups.
- **Evidence location:** `projects/CodeMarkBench/results/tables/suite_all_models_methods/`.
- **Allowed claim:** the included baselines complete the released canonical run inventory and exhibit measurable utility, robustness, stealth, and efficiency tradeoffs under the executable stress matrix.
- **Forbidden claim:** the result does not prove that all possible code watermarking methods fail or that the included baselines generalize outside the released model/source/attack matrix.

## SemCodebook

- **Role in the submission:** structured white-box provenance watermark.
- **Primary denominator:** 31,200 positive recovery rows and 62,400 fixed negative-control rows within 93,600 admitted white-box records, plus a separate 62,400-row blind replay false-positive gate.
- **Evidence location:** `results/SemCodebook/artifacts/generated/`.
- **Allowed claim:** SemCodebook recovers structured provenance at the reported rate within the admitted white-box family and scale cells: 30,330/31,200 positive recoveries, 0/62,400 fixed negative-control hits, and 0/62,400 blind replay hits under separate fail-closed gates.
- **No-retry boundary:** 352 no-retry-origin positives are retained only as a disclosed non-promoted origin subset; they are not a first-sample or natural-generation success claim.
- **Forbidden claim:** the result is not a universal semantic watermarking guarantee, a first-sample/no-retry claim, a validator-repair success claim, or a claim outside admitted cells.

## CodeDye

- **Role in the submission:** conservative black-box null-audit evidence.
- **Primary denominator:** 300 live audit samples, 300 positive controls, and 300 negative controls in the submitted dissertation surface.
- **Evidence location:** `results/CodeDye/artifacts/generated/`.
- **Allowed claim:** CodeDye preserves conservative black-box audit evidence with fixed controls and support-row separation. The submitted dissertation surface reports 4/300 sparse live signals, 170/300 positive controls, and 0/300 negative controls. This supports a bounded null-audit interpretation, not a high-recall detector interpretation.
- **Forbidden claim:** the result is not a contamination accusation, a contamination prevalence estimate, or a high-recall detector claim; in short, no high-recall detector claim is made.

## ProbeTrace

- **Role in the submission:** active-owner, source-bound commitment/witness verification protocol.
- **Primary denominator:** 6,000 DeepSeek five-owner commitment/witness rows.
- **Control denominator:** 5,250 wrong/null/random/same-provider controls in the five-owner surface.
- **Support surfaces:** APIS-300 with 1,200 false-owner controls and 900 receipt-complete transfer rows remain scoped support evidence; they do not enlarge the primary denominator or create provider-general transfer claims.
- **Evidence location:** `results/ProbeTrace/artifacts/generated/`.
- **Allowed claim:** ProbeTrace supports scoped DeepSeek-only five-owner active-owner commitment/witness verification under the evaluated registry and source split.
- **Forbidden claim:** the result is not provider-general authorship proof, cross-provider attribution, shortcut-free absolute proof, or unbounded transfer generalization.

## SealAudit

- **Role in the submission:** watermark-as-security-object selective triage.
- **Primary denominator:** 960 marker-hidden claim rows over 320 cases.
- **Evidence location:** `results/SealAudit/artifacts/generated/`.
- **Allowed claim:** SealAudit reports conservative marker-hidden selective triage with explicit abstention and provider-flag unsafe-pass tracking. The submitted dissertation surface is 320/960 decisive marker-hidden rows and 0/960 provider-flag unsafe-pass rows. The remaining nondecisive rows are retained as abstention or review load rather than forced labels.
- **Forbidden claim:** the result is not an automatic safety classifier, harmlessness certificate, or security certificate for all watermarking mechanisms; no security certificate is claimed.

## Cross-Project Rule

Diagnostic, support-only, canary, scaffold, stress, and post-submission continuation rows can be retained as engineering evidence, but they do not change the submitted FYP denominators unless a project-specific manifest explicitly promotes a new surface before interpretation.
