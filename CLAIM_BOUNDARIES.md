# Claim Boundaries

This file records the interpretation boundary for each dissertation result. It is intended to make the repository auditable: a reader can inspect the code, inspect the result artifact, and verify whether the dissertation claim stays inside the evaluated denominator.

## CodeMarkBench

- **Role in the dissertation:** benchmark foundation for executable source-code watermark evaluation.
- **Primary denominator:** 140 canonical run-completion records over 4 watermark baselines, 5 local code models, and 7 source groups.
- **Evidence location:** `projects/CodeMarkBench/results/tables/suite_all_models_methods/`.
- **Allowed claim:** the included baselines complete the released canonical run inventory and exhibit measurable utility, robustness, stealth, and efficiency tradeoffs under the executable stress matrix.
- **Forbidden claim:** the result does not prove that all possible code watermarking methods fail or that the included baselines generalize outside the released model/source/attack matrix.

## SemCodebook

- **Role in the dissertation:** structured white-box provenance watermark.
- **Primary denominator:** 24,000 positive recovery rows and 48,000 negative-control rows within 72,000 white-box records.
- **Evidence location:** `results/SemCodebook/artifacts/generated/`.
- **Allowed claim:** SemCodebook recovers structured provenance at the reported rate within the admitted white-box family and scale cells.
- **Forbidden claim:** the result is not a universal semantic watermarking guarantee, a first-sample/no-retry claim, a validator-repair success claim, or a claim outside admitted cells.

## CodeDye

- **Role in the dissertation:** conservative black-box contamination null-audit.
- **Primary denominator:** 300 live DeepSeek audit rows, plus separate positive and negative control denominators.
- **Evidence location:** `results/CodeDye/artifacts/generated/`.
- **Allowed claim:** CodeDye preserves sparse audit evidence with fixed controls, hashes, thresholds, and support-row exclusion.
- **Forbidden claim:** the result is not a contamination accusation, a contamination prevalence estimate, or a high-recall detector claim.

## ProbeTrace

- **Role in the dissertation:** active-owner, source-bound attribution protocol.
- **Primary denominator:** APIS-300 attribution rows.
- **Control denominator:** 1,200 false-owner controls.
- **Transfer support surface:** 900 receipt-complete transfer rows over the scoped source-bound setting; these rows support transfer-boundary analysis and are not 900 independent primary attribution tasks.
- **Evidence location:** `results/ProbeTrace/artifacts/generated/`.
- **Allowed claim:** ProbeTrace supports scoped single-active-owner/source-bound attribution under the evaluated registry and source split.
- **Forbidden claim:** the result is not provider-general authorship proof, multi-owner attribution, or unbounded transfer generalization.

## SealAudit

- **Role in the dissertation:** watermark-as-security-object selective triage.
- **Primary denominator:** 960 marker-hidden claim rows over 320 cases.
- **Evidence location:** `results/SealAudit/artifacts/generated/`.
- **Allowed claim:** SealAudit reports conservative marker-hidden selective triage with explicit abstention and unsafe-pass tracking.
- **Forbidden claim:** the result is not an automatic safety classifier, harmlessness certificate, or security certificate for all watermarking mechanisms.

## Cross-Project Rule

Diagnostic, support-only, canary, scaffold, and stress rows can be retained as engineering evidence, but they do not change the main denominators unless a project-specific manifest explicitly promotes them into the claim-bearing surface before interpretation.
