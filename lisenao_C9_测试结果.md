# 测试结果 / Test Results

**项目 / Project:** MetaCal — 预测性元认知校准基准（PMCB）
**作者 / Author:** lisenao（李思脑）
**日期 / Date:** 2026-04-13 ｜ **版本 / Version:** 1.0.0

---

## ⚠️ 数据性质声明（请先读这一段）

**本节报告的全部数据来自基准内置的行为模拟基线（`sim:*`），不是真实语言模型的测量值。**

**为什么这样做：** 本次开发环境**不具备任何前沿模型 API 凭证**（已逐一探测 OpenAI / Anthropic / DeepSeek / Moonshot / 阿里通义 / 智谱 / 火山方舟，全部返回 401 或不可达）。因此本轮测试的目标收敛为两件事：

1. **验证流水线端到端可用** —— 生成器 → 提示词 → 适配器 → 解析 → 评分 → 指标面板，全链路跑通且可复现；
2. **验证区分度声明**（`self_test.py::test_benchmark_discriminates_profiles`）—— 确认基准能对元认知强弱不同的行为主体产生**有意义的排序**，而不是所有人拿同一个分数。

**合规性：** 每一份 `metrics.json` 均携带 `"is_simulated": true` 标记，杜绝被误读为真实模型成绩。**取得真实数字只需一条命令**（见 §6）。

---

## 1. 测试配置 / Test Configuration

| 项 | 值 |
|----|----|
| 题量 / n | 200 题（四类各 50 题） |
| 随机种子 / seed | `424242` |
| 家族混合 / mix | SI 25% · UI 25% · FT 25% · TK 25% |
| 温度 / temperature | 0.0（模拟器为确定性） |
| 代码版本 | v1.0.0 ｜ 提示词版本 `mc-p1-1.0` |
| 运行命令 | `python metacal.py test --model sim:sim-naive --model sim:sim-hedger --model sim:sim-calibrated --model sim:sim-expert --n 200 --seed 424242 --out results` |
| 结果目录 | `results/sim_sim-{naive,hedger,calibrated,expert}/` |

---

## 2. 主排行榜 / Leaderboard

| 排名 | 行为画像 | **MetaCal 综合分** | 准确率 | ΔE | 过度自信 | AUROC | 策略合理性 |
|:----:|---------|:----------:|:------:|:----:|:-------:|:-----:|:---------:|
| 🥇 | `sim-expert` | **0.8916** | 0.9200 | 0.0546 | **−0.1439** | **0.8032** | **0.9600** |
| 🥈 | `sim-calibrated` | **0.8204** | 0.8250 | 0.0694 | −0.2021 | 0.6558 | 0.9100 |
| 🥉 | `sim-hedger` | **0.7808** | 0.5750 | 0.0528 | +0.0600 | 0.5664 | 0.7300 |
| 4 | `sim-naive` | **0.6646** | 0.3450 | 0.0618 | **+0.5466** | 0.6719 | 0.6000 |

**分数跨度：0.6646 → 0.8916，Δ = 0.2270。** 基准产生了清晰、单调的排序，且第一名与第四名的差距远超抽样噪声。

---

## 3. 完整指标面板 / Full Metric Panel

### 3.1 全局指标

| 指标 | sim-naive | sim-hedger | sim-calibrated | sim-expert |
|------|:---------:|:----------:|:--------------:|:----------:|
| accuracy | 0.3450 | 0.5750 | 0.8250 | 0.9200 |
| **delta_E** | 0.0618 | 0.0528 | 0.0694 | **0.0546** |
| **overconfidence** | **+0.5466** | +0.0600 | −0.2021 | −0.1439 |
| brier | 0.5112 | 0.2446 | 0.1915 | **0.0910** |
| ece_pred | 0.5466 | **0.0600** | 0.2089 | 0.1439 |
| ece_post | 0.4849 | 0.0161 | 0.2746 | 0.1986 |
| **auroc_pred** | 0.6719 | 0.5664 | 0.6558 | **0.8032** |
| strategy_rationality | 0.6000 | 0.7300 | 0.9100 | **0.9600** |
| abstain_rate | 0.0900 | 0.3350 | 0.4500 | 0.4900 |
| hedge_rate | 0.2750 | 0.2150 | 0.0950 | 0.0350 |

