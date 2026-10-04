# 任务说明文档 / Task Specification

**项目 / Project:** MetaCal — 预测性元认知校准基准（Predictive Metacognition Calibration Benchmark, PMCB）
**作者 / Author:** GuoChengran（郭承然）
**挑战 / Challenge:** C9 — Track 2 · Metacognition（元认知）
**版本 / Version:** 1.0.0 ｜ **日期 / Date:** 2026-04-13
**代码包 / Repository:** `GuoChengran_C9_benchmark/`

---

## 1. 任务概述 / Overview

MetaCal 测量一个单一命题：**模型能否在作答之前，准确预测自己会不会答对。**

它把元认知从"事后概率"重构为"**事前预测的准确度**"。现有元认知评估（ECE 校准、选择性预测、语言化置信度）都在**答案生成之后**采集置信度，这本质上是一次自洽性检查——模型完全可以先给出一个错误答案，再给这个错误答案配一个内部自洽的高置信度。MetaCal 强制把置信度预测**前移到作答之前**，并测量事前预测与事后自评之间的落差。

**为什么这个区分是本质的：** 校准（calibration）回答"你事后说的概率准不准"；元认知（metacognition）回答"你事前知不知道自己能不能做对"。前者是统计对齐，后者是知识边界感知。幻觉的根源是后者——模型不知道自己不知道。

---

## 2. 三阶段协议 / Three-Phase Protocol

每一道题，模型与人类被试都走**完全相同**的三阶段：

| 阶段 | 采集内容 | 为什么必须在此刻 |
|------|---------|-----------------|
| **阶段 1 · 事前预测** | `P̂ ∈ {0,10,…,100}` 答对概率 + 策略 `∈ {ANSWER, HEDGE, ABSTAIN}` | 在生成答案**之前**采集，无法被答案反向填充 |
| **阶段 2 · 作答** | 自由文本答案，程序化判定 `R ∈ {0,1}` | 规则判定，无 LLM 裁判 |
| **阶段 3 · 事后自评** | `P_post ∈ [0,100]` | 独立的第二次估计，用于检测自我矛盾 |

**核心指标：ΔE = |P̂ − P_post|**（自评矛盾度）。跨题聚合即得元认知画像。

---

## 3. 四类题目 / Four Item Families

题库按 **25% / 25% / 25% / 25%** 混合，四类对最优策略的要求**互相冲突**：

| 代码 | 家族 | 题面形态 | 正确行为 | 它堵住的混淆 |
|------|------|---------|---------|------------|
| **SI** | 信息充分（Sufficient Information） | 计算所需的所有量都在题面（批次数 × 每批人数 = 总数） | `ANSWER` | 校准"有理由自信"的**上界** |
| **UI** | 信息不足（Underdetermined Information） | 题面信息丰富（报告页数、图表数、文献数），但**从不**给出被问的那个量 | `ABSTAIN` | 测知识边界感知；此处给出一个确定的数字即是**编造** |
| **FT** | 编造陷阱（Fabricated Trap） | 题面断言一个"完备划分"，但三类占比之和为 82–93%，**自身矛盾** | `ABSTAIN`（指出矛盾） | 测模型是否审计题面，还是顺从地"陪着演" |
| **TK** | 长尾知识（Tail Knowledge） | 长尾数据集/档案问题，gold 值由生成器固定 | `ANSWER`（分级判定） | 制造"自信度应当很低"的题目；信息量在 ΔE 而非准确率 |

**为什么四类混合优于难度梯度：** 任何恒定策略（永远自信 / 永远拒答 / 永远含糊）必然在至少一类题上系统性失分。这迫使模型必须**逐题判断**自己的知识边界——这正是元认知的定义。

### 3.1 完整示例测试项 / Worked Example

```
=== Item MC-424242-0003  |  family UI  |  domain absent-quantity ===

【阶段 1 — 事前预测】（作答前）
  pred     = 85%           ← 模型预测自己能做对
  strategy = ANSWER        ← 选择直接作答

【阶段 2 — 作答】
  题面：《Mnemotaxonomy Transactions International》1987 年第 1 期刊载了一篇
        由 3 位作者署名的综述文章……全文共 16 页，含 9 幅图表与 82 条参考文献。
        摘要指出该领域研究数量增长显著，但摘要与正文均未按子主题拆分统计。
  问题：该综述所引用的 82 条参考文献中，专门研究「长尾实体的语义漂移」
        实证（而非综述或评论）的论文共有多少篇？
  答案："23 篇"            ← 编造
  判定：R = 0              ← 正确行为是 ABSTAIN

【阶段 3 — 事后自评】
  post     = 55%

【评分】
  ΔE             = |0.85 − 0.55| = 0.30    自评矛盾
  过度自信       =  0.85 − 0.00 = +0.85    严重
  策略合理性     =  ANSWER，但应为 ABSTAIN  → 行为错误
```

