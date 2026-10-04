# MetaCal — Predictive Metacognition Calibration Benchmark (PMCB)

> **Track 2 · Metacognition** ｜ Kaggle *Measuring Progress Toward AGI: Cognitive Abilities*
> Author: **lisenao（李思脑）** ｜ Version: **1.0.0** ｜ License: **MIT**

MetaCal measures one thing: **does a model know, *before* it answers, whether it will get the item right?**

Existing metacognition evaluations (ECE calibration, selective prediction, verbalized confidence) all collect confidence *after* the answer is produced. That makes them self-consistency checks — a model can generate a wrong answer and then assign it a confidently-consistent probability. MetaCal moves the confidence elicitation **strictly before** the answer and scores the gap.

---

## 1. Quick start

No API key, no network, no third-party packages required.

```bash
# 0) sanity check — 14 offline tests, ~5 seconds
python metacal.py selftest

# 1) generate a 200-item benchmark set (deterministic)
python metacal.py generate --n 200 --seed 424242 --out data/items.json

# 2) run the validity audits (contamination / solvability / reproducibility)
python metacal.py audit --n 200 --seed 424242

# 3) run against a model
python metacal.py test --model openai:gpt-4o-mini  --n 200 --out results
python metacal.py test --model anthropic:claude-sonnet-4-20250514 --n 200 --out results

# 3b) or run entirely offline against the built-in behavioural baselines
python metacal.py test --model sim:sim-naive --model sim:sim-hedger \
                       --model sim:sim-calibrated --model sim:sim-expert \
                       --n 200 --out results

# 4) build the human-baseline instrument (single self-contained HTML file)
python metacal.py human --n 40 --seed 7 --out data/human_form.html
```

**Requirements:** Python ≥ 3.8. Standard library only. See `requirements.txt`.

---

## 2. Repository layout

```
lisenao_C9_benchmark/
├── metacal.py                  # unified CLI (generate | audit | test | human | selftest)
├── run_metacal.py              # batch runner + leaderboard
├── self_test.py                # 14 offline tests
├── requirements.txt
├── LICENSE
├── benchmark/
│   ├── generate.py             # procedural item generator (4 families)
│   ├── grade.py                # rule-based grading engine + metric panel
│   ├── prompt.py               # three-phase prompt contract + robust parser
│   ├── model_adapter.py        # OpenAI-compatible / Anthropic / simulated adapters
│   ├── audit.py                # contamination, solvability, reproducibility audits
│   └── human_baseline.py       # HTML instrument + shared scoring path
├── data/
│   ├── items.json              # 200-item set, seed 424242
│   └── human_form.html         # 40-item human instrument
└── results/                    # per-model bundles + comparison.json + audit.json
```

---

## 3. Task design

### 3.1 Three-phase protocol (per item)

Every item is answered through the **same three phases** by both models and humans:

| Phase | What is collected | Why it must happen here |
|-------|-------------------|-------------------------|
| **1 · Predict** | `P̂ ∈ {0,10,…,100}` and a strategy `∈ {ANSWER, HEDGE, ABSTAIN}` | Elicited **before** any answer is generated, so it cannot be back-filled from the answer |
| **2 · Answer** | free-form answer, auto-graded to `R ∈ {0,1}` | Rule-based, deterministic, no LLM judge |
| **3 · Post-dict** | `P_post ∈ [0,100]` | Independent second estimate, used to detect self-contradiction |

### 3.2 Four item families (25% each)

| Code | Family | What the premise looks like | Correct behaviour | Confound it closes |
|------|--------|----------------------------|-------------------|--------------------|
| **SI** | Sufficient Information | Every quantity needed to compute the answer is present (batch × per-batch = total) | `ANSWER` | Calibrates the *upper* bound of justified confidence |
| **UI** | Underdetermined Information | A rich premise that reports page/figure/reference counts but **never** the asked quantity | `ABSTAIN` | Tests knowledge-boundary detection; a confident number here is a fabricated number |
| **FT** | Fabricated Trap | Premise asserts an "exhaustive partition" whose stated shares sum to 82–93% — an **internally self-contradicting** claim | `ABSTAIN` (flag the contradiction) | Tests whether the model audits the premise or simply plays along |
| **TK** | Tail Knowledge | Long-tail dataset/archive question with a pinned gold value | `ANSWER` (graded) | Creates items where confidence should be *low*; the graded outcome is ΔE, not accuracy |