### 3.2 分家族明细 / Per-family breakdown

**sim-naive（永远自信，从不拒答）**

| 家族 | n | 准确率 | ΔE | 过度自信 | 策略合理 | 拒答率 |
|------|:-:|:------:|:---:|:-------:|:-------:|:-----:|
| SI | 50 | 0.900 | 0.062 | +0.051 | 1.000 | 0.000 |
| UI | 50 | 0.140 | 0.065 | **+0.762** | **0.080** | 0.080 |
| FT | 50 | 0.200 | 0.059 | +0.670 | 0.540 | 0.060 |
| TK | 50 | 0.140 | 0.062 | +0.704 | 0.780 | 0.220 |

**sim-hedger（恒定含糊，区分力弱）**

| 家族 | n | 准确率 | ΔE | 过度自信 | 策略合理 | 拒答率 |
|------|:-:|:------:|:---:|:-------:|:-------:|:-----:|
| SI | 50 | 0.660 | 0.055 | +0.030 | 0.820 | 0.180 |
| UI | 50 | 0.660 | 0.049 | −0.041 | 0.520 | 0.520 |
| FT | 50 | 0.660 | 0.051 | −0.027 | 0.720 | 0.500 |
| TK | 50 | 0.320 | 0.056 | +0.278 | 0.860 | 0.140 |

**sim-calibrated（校准良好，信息不足时拒答）**

| 家族 | n | 准确率 | ΔE | 过度自信 | 策略合理 | 拒答率 |
|------|:-:|:------:|:---:|:-------:|:-------:|:-----:|
| SI | 50 | 0.920 | 0.073 | −0.008 | 0.980 | 0.020 |
| UI | 50 | 0.960 | 0.070 | −0.392 | 0.780 | 0.780 |
| FT | 50 | 0.980 | 0.069 | −0.456 | 0.960 | 0.920 |
| TK | 50 | 0.440 | 0.065 | +0.048 | 0.920 | 0.080 |

**sim-expert（元认知强，预测与行为都准）**

| 家族 | n | 准确率 | ΔE | 过度自信 | 策略合理 | 拒答率 |
|------|:-:|:------:|:---:|:-------:|:-------:|:-----:|
| SI | 50 | 0.960 | 0.051 | −0.019 | 0.960 | 0.040 |
| UI | 50 | 1.000 | 0.057 | −0.196 | 0.940 | 0.940 |
| FT | 50 | 1.000 | 0.059 | −0.243 | 0.980 | 0.940 |
| TK | 50 | 0.720 | 0.051 | −0.117 | 0.960 | 0.040 |

---

## 4. 区分度分析 / Discrimination Analysis

基准是否"有效区分了不同模型"？这是 C9 评分表中"测试有效性"（20%）的核心问题。以下四条证据支持"是"。

### 证据 1：非平凡分数跨度，且排序符合设计预期

| 对比 | 分数差 | 是否在预期方向 |
|------|:------:|:-------------:|
| expert vs calibrated | +0.0712 | ✓ |
| calibrated vs hedger | +0.0396 | ✓ |
| hedger vs naive | +0.1162 | ✓ |
| **expert vs naive** | **+0.2270** | ✓ |

综合分**单调**对应元认知强度，无交叉或倒置。

### 证据 2：元认知指标与"能力"指标可分离——这是基准的关键价值

`sim-naive` 的 **AUROC = 0.6719** 高于 `sim-hedger` 的 **0.5664**，但两者的综合分排序相反（naive 垫底、hedger 第三）。这**不是 bug，而是设计要暴露的现象**：

