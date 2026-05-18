# WatermarkScope Viva Q&A Control Cheat Sheet

Use this sheet only for rehearsal. During the viva, stay on the final Thank you / Q&A control page and use the shortcut buttons when the examiner asks for evidence.

## Core Rule

**中文：** 先直接回答，再给一个数字或文件，最后说边界。不要一上来长篇解释。  
**English:** Answer directly first, then give one number or file, then state the boundary. Do not start with a long explanation.

## Fast Routes

### 1. 老师问：你的数据集怎么构建的？

**Click:** `Dataset`

**中文先说：** 我这里更准确地说是五个固定 evaluation surfaces，不是一个混在一起的大 dataset。  
**English to say:** I would describe them as five fixed evaluation surfaces, not one mixed dataset.

**Evidence to open:** `Method index: all denominators`, then `SemCodebook denominator manifest` if the examiner wants detail.

**Boundary:** 每个 surface 有自己的分母，不能共享一个 accuracy。

### 2. 老师问：你的评估指标是什么？

**Click:** `Metrics`

**中文先说：** 我的指标跟 claim 绑定，不同阶段有不同指标。  
**English to say:** My metrics are tied to the claim, so each stage has its own metric.

**Evidence to open:** `Results summary`, then `Method index: metric definitions`.

**Boundary:** 不把 benchmark completion、recovery、audit、attribution 和 triage 合成一个总分数。

### 3. 老师说：打开代码给我看一下。

**Click:** `Code`

**中文先说：** 我会先展示主方法 SemCodebook 的 detector 和 evaluation，再展示 traceability matrix 说明代码如何连到结果。  
**English to say:** I will start with the SemCodebook detector and evaluation files, then use the traceability matrix to show how the code connects to the result.

**Evidence to open:** `SemCodebook detector`, `SemCodebook evaluation`, then `Traceability matrix`.

**Boundary:** 现场不逐行读代码，只解释输入、输出、判定逻辑和证据路径。

### 4. 老师问：你的主要方法具体在哪里？

**Click:** `Main method`

**中文先说：** 主要方法是 SemCodebook，它把 provenance 信息放进结构化代码载体，并用 detector 和 negative controls 检查。  
**English to say:** The main method is SemCodebook. It puts provenance information into structured code carriers and checks it with detector logic and negative controls.

**Evidence to open:** `Detector logic`, `Negative controls`, `Negative replay gate`, `Final claim lock`.

**Boundary:** 这是白盒 admitted-cell provenance recovery，不是所有自然生成代码的通用水印检测。

### 5. 老师问：结果证据在哪里？

**Click:** `Artifacts`

**中文先说：** 结果不只写在论文里，还绑定到 manifest、artifact 和 claim boundary。  
**English to say:** The results are not only written in the dissertation. They are bound to manifests, artifacts, and claim boundaries.

**Evidence to open:** `Result manifest`, `Main table source manifest`, `Claim boundaries`, `Traceability matrix`.

**Boundary:** 数字必须跟固定分母和 artifact 一起解释。

### 6. 老师问：能现场复现吗？

**Click:** `Reproduce`

**中文先说：** 完整实验不能现场重跑，因为需要 GPU、模型权重或 API；但我可以现场跑轻量检查并展示完整证据路线。  
**English to say:** The full experiments cannot be rerun live because they need GPUs, model weights, or APIs. But I can run the lightweight check and show the evidence route.

**Evidence to open:** `viva_check.py`, `Repository README`, `Traceability matrix`.

**Boundary:** `viva_check.py` 是一致性检查，不是完整实验复现。

### 7. 老师问：为什么 CodeDye 只有 6/300？

**Click:** `Metrics` or use the lower `CodeDye sparse?` prompt.

**中文先说：** 如果我声称高召回检测器，6/300 肯定不够；但我没有这样声称。它是保守黑盒审计证据。  
**English to say:** If I claimed a high-recall detector, 6/300 would be too sparse. But I do not make that claim. It is conservative black-box audit evidence.

**Evidence to open:** `Results summary`, `Claim boundaries`.

**Boundary:** 不能说成污染比例、provider 指控或 proof of absence。

### 8. 老师问：future work 和提交版是什么关系？

**Click:** lower `Future work?` prompt.

**中文先说：** 今天 defend 的是提交版 FYP；future repositories 是后续投稿方向，不替换提交版分母。  
**English to say:** The submitted FYP is what I defend today. The future repositories are continuation tracks and do not replace the submitted denominators.

**Evidence to open:** `Claim boundaries` if needed.

**Boundary:** 后续实验必须作为新的 evidence surface 单独报告。

### 9. 老师问：你为什么做这个方向？或者你已经有相关工作了吗？

**Click:** `Research line`

**中文先说：** 这是我持续推进的一条研究线。我已经有两篇早期相关工作被 FSE 2026 IVR 接收，但它们只是研究背景，不是这次 submitted FYP 的结果。  
**English to say:** This is a research line that I have been developing. I already have two earlier related papers accepted by FSE 2026 IVR, but I use them only as research context, not as part of the submitted FYP result.

**Evidence to open:** `FSE 2026 IVR track`, then the current opening page context if needed.

**Boundary:** 相关已接收论文用于说明研究连续性，不替换当前 FYP 的 fixed evidence surface。

## Emergency Lines

**没听清：** Sorry, could you please repeat the question more slowly?

**需要思考：** Let me think for a second. I want to answer this accurately.

**老师质疑数字：** The number I defend here is the submitted FYP surface. Later continuation results are separate future work and should not replace this denominator.
