# Claim Boundaries

This file records the interpretation boundary for each submission result. It is intended to make the repository auditable: a reader can inspect the code, inspect the result artifact, and verify whether the paper claim stays inside the evaluated denominator.

## Shared Benchmark Support: CodeMarkBench

- **Role in the submission:** shared benchmark foundation and support material for executable source-code watermark evaluation. It is not a fifth paper in the four-watermark package and does not create an additional main claim surface.
- **Primary denominator:** 140 canonical run-completion records over 4 watermark baselines, 5 local code models, and 7 source groups.
- **Evidence location:** `projects/CodeMarkBench/results/tables/suite_all_models_methods/`.
- **Allowed claim:** the included baselines complete the released canonical run inventory and exhibit measurable utility, robustness, stealth, and efficiency tradeoffs under the executable stress matrix.
- **Forbidden claim:** the result does not prove that all possible code watermarking methods fail or that the included baselines generalize outside the released model/source/attack matrix.

## SemCodebook

- **Role in the submission:** structured white-box provenance watermark.
- **Primary denominator:** 24,000 positive recovery rows and 48,000 negative-control rows in the submitted dissertation surface.
- **Evidence location:** `results/SemCodebook/artifacts/generated/`.
- **Allowed claim:** SemCodebook recovers structured provenance at the reported rate within the admitted white-box cells: 23,342/24,000 positive recoveries and 0/48,000 negative-control hits.
- **No-retry boundary:** no first-sample, no-retry, or natural-generation success claim is made from this submitted FYP surface.
- **Forbidden claim:** the result is not a universal semantic watermarking guarantee, a first-sample/no-retry claim, a validator-repair success claim, or a claim outside admitted cells.

## CodeDye

- **Role in the submission:** conservative black-box contamination null-audit.
- **Primary denominator:** 300 live audit samples, 300 positive controls, and 300 negative controls in the submitted dissertation surface.
- **Evidence location:** `results/CodeDye/artifacts/generated/`.
- **Allowed claim:** CodeDye preserves conservative black-box null-audit evidence: 6/300 sparse live signals, 170/300 positive controls, and 0/300 negative controls.
- **Forbidden claim:** the result is not a contamination accusation, a contamination prevalence estimate, or a high-recall detector claim; in short, no high-recall detector claim is made.

## ProbeTrace

- **Role in the submission:** active-owner, source-bound commitment/witness verification protocol.
- **Primary denominator:** 300 scoped active-owner decisions in the submitted dissertation surface.
- **Control denominator:** 1,200 false-owner controls.
- **Support surfaces:** continuation and transfer rows are future-work support evidence; they do not enlarge the submitted FYP denominator or create provider-general transfer claims.
- **Evidence location:** `results/ProbeTrace/artifacts/generated/`.
- **Allowed claim:** ProbeTrace supports scoped active-owner attribution under the evaluated registry and source split: 300/300 scoped decisions and 0/1,200 false-owner controls.
- **Forbidden claim:** the result is not provider-general authorship proof, cross-provider attribution, shortcut-free absolute proof, or unbounded transfer generalization.

## SealAudit

- **Role in the submission:** watermark-as-security-object selective triage.
- **Primary denominator:** 960 marker-hidden claim rows over 320 cases.
- **Evidence location:** `results/SealAudit/artifacts/generated/`.
- **Allowed claim:** SealAudit reports conservative marker-hidden selective triage with explicit abstention and unsafe-pass tracking. The submitted surface is 81/960 decisive triage outcomes with 0 observed unsafe passes; nondecisive rows remain review load rather than forced labels.
- **Forbidden claim:** the result is not an automatic safety classifier, harmlessness certificate, or security certificate for all watermarking mechanisms; no security certificate is claimed.

## Cross-Project Rule

Diagnostic, support-only, canary, scaffold, and stress rows can be retained as engineering evidence, but they do not change the main denominators unless a project-specific manifest explicitly promotes them into the claim-bearing surface before interpretation.