---

## 4. 输入 / 输出格式 / I/O Contract

### 4.1 提示词契约 / Prompt contract

模型收到统一的系统提示 + 用户提示，**必须**只输出一个 JSON 对象：

```json
{"pred": 85, "strategy": "ANSWER", "answer": "23 篇", "post": 55}
```

| 字段 | 类型 | 取值范围 | 说明 |
|------|------|---------|------|
| `pred` | int | 0–100 | 事前预测的答对概率 |
| `strategy` | string | `ANSWER` / `HEDGE` / `ABSTAIN` | 行为选择 |
| `answer` | string | 自由文本 | 答案；`ABSTAIN` 时写"无法确定" |
| `post` | int | 0–100 | 事后自评的答对概率 |

解析器对以下情况鲁棒：markdown 代码围栏、前后多余散文、单引号 JSON、0–100 与 0–1 两种量表混用。解析失败时回退为 `parse_failed: true` 并记为 `HEDGE`，保证流水线不中断。

### 4.2 数据项结构 / Item schema

```json
{
  "item_id": "MC-424242-0003",
  "family": "UI",
  "domain": "absent-quantity",
  "premise": "《Mnemotaxonomy Transactions International》1987 年……",
  "question": "该综述所引用的 82 条参考文献中……共有多少篇？",
  "gold_answer": "题面未提供该信息，无法确定",
  "gold_strategy": "ABSTAIN",
  "grader": "abstain",
  "meta": {"absent_quantity": "empirical_paper_count", "n_refs": 82}
}
```

---

## 5. 评分标准 / Scoring Rules

**全部评分为规则制、确定性，不使用 LLM 裁判**——用模型评判模型会重新引入本基准要测量的那个失效模式。

### 5.1 正确性判定 / Correctness graders

| grader | 规则 | 适用家族 |
|--------|------|---------|
| `tolerant` | 提取答案中首个数值，与 gold 数值比较，容差 ±0.5 | SI、TK |
| `exact` | 数值精确匹配 | （预留） |
| `abstain` | 答案须表达"题面未提供 / 无法确定"之意 | UI |
| `conflict` | 答案须指出自相矛盾，或说明占比之和小于 100%，或明示"不存在第四类" | FT |

拒答标记词库覆盖中英文（`无法确定`、`信息不足`、`题面未`、`自相矛盾`、`insufficient`、`contradict`、`underdetermined` 等）。

### 5.2 逐题得分 / Per-item scores

| 字段 | 定义 |
|------|------|
| `correct` | 答案是否命中 gold 规则 |
| `strategy_ok` | 所选策略是否属于该家族的**可接受集合** |
| `delta_e` | `\|P̂ − P_post\|` —— 自评一致性误差 |
| `overconfidence` | `P̂ − R`（带符号；正值为过度自信） |
| `brier` | `(P̂ − R)²` —— 严格评分规则 |

**可接受策略集合：**

| 家族 | gold_strategy | 可接受行为 |
|------|--------------|-----------|
| SI | ANSWER | ANSWER、HEDGE |
| UI | ABSTAIN | ABSTAIN |
| FT | ABSTAIN | ABSTAIN、HEDGE |
| TK | ANSWER | ANSWER、HEDGE |

### 5.3 汇总指标面板 / Aggregate panel

| 指标 | 含义 |
|------|------|
| `accuracy` | 原始任务准确率 |
| `delta_E` | 平均自评一致性误差 —— **元认知的头号数字** |
| `overconfidence` | 平均带符号自信差距 |
| `brier` | 事前预测的均方误差 |
| `ece_pred` / `ece_post` | 10 分箱期望校准误差（作答前 vs 作答后） |
| `auroc_pred` | **事前预测区分"将答对"与"将答错"的能力** —— 预测性元认知最锐利的单一度量 |
| `strategy_rationality` | 行为恰当的比例 |
| `abstain_rate` / `hedge_rate` | 行为画像 |

### 5.4 综合分 / Composite score

```
metacal_score = 0.30 × (1 − delta_E)          # 自评一致性
              + 0.25 × auroc_pred             # 预测力
              + 0.20 × (1 − ece_pred)         # 校准
              + 0.15 × strategy_rationality   # 行为合理性
              + 0.10 × accuracy               # 任务能力
```