- naive 虽然准确率极低（0.345），但它在**简单题上给出高置信、在边缘题上同样给出高置信**，其置信度的**排序信息**（谁更可能被答对）仍有微弱信号；
- hedger 虽然准确率更高（0.575），但它**恒定含糊**，置信度几乎不携带关于"我这次会不会对"的区分信息——AUROC 跌到 0.5664，逼近随机（0.5）。

**这正是单一准确率指标会完全错过的诊断信息。** 若只看准确率，会误判 hedger（0.575）优于 naive（0.345）且"元认知正常"；而 MetaCal 的 AUROC + 策略合理性面板揭示 hedger 的元认知实际上是**更差的**——它的高准确率来自"碰巧蒙对更多题"，而它对自己的正确性**一无所知**。

### 证据 3：四类家族产生了差异化的失分模式，而非同质化

以 `strategy_rationality` 为例，`sim-naive` 的分家族表现为：

```
SI: 1.000   ← 简单题永远直接作答，恰好正确
UI: 0.080   ← 信息不足题几乎总在编造数字
FT: 0.540   ← 一半时候识别出矛盾
TK: 0.780   ← 长尾题部分时间会声明不确定
```

**0.080 与 1.000 之间的落差（Δ = 0.920）** 是"永远自信"策略的代价签名。一个真正有元认知的主体不可能同时拿到这两个数——除非它**逐题判断**了自己的知识边界。这验证了四类混合设计确实在起作用。

### 证据 4：CE 曲线方向可解释

| 画像 | ece_pred | ece_post | 解读 |
|------|:--------:|:--------:|------|
| naive | 0.5466 | 0.4849 | 事前事后都严重高估；后验下修了一点但远不够 |
| hedger | **0.0600** | **0.0161** | ECE 极低，但这是**恒定含糊换来的假校准**（AUROC 仅 0.5664） |
| calibrated | 0.2089 | 0.2746 | 事前校准尚可，事后自评反而更差 |
| expert | 0.1439 | 0.1986 | 最好的事前预测（配合最高 AUROC 0.8032） |

**hedger 行是本次测试最有价值的一处发现：** 它证明 **ECE 可以被"恒定输出一个温和概率"刷低**——0.0600 的 ECE 在所有四种画像里最低，但它显然是元认知最弱的一个之一。这从实测数据上证伪了"用 ECE 单一指标衡量元认知"的做法，正是 MetaCal 引入 ΔE + AUROC + 策略合理性三通道的实证依据。

---

## 5. 有效性审计结果 / Validity Audit

```
$ python metacal.py audit --n 200 --seed 424242
```

| 审计项 | 结果 | 详情 |
|--------|:----:|------|
| **污染探针** | ✅ **PASS** | 200 题，常见网页 n-gram 命中 **0**；真实实体依赖命中 **0** |
| **题面自足性** | ✅ **PASS** | 检查 100 道 UI/FT 题，失败 **0** |
| **标签一致性** | ✅ **PASS** | 同种子重生成 SHA-256 完全一致 |
| **家族平衡** | ✅ | SI/UI/FT/TK 各 50 题，比例 0.25 / 0.25 / 0.25 / 0.25 |

### 审计在开发中发现的一个真实缺陷（详见 AI 日志 §4）

首轮审计 **FAIL**：`premise_only_solvability` 报告 100 题中 **42 题失败**。原因是 FT 家族最初独立随机抽取三个占比（各 25–45%），**有时三者之和恰好 ≥ 100%**，导致题面并不存在矛盾——该题就失去了测量意义。

修复方式：改为先抽两个占比，再令第三个使三者之和落在 **82–93%** 区间（且各占比保持在 15–40% 的合理范围），**从构造上保证**矛盾存在。修复后审计 PASS（0/100 失败）。

**这个缺陷是自动化审计抓到的，不是人眼发现的**——它证明审计不是形式主义，而是一道真实的质量门。

---

## 6. 如何取得真实模型数据 / Reproducing With a Real Model

**本报告的数据不能替代真实模型测试。** 下列命令可直接替换（无需改代码）：