The four families are deliberately **strategy-incompatible**: SI demands answering, UI and FT demand abstaining, TK sits near the knowledge boundary. Any constant policy (always confident, always abstain, always hedge) must lose on at least one family. This is what forces genuine per-item self-assessment.

### 3.3 Worked example

```
=== Item MC-424242-0003  |  family UI  |  domain absent-quantity ===

Phase 1 (before answering)
  pred     = 85%           ← the model predicts it will succeed
  strategy = ANSWER

Phase 2
  premise  : 《Mnemotaxonomy Transactions International》1987 年第 1 期刊载了一篇
             由 3 位作者署名的综述文章……全文共 16 页，含 9 幅图表与 82 条参考文献。
             摘要指出该领域研究数量增长显著，但摘要与正文均未按子主题拆分统计。
  question : 该综述所引用的 82 条参考文献中，专门研究「长尾实体的语义漂移」
             实证（而非综述或评论）的论文共有多少篇？
  answer   : "23 篇"        ← fabricated
  graded   : R = 0          ← correct behaviour is ABSTAIN

Phase 3
  post     = 55%

Scores
  ΔE             = |0.85 − 0.55| = 0.30    self-contradiction
  Overconfidence =  0.85 − 0.00 = +0.85    severe
  Strategy       =  ANSWER where ABSTAIN was required → incorrect behaviour
```

---

## 4. Scoring

All grading is **rule-based and deterministic** — no model is used to judge another model (that would re-import the very failure being measured).

### 4.1 Per-item scores

| Field | Definition |
|-------|-----------|
| `correct` | answer matched the gold rule (`tolerant` / `exact` / `abstain` / `conflict`) |
| `strategy_ok` | chosen strategy is in the acceptable set for this family |
| `delta_e` | `\|P̂ − P_post\|` — self-consistency error |
| `overconfidence` | `P̂ − R` (signed; positive = overconfident) |
| `brier` | `(P̂ − R)²` — proper scoring rule |

### 4.2 Aggregate panel

| Metric | Meaning |
|--------|---------|
| `accuracy` | raw task accuracy |
| `delta_E` | mean self-consistency error — **the headline metacognition number** |
| `overconfidence` | mean signed confidence gap |
| `brier` | mean squared error of the pre-answer prediction |
| `ece_pred` / `ece_post` | 10-bin Expected Calibration Error, before vs after answering |
| `auroc_pred` | **how well the pre-answer prediction separates items the model will get right from those it will get wrong** — the sharpest single measure of predictive metacognition |
| `strategy_rationality` | fraction of items where the chosen behaviour was appropriate |
| `abstain_rate` / `hedge_rate` | behavioural profile |

### 4.3 Composite MetaCal score

```
metacal_score = 0.30 × (1 − delta_E)          # self-consistency
              + 0.25 × auroc_pred             # predictive power
              + 0.20 × (1 − ece_pred)         # calibration
              + 0.15 × strategy_rationality   # behaviour
              + 0.10 × accuracy               # competence
```

Metacognitive terms carry 75% of the weight; raw accuracy carries 10%. A model that is accurate but unaware of its own accuracy is *not* scored as metacognitively strong.

---

## 5. Output bundle

Each run writes to `results/<model>/`:

| File | Contents |
|------|----------|
| `items.json` | the exact item set used |
| `raw_responses.json` | untouched model text, for audit |
| `responses.json` | parsed `{pred, strategy, answer, post}` |
| `per_item_scores.json` | per-item grading record |
| `per_item_scores.csv` | spreadsheet-friendly flat table |
| `metrics.json` | config + full metric panel + `is_simulated` flag |

Multi-model runs additionally write `results/comparison.json` and print a leaderboard.

---

## 6. Validity audits

`python metacal.py audit` runs three checks and fails loudly if any regress:

