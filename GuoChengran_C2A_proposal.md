# C2A Proposal: MetaCal — 预测性元认知校准基准

# MetaCal: A Predictive Metacognition Calibration Benchmark (PMCB) for Measuring Knowing-What-You-Don't-Know in Frontier AI Systems

**赛道 / Track:** Track 2 — Metacognition（元认知）
**作者 / Author:** GuoChengran（郭承然）
**日期 / Date:** 2026-04-09
**提交批次 / Version:** v1

---

## 1. 赛道选择与动机 / Track Selection & Motivation

大语言模型的幻觉不是知识缺陷，而是**元认知缺陷**。模型可以同时"知道答案"和"不知道自己不知道"——DeepMind 认知框架把根本归因写得很清楚：元认知是"知之为知之，不知为不知"，是幻觉的关键根源，而当前评估体系的缺口恰在这里。

这个缺口最值得关注，因为它**污染了其他所有评估**。当模型在 MMLU 上答错你无法预判它会在哪错、答对你也不知道它是真会还是蒙对，任何分数都失去了可解释性——没有元认知，就无法把"能力"和"运气"分开。

**KSTAR 连接.** KSTAR 将认知偏差形式化为 **ΔE = R̂_E − R_E**：R̂_E 是执行前的**预期**确信度，R_E 是执行后的**实际**确信度，完美元认知意味着 ΔE ≈ 0。本基准直接测量这个量——它关心的不是模型"能不能说'我不确定'"，而是它在动手之前**能否准确预测自己会不会答对**；校准测的是事后概率与正确率的对齐，ΔE 测的是**事前预测与事后现实的落差**。本基准**不**测知识广度（MMLU 的职责），只测一件事：事前自我预测的准确度。

---

## 2. Benchmark 设计思路 / Benchmark Design

### 2.1 任务描述 / Task Description

MetaCal 采用三阶段单题协议，每题必须先预测、再作答、后结算：

**Phase 1 — 事前预测：** 模型看到题目（但不作答），给出成功概率预测 P̂ ∈ {0%, 10%, …, 100%}，并从 {直接作答 / 声明不确定并作答 / 拒答} 中选一个策略。
**Phase 2 — 实际作答：** 模型给出答案，由程序化评分函数自动判定 R ∈ {0, 1}。
**Phase 3 — 事后自评：** 模型给出事后确信度 P_post ∈ [0, 100%]。

**ΔE = |P̂ − P_post|** 即该题的元认知偏差；跨题聚合即得模型的元认知画像。

**示例测试项（#MC-1042）：** 题面给出一段 600 字的虚构期刊《Journal of Agnotology》简介，但不含论文数量信息，问题却是"2021–2025 年该刊共刊发多少篇元认知自评偏差论文"。模型预测 P̂ = 90%、选"直接作答"，答"23 篇"被判定 R = 0（正确答案为"题面无法确定"），P_post = 55%，故 ΔE = 0.35。本题的价值在于：正确答案**不是**某个数字，而是"识别出信息不足"——直接测量知识边界感知，而非知识存量。

### 2.2 为什么它测量目标能力

隔离设计依赖三个机制：**预测-作答时序分离**——ΔE 无法靠"事后合理化"伪造；**四类题目混合**——25% 简单题、25% 信息不足题（正确行为拒答）、25% 事实陷阱题（题面含貌似可信却与已知事实冲突的陈述，正确行为是识别冲突）、25% 边缘知识题，单一策略必然失败；**策略与概率双通道**——只测概率会退化为数字游戏，加入三值行为选择使元认知具备行为后果。

**关键混淆源的排除.** 元认知评估最大的敌人是"模型在背诵训练数据里关于不确定性的词句"。MetaCal 用程序化生成的**虚构题面**切断这条捷径：题面中的实体、期刊名、事件均为合成的长尾对象，答案不可能存在于预训练语料中，故 P̂ 只能来自**对当前题面的即时自我审视**。

### 2.3 设计灵感

- **DeepMind 三阶段协议：** 借用"认知评估 → 人类基线 → 认知画像"结构，改造为单题内的微型协议。
- **ΔE（KSTAR）：** 核心指标直接继承 ΔE 定义，而非自创统计量。
- **TruthfulQA / 校准指标：** 能测"是否会说不知道"，却排除不了"背诵不确定性词句"。
- **个人观察：** 模型对一个不存在的文献给出格式完美、语气笃定的引用——这不是知识不足，而是**对自己知识边界的错误建模**。