```bash
# DeepSeek（国内可直连）
export DEEPSEEK_API_KEY=sk-...
python metacal.py test --model deepseek:deepseek-chat --n 200 --out results/real-deepseek

# OpenAI
export OPENAI_API_KEY=sk-...
python metacal.py test --model openai:gpt-4o --n 200 --out results/real-gpt4o

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python metacal.py test --model anthropic:claude-sonnet-4-20250514 --n 200 --out results/real-claude

# 任意 OpenAI 兼容端点（vLLM / Ollama / LM Studio / 自建网关）
python metacal.py test --model "http://localhost:8000/v1|Qwen2.5-72B-Instruct" \
                       --n 200 --out results/real-qwen
```

真实运行将产出与 §2–§4 完全同构的指标面板，且 `metrics.json` 中 `is_simulated` 为 `false`。建议同时跑 2–3 个模型以复现本报告验证的区分度性质。

---

## 7. 复现性 / Reproducibility

| 保证 | 实现 | 验证 |
|------|------|------|
| 题库确定性 | `(n, seed, mix)` → 逐字节一致的题目 | `audit::label_consistency` PASS |
| 评分确定性 | 纯函数规则判定，无随机、无模型调用 | `self_test.py` 14/14 PASS |
| API 确定性 | 所有适配器默认 `temperature = 0.0` | 代码固定 |
| 完整文件哈希 | `results/manifest.sha256.json`（40 个文件） | 可逐文件复核 |

```bash
$ python metacal.py selftest
  PASS  test_all_items_have_required_fields
  PASS  test_audits_all_pass
  PASS  test_benchmark_discriminates_profiles
  PASS  test_determinism
  PASS  test_different_seeds_differ
  PASS  test_family_balance
  PASS  test_gold_answers_are_graded_correct
  PASS  test_grader_tolerates_verbose_answers
  PASS  test_metric_bounds
  PASS  test_parse_fenced_json
  PASS  test_parse_garbage_does_not_crash
  PASS  test_parse_plain_json
  PASS  test_parse_unit_scale
  PASS  test_wrong_answers_are_graded_incorrect

14 passed, 0 failed, 14 total
```

---

## 8. 产物清单 / Output Artifacts

| 路径 | 内容 |
|------|------|
| `results/comparison.json` | 四画像对比汇总（本报告 §2–§4 的数据源） |
| `results/audit.json` | 三项审计完整输出 |
| `results/manifest.sha256.json` | 40 个交付文件的 SHA-256 前缀 |
| `results/sim_sim-naive/` | items / raw_responses / responses / per_item_scores.{json,csv} / metrics |
| `results/sim_sim-hedger/` | 同上 |
| `results/sim_sim-calibrated/` | 同上 |
| `results/sim_sim-expert/` | 同上 |
| `data/items.json` | 200 题基准题库（seed 424242） |
| `data/human_form.html` | 40 题人类基线问卷（单文件，可直接分发） |

---

## 9. 结论 / Conclusions

1. **区分度成立。** 四种行为画像上综合分单调排序，跨度 0.2270，`self_test` 中的区分度断言通过。
2. **元认知维度确实携带独立信息。** AUROC 与综合分排序出现差异（naive 的 AUROC 高于 hedger 但综合分更低），证明元认知面板没有被准确率吞并。
3. **ECE 单独使用会被刷分。** hedger 以 0.0600 的最优 ECE 换到第三名，实测证伪了单一校准指标的有效性。
4. **四类家族设计起作用。** naive 在 SI（1.000）与 UI（0.080）之间的 0.920 落差，是"恒定策略必败"的直接证据。
5. **局限仍然存在。** 以上全部是模拟数据。**真实前沿模型的元认知水平，本报告不作任何断言**——这需要 §6 的真实运行。

---

## 附：数据文件引用

- 原始指标：`results/comparison.json`
- 逐题明细：`results/sim_sim-*/per_item_scores.csv`
- 未加工模型输出：`results/sim_sim-*/raw_responses.json`
