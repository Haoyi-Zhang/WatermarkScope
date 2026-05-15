# Viva Preparation

This file lists likely supervisor or examiner questions and the concise answers supported by the submitted FYP dissertation and repository.

Use the submitted FYP dissertation numbers during the viva. Later paper-continuation runs may be mentioned only as future work, not as the defended submission result.

## Core Story

**Q: What is the single contribution of this project?**  
A: WatermarkScope is a benchmark-to-audit framework for source-code watermarking. It shows that code watermark evidence should be evaluated as an evidence chain: executable benchmark, structured provenance, black-box audit, active attribution, and security triage.

**Q: Why are there five modules?**  
A: They correspond to different access models and evidence objects. A local white-box watermark, a black-box provider audit, an active-owner attribution protocol, and a safety triage system cannot honestly share one detector score.

**Q: What is the most technically original part?**  
A: SemCodebook is the main method contribution, because it moves provenance recovery from token-level detection to typed program carriers: AST, CFG, and SSA, with keyed scheduling and ECC-style recovery. The broader framework contribution is the denominator-aware audit discipline across all modules.

## Evaluation Questions

**Q: Does 140/140 mean the benchmark methods succeeded?**  
A: No. It means 140 canonical runs completed under the release matrix. The watermark method quality is reported through utility, robustness, stealth, efficiency, and false-positive tables.

**Q: Does CodeDye prove contamination?**  
A: No. In the submitted FYP dissertation surface, CodeDye reports 4/300 sparse live signals, 170/300 positive controls, and 0/300 negative controls. This is conservative null-audit evidence. It does not estimate contamination prevalence, prove absence, or accuse a provider.

**Q: ProbeTrace has 750/750 true-owner positives. Is that overclaiming?**  
A: It would be overclaiming if I presented it as universal authorship proof. In the submitted FYP dissertation surface, ProbeTrace has 6,000 five-owner rows with 750/750 true-owner positives and 0/5,250 false-attribution controls. The claim is limited to that registry, split, and control surface.

**Q: SealAudit is still selective. Is that weak?**  
A: It is selective by design. In the submitted FYP dissertation surface, SealAudit reports 320/960 decisive marker-hidden triage outcomes with 0/960 unsafe passes. The remaining cases are treated as abstention or review load, not forced classification.

**Q: Why report confidence intervals for zero events?**  
A: Because 0 observed events is not the same as zero risk. Wilson intervals make uncertainty explicit and prevent overclaiming.

## Implementation Questions

**Q: Where is the code?**  
A: Under `projects/`. CodeMarkBench contains a full benchmark repository snapshot. SemCodebook, CodeDye, ProbeTrace, and SealAudit contain implementation snapshots, scripts, tests, and project claim maps.

**Q: How can the repository be checked quickly?**  
A: Run `python scripts/viva_check.py` from the root. It checks that the viva-facing documents, manifest entries, claim boundaries, and key artifact hashes are present and consistent. It is not a full GPU/API rerun.

**Q: Why is this not a full raw-experiment dump?**  
A: The FYP package is designed for examination. It includes code, result artifacts, manifests, and hashes. Full raw reruns require GPUs, model weights, or provider APIs, and those boundaries are documented in `docs/ENVIRONMENT.md` and `docs/RUNBOOK.md`.

## Limitations Questions

**Q: What is the biggest limitation?**  
A: Scope. Each module has a finite model/provider/source/attack denominator. The dissertation handles this by explicitly stating boundaries rather than broadening claims.

**Q: What future work would most improve the project?**  
A: Expand provider families beyond DeepSeek for the black-box modules once keys are available, add more independent white-box model cells for SemCodebook if compute allows, and continue reporting coverage-risk frontiers rather than broadening claims.

**Q: Why should this receive a high mark?**  
A: It combines a coherent research question, a substantial software artifact, mathematical definitions, algorithms, controlled experiments, confidence intervals, claim boundaries, reproducibility checks, and an honest limitations section.

