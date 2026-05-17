# WatermarkScope Viva Oral Script and Q&A

Use this as a bilingual speaking guide. The Chinese text is for understanding and memory. The English text is what I should say in the viva. Do not read every line mechanically; speak in short, clear sentences.

## One-Sentence Story

**中文理解：** 我的项目不是只做一个水印检测器，而是研究“代码水印结果怎样才算可以被老师和审稿人检查的证据”。

**English to say:** WatermarkScope is my framework for treating source-code watermarking as inspectable evidence, not just as one detector score.

## 10-Minute Route

| Page | Time | 中文目标 | English goal |
|---|---:|---|---|
| Opening | 45 sec | 说清题目和主线 | State title and one-sentence story |
| Problem | 1 min 15 sec | 说明为什么一个分数不够 | Explain why one score is weak |
| Method | 1 min 45 sec | 讲 evidence contract 和五个阶段 | Explain evidence contract and five stages |
| Results | 2 min | 只讲核心数字和边界 | Give key numbers with boundaries |
| Demo | 1 min 30 sec | 点 Play demo，展示可检查性 | Play the demo and show inspectability |
| Future | 45 sec | 说明后续仓库是 future work | Separate future repos from submitted FYP |
| Q&A landing | 15 sec | 停在 Q&A 页 | Stop and answer questions |

## Homepage Control

**中文理解：** 真实 viva 推荐用滚轮或 Next 一页一页切。到 Demo 页时，点击 **Play demo**，它会自动播放仓库证据路线。

**English to say:** I will use this homepage as my presentation route. On the demo page, I will click Play demo. It will automatically show the evidence route: README, claim boundaries, traceability, manifest, and the quick viva check.

## Full Oral Script

### 1. Opening

**中文理解：** 先介绍自己、题目、主页演示方式。重点说“一个检测分数不够”。

**English to say:** Good afternoon. I am Haoyi Zhang. My project is WatermarkScope: A Benchmark-to-Audit Framework for Source-Code Watermarking in Code Generation Models.

I will use this homepage as my presentation route. I will move page by page, so the talk stays close to ten minutes.

The main idea is simple. Large language models can generate code, but later that code may be copied, edited, translated, or used in another project. When that happens, one detector score is not enough for a strong watermark claim.

So my question is: if I see a watermark signal, what evidence can I really defend?

### 2. Problem

**中文理解：** 问题不是“能不能检测”，而是检测结果离开原始 prompt 后还能不能被 defend。

**English to say:** The gap I focus on is not only detection performance. The bigger problem is how to defend the evidence after generated code leaves the original prompt session.

There are three reasons. First, generated code can move into another context. Second, source code is not only text; it should still run. Third, different access settings mean different claims.

A white-box recovery method, a black-box audit, an owner-attribution protocol, and a security triage system are different questions. So before I interpret any result, I need to fix the denominator, the controls, and the boundary.

### 3. Method

**中文理解：** 方法就是 evidence contract。每个结果都必须回答：数了什么？控制组是什么？证据在哪？什么访问条件？不能声称什么？

**English to say:** My method has two parts. The first part is an evidence contract. The second part is a five-stage implementation.

The evidence contract asks five questions before I make a claim. What is counted? What controls were used? Where is the artifact? What access model is assumed? And what claim boundary should I not cross?

Then I implemented this through five stages.

CodeMarkBench gives the executable benchmark foundation. SemCodebook is the main white-box provenance recovery method. CodeDye is a conservative black-box audit. ProbeTrace studies scoped active-owner attribution. SealAudit studies marker-hidden security triage.

The important point is that I do not merge these into one universal accuracy score. Each stage has its own evidence surface.

### 4. Results

**中文理解：** 不要逐个读表。讲“每个数字都必须带分母、控制组、边界”。

**English to say:** On the results page, I will not read every number. I will explain the results through denominator, controls, and boundary.

First, CodeMarkBench has 140 out of 140 canonical runs. This means the benchmark rows are executable and countable. It is benchmark support, not watermark success.

Second, SemCodebook is the main method result. In the submitted dissertation, it recovers 23,342 out of 24,000 positive cases, with 0 hits in 48,000 negative controls. So the safe claim is structured white-box provenance recovery inside the admitted cells.

Third, the other stages show why boundaries matter. CodeDye has 6 out of 300 sparse live signals, with positive and negative controls. ProbeTrace has 300 out of 300 scoped decisions with 0 out of 1,200 false-owner controls. SealAudit has 81 out of 960 decisive triage outcomes with 0 observed unsafe passes.

So my result message is: do not trust one big detector score. Check what was counted, what controls were run, and what the claim is allowed to mean.

### 5. Demo

**中文理解：** Demo 不是完整重跑实验。Demo 是证明仓库可以检查：README、边界、traceability、manifest、viva_check。

**English to say:** For the demo, I will not rerun the full experiments in the room. Some experiments need GPUs, model weights, or provider APIs.