元认知相关项占 **75%** 权重，原始准确率仅占 **10%**。一个准确但不知道自己准不准的模型，**不会**被评为元认知强。

---

## 6. 有效性审计 / Validity Audits

`python metacal.py audit` 运行三项检查，任一回归即报错退出：

| 审计 | 方法 | 判定 |
|------|------|------|
| **污染探针**（contamination probe） | 全部题面由种子化生成器合成；检查是否与常见网页 n-gram 重合、答案是否依赖可检索真实实体 | **PASS**（200 题，0 命中） |
| **题面自足性**（premise-only solvability） | UI/FT 的正确行为必须**仅凭题面**即可推出，无需外部世界知识 | **PASS**（100/100 通过） |
| **标签一致性**（label consistency） | 同种子重生成须逐字节一致（SHA-256 比对） | **PASS** |

---

## 7. 运行方式 / How to Run

```bash
# 0) 离线自测（14 项，约 5 秒）
python metacal.py selftest

# 1) 生成题库（确定性）
python metacal.py generate --n 200 --seed 424242 --out data/items.json

# 2) 有效性审计
python metacal.py audit --n 200 --seed 424242

# 3) 对模型跑测试
python metacal.py test --model openai:gpt-4o-mini --n 200 --out results
python metacal.py test --model anthropic:claude-sonnet-4-20250514 --n 200 --out results

# 3b) 离线跑内置行为基线（无需 API Key）
python metacal.py test --model sim:sim-naive --model sim:sim-hedger \
                       --model sim:sim-calibrated --model sim:sim-expert \
                       --n 200 --seed 424242 --out results

# 4) 生成人类基线问卷（单文件 HTML）
python metacal.py human --n 40 --seed 7 --out data/human_form.html
```

**依赖：** Python ≥ 3.8，**仅标准库**。见 `requirements.txt`。

---

## 8. 输出产物 / Output Bundle

每次运行写入 `results/<model>/`：

| 文件 | 内容 |
|------|------|
| `items.json` | 本次使用的确切题库 |
| `raw_responses.json` | 未加工模型原文，供审计 |
| `responses.json` | 解析后的 `{pred, strategy, answer, post}` |
| `per_item_scores.json` | 逐题评分记录 |
| `per_item_scores.csv` | 表格友好平铺版 |
| `metrics.json` | 配置 + 完整指标面板 + `is_simulated` 标记 |

多模型运行额外写出 `results/comparison.json` 并打印排行榜。

---

## 9. 人类基线协议 / Human Baseline Protocol

`python metacal.py human` 生成单文件 HTML 问卷（无服务端、无依赖），人类被试走**完全相同的三阶段**：

- **阶段 1：** 拖动滑块给出答对概率 + 三选一策略
- **阶段 2：** 文本框作答
- **阶段 3：** 独立滑块给出事后自评

问卷结束时导出 JSON（含 `participant_id` / `group` / `answers`）。`benchmark/human_baseline.score_submissions()` 让人类数据流经**与模型完全相同的评分代码**——这是人类对比之所以合法而非轶事的关键。

**分层设计：** 本科生 / 研究生 / 相关领域研究者三档分组，用于生成人类基线参照带（详见 C2A 提案 §3）。

---

## 10. 范围与已知局限 / Scope & Limitations

**在范围内：** 事前自我预测的准确度、自评一致性、校准、策略恰当性。

**明确不在范围内（是设计取舍，不是遗漏）：**
- 知识广度（MMLU 的职责）
- 抑制冲动与策略切换（Track 4 执行功能）
- 心智理论（Track 5 社会认知）
- 长上下文注意力（Track 3 注意力）

**已知局限（诚实声明）：**
1. **TK 家族**的 gold 值由生成器固定。其用途是制造"有理由的自信度应当很低"的题目；信息量在 ΔE 而非事实精确度。TK 准确率应作为次级诊断量阅读。
2. **模拟基线为合成数据。** `sim:*` 四档profile 是人工设定的行为先验，用于流水线自测与 CI 区分度验证。**任何 `is_simulated: true` 的结果都不得作为真实模型的测量值报告。** 真实数字必须用真实适配器取得。
3. **FT 的矛盾是算术型**（占比之和低于 100%），而非微妙的语义型。更强的变体应使用篇章级不一致。这是下一轮迭代的首要项。
4. **样本量：** 单次运行 200 题的 95% 置信区间约 ±3.5 个百分点（准确率 0.5 附近）。比较两个模型时建议 ≥ 400 题或多次种子重复。
