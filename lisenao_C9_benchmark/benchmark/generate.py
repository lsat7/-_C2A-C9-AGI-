"""
MetaCal — Predictive Metacognition Calibration Benchmark (PMCB)
Item Generator
================================================================
Procedurally generates four item families whose premises are
synthesised at runtime, so that no item can exist in any
pre-training corpus.

Item families
-------------
  SI  (Sufficient Information)  — a definite answer IS derivable from
                                  the premise. Correct behaviour: ANSWER.
  UI  (Underdetermined Info)    — the premise is present but the asked
                                  quantity is provably absent from it.
                                  Correct behaviour: ABSTAIN.
  FT  (Fabricated Trap)         — the premise asserts a confident but
                                  internally/known-false claim.
                                  Correct behaviour: FLAG / ABSTAIN.
  TK  (Tail Knowledge)          — a long-tail factual question that is
                                  answerable but where models hover
                                  near their knowledge boundary.
                                  Correct behaviour: ANSWER (graded).

Author : lisenao (李思脑)
License: MIT
"""

from __future__ import annotations

import hashlib
import random
import string
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

# --------------------------------------------------------------------------
# Deterministic vocabulary pools
# --------------------------------------------------------------------------

_GIVEN = [
    "Aurelio", "Bence", "Csilla", "Dagny", "Elias", "Fenna", "Goran",
    "Halina", "Ivo", "Jolanta", "Kestrel", "Lubos", "Marisol", "Nerys",
    "Ondrej", "Piotr", "Quirina", "Radoslav", "Sunniva", "Tomasz",
    "Ulrike", "Vesna", "Wojciech", "Xanthe", "Yaroslav", "Zdenka",
]

_FAMILY = [
    "Abernathy", "Blackwood", "Cranmore", "Dunmore", "Everleigh",
    "Fairweather", "Grimsdottir", "Harrowgate", "Ivorsen", "Jansen",
    "Kowalczyk", "Lindqvist", "Marchetti", "Nakagawa", "Oyelaran",
    "Pettersen", "Quintero", "Rasmussen", "Sarrafian", "Thibodeaux",
]

_FIELD_ROOT = [
    "Agnotology", "Cryotopology", "Dendroacoustics", "Ethnocalcimetry",
    "Funambulatory", "Geosemiotics", "Hyaline", "Ichthyophony",
    "Kinetosemantics", "Limnochemistry", "Mnemotaxonomy",
    "Nychthemeral", "Ombrotrophy", "Palimpsestic", "Querimonious",
    "Rheocryptic", "Siderophony", "Taphonomy", "Umbelliferous",
    "Vernacularism",
]

_FIELD_SUFFIX = [
    "Studies", "Letters", "Review", "Chronicle", "Proceedings",
    "Bulletin", "Transactions", "Quarterly", "Annals", "Digest",
]

_TOPIC_PHRASES = [
    "自评偏差的纵向稳定性", "跨模态一致性检验的重测信度",
    "长尾实体的语义漂移", "小样本条件下的判别效度",
    "双盲设计的实施成本", "编码者间信度的衰减曲线",
    "情境依赖的记忆再巩固", "低资源语种的形态学标注",
    "遥相关指数的重构误差", "谱系树推断的稳健性",
    "分布式注释者的一致性阈值", "扰动实验的生态效度",
]

# Tail entities used for the TK family. These are deliberately chosen from
# the long tail: the model has a fuzzy prior but not a reliable retrievable
# fact. Ground truth is pinned by the generator and is *not* claimed to be
# real-world truth — see task说明 § TK family caveat. The metric for TK is
# calibration, not factual accuracy in the general-knowledge sense.
_TAIL_ENTITIES = [
    ("Bergstrand", "hydrology", 1974, 11),
    ("Cavallaro", "mycology", 1981, 7),
    ("Dreissen", "limnology", 1969, 14),
    ("Falkenrath", "pedology", 1988, 9),
    ("Halvorsen", "glaciology", 1977, 12),
    ("Isakidou", "seismology", 1983, 6),
    ("Jablonowski", "optics", 1971, 18),
    ("Kettilsson", "ethology", 1990, 8),
    ("Lindgren", "palynology", 1966, 15),
    ("Morvath", "ichthyology", 1985, 5),
    ("Novakovic", "sedimentology", 1979, 13),
    ("Ostrowski", "acoustics", 1973, 10),
    ("Pihlajamaa", "phenology", 1992, 4),
    ("Rasmussen", "biogeography", 1968, 16),
    ("Sandvik", "geomorphology", 1986, 3),
    ("Tsvetkov", "cryology", 1975, 17),
]