Instead, I will show inspectability. I will click Play demo here. The page will automatically go through the repository README, claim boundaries, traceability matrix, result manifest, and the lightweight viva check.

The point is not to prove everything again from zero. The point is to show that each claim points to code, artifacts, manifests, and boundaries.

### 6. Future Work and Close

**中文理解：** 未来工作可以展示，但必须说清“不是提交版论文的一部分”。

**English to say:** The submitted FYP version is the version I am defending today. The future page shows continuation repositories, but I keep them separate from the submitted evidence.

If the examiner is interested, I can briefly open those repositories. But I will not mix them with the dissertation result, because the submitted FYP has its own fixed evidence surface.

To summarize, my contribution is a practical framework for making source-code watermarking evidence more honest and inspectable. I built the benchmark, method modules, controls, artifacts, and claim boundaries so the result can be checked instead of only trusted.

Thank you. I am happy to answer questions.

## Short Version If Time Is Tight

**中文理解：** 如果紧张，就只说这四句话的逻辑：问题、方法、结果、边界。

**English to say:** My project is WatermarkScope. The problem is that generated code can be copied, edited, and deployed outside the original generation session, so a single detector score is not enough.

My method is an evidence contract. Before I make a claim, I fix the denominator, controls, artifact, access model, and boundary.

I implemented this through five stages: benchmark, white-box recovery, black-box audit, owner attribution, and security triage.

The main contribution is not one universal score. The contribution is disciplined, inspectable evidence.

## Demo Script

**中文理解：** 到 demo 页之后，只需要点击 Play demo。不要打开太多外链，除非老师要求。

1. **中文：** 点击 Play demo。  
   **English:** I will click Play demo. This is a short automatic walkthrough of the evidence route.

2. **中文：** README 定义提交版工作。  
   **English:** The README defines the submitted FYP surface and the route into the artifacts.

3. **中文：** Claim boundaries 说明能说什么、不能说什么。  
   **English:** The claim boundary file is important because it states both what I can claim and what I cannot claim.

4. **中文：** Traceability 把 claim 对到代码和 artifact。  
   **English:** The traceability matrix connects a claim to the relevant code path and result artifact.

5. **中文：** Manifest 保存证据记录和 hash。  
   **English:** The manifest preserves evidence records with paths and hashes.

6. **中文：** viva_check 是轻量检查，不是完整重跑。  
   **English:** The quick viva check is not a full experimental rerun. It checks that the viva-facing evidence route is present and consistent.

## Answering Rule

**中文理解：** QA 时不要长篇解释。先直接回答，再给一个数字或文件，最后说边界。

**English pattern:** Direct answer first. Then one evidence number or file. Then the boundary.

Example:

**中文理解：** CodeDye 不是污染证明。

**English to say:** No, CodeDye does not prove contamination. In the submitted surface it reports 6/300 sparse live signals with 0/300 negative controls. I only claim conservative black-box audit evidence, not provider wrongdoing.

## Detailed Q&A

### Core Understanding

**Q1. What is your project about? / 你的项目是做什么的？**  
**中文：** 让代码水印结果变成可检查证据。  
**English:** It is about making source-code watermarking evidence easier to defend. Instead of only reporting a detector score, I connect each result to a denominator, controls, artifacts, access model, and claim boundary.

**Q2. What is the main research gap? / 主要研究空白是什么？**  
**中文：** 生成代码会离开原始会话，但很多评估还像只看一个分数。  
**English:** The gap is that generated code moves away from the original prompt session, but many watermark results are still reported as if one score is enough.

**Q3. What is your main contribution? / 主要贡献是什么？**  
**中文：** evidence contract 加五阶段实现。  
**English:** My main contribution is the WatermarkScope evidence contract and the five-stage implementation around it.

**Q4. Why source code, not normal text? / 为什么研究代码而不是普通文本？**  
**中文：** 代码有可执行性，不能只当文本。  
**English:** Source code has execution behavior. If a watermarked snippet no longer runs, the claim is much less useful.

### Method and Novelty

**Q5. What is the evidence contract? / evidence contract 是什么？**  
**中文：** 一个结果要有分母、控制组、证据文件、访问模型、边界，才可以被解释。  
**English:** It is my rule for admitting a watermark result. A result needs a denominator, controls, artifact, access model, and claim boundary before I treat it as evidence.

**Q6. Why not just use accuracy? / 为什么不用一个 accuracy？**  
**中文：** 因为不同阶段问的问题不一样。  
**English:** Accuracy is useful only after we know what was counted. White-box recovery, black-box audit, owner attribution, and triage answer different questions.

**Q7. What is the most technical part? / 最技术的部分是什么？**  
**中文：** SemCodebook，结构化白盒溯源。  
**English:** SemCodebook is the main method part. It uses structured program carriers and recovery logic instead of treating code only as plain text.

**Q8. Why five stages? / 为什么需要五个阶段？**  
**中文：** 因为访问条件不同，claim 就不同。  
**English:** Because watermark evidence changes with access. A white-box method can inspect more than a black-box audit, and owner attribution is different from security triage.

