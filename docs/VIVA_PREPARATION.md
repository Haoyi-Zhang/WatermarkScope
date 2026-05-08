# Viva Preparation

This file lists likely supervisor or examiner questions and the concise answers supported by the dissertation and repository.

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
A: No. CodeDye reports a conservative null-audit: 6 sparse signals over 300 live DeepSeek rows, with controls. It does not estimate contamination prevalence and does not accuse a provider.

**Q: ProbeTrace has 300/300. Is that overclaiming?**  
A: The dissertation deliberately scopes it to a single-active-owner/source-bound setting and reports false-owner controls. The 900 transfer rows are support evidence over 300 task clusters, not 900 independent primary attribution tasks.

**Q: SealAudit only has 8.44% decisive coverage. Is that weak?**  
A: It is a selective triage system, not an automatic classifier. The contribution is explicit abstention and 0 observed unsafe-pass outcomes in the current denominator, with a nonzero confidence upper bound.

**Q: Why report confidence intervals for zero events?**  
A: Because 0 observed events is not the same as zero risk. Wilson intervals make uncertainty explicit and prevent overclaiming.

## Implementation Questions

**Q: Where is the code?**  
A: Under `projects/`. CodeMarkBench contains a full benchmark repository snapshot. SemCodebook, CodeDye, ProbeTrace, and SealAudit contain implementation snapshots, scripts, tests, and project claim maps.

**Q: How can the repository be checked quickly?**  
A: Run `python scripts/examiner_check.py` from the root. It runs the integrity check and result summary, and it verifies the key examiner-facing documents.

**Q: Why is this not a full raw-experiment dump?**  
A: The FYP package is designed for examination. It includes code, result artifacts, manifests, and hashes. Full raw reruns require GPUs, model weights, or provider APIs, and those boundaries are documented in `docs/ENVIRONMENT.md` and `docs/RUNBOOK.md`.

## Limitations Questions

**Q: What is the biggest limitation?**  
A: Scope. Each module has a finite model/provider/source/attack denominator. The dissertation handles this by explicitly stating boundaries rather than broadening claims.

**Q: What future work would most improve the project?**  
A: Expand SemCodebook cell-level publication tables, add more provider families for black-box modules, complete multi-owner ProbeTrace support, and raise SealAudit decisive coverage while keeping unsafe-pass bounded.

**Q: Why should this receive a high mark?**  
A: It combines a coherent research question, a substantial software artifact, mathematical definitions, algorithms, controlled experiments, confidence intervals, claim boundaries, reproducibility checks, and an honest limitations section.

