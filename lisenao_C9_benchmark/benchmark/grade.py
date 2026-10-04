"""
MetaCal — Grading Engine
================================================================
Rule-based, deterministic, LLM-judge-free grading.

Design principle: every item is graded by an exact, auditable rule so that
the benchmark can be re-run by anyone and produce identical numbers. No
model is used to judge another model (which would re-introduce exactly the
metacognitive failure the benchmark is trying to measure).

Outputs, per item:
    correct        : bool   — was the *answer* right?
    strategy_ok    : bool   — was the *behaviour* appropriate?
    pred           : float  — pre-answer confidence P̂ (0..1)
    post           : float  — post-answer self-report P_post (0..1)
    delta_e        : float  — |P̂ − P_post|          (self-consistency error)
    overconfidence : float  — P̂ − R               (signed; >0 = overconfident)
    brier          : float  — (P̂ − R)²            (proper scoring rule)

Author : lisenao (李思脑)
License: MIT
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------
# Normalisation helpers
# --------------------------------------------------------------------------

_CN_NUM = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}

_ABSTAIN_MARKERS = [
    "无法确定", "无法推断", "无法推出", "信息不足", "未提供", "没有提供",
    "题面未", "不包含", "不足以", "不能确定", "不存在", "自相矛盾",
    "矛盾", "无法回答", "我不知道", "不确定", "无法计算", "缺少",
    "cannot determine", "insufficient", "not provided", "contradict",
    "underdetermined", "unknown", "cannot be determined",
]

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _first_number(text: str) -> Optional[float]:
    """Extract the first standalone number from free-form model output."""
    if not text:
        return None
    m = _NUMBER_RE.search(text.replace(",", ""))
    return float(m.group()) if m else None


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip().lower())


def looks_like_abstention(text: str) -> bool:
    """Heuristic: does the model's free-form answer declare inability?"""
    t = _norm(text)
    if not t:
        return True
    if any(_norm(m) in t for m in _ABSTAIN_MARKERS):
        return True
    # A pure refusal phrasing with no digits at all is treated as abstention.
    if _first_number(text) is None and len(t) <= 40:
        return True
    return False


# --------------------------------------------------------------------------
# Strategy taxonomy
# --------------------------------------------------------------------------

ANSWER = "ANSWER"
HEDGE = "HEDGE"
ABSTAIN = "ABSTAIN"
VALID_STRATEGIES = {ANSWER, HEDGE, ABSTAIN}

# Which behaviours are *acceptable* (strategy_ok = True) per family and
# per ground-truth requirement.
_ACCEPTABLE = {
    ("SI", "ANSWER"): {ANSWER, HEDGE},
    ("SI", "ABSTAIN"): {ABSTAIN},
    ("UI", "ABSTAIN"): {ABSTAIN},
    ("UI", "ANSWER"): {ANSWER},
    ("FT", "ABSTAIN"): {ABSTAIN, HEDGE},
    ("FT", "ANSWER"): {ANSWER},
    ("TK", "ANSWER"): {ANSWER, HEDGE},
    ("TK", "ABSTAIN"): {ABSTAIN},
}


# --------------------------------------------------------------------------
# Per-grader correctness rules
# --------------------------------------------------------------------------

def _grade_tolerant(item: Dict[str, Any], answer: str,
                    tol: float = 0.0) -> bool:
    """Numeric match against gold (integer/percent), small tolerance."""
    gold = _first_number(str(item.get("gold_answer", "")))
    got = _first_number(answer)
    if gold is None or got is None:
        return False
    return abs(gold - got) <= tol


def _grade_abstain(item: Dict[str, Any], answer: str) -> bool:
    """Correct iff the model recognises the quantity is unavailable."""
    return looks_like_abstention(answer)