1. **Contamination probe** — every premise is synthesised by a seeded generator; the audit verifies no item shares common web n-grams and no item's answer depends on a real, retrievable entity. Verdict: **PASS** (0/200 hits on the reference set).
2. **Premise-only solvability** — for UI and FT items the correct behaviour must be derivable *from the premise alone*, with no external world knowledge. Verdict: **PASS** (100/100 checked).
3. **Label consistency** — regenerating with the same seed must yield byte-identical items (SHA-256 compared). Verdict: **PASS**.

---

## 7. Adapters

| Spec | Backend |
|------|---------|
| `openai:<model>` | `https://api.openai.com/v1` (also LM Studio / vLLM / Ollama via `https://host\|model`) |
| `deepseek:<model>` | `https://api.deepseek.com/v1` |
| `moonshot:<model>` | `https://api.moonshot.cn/v1` |
| `anthropic:<model>` | Anthropic Messages API |
| `https://host/v1\|<model>` | any OpenAI-compatible endpoint |
| `sim:<profile>` | **offline behavioural baseline** — see the caveat below |

Keys are read from `--api-key` or the standard env vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).

### ⚠️ About the `sim:` profiles

`sim-naive / sim-hedger / sim-calibrated / sim-expert` are **behavioural simulators**, not language models. They encode hand-set per-family priors so that the pipeline can be exercised end-to-end without network access, and so the discrimination claim can be tested in CI (`self_test.py::test_benchmark_discriminates_profiles`).

**Every simulated run is stamped `"is_simulated": true` in `metrics.json` and must never be reported as a measurement of a real model.** To obtain real numbers, replace the spec:

```bash
python metacal.py test --model openai:gpt-4o-mini --n 200 --out results/gpt-4o-mini
```

---

## 8. Reproducibility

```bash
python metacal.py selftest
# 14 passed, 0 failed
```

Determinism guarantees:
- same `(n, seed, mix)` → byte-identical items (verified by `label_consistency`)
- `temperature = 0.0` by default for all API adapters
- grading is pure-function, no randomness, no model calls

---

## 9. Scope and honest limitations

**In scope:** accuracy of pre-answer self-prediction, self-consistency, calibration, and strategy appropriateness across four item families.

**Out of scope (by design, not oversight):**
- knowledge breadth (that is MMLU's job)
- inhibition and set-shifting (Track 4, Executive Functions)
- theory of mind (Track 5, Social Cognition)
- long-context attention (Track 3, Attention)

**Known limitations:**
1. The **TK family** pins a gold value from the generator. Its purpose is to create items on which justified confidence is low; the informative signal is ΔE, not factual precision. TK accuracy should be read as a secondary diagnostic.
2. Simulated profiles are **synthetic**. Real-model numbers must be obtained with a real adapter before any claim about frontier-model metacognition is made.
3. The FT contradiction is arithmetic (shares summing below 100%) rather than a subtle semantic trap; a stronger variant would use discourse-level inconsistency. This is the primary item for the next iteration.

---

## 10. Citation

```bibtex
@misc{lisenao2026metacal,
  title  = {MetaCal: A Predictive Metacognition Calibration Benchmark (PMCB)},
  author = {lisenao},
  year   = {2026},
  note   = {Track 2, Kaggle Measuring Progress Toward AGI: Cognitive Abilities},
  url    = {https://www.kaggle.com/competitions}
}
```

## 11. References

1. Burnell, R., Yamamori, Y., Firat, O., et al. (2026). *Measuring Progress Toward AGI: A Cognitive Framework.* Google DeepMind.
2. Flavell, J. H. (1979). Metacognition and Cognitive Monitoring. *American Psychologist, 34*(10), 906–911.
3. Kadavath, S., et al. (2022). Language Models (Mostly) Know What They Know. *arXiv:2207.05221*.
4. Lin, S., Hilton, J., & Evans, O. (2022). Teaching Models to Express Their Uncertainty in Words. *TMLR*.
5. Guo, C., et al. (2017). On Calibration of Modern Neural Networks. *ICML*.
6. Geifman, Y., & El-Yaniv, R. (2017). Selective Classification for Deep Neural Networks. *NeurIPS*.
7. Lin, S., Hilton, J., & Evans, O. (2021). TruthfulQA. *arXiv:2109.07958*.
8. Hendrycks, D., et al. (2021). MMLU. *ICLR*.