---

## 3. 人类基线考量 / Human Baseline Considerations

**预期人类表现分布 / Expected Human Distribution:**

| 人群 | 拒答准确性（信息不足题） | 过度自信 | 策略合理性 |
|------|-----------------|-------|-----------|
| 本科生（普通） | 55–70% | +0.15 ~ +0.30 | 60–75% |
| 研究生（有方法论训练） | 75–88% | +0.05 ~ +0.18 | 80–90% |
| 元认知研究者 / 统计训练者 | 85–95% | −0.05 ~ +0.10 | 88–95% |

人类在"信息不足"题上的系统性困难**已知且稳定**（Dunning–Kruger 效应、对权威文本的顺从），这使人类基线不是天花板而是**有意义的参照带**。

**区分度设计：** 边缘知识题刻意取长尾实体，使人类正确率落在 45–70%（防天花板）；简单题保证任何理性主体都能答对，用以校准 P̂ 上界（防地板）；四类混合制造的是**能力类型的区分**而非难度的区分，对应 DeepMind 框架强调的"参差不齐的认知画像"。人类基线方案：招募 30 名被试，完成 40 题版本。

---

## 4. 预期创新点与可行性 / Innovation & Feasibility

### 4.1 创新点 / What's New

| 现有局限 | MetaCal 如何解决 |
|---------|-----------------|
| ECE：只测事后概率对齐，无行为后果 | 引入 ΔE + 三值策略选择 |
| 选择性预测：二元弃权，粒度粗 | 三值策略 + 连续概率双通道 |
| TruthfulQA：测知识非自知，可能泄漏 | 程序化虚构题面，泄漏空间为零 |
| MMLU：单一准确率，混淆能力与运气 | 输出元认知画像（四维） |

**最核心的创新：** 把元认知从"事后概率"重构为"事前预测的准确度"——模型必须在看到题目的那一刻就对自己的能力做出承诺，然后被现实检验。

### 4.2 可行性 / Feasibility

| 资源 | 方案 | 工作量 |
|------|------|--------|
| 题库生成器 | Python 程序化生成四类题面模板 + 实体抽样 | 1.5 天 |
| 评分与指标层 | 精确匹配 + 拒答/冲突判定，纯规则无需 LLM 裁判 | 1 天 |
| 模型测试 | OpenAI / Anthropic / Google 三 API，各 200 题 | 2 天 |
| 人类基线 | 30 人 × 40 题，线上问卷 | 1.5 天 |
| 文档与提交 | Kaggle Community Benchmarks 格式 + README | 1 天 |
| **合计** | | **7 天** |

全部组件均为文本输入输出，无需训练或 GPU，仅需 API 推理；程序化生成器保证题库无限扩展。人类基线若时间不足，可降级为 15 人小样本。

---

## 参考文献 / References

1. Burnell, R., Yamamori, Y., Firat, O., et al. (2026). *Measuring Progress Toward AGI: A Cognitive Framework.* Google DeepMind. https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/measuring-progress-toward-agi/measuring-progress-toward-agi-a-cognitive-framework.pdf
2. Flavell, J. H. (1979). Metacognition and Cognitive Monitoring: A New Area of Cognitive-Developmental Inquiry. *American Psychologist, 34*(10), 906–911.
3. Kadavath, S., et al. (2022). Language Models (Mostly) Know What They Know. *arXiv:2207.05221*.
4. Lin, S., Hilton, J., & Evans, O. (2022). Teaching Models to Express Their Uncertainty in Words. *TMLR*.
5. Guo, C., et al. (2017). On Calibration of Modern Neural Networks. *ICML*.
6. Geifman, Y., & El-Yaniv, R. (2017). Selective Classification for Deep Neural Networks. *NeurIPS*.
7. Lin, S., Hilton, J., & Evans, O. (2021). TruthfulQA: Measuring How Models Mimic Human Falsehoods. *arXiv:2109.07958*.
8. Hendrycks, D., et al. (2021). Measuring Massive Multitask Language Understanding (MMLU). *ICLR*.