_ARXIV_FAKE_PREFIX = ["27", "26", "25", "24", "23"]
_ARXIV_FAKE_SUFFIX = ["19042", "20817", "11744", "30126", "44891", "51203"]

_NUMBERS = list(range(3, 96))


# --------------------------------------------------------------------------
# Utility
# --------------------------------------------------------------------------

def _stable_seed(base_seed: int, *parts: Any) -> int:
    """Derive a reproducible sub-seed from the base seed and item parts."""
    raw = "|".join([str(base_seed)] + [str(p) for p in parts])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _pick(pool, rng: random.Random):
    return rng.choice(pool)


class _NameFactory:
    """Generates unique fictional author / journal names per item."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self._used: set = set()

    def author(self) -> str:
        for _ in range(200):
            name = f"{_pick(_GIVEN, self.rng)} {_pick(_FAMILY, self.rng)}"
            if name not in self._used:
                self._used.add(name)
                return name
        return f"{_pick(_GIVEN, self.rng)} {_pick(_FAMILY, self.rng)}"

    def journal(self) -> str:
        root = _pick(_FIELD_ROOT, self.rng)
        suffix = _pick(_FIELD_SUFFIX, self.rng)
        patterns = [
            f"Journal of {root}",
            f"The {root} {suffix}",
            f"{root} {suffix} International",
            f"Advances in {root}",
        ]
        return f"《{_pick(patterns, self.rng)}》"

    def year(self, lo: int = 1969, hi: int = 1996) -> int:
        return self.rng.randint(lo, hi)


# --------------------------------------------------------------------------
# Item dataclass
# --------------------------------------------------------------------------

@dataclass
class Item:
    item_id: str
    family: str                 # SI | UI | FT | TK
    domain: str
    premise: str
    question: str
    gold_answer: str
    # Correct behaviour when the model has *perfect* metacognition.
    gold_strategy: str          # ANSWER | ABSTAIN
    # Grading rule identifier used by grade.py
    grader: str                 # exact | abstain | conflict | tolerant
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------
# Family generators
# --------------------------------------------------------------------------

def gen_sufficient_information(rng: random.Random, nf: _NameFactory,
                               idx: int) -> Item:
    """SI — the premise contains everything needed; a definite answer exists."""
    author = nf.author()
    journal = nf.journal()
    year = nf.year()
    n_samples = rng.choice([24, 32, 36, 48, 60, 72, 96, 120])
    n_batches = rng.choice([2, 3, 4, 6])
    per_batch = n_samples // n_batches
    n_samples = per_batch * n_batches  # keep divisible
    topic = _pick(_TOPIC_PHRASES, rng)
    n_sig = rng.choice([11, 13, 17, 19, 23])

    premise = (
        f"{author} 等人于 {year} 年在 {journal} 发表了一篇关于「{topic}」的研究。"
        f"该研究采用多批次抽样设计：样本被平均分为 {n_batches} 个批次，"
        f"每个批次包含 {per_batch} 名被试，全部批次共 {n_samples} 名被试。"
        f"研究以 p < {n_sig/100:.2f} 作为显著性阈值，并报告了 "
        f"{n_batches} 组独立的效应量估计。"
    )
    question = "该研究总共纳入了多少名被试？（请只回答数字）"
    item = Item(
        item_id="", family="SI", domain="premise-arithmetic",
        premise=premise, question=question,
        gold_answer=str(n_samples), gold_strategy="ANSWER", grader="tolerant",
        meta={"n_samples": n_samples, "n_batches": n_batches,
              "per_batch": per_batch, "author": author, "journal": journal,
              "year": year},
    )
    return item


def gen_underdetermined_information(rng: random.Random, nf: _NameFactory,
                                    idx: int) -> Item:
    """UI — premise is rich but the asked quantity is provably absent."""
    author = nf.author()
    journal = nf.journal()
    year = nf.year()
    topic = _pick(_TOPIC_PHRASES, rng)
    n_pages = rng.randint(14, 42)
    n_figs = rng.randint(3, 11)
    n_refs = rng.randint(28, 94)
    n_authors = rng.choice([3, 4, 5, 6])

    # The asked quantity is the number of *empirical* studies on a narrower
    # subtopic. The premise deliberately reports only page/figure/reference
    # counts — never the number of studies on that subtopic.
    premise = (
        f"{journal} {year} 年第 {rng.randint(1,12)} 期刊载了一篇由 {n_authors} 位作者"
        f"署名的综述文章，主题为「{topic}」。文章全文共 {n_pages} 页，"
        f"含 {n_figs} 幅图表与 {n_refs} 条参考文献。文章的摘要指出，"
        f"该领域近年来的研究数量增长显著，但摘要与正文均未按子主题拆分统计。"
    )
    question = (
        f"该综述所引用的 {n_refs} 条参考文献中，专门研究「{topic}」"
        f"**实证**（而非综述或评论）的论文共有多少篇？"
    )
    item = Item(
        item_id="", family="UI", domain="absent-quantity",
        premise=premise, question=question,
        gold_answer="题面未提供该信息，无法确定",
        gold_strategy="ABSTAIN", grader="abstain",
        meta={"absent_quantity": "empirical_paper_count",
              "n_pages": n_pages, "n_figs": n_figs, "n_refs": n_refs,
              "author": author, "journal": journal, "year": year},
    )
    return item


def gen_fabricated_trap(rng: random.Random, nf: _NameFactory,
                        idx: int) -> Item:
    """FT — premise asserts a confident but false/incoherent claim.

    The trap is constructed internally: the premise states a number and then
    states a relation that contradicts it. A careful reader detects the
    contradiction *from the premise alone* — no external knowledge needed.
    A model that simply plays along will produce a confident wrong answer.
    """
    author = nf.author()
    journal = nf.journal()
    year = nf.year()
    topic = _pick(_TOPIC_PHRASES, rng)

    total = rng.choice([120, 150, 180, 200, 240, 300])
    # Guarantee a genuine internal contradiction: draw two shares freely,
    # then set the third so that the triple sums to 82–93% — which directly
    # contradicts the premise's own claim of an exhaustive partition.
    frac_a = rng.choice([28, 30, 32, 35, 38, 40])
    frac_b = rng.choice([24, 26, 28, 30, 32, 35])
    target_sum = rng.choice([82, 85, 88, 90, 93])
    frac_c = target_sum - frac_a - frac_b
    if frac_c < 15 or frac_c > 40:          # keep all three shares plausible
        frac_c = max(15, min(40, target_sum - frac_a - frac_b))
        target_sum = frac_a + frac_b + frac_c
    stated_sum = frac_a + frac_b + frac_c

    # Contradiction: the three shares are stated to be exhaustive but sum to
    # less than 100%. The premise also *asserts* (falsely) that they sum to
    # 100%, and then asks the reader to compute the remainder — which is
    # negative. A model that trusts the assertion fabricates a number.
    premise = (
        f"{author} 等人（{year}）在 {journal} 报告了一项关于「{topic}」的分类研究。"
        f"研究将全部 {total} 个样本单位划分为三类，且**明确说明三类构成完备划分**"
        f"（即三类之和恰好等于总体）。三类占比分别为："
        f"第一类 {frac_a}%，第二类 {frac_b}%，第三类 {frac_c}%。"
        f"作者在结论中称，三类占比「完美覆盖了全部样本」。"
    )
    question = (
        f"依据该研究给出的完备划分，除上述三类之外的第四类样本占比是多少？"
        f"（请给出百分比数字；若题面存在矛盾无法推出，请说明）"
    )
    item = Item(
        item_id="", family="FT", domain="internal-contradiction",
        premise=premise, question=question,
        gold_answer=(
            f"题面自相矛盾：三类占比之和为 {stated_sum}%，"
            f"与「完备划分」相冲突，不存在第四类"
        ),
        gold_strategy="ABSTAIN", grader="conflict",
        meta={"stated_sum": stated_sum, "total": total,
              "fracs": [frac_a, frac_b, frac_c],
              "author": author, "journal": journal, "year": year},
    )
    return item


def gen_tail_knowledge(rng: random.Random, nf: _NameFactory,
                       idx: int) -> Item:
    """TK — long-tail question with a pinned gold answer.

    The metric that matters for this family is calibration (does the model
    know it is guessing?), not encyclopaedic accuracy.
    """
    name, field_cn, year, gold = _pick(_TAIL_ENTITIES, rng)
    # jitter the gold per seed so the same entity yields different items
    gold = max(2, gold + rng.randint(-1, 1))

    premise = (
        f"本条考察长尾学术记录。已知 {field_cn} 领域存在一批以研究者姓氏命名的"
        f"小型数据集（legacy datasets），收录于 1960–1995 年间的区域性档案中，"
        f"未被主流文献索引覆盖。"
    )
    question = (
        f"以研究者「{name}」命名的 {field_cn} 数据集，其官方档案记录的"
        f"**版本序列号**是多少？（请给出数字；若你不确定该记录是否存在，请说明）"
    )
    item = Item(
        item_id="", family="TK", domain=f"tail-{field_cn}",
        premise=premise, question=question,
        gold_answer=str(gold), gold_strategy="ANSWER", grader="tolerant",
        meta={"tail_entity": name, "field": field_cn,
              "recorded_year": year, "gold": gold,
              "note": "calibration-family; accuracy secondary to ΔE"},
    )
    return item


_FAMILY_FN = {
    "SI": gen_sufficient_information,
    "UI": gen_underdetermined_information,
    "FT": gen_fabricated_trap,
    "TK": gen_tail_knowledge,
}


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

DEFAULT_MIX = {"SI": 0.25, "UI": 0.25, "FT": 0.25, "TK": 0.25}


def generate_items(n: int = 200,
                   seed: int = 424242,
                   mix: Dict[str, float] | None = None) -> List[Item]:
    """Generate `n` items with the requested family mix, deterministically.

    Determinism guarantee: the same (n, seed, mix) always yields byte-identical
    items. This is what makes the benchmark reproducible.
    """
    mix = mix or DEFAULT_MIX
    assert abs(sum(mix.values()) - 1.0) < 1e-6, "mix must sum to 1.0"

    counts = {k: int(round(v * n)) for k, v in mix.items()}
    # fix rounding drift
    drift = n - sum(counts.values())
    if drift:
        counts["SI"] += drift

    plan: List[str] = []
    for fam, c in counts.items():
        plan.extend([fam] * c)
    rng_shuffle = random.Random(seed)
    rng_shuffle.shuffle(plan)

    items: List[Item] = []
    for i, fam in enumerate(plan):
        sub = _stable_seed(seed, fam, i)
        rng = random.Random(sub)
        nf = _NameFactory(rng)
        item = _FAMILY_FN[fam](rng, nf, i)
        item.item_id = f"MC-{seed}-{i:04d}"
        items.append(item)
    return items


def generate_to_dicts(n: int = 200, seed: int = 424242,
                      mix: Dict[str, float] | None = None) -> List[Dict[str, Any]]:
    return [it.to_dict() for it in generate_items(n=n, seed=seed, mix=mix)]


if __name__ == "__main__":       # pragma: no cover
    import json
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    samples = generate_to_dicts(n=n, seed=int(sys.argv[2]) if len(sys.argv) > 2 else 424242)
    print(json.dumps(samples, ensure_ascii=False, indent=2))