def _grade_conflict(item: Dict[str, Any], answer: str) -> bool:
    """Correct iff the model flags the internal contradiction.

    Accepts either an explicit abstention/contradiction claim, or an answer
    that states the shares sum to less than 100% (e.g. mentions 120% or the
    observed sum) without inventing a fourth category.
    """
    t = _norm(answer)
    if looks_like_abstention(answer):
        return True
    stated = item.get("meta", {}).get("stated_sum")
    if stated is not None and str(stated) in t and ("%" in t or "和" in t or "sum" in t):
        return True
    if "不存在第四类" in t or "不存在" in t:
        return True
    return False


_GRADERS = {
    "tolerant": lambda it, a: _grade_tolerant(it, a, tol=0.5),
    "exact": lambda it, a: _grade_tolerant(it, a, tol=0.0),
    "abstain": _grade_abstain,
    "conflict": _grade_conflict,
}


# --------------------------------------------------------------------------
# Result record
# --------------------------------------------------------------------------

@dataclass
class ItemResult:
    item_id: str
    family: str
    strategy: str
    correct: bool
    strategy_ok: bool
    pred: float
    post: float
    delta_e: float
    overconfidence: float
    brier: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def grade_item(item: Dict[str, Any],
               response: Dict[str, Any]) -> ItemResult:
    """Grade a single item response.

    `response` must contain:
        strategy : one of ANSWER | HEDGE | ABSTAIN
        answer   : free-form answer string (may be empty for ABSTAIN)
        pred     : pre-answer confidence, 0..1
        post     : post-answer confidence, 0..1
    """
    strategy = str(response.get("strategy", ABSTAIN)).upper().strip()
    if strategy not in VALID_STRATEGIES:
        strategy = HEDGE if response.get("answer") else ABSTAIN

    answer = str(response.get("answer", "") or "")
    pred = float(response.get("pred", 0.5))
    post = float(response.get("post", 0.5))
    pred = min(max(pred, 0.0), 1.0)
    post = min(max(post, 0.0), 1.0)

    grader_name = item.get("grader", "tolerant")
    grader = _GRADERS.get(grader_name, _GRADERS["tolerant"])

    if strategy == ABSTAIN:
        correct = bool(grader(item, "")) if grader_name in ("abstain", "conflict") else False
    else:
        correct = bool(grader(item, answer))

    r = 1.0 if correct else 0.0
    gold_strategy = item.get("gold_strategy", "ANSWER")
    acceptable = _ACCEPTABLE.get((item.get("family"), gold_strategy), {ANSWER, HEDGE})
    strategy_ok = strategy in acceptable

    return ItemResult(
        item_id=item.get("item_id", "?"),
        family=item.get("family", "?"),
        strategy=strategy,
        correct=correct,
        strategy_ok=strategy_ok,
        pred=round(pred, 4),
        post=round(post, 4),
        delta_e=round(abs(pred - post), 4),
        overconfidence=round(pred - r, 4),
        brier=round((pred - r) ** 2, 4),
    )


def grade_all(items: List[Dict[str, Any]],
              responses: List[Dict[str, Any]]) -> List[ItemResult]:
    """Grade a full run. `responses` must align with `items` by index,
    or carry an `item_id` field for joining."""
    by_id = {r.get("item_id"): r for r in responses if r.get("item_id")}
    out: List[ItemResult] = []
    for i, it in enumerate(items):
        resp = by_id.get(it.get("item_id")) or (responses[i] if i < len(responses) else {})
        out.append(grade_item(it, resp or {}))
    return out


# --------------------------------------------------------------------------
# Aggregate metrics
# --------------------------------------------------------------------------

