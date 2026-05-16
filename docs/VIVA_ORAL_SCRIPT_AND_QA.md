# WatermarkScope Viva Oral Script and Q&A

Use this as a speaking guide, not as a text to read word by word. The style should sound like a student explaining his own work: clear, direct, and honest. Short sentences are preferred because the viva is spoken, not read.

## One-Sentence Story

WatermarkScope is my framework for checking source-code watermarking as evidence that people can inspect, not just as one detector score.

## 10-Minute Route

| Page | Time | What to say |
|---|---:|---|
| Opening | 45 sec | Project title, one-sentence story, why this matters. |
| Problem | 1 min 15 sec | Generated code moves; a score alone is weak. |
| Method | 1 min 45 sec | Evidence contract plus five-stage pipeline. |
| Results | 2 min | Five submitted result surfaces; focus on what each number can safely mean. |
| Demo | 1 min 30 sec | Repository, claim boundary, traceability, manifest, viva check. |
| Future and close | 45 sec | Submitted FYP is fixed; future work is separate. |
| Q&A landing | 15 sec | Stop on the Q&A page and use the hot-seat rule. |
| Buffer | 1 min 30 sec | Slow down, answer interruption, or skip demo details if needed. |

## Full Oral Script

### Opening

Good afternoon. I am Haoyi Zhang. My project is WatermarkScope: A Benchmark-to-Audit Framework for Source-Code Watermarking in Code Generation Models.

I will use this homepage as my presentation route. I will move through the pages one by one, so the talk stays close to ten minutes.

The main idea is simple. Large language models can generate code, but later that code may be copied, edited, translated, or used in another project. When that happens, one detector score is not enough for a strong watermark claim.

So in this project I ask a practical question: if I see a watermark signal, what evidence can I really defend?

My answer is WatermarkScope. It treats source-code watermarking as an evidence problem. I look at what was counted, what controls were used, where the artifacts are, what access setting was assumed, and what claim boundary I should not cross.

### Problem

When I started this work, the main gap I saw was not only detection performance. The bigger problem was how to defend the evidence.

There are three reasons. First, generated code can leave the original prompt session. Second, source code is not only text; it should still run. Third, different access settings mean different claims. A white-box recovery method, a black-box audit, an owner-attribution protocol, and a security triage system are different questions.

So before I interpret any number, I first need to define the evidence surface clearly. That means I need to know the denominator, the controls, and the boundary.

### Method

The method has two parts. The first part is an evidence contract. The second part is a five-stage implementation.

The evidence contract is my rule for making a claim. A result should have five things before I treat it as evidence: a denominator, controls, an artifact, an access model, and a boundary.

The denominator tells me what was counted. The controls tell me what would make the signal fail. The artifact tells me where the evidence is stored. The access model tells me whether this is white-box, black-box, active-owner, or security-facing. The boundary tells me what I must not claim.

Then I implemented this through five stages.

CodeMarkBench gives the executable benchmark foundation. SemCodebook is the main white-box provenance recovery method. CodeDye is a conservative black-box audit. ProbeTrace studies scoped active-owner attribution. SealAudit studies marker-hidden security triage.

The key point is this: the five stages are connected by the same evidence discipline, but I do not merge them into one universal accuracy score.

### Results

On the results page, I will not read every number. I will explain the results in three points.

First, the benchmark foundation is complete. CodeMarkBench has 140 out of 140 canonical runs. This tells me the benchmark rows are executable and countable. It does not mean every watermark method succeeds.

Second, SemCodebook is the main method result. It recovers 30,330 out of 31,200 positive cases. It also has 0 hits in 62,400 fixed negative controls and 0 hits in 62,400 blind replay negative controls. So the safe claim is structured white-box provenance recovery inside the admitted cells.

Third, the other stages show why boundaries matter. CodeDye has sparse black-box evidence, so I do not call it contamination proof. ProbeTrace has strong scoped owner verification, but I do not call it general authorship proof. SealAudit gives selective triage, but I do not call it a safety certificate.