### Results

**Q9. What is your strongest result? / 最强结果是什么？**  
**中文：** SemCodebook。  
**English:** SemCodebook is the strongest method result. It reports 23,342 recoveries out of 24,000 positives, with zero hits in 48,000 negative controls.

**Q10. Does 140/140 mean watermark success? / 140/140 是否代表水印成功？**  
**中文：** 不，是 benchmark 跑通。  
**English:** No. It means the canonical benchmark runs completed and are countable. It is the foundation for evaluation, not a success claim for every watermark.

**Q11. What does CodeDye prove? / CodeDye 证明了什么？**  
**中文：** 保守黑盒审计证据，不是污染证明。  
**English:** CodeDye gives conservative black-box audit evidence: 6/300 sparse live signals, positive-control support, and 0/300 negative controls.

**Q12. Is 6/300 too small? / 6/300 太小了吗？**  
**中文：** 如果声称高召回就太小，但我没有这样声称。  
**English:** It would be too small for a high-recall detector claim. I do not claim that. I claim sparse, conservative audit evidence under controls.

**Q13. Is ProbeTrace overclaiming? / ProbeTrace 是否过度声称？**  
**中文：** 不，它是有边界的 active-owner attribution。  
**English:** I avoid overclaiming by limiting the claim. ProbeTrace has 300/300 scoped decisions and 0/1,200 false-owner controls inside the submitted surface.

**Q14. Is SealAudit weak because only 81/960 is decisive? / SealAudit 只有 81/960 明确结果，是不是弱？**  
**中文：** 它是 selective triage，弃权是设计的一部分。  
**English:** I see it as selective by design. For security-facing work, forced decisions can be dangerous. I report decisive outcomes and keep uncertain rows as review load.

### Validity and Limitations

**Q15. What is the biggest limitation? / 最大限制是什么？**  
**中文：** 范围有限，每个结果都有固定分母。  
**English:** The biggest limitation is scope. Each result has a finite denominator, so I state boundaries instead of broadening the claim.

**Q16. Can it generalize to other models? / 能泛化到其他模型吗？**  
**中文：** 可能可以，但需要新的 evidence surface。  
**English:** Possibly, but I would not claim that without a new admitted surface.

**Q17. Could someone attack the watermark? / 水印能被攻击吗？**  
**中文：** 可以，所以更需要 controls 和 boundaries。  
**English:** Yes, attacks are possible. That is why I report controls and boundaries. The project is not saying watermarking is impossible to break.

**Q18. Why is abstention acceptable? / 为什么允许弃权？**  
**中文：** 证据不足时强行分类会过度声称。  
**English:** Abstention is more honest than a forced label when the evidence is insufficient.

### Implementation and Reproducibility

**Q19. Can the examiner reproduce everything live? / 老师能现场复现全部实验吗？**  
**中文：** 不能完整重跑，但能检查证据路线。  
**English:** Not all full experiments live, because some need GPUs, model weights, or provider APIs. But the repository is inspectable, and the quick check verifies the viva-facing route.

**Q20. What does `viva_check.py` do? / viva_check.py 做什么？**  
**中文：** 检查文档、manifest、关键 artifact 是否存在且一致。  
**English:** It checks that the key viva-facing documents, result manifest, artifacts, traceability matrix, and claim boundaries are present.

**Q21. Where is the code evidence? / 代码证据在哪里？**  
**中文：** 仓库里的项目目录、manifest、traceability。  
**English:** The code evidence is in the submitted repository. The strongest live route is README, CLAIM_BOUNDARIES.md, TRACEABILITY_MATRIX.md, RESULT_MANIFEST.jsonl, and viva_check.py.

### Future Work

**Q22. Are the future repositories part of the submitted FYP? / future repos 是提交版 FYP 吗？**  
**中文：** 不是，它们是后续投稿准备。  
**English:** No. They are continuation tracks. The submitted FYP evidence surface stays fixed.

**Q23. What would you do next? / 后续怎么做？**  
**中文：** 增加新模型、新 provider、更强黑盒校准、更大 owner registry。  
**English:** I would add new admitted surfaces: more models, more provider families, stronger black-box calibration, and broader owner registries.

**Q24. Why did you organize this as several repositories? / 为什么分多个仓库？**  
**中文：** 因为每个问题的 evidence surface 不同，分开更清楚。  
**English:** Because each continuation track has a different evidence question. Keeping them separate avoids mixing denominators and claims.

## Emergency Answers

**If I do not understand the question / 没听清问题：**  
**English:** Sorry, could you please repeat the question more slowly?

**If I need a moment / 需要思考：**  
**English:** Let me think for a second. I want to answer this accurately.

**If the examiner challenges a number / 老师质疑数字：**  
**English:** The number I defend here is the submitted FYP surface. Later continuation results are separate and should not replace this denominator.

**If asked whether the work is too broad / 老师问是否太宽：**  
**English:** It is broad in modules, but narrow in principle. Every stage follows the same evidence contract, and each claim is bounded.
