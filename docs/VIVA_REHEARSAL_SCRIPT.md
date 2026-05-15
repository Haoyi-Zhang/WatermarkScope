# WatermarkScope Viva Rehearsal Script

Use this as a speaking guide, not as a script to read word by word. The target is 8 to 10 minutes using the project page, then Q&A.

## Timing Plan

| Part | Page route | Target time | Purpose |
|---|---|---:|---|
| Opening and problem | Hero, Problem | 1.5 min | Explain why code watermark evidence needs boundaries. |
| Method and framework | Contract | 2.0 min | Explain denominator, evidence object, and admission protocol. |
| Results and interpretation | Submitted results, Walkthrough | 3.0 min | Report submitted FYP numbers without overclaiming. |
| Demo route | Evidence demo | 2.0 min | Show repository evidence links and quick inspection check. |
| Defence and future work | Limits, Future work, Q&A | 1.5 min | Close with boundaries, roadmap, and Q&A readiness. |

## Core 10-Minute Story

Good afternoon. I am Haoyi Zhang. My project is WatermarkScope, a benchmark-to-audit framework for source-code watermarking in code generation models.

The problem is that generated code does not stay inside one chat session. It may be copied, edited, translated, and deployed somewhere else. In that setting, a single detector score is not enough. A score becomes useful only when we know the denominator, controls, artifact, access model, and claim boundary.

The main idea of WatermarkScope is simple: before making a watermark claim, first admit the evidence object. In my notation, the evidence object contains the denominator, controls, artifact and access, hash, and boundary. If one of these is missing, the result should not be promoted into a broad claim.

The framework has five stages. CodeMarkBench gives the executable benchmark denominator. SemCodebook studies structured white-box provenance recovery. CodeDye keeps conservative black-box null-audit evidence. ProbeTrace studies scoped active-owner attribution. SealAudit studies marker-hidden security triage. These stages are connected by the same evidence contract, but they do not share one universal score.

In the submitted FYP dissertation surface, CodeMarkBench completed 140 out of 140 canonical runs. SemCodebook recovered 30,330 out of 31,200 positive cases with zero hits in 62,400 fixed negative controls and zero hits in 62,400 blind negative replay controls. CodeDye found 4 sparse live signals in 300 samples, with 170 out of 300 positive controls and zero out of 300 negative controls. ProbeTrace contains 6,000 five-owner rows, with 750 out of 750 true-owner positives and zero out of 5,250 false-attribution controls. SealAudit produced 320 decisive marker-hidden outcomes out of 960, with zero out of 960 unsafe passes.

The key conclusion is not that one method solves source-code watermarking. The conclusion is that reliable evaluation needs fixed denominators, executable controls, uncertainty reporting, access-specific boundaries, and explicit abstention when evidence is insufficient.

For the demo, I will not rerun the full experiments in the room. That would require compute and external API resources. Instead, I will show inspectability. I will open the project page, then the repository, claim boundaries, traceability matrix, manifest, and the quick viva check. The check verifies the submitted inspection route, not a full experimental rerun.

The future work is to develop the benchmark part toward TOSEM and the four watermarking workstreams toward EMNLP-style papers. The submitted FYP artifact remains my individual implementation, dissertation, and evidence package.

## Demo Steps

1. Open the project page: `https://haoyi-zhang.github.io/WatermarkScope/`
2. Use the page route: Problem, Contract, Submitted Results, Walkthrough, Demo, Limits.
3. Open `CLAIM_BOUNDARIES.md` and show one allowed claim and one forbidden claim.
4. Open `docs/TRACEABILITY_MATRIX.md` and show that claims point to artifacts.
5. Run `python scripts/viva_check.py`.
6. Say clearly: this is a quick inspection check, not a full GPU/API rerun.

## Short Q&A Answers

**Why not one detector score?**  
Because the five stages have different access models and evidence objects. One score would mix incompatible claims.

**Does CodeDye prove contamination?**  
No. It reports sparse live signal under controls. It is a conservative audit surface, not a provider accusation.

**Is ProbeTrace too perfect?**  
The claim is scoped. It is 750/750 true-owner positives inside the five-owner surface, with 0/5,250 false-attribution controls. It is not general authorship proof.

**What does the demo prove?**  
It proves inspectability and repository consistency. It does not rerun the full experiments.

**What is the biggest limitation?**  
Finite denominators. A broader claim needs a new admitted evidence surface.

**What is your main contribution?**  
The main contribution is the evidence-contract framing for source-code watermarking, plus a working repository that connects benchmark rows, controls, artifacts, and claim boundaries.

## Final Reminder

Answer first. Then state the boundary. Then point to the evidence file.