So the result message is: do not trust one big detector score. Check the denominator, the controls, and the boundary for each claim.

### Demo

For the demo, I will not rerun the full experiments in the room. Some experiments need GPUs, model weights, or provider APIs, so a full rerun is not realistic in a viva.

Instead, I will show inspectability. I will open the repository, then the claim boundary document, the traceability matrix, the result manifest, and the quick viva check.

The point is not to prove everything again from zero. The point is to show that the submitted work is organized so it can be checked. Each claim points to code, artifacts, manifests, and boundaries.

### Future Work and Close

The submitted FYP version is the version I am defending today. The future page shows five continuation tracks, but I keep them separate from the submitted evidence.

If the examiner is interested, I can briefly show these repositories. But I will not mix them with the dissertation result, because the submitted FYP has its own fixed evidence surface.

To summarize, my contribution is a practical framework for making source-code watermarking evidence more honest and inspectable. I built the benchmark, the method modules, the controls, the artifacts, and the claim boundaries so the result can be checked instead of only trusted.

Then I will stop on the Q&A page. My answer rule is simple: direct answer first, one evidence number second, and the boundary third. Thank you. I am happy to answer questions.

## Short Version If Time Is Tight

My project is WatermarkScope. The problem is that generated code may be copied, edited, and deployed outside the original generation session, so a single watermark detector score is not enough.

My method is an evidence contract. Before I make a claim, I fix the denominator, controls, artifact, access model, and boundary.

I implemented this through five stages: CodeMarkBench for executable benchmark rows, SemCodebook for white-box provenance recovery, CodeDye for black-box audit, ProbeTrace for owner attribution, and SealAudit for security triage.

The submitted results show that the framework can connect benchmark rows, controls, artifacts, and claim boundaries. The main point is not one universal score. The main point is disciplined evidence.

## Demo Script

1. Open the homepage.
   - "This page is my viva route. I will use it to keep the story short."

2. Open the repository.
   - "The repository contains the submitted FYP code, result artifacts, manifest, and viva-facing documents."

3. Open `CLAIM_BOUNDARIES.md`.
   - "This is important because it says both what I can claim and what I cannot claim."

4. Open `docs/TRACEABILITY_MATRIX.md`.
   - "Here I can trace a claim back to the relevant code, artifact, and document."

5. Open `RESULT_MANIFEST.jsonl`.
   - "The manifest is used to preserve evidence records with hashes and paths."

6. Run or show `python scripts/viva_check.py`.
   - "This quick check is not a full experimental rerun. It checks that the viva-facing evidence route is present and consistent."

## Answering Style

Use this pattern:

1. Direct answer.
2. One evidence number or file.
3. Boundary.

If I feel nervous, I should slow down and answer in one short paragraph. I do not need to prove everything again in one answer.

Example:

"No, CodeDye does not prove contamination. In the submitted surface it reports 4/300 sparse live signals with 0/300 negative controls. I only claim conservative black-box audit evidence, not provider wrongdoing."

## Detailed Q&A

### Core Understanding

**Q1. What is your project about?**  
A: It is about making source-code watermarking evidence easier to defend. Instead of only reporting a detector score, I connect each result to a denominator, controls, artifacts, access model, and claim boundary.

**Q2. What is the main research gap?**  
A: The gap is that generated code moves away from the original prompt session, but many watermark results are still reported as if one score is enough. For code, I think the result must also be executable, inspectable, and bounded.

**Q3. What is your main contribution?**  
A: My main contribution is the WatermarkScope evidence contract and the five-stage implementation around it. The contract makes each watermark claim explicit: what is counted, what controls exist, and what the claim is not allowed to mean.

**Q4. Why is this a final year project rather than only a survey?**  
A: Because I built an actual repository with benchmark code, method modules, scripts, result artifacts, manifests, and viva checks. The dissertation is supported by implementation and preserved evidence, not only discussion.

