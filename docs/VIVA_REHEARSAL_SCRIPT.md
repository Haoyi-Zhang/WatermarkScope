# WatermarkScope Viva Rehearsal Script

Use `docs/VIVA_ORAL_SCRIPT_AND_QA.md` as the full speaking and Q&A guide. This file is the short rehearsal checklist.

## Route

| Page | Target |
|---|---:|
| Opening | 45 sec |
| Problem | 1 min 15 sec |
| Method | 2 min |
| Results | 2 min 30 sec |
| Demo | 1 min 30 sec |
| Future and Q&A landing | 1 min |

## Core Story

Good afternoon. I am Haoyi Zhang. My project is WatermarkScope, a benchmark-to-audit framework for source-code watermarking in code generation models.

The problem I focus on is simple: generated code may be copied, edited, translated, or deployed outside the original prompt session. So a detector score alone is not enough. I need to know what was counted, what controls were used, where the artifact is, and what the result is allowed to claim.

My method is an evidence contract. A result becomes a claim only after I fix the denominator, controls, artifact, access model, and boundary. I implemented this through five stages: CodeMarkBench, SemCodebook, CodeDye, ProbeTrace, and SealAudit.

For results, I will not read every table. I will explain the five submitted evidence surfaces with their denominators and boundaries. The key point is that the project does not claim one universal detector score. It claims disciplined, inspectable evidence.

For the demo, I will show the repository, claim boundaries, traceability matrix, result manifest, and the quick viva check. I will clearly say that this is an inspection route, not a full GPU or API rerun.

The submitted FYP version is the version I am defending. The continuation repositories are future paper tracks and do not change the submitted dissertation evidence.

## Answer Pattern

Answer directly, give one evidence number or file, then state the boundary.

