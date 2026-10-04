# MetaCal — 用「事前预测的准确度」衡量 AGI 的元认知

> **C2A / C9 挑战** ｜ [*Measuring Progress Toward AGI: Cognitive Abilities*](https://deepmind.google/) ｜ **Track 2 · Metacognition（元认知）**
> 作者 / Author: **lisenao** ｜ 版本 **1.0.0** ｜ 许可 **MIT**

本项目针对 DeepMind 认知框架中的 **Track 2（元认知）**，提出并实现了一个可运行、可复现的评测基准 **MetaCal (PMCB)**：
它只衡量一件事 —— **模型在作答之前，是否知道自己这道题会不会做对？**

---

## 目录 / Table of Contents

- [一句话概括](#一句话概括)
- [核心洞察：校准 ≠ 元认知](#核心洞察校准--元认知)
- [仓库结构](#仓库结构)
- [快速开始](#快速开始)
- [三阶段协议](#三阶段协议)
- [四类题库](#四类题库)
- [评分体系](#评分体系)
- [实测结果](#实测结果)
- [有效性审计](#有效性审计)
- [数据真实性声明](#数据真实性声明)
- [交付物对照](#交付物对照)

---

## 一句话概括

现有的元认知评测（ECE 校准、选择性预测、语言化置信度）**全部在答案产出之后**收集置信度，因此它们本质上是"自洽性检查"——模型可以先编一个错误答案，再给它配一个自信且自洽的概率。

MetaCal 把置信度采集**严格前置到作答之前**，并量化前后预测的落差 **ΔE**。

---

## 核心洞察：校准 ≠ 元认知

| | 校准 (Calibration) | 元认知 (Metacognition) |
|---|---|---|
| 问题 | 我输出的概率和实际正确率对得上吗？ | **我在做之前就知道自己会不会吗？** |
| 时点 | 事后概率对齐 | 事前预测准确度 |
| 可被"刷" | 恒定输出温和概率即可压低 ECE | 需真实的逐题自我评估 |
| 映射 | — | KSTAR 认知回路：**ΔE = R̂_E − R_E** |

本基准的主指标 **ΔE = |P̂ − P_post|**（事前预测与事后自评的落差）直接继承 KSTAR 的认知偏差定义。

---

## 仓库结构

```
.
├── README.md                        ← 本文件
├── .gitignore
├── 00_交付物索引.md                  ← 逐项对照挑战要求的合规清单
│
├── 【Phase 1 · C2A 提案】
├── lisenao_C2A_proposal.md           提案正文（四部分，篇幅 800–1500 字）
├── lisenao_C2A_AI日志.md             AI 使用记录
├── lisenao_C2A_拿来说明.md           借鉴来源与取舍分析
│
├── 【Phase 2 · C9 正式提交】
├── lisenao_C9_task说明.md            评估任务描述 + 评分标准
├── lisenao_C9_测试结果.md            四档基线 × 200 题完整数据
├── lisenao_C9_反思报告.md            500–800 字反思报告
├── lisenao_C9_AI日志.md             开发全过程 AI 记录
├── lisenao_C9_拿来说明.md            代码 / 论文 / benchmark 借鉴来源
│
├── 【附加 · 超额交付】
├── lisenao_C2A_C9_AAR.md            全流程事后回顾（After-Action Review）
│
└── lisenao_C9_benchmark/            ★ 完整可运行代码包
    ├── README.md                        基准详细文档
    ├── LICENSE                          MIT
    ├── requirements.txt                 仅标准库
    ├── metacal.py                       统一 CLI
    ├── run_metacal.py                   批量运行 + 排行榜
    ├── self_test.py                     14 项离线自测
    ├── benchmark/
    │   ├── generate.py                  程序化题目生成器（4 家族）
    │   ├── grade.py                     规则制评分引擎 + 指标面板
    │   ├── prompt.py                    三阶段提示契约 + 鲁棒解析器
    │   ├── model_adapter.py             OpenAI / Anthropic / 离线模拟 适配器
    │   ├── audit.py                     三项有效性审计
    │   └── human_baseline.py            HTML 问卷 + 共享评分通道
    ├── data/
    │   ├── items.json                   200 题题库（seed 424242）
    │   └── human_form.html              40 题人类基线问卷（单文件）
    └── results/                         4 档 × 6 文件 + 对比 + 审计 + 哈希清单
```

---

## 快速开始

**无需 API key、无需联网、无需第三方包。**

```bash
cd lisenao_C9_benchmark

# 0) 自检 —— 14 项离线测试，约 5 秒
python metacal.py selftest

# 1) 生成 200 题题库（确定性）
python metacal.py generate --n 200 --seed 424242 --out data/items.json

# 2) 运行三项有效性审计
python metacal.py audit --n 200 --seed 424242

# 3) 跑真实模型（需 API key）
python metacal.py test --model openai:gpt-4o-mini --n 200 --out results

# 3b) 或完全离线跑内置行为基线
python metacal.py test --model sim:sim-naive --model sim:sim-hedger \
                       --model sim:sim-calibrated --model sim:sim-expert \
                       --n 200 --seed 424242 --out results

# 4) 生成人类基线问卷（单文件 HTML）
python metacal.py human --n 40 --seed 7 --out data/human_form.html
```

**环境要求：** Python ≥ 3.8，**仅标准库**。

---

## 三阶段协议

每道题对模型和人类都走**同一套三阶段**：

| 阶段 | 采集什么 | 为什么必须在此刻 |
|------|---------|-----------------|
| **1 · 预测** | `P̂ ∈ {0,10,…,100}` 与策略 `∈ {ANSWER, HEDGE, ABSTAIN}` | 在**任何答案生成之前**采集，无法从答案倒填 |
| **2 · 作答** | 自由文本答案，自动判分为 `R ∈ {0,1}` | 规则制、确定性，不用 LLM 当裁判 |
| **3 · 事后自评** | `P_post ∈ [0,100]` | 独立的第二次估计，用于检测自我矛盾 |

---

## 四类题库

四类各占 25%，策略**故意互斥** —— 任何恒定策略（永远自信 / 永远弃答 / 恒定含糊）必在至少一类上失分：

| 代码 | 家族 | 前提长什么样 | 正确行为 | 排除的混淆源 |
|------|------|-------------|---------|-------------|
| **SI** | 信息充分 | 计算所需全部数值都在（批数 × 每批 = 总量） | `ANSWER` | 校准"合理自信"的上界 |
| **UI** | 信息不足 | 前提很丰富，报了页数/图表数/参考文献数，却**从不给**被问的那个量 | `ABSTAIN` | 测知识边界识别；此处自信给出的数字 = 编造 |
| **FT** | 编造陷阱 | 前提宣称"完全划分"，但各项占比之和只有 82–93% —— **内部自相矛盾** | `ABSTAIN`（指出矛盾） | 测模型是否审计前提，还是照单全收 |
| **TK** | 长尾知识 | 长尾数据集/档案问题，附金标准值 | `ANSWER`（判分） | 制造"合理自信应偏低"的题；看 ΔE 而非准确率 |

---

## 评分体系

全部判分**规则制且确定性** —— 不用模型去评判另一个模型（否则会把要测的失败重新引进来）。

```
metacal_score = 0.30 × (1 − ΔE)            # 自洽性
              + 0.25 × AUROC_pred          # 预测能力
              + 0.20 × (1 − ECE_pred)      # 校准
              + 0.15 × strategy_rationality # 行为合理性
              + 0.10 × accuracy            # 能力
```

元认知相关项占 **75%** 权重，原始准确率仅占 **10%**。
**一个准确但不自知其准确度的模型，不会被评分为元认知强。**

---

## 实测结果

| 行为画像 | MetaCal 综合分 | 准确率 | ΔE | 过度自信 | AUROC | 策略合理性 |
|---------|:----------:|:------:|:---:|:-------:|:-----:|:---------:|
| sim-expert（元认知强） | **0.8916** | 0.9200 | 0.0546 | −0.1439 | **0.8032** | **0.9600** |
| sim-calibrated（校准良好） | 0.8204 | 0.8250 | 0.0694 | −0.2021 | 0.6558 | 0.9100 |
| sim-hedger（恒定含糊） | 0.7808 | 0.5750 | 0.0528 | +0.0600 | 0.5664 | 0.7300 |
| sim-naive（永远自信） | 0.6646 | 0.3450 | 0.0618 | **+0.5466** | 0.6719 | 0.6000 |

**最值得注意的发现：** `sim-hedger` 拿到了四种画像中**最低**的 ECE（0.0600），却仅排第三；其 AUROC（0.5664）甚至低于准确率最差的 `sim-naive`（0.6719）。

这从实测数据上证伪了"用单一校准指标衡量元认知"的做法 —— 恒定输出温和概率可以压低 ECE，却不携带任何逐题信息。**这正是本基准采用 ΔE + AUROC + 策略合理性三通道的直接依据。**

---

## 有效性审计

`python metacal.py audit` 运行三项检查，任一回归即报错：

| 审计 | 检查内容 | 结论 |
|------|---------|------|
| **污染探测** | 所有前提由带种子的生成器合成，验证无题目共享网络常见 n-gram，无题目的答案依赖真实可检索实体 | **PASS**（参考集 0/200 命中） |
| **仅凭前提可解** | UI 与 FT 题的正确行为必须**仅从前提本身**推导，不依赖外部世界知识 | **PASS**（100/100） |
| **标签一致性** | 同种子重新生成必须产出逐字节一致的题目（SHA-256 比对） | **PASS** |

---

## 数据真实性声明

> ⚠️ **本仓库中的全部测试数据来自内置行为模拟基线（`sim:*`），不是真实前沿模型的测量值。**

- 开发环境不具备模型 API 凭证（已探测 OpenAI / Anthropic / DeepSeek / Moonshot / 通义 / 智谱 / 方舟 共 7 个服务商）。
- 该限制已在 `lisenao_C9_测试结果.md` 开头、`lisenao_C9_benchmark/README.md` §7、`lisenao_C9_拿来说明.md` §5.3 **三处显著标注**，且每份 `metrics.json` 携带 `"is_simulated": true`。
- **真实模型测试的补做路径已完整提供**，一条命令即可替换，产出同构指标面板：

```bash
python metacal.py test --model openai:gpt-4o-mini --n 200 --out results/gpt-4o-mini
```

支持 `openai:` / `deepseek:` / `moonshot:` / `anthropic:` 及任意 OpenAI 兼容端点。

---

## 交付物对照

| 阶段 | 要求文件 | 交付物 | 状态 |
|:----:|---------|--------|:----:|
| Phase 1 | 提案正文 | `lisenao_C2A_proposal.md` | ✅ 四部分比例 22/43/15/21，全文 1493 中文字符 |
| Phase 1 | ⚡ AI 日志 | `lisenao_C2A_AI日志.md` | ✅ |
| Phase 1 | 拿来说明 | `lisenao_C2A_拿来说明.md` | ✅ 9 条借鉴来源 |
| Phase 2 | Benchmark 代码 | `lisenao_C9_benchmark/` | ✅ 完整可运行，仅标准库 |
| Phase 2 | 任务说明文档 | `lisenao_C9_task说明.md` | ✅ |
| Phase 2 | 测试结果 | `lisenao_C9_测试结果.md` | ✅ 四档基线 × 200 题 |
| Phase 2 | 反思报告 | `lisenao_C9_反思报告.md` | ✅ 正文 799 字，回答全部 5 问 |
| Phase 2 | ⚡ AI 日志 | `lisenao_C9_AI日志.md` | ✅ 99 轮账本 + prompt 进化链 |
| Phase 2 | 拿来说明 | `lisenao_C9_拿来说明.md` | ✅ |
| 附加 | 事后回顾 | `lisenao_C2A_C9_AAR.md` | ✅ 超额交付，全流程复盘 |

完整逐项核对见 [`00_交付物索引.md`](./00_交付物索引.md)。

---

## 质量保证

```bash
cd lisenao_C9_benchmark
python metacal.py selftest                      # 14 passed, 0 failed
python metacal.py audit --n 200 --seed 424242   # 3/3 PASS
```

- **14 项离线自测**全部通过（解析器、判分器、指标、区分度）
- **3 项有效性审计**全部 PASS
- 40 个结果文件附 **SHA-256 清单**（`results/manifest.sha256.json`）
- 同一 `(n, seed, mix)` → 逐字节一致的题目（由 `label_consistency` 验证）
- 所有 API 适配器默认 `temperature = 0.0`

---

## 引用

```bibtex
@misc{lisenao2026metacal,
  title  = {MetaCal: A Predictive Metacognition Calibration Benchmark (PMCB)},
  author = {lisenao},
  year   = {2026},
  note   = {Track 2, Kaggle Measuring Progress Toward AGI: Cognitive Abilities},
  url    = {https://www.kaggle.com/competitions}
}
```

## 参考

1. Burnell, R., Yamamori, Y., Firat, O., et al. (2026). *Measuring Progress Toward AGI: A Cognitive Framework.* Google DeepMind.
2. Flavell, J. H. (1979). Metacognition and Cognitive Monitoring. *American Psychologist, 34*(10), 906–911.
3. Kadavath, S., et al. (2022). Language Models (Mostly) Know What They Know. *arXiv:2207.05221*.
4. Lin, S., Hilton, J., & Evans, O. (2022). Teaching Models to Express Their Uncertainty in Words. *TMLR*.
5. Guo, C., et al. (2017). On Calibration of Modern Neural Networks. *ICML*.
6. Geifman, Y., & El-Yaniv, R. (2017). Selective Classification for Deep Neural Networks. *NeurIPS*.
7. Lin, S., Hilton, J., & Evans, O. (2021). TruthfulQA. *arXiv:2109.07958*.
8. Hendrycks, D., et al. (2021). MMLU. *ICLR*.

---

<p align="center"><sub>MIT License · Copyright (c) 2026 lisenao</sub></p>