**Q5. Why source code and not normal text?**  
A: Source code has execution behavior. If a watermarked snippet no longer runs, the claim is much less useful. That is why I treat executable benchmark rows as part of the evidence.

### Method and Novelty

**Q6. What is the evidence contract?**  
A: It is my rule for admitting a watermark result. A result needs a denominator, controls, artifact, access model, hash or preservation route, and claim boundary before I treat it as evidence.

**Q7. Why not just use accuracy?**  
A: Accuracy is useful only after we know what was counted. In this project, white-box recovery, black-box audit, owner attribution, and security triage answer different questions, so one accuracy score would mix different claims.

**Q8. What is the most original technical part?**  
A: SemCodebook is the main method part. It uses structured program carriers and recovery logic instead of treating code only as text. The relevant implementation is in files such as `projects/SemCodebook/src/semcodebook/carriers.py`, `detector.py`, and the evaluation scripts.

**Q9. What are the five stages?**  
A: CodeMarkBench is the benchmark foundation. SemCodebook is white-box recovery. CodeDye is black-box audit. ProbeTrace is active-owner attribution. SealAudit is marker-hidden security triage.

**Q10. Why do you need five stages?**  
A: Because watermark evidence changes with access. A white-box method can inspect more than a black-box audit. An owner-attribution protocol is different from a security triage system. I separate them so I do not overclaim.

**Q11. What is the innovation compared with a normal benchmark?**  
A: A normal benchmark often reports performance. WatermarkScope also asks what claim the performance is allowed to support. That extra boundary is important for watermarking because the social meaning of a false claim can be serious.

**Q12. Where is the innovation in code?**  
A: The benchmark structure is under `projects/CodeMarkBench/`. The SemCodebook method is under `projects/SemCodebook/src/semcodebook/`. CodeDye audit logic is under `projects/CodeDye/src/codedye/`. ProbeTrace scripts are under `projects/ProbeTrace/scripts/`. SealAudit triage code is under `projects/SealAudit/src/sealaudit/` and `projects/SealAudit/scripts/`.

### Results

**Q13. What is your strongest result?**  
A: SemCodebook is the strongest method result. It reports 30,330 recoveries out of 31,200 positives, with zero hits in both fixed and blind negative-control surfaces. I still keep the claim limited to the admitted white-box cells.

**Q14. Does 140/140 mean the benchmark proves watermark success?**  
A: No. It means the canonical benchmark runs completed and are countable. It is the foundation for evaluation, not a claim that every watermark method succeeded.

**Q15. What does SemCodebook prove?**  
A: It supports structured white-box provenance recovery within the admitted denominator. It does not prove universal watermarking for every model or every natural code distribution.

**Q16. What does CodeDye prove?**  
A: CodeDye gives conservative black-box audit evidence. In the submitted version it has 4/300 sparse live signals, positive-control support, and 0/300 negative controls. It does not prove contamination or wrongdoing.

**Q17. Is 4/300 too small?**  
A: It would be small if I claimed high-recall detection. I do not claim that. I claim sparse, conservative audit evidence under controls, which is the honest interpretation of that surface.

**Q18. ProbeTrace looks very strong. Are you overclaiming?**  
A: I avoid overclaiming by limiting the claim. ProbeTrace has 750/750 true-owner positives and 0/5,250 false-attribution controls inside a fixed five-owner surface. That is scoped owner verification, not universal authorship proof.

**Q19. SealAudit only has 320 decisive outcomes out of 960. Is that weak?**  
A: I see it as selective by design. For security-facing work, forced decisions can be dangerous. I report decisive outcomes and keep uncertain rows as abstention or review load.

**Q20. Why do you report zero unsafe passes?**  
A: Because it is an important observed control result, but I do not treat it as zero risk. Zero observed events still have finite-sample uncertainty.

### Validity and Limitations