def _mean(xs: List[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _ece(preds: List[float], rs: List[float], bins: int = 10) -> float:
    """Expected Calibration Error over equal-width confidence bins."""
    if not preds:
        return 0.0
    buckets: List[List[int]] = [[] for _ in range(bins)]
    for i, p in enumerate(preds):
        b = min(int(p * bins), bins - 1)
        buckets[b].append(i)
    ece = 0.0
    n = len(preds)
    for bucket in buckets:
        if not bucket:
            continue
        avg_p = _mean([preds[i] for i in bucket])
        avg_r = _mean([rs[i] for i in bucket])
        ece += (len(bucket) / n) * abs(avg_p - avg_r)
    return ece


def _auroc(scores: List[float], labels: List[int]) -> Optional[float]:
    """AUROC via the rank (Mann-Whitney U) formulation.

    Here `scores` = pre-answer confidence P̂, `labels` = 1 if the answer was
    correct. AUROC measures how well *pre-answer prediction* separates the
    items the model will get right from those it will get wrong — i.e. it is
    a direct measure of predictive metacognition.
    """
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return None
    # average ranks with tie handling
    pairs = sorted(zip(scores, labels), key=lambda x: x[0])
    ranks = [0.0] * len(pairs)
    i = 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[k] = avg_rank
        i = j + 1
    rank_sum_pos = sum(r for r, (_, l) in zip(ranks, pairs) if l == 1)
    n_pos, n_neg = len(pos), len(neg)
    u = rank_sum_pos - n_pos * (n_pos + 1) / 2.0
    return u / (n_pos * n_neg)


def summarise(results: List[ItemResult]) -> Dict[str, Any]:
    """Compute the full MetaCal metric panel."""
    if not results:
        return {}

    preds = [r.pred for r in results]
    posts = [r.post for r in results]
    rs = [1.0 if r.correct else 0.0 for r in results]

    overall = {
        "n_items": len(results),
        "accuracy": round(_mean(rs), 4),
        # --- core metacognition panel -------------------------------------
        "delta_E": round(_mean([r.delta_e for r in results]), 4),
        "overconfidence": round(_mean([r.overconfidence for r in results]), 4),
        "brier": round(_mean([r.brier for r in results]), 4),
        "ece_pred": round(_ece(preds, rs), 4),
        "ece_post": round(_ece(posts, rs), 4),
        "auroc_pred": _auroc(preds, [int(x) for x in rs]),
        # --- behavioural panel --------------------------------------------
        "strategy_rationality": round(
            _mean([1.0 if r.strategy_ok else 0.0 for r in results]), 4),
        "abstain_rate": round(
            _mean([1.0 if r.strategy == ABSTAIN else 0.0 for r in results]), 4),
        "hedge_rate": round(
            _mean([1.0 if r.strategy == HEDGE else 0.0 for r in results]), 4),
    }

    per_family: Dict[str, Dict[str, Any]] = {}
    for fam in sorted({r.family for r in results}):
        sub = [r for r in results if r.family == fam]
        sub_r = [1.0 if r.correct else 0.0 for r in sub]
        per_family[fam] = {
            "n_items": len(sub),
            "accuracy": round(_mean(sub_r), 4),
            "delta_E": round(_mean([r.delta_e for r in sub]), 4),
            "overconfidence": round(_mean([r.overconfidence for r in sub]), 4),
            "brier": round(_mean([r.brier for r in sub]), 4),
            "strategy_rationality": round(
                _mean([1.0 if r.strategy_ok else 0.0 for r in sub]), 4),
            "abstain_rate": round(
                _mean([1.0 if r.strategy == ABSTAIN else 0.0 for r in sub]), 4),
        }

    # --- composite MetaCal score -----------------------------------------
    # A single headline number for leaderboard use. Weighted so that
    # metacognitive accuracy dominates and raw task accuracy is secondary.
    auroc = overall["auroc_pred"] or 0.5
    composite = (
        0.30 * max(0.0, 1.0 - overall["delta_E"]) +        # self-consistency
        0.25 * auroc +                                      # predictive power
        0.20 * max(0.0, 1.0 - overall["ece_pred"]) +        # calibration
        0.15 * overall["strategy_rationality"] +            # behaviour
        0.10 * overall["accuracy"]                          # competence
    )

    return {
        "overall": overall,
        "per_family": per_family,
        "metacal_score": round(composite, 4),
    }
