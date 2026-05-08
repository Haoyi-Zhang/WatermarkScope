# Method Index

This index helps an examiner connect each dissertation method to its formal definition, main denominator, result artifact, and interpretation boundary.

## Notation And Confidence Intervals

Rates in the dissertation use fixed denominators. For binomial rates, the repository reports Wilson 95% intervals when a zero-event or perfect-event result could otherwise be misread as absolute certainty.

For observed successes \(k\) out of \(n\), with \(z=1.96\), the Wilson interval is:

\[
\hat{p}_{W}=\frac{\hat{p}+z^2/(2n)}{1+z^2/n},\qquad
\Delta_W=\frac{z}{1+z^2/n}\sqrt{\frac{\hat{p}(1-\hat{p})}{n}+\frac{z^2}{4n^2}}.
\]

The reported interval is \([\max(0,\hat{p}_W-\Delta_W),\min(1,\hat{p}_W+\Delta_W)]\).

## CodeMarkBench

- **Dissertation location:** Chapter 3.
- **Role:** executable benchmark foundation.
- **Formal object:** benchmark tuple \(B=(T,M,W,A,E)\), where tasks, models, watermark methods, attacks, and executable evaluators define a run matrix.
- **Main denominator:** 140 canonical run-completion records.
- **Primary artifacts:** `projects/CodeMarkBench/results/tables/suite_all_models_methods/`.
- **Safe interpretation:** the benchmark exposes utility, robustness, stealth, efficiency, and stress tradeoffs for the released baselines.
- **Unsafe interpretation:** `140/140` is not a watermark detection score and not proof that all watermarking methods fail.

## SemCodebook

- **Dissertation location:** Chapter 4.
- **Role:** white-box structured provenance watermark.
- **Core definition:** implementation carrier families are grouped by AST-, CFG-, and SSA-style evidence levels, \(C(x)=\bigsqcup_r \{(r,z):z\in C_r(x)\}\).
- **Scheduling:** adaptive keyed schedule over carrier families using applicability, frozen family bias, and HMAC-derived tie-breaking.
- **Main denominator:** 24,000 positive recovery rows and 48,000 negative-control rows within 72,000 white-box records.
- **Result:** 23,342/24,000 positive recoveries; 0/48,000 negative-control hits with Wilson 95% upper bound 0.008%.
- **Ablation support:** 43,200 generation-changing ablation rows; supports method interpretation, not first-sample/no-retry promotion.
- **Primary artifacts:** `results/SemCodebook/artifacts/generated/semcodebook_whitebox_*` and `semcodebook_generation_changing_ablation_*`.
- **Safe interpretation:** structured provenance recovery in admitted white-box family and scale cells.
- **Unsafe interpretation:** universal semantic watermarking, validator-repair success, or claims outside admitted cells.

## CodeDye

- **Dissertation location:** Chapter 4.
- **Role:** conservative black-box contamination null-audit.
- **Record definition:** prompt hash, raw-response hash, structured-response hash, detector version, threshold version, control role, and claim-bearing status.
- **Claim-bearing predicate:** the current promoted reporting rule is a frozen non-weighted gate vector over family observation, structural or stable witness evidence, output-visible canary evidence, and heldout/rewrite context, with prompt/raw/structured hashes retained for audit.
- **Protocol-freeze boundary:** the v2 dual-evidence artifact records threshold discipline and future rerun readiness; it is support-only unless a fresh claim-bearing rerun is promoted.
- **Main denominator:** 300 live DeepSeek audit rows.
- **Result:** 6/300 sparse signals with Wilson 95% CI 0.92%-4.29%.
- **Controls:** 170/300 positive-control hits with Wilson 95% CI 51.01%-62.15%; 0/300 negative-control hits with upper bound 1.26%.
- **Support rows:** 806 support/public rows are excluded from the main denominator.
- **Primary artifacts:** `results/CodeDye/artifacts/generated/codedye_*`.
- **Safe interpretation:** sparse, hash-bound null-audit evidence with moderate positive-control sensitivity.
- **Unsafe interpretation:** contamination accusation, prevalence estimate, or high-recall detector claim.

## ProbeTrace

- **Dissertation location:** Chapter 5.
- **Role:** active-owner, source-bound attribution protocol.
- **Registry definition:** \(R=\{(\mathrm{owner\_id},\mathrm{owner\_key},\mathrm{source\_split\_hash})\}\).
- **Main attribution denominator:** APIS-300.
- **Control denominator:** 1,200 false-owner controls.
- **Transfer support:** 900 receipt-complete transfer rows over the scoped source-bound setting; these are not 900 independent primary attribution tasks.
- **Result:** 300/300 APIS successes with Wilson 95% lower bound 98.74%; 0/1,200 false-owner controls with upper bound 0.32%.
- **Primary artifacts:** `results/ProbeTrace/artifacts/generated/apis300_*`, `probetrace_*`, and `student_transfer_*`.
- **Safe interpretation:** single-active-owner/source-bound attribution under the evaluated registry.
- **Unsafe interpretation:** provider-general authorship proof, multi-owner attribution, or unbounded transfer generalization.

## SealAudit

- **Dissertation location:** Chapter 5.
- **Role:** watermark-as-security-object selective triage.
- **Decision set:** \(Y=\{\mathrm{benign},\mathrm{latent\_risk},\mathrm{needs\_review}\}\).
- **Main denominator:** 960 marker-hidden claim rows over 320 cases.
- **Result:** 81/960 decisive rows with Wilson 95% CI 6.84%-10.37%; 879/960 needs-review rows; 0/960 observed unsafe-pass outcomes with upper bound 0.40%.
- **Diagnostic-only surface:** 320 marker-visible rows are excluded from the main denominator.
- **Primary artifacts:** `results/SealAudit/artifacts/generated/canonical_claim_surface_results.json` and `sealaudit_coverage_risk_frontier_gate_20260505.json`.
- **Safe interpretation:** conservative selective triage with explicit abstention and unsafe-pass tracking.
- **Unsafe interpretation:** automatic safety classifier, harmlessness certificate, or security certificate.
