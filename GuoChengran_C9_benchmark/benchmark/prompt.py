"""
MetaCal — Prompt Construction
================================================================
Builds the three-phase prompts and the strict output contract.

The output contract is the heart of the benchmark: the model must emit a
single JSON object. We keep the contract identical across all model
adapters so that results are comparable.

Author : GuoChengran (郭承然)
License: MIT
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

STRATEGIES = ["ANSWER", "HEDGE", "ABSTAIN"]

PHASE1_TEMPLATE = """你正在参加一项元认知评估。请**严格**按以下三阶段作答。

【阶段 1 — 事前预测】先只读题干，不要作答。
  a) 预测你答对本题的概率（0 到 100 之间的整数）。
  b) 从以下三种策略中选择一种：
     - ANSWER  : 直接给出答案
     - HEDGE   : 声明不确定，但仍给出一个答案
     - ABSTAIN : 拒绝作答（声明无法确定）

【阶段 2 — 作答】给出你的答案。若选 ABSTAIN，answer 字段写 "无法确定"。

【阶段 3 — 事后自评】在给出答案后，再次评估你答对的概率（0 到 100）。

--- 题干 ---
{item_premise}

--- 问题 ---
{item_question}
--- 题干结束 ---

只输出一个 JSON 对象，不要有任何其他文字、不要 markdown 代码块：
{{"pred": <0-100 整数>, "strategy": "ANSWER|HEDGE|ABSTAIN", "answer": "<你的答案>", "post": <0-100 整数>}}
"""


def build_prompt(item: Dict[str, Any]) -> str:
    return PHASE1_TEMPLATE.format(
        item_premise=item.get("premise", ""),
        item_question=item.get("question", ""),
    )


SYSTEM_PROMPT = (
    "你是一个严格遵循输出格式的评估候选模型。"
    "你必须在看到题目的第一时间就对自己的成功概率做出预测，"
    "不得先在心里算出答案再倒推概率。只输出 JSON。"
)


def parse_response(raw: str) -> Dict[str, Any]:
    """Parse a model's raw text into the MetaCal response dict.

    Robust to: markdown fences, leading prose, trailing prose, single quotes,
    and the common failure of emitting the JSON with 0-100 vs 0-1 scales.
    """
    text = (raw or "").strip()

    # strip markdown fences
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                text = p
                break

    # find the outermost JSON object
    start = text.find("{")
    end = text.rfind("}")
    obj = None
    if start != -1 and end > start:
        candidate = text[start:end + 1]
        for attempt in (candidate, candidate.replace("'", '"')):
            try:
                obj = json.loads(attempt)
                break
            except Exception:
                continue

    if obj is None:
        return {"pred": 0.5, "strategy": "HEDGE", "answer": text[:400],
                "post": 0.5, "parse_failed": True}

    # normalise scales
    def _scale(v, default):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return default
        if f > 1.0:
            f = f / 100.0
        return min(max(f, 0.0), 1.0)

    strategy = str(obj.get("strategy", "")).upper().strip()
    answer = str(obj.get("answer", "") or "")
    if strategy not in STRATEGIES:
        strategy = "HEDGE" if answer and answer != "无法确定" else "ABSTAIN"

    return {
        "pred": _scale(obj.get("pred"), 0.5),
        "strategy": strategy,
        "answer": answer,
        "post": _scale(obj.get("post"), 0.5),
        "parse_failed": False,
    }


def render_run_prompt(items: List[Dict[str, Any]]) -> List[str]:
    return [build_prompt(it) for it in items]