**Q21. What is the biggest limitation?**  
A: Scope. Each result has a finite denominator: specific models, providers, tasks, owners, or triage rows. The dissertation handles this by stating boundaries instead of broadening claims.

**Q22. Could your results generalize to other models?**  
A: Possibly, but I would not claim that without a new admitted surface. The correct next step is to add more model cells and report them as new evidence, not to stretch the current result.

**Q23. Could someone attack the watermark?**  
A: Yes, attacks are always possible. That is why I report controls and boundaries. The project is not saying watermarking is impossible to break; it is saying how to evaluate evidence more carefully.

**Q24. Why is abstention acceptable?**  
A: Because abstention is more honest than a forced label when the evidence is insufficient. In this project, abstention is a way to avoid turning weak evidence into a strong claim.

**Q25. How do you avoid cherry-picking?**  
A: I use fixed denominators, controls, manifests, and claim boundaries. Misses and nondecisive rows remain in the denominator instead of being hidden.

**Q26. Why confidence intervals or uncertainty reporting?**  
A: Because an observed zero is not the same as true zero. Uncertainty reporting reminds the reader that the result is based on a finite sample.

**Q27. What would you do if you had more time?**  
A: I would add more admitted surfaces: more models, more provider families, stronger black-box calibration, and broader owner registries. I would keep each new result separate from the submitted FYP denominator.

### Implementation and Reproducibility

**Q28. Can the examiner reproduce everything live?**  
A: Not all full experiments live, because some require GPUs, model weights, or provider APIs. But the repository is inspectable, and the viva check verifies the submitted evidence route.

**Q29. What does `viva_check.py` do?**  
A: It checks that viva-facing documents, manifests, claim boundaries, and key artifacts are present and consistent. It is a quick inspection check, not a full GPU/API rerun.

**Q30. Why use manifests?**  
A: Manifests make the evidence easier to inspect. They record paths, hashes, and result records so that claims are tied to preserved artifacts.

**Q31. Why are some future repositories separate?**  
A: Because the submitted FYP version is fixed. The other repositories are continuation tracks for paper development. I can show them as future work, but they do not change the defended dissertation evidence.

**Q32. If a repository link is private, how will the examiner see it?**  
A: For the submitted FYP, the main WatermarkScope repository is the defended artifact. The continuation repositories can be shown from my logged-in laptop if there is time, but they are not required to validate the submitted dissertation.

**Q33. What part did you personally implement?**  
A: The submitted FYP artifact is my individual work: the framework design, repository organization, implementation snapshots, result preservation, dissertation, and viva-facing evidence route.

### Examiner Challenges

**Q34. Is this too broad for one FYP?**  
A: It is broad, but the unifying idea is narrow: every stage is evaluated through the same evidence contract. I also keep claims bounded, so I do not present all five modules as complete final papers.

**Q35. Are you mixing completed FYP work with future work?**  
A: No. During the viva I defend the submitted FYP evidence. Future repositories are only continuation tracks and do not change the submitted denominator or conclusions.

**Q36. Why should this receive a high mark?**  
A: Because it has a clear research gap, a working software artifact, controlled experiments, preserved result artifacts, claim boundaries, and an honest limitation structure. The work is large, but it is also organized around one defensible idea.

**Q37. What is one thing you would change in the dissertation?**  
A: I would make the oral story shorter earlier. The dissertation contains many details, but for the viva the strongest story is the evidence contract and the five result surfaces.

**Q38. If your method fails on a new model, does the project fail?**  
A: No. A new failure would become a new evidence surface. The framework is designed to report success, misses, controls, and boundaries, not to hide failures.

**Q39. What is the practical value?**  
A: It helps researchers and reviewers ask better questions before trusting a watermark result: what was counted, what controls were used, what artifact supports it, and what claim is forbidden.

**Q40. What is your final takeaway?**  
A: My final takeaway is that code watermarking should be evaluated as evidence. A detector score is useful, but only after it is tied to a clear denominator, controls, artifacts, access model, and boundary.
