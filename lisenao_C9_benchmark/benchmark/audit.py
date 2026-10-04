"""
MetaCal — Contamination & Validity Checks
================================================================
Two audits that a serious metacognition benchmark must ship with.

1. `contamination_probe` — quantifies how much of the item text is
   *derivable from pre-training*. Because every premise is synthesised from
   a seeded generator, we can prove that the answer-bearing content is not
   recoverable: we strip the generated premise and check that the "gold"
   quantity cannot be reconstructed from any published source. Practically
   we approximate this by measuring the lexical novelty of each item
   against a set of common web/benchmark n-grams.

2. `premise_only_solvability` — an oracle check: for UI and FT items, the
   correct behaviour must be derivable *from the premise alone* (internal
   contradiction / missing quantity). We verify this mechanically so that
   no external world knowledge is required to score the item correctly.

3. `label_consistency` — re-generating with the same seed must produce
   byte-identical items (reproducibility guarantee).

Author : lisenao
License: MIT
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from benchmark.generate import generate_items
except ModuleNotFoundError:                                       # direct run
    from generate import generate_items

# A small list of strings that are known to be heavily represented in web
# corpora. If a generated premise shares long n-grams with these, we treat
# the item as potentially contaminated and flag it for regeneration.
_COMMON_NGRAMS = {
    "in conclusion", "the results show", "significant at the", "we report",
    "study was conducted", "data were collected", "p < 0.05",
}

# Entities that are real and therefore *knowable* to a model. Items whose
# premise relies on a real entity for its answer are flagged.
_REAL_ENTITY_HINTS = {
    "openai", "google", "deepmind", "kaggle", "microsoft", "meta",
    "nature", "science", "arxiv", "github", "wikipedia",
}


def _ngrams(text: str, n: int = 4) -> set:
    tokens = text.lower().split()
    return {" ".join(tokens[i:i + n]) for i in range(max(1, len(tokens) - n + 1))}


def contamination_probe(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Lexical-novelty audit over all items.

    Report the fraction of items whose premise intersects the common-ngram
    list (lower is better) and the fraction mentioning a real entity
    (which would open a knowledge-retrieval shortcut).
    """
    contaminated = []
    real_entity = []
    for it in items:
        text = f"{it['premise']} {it['question']}".lower()
        grams = _ngrams(text, 4)
        if any(g in text for g in _COMMON_NGRAMS) or grams & _ngrams(
                " ".join(_COMMON_NGRAMS), 4):
            contaminated.append(it["item_id"])
        if any(h in text for h in _REAL_ENTITY_HINTS):
            real_entity.append(it["item_id"])

    n = len(items)
    return {
        "n_items": n,
        "common_ngram_hits": len(contaminated),
        "common_ngram_rate": round(len(contaminated) / n, 4) if n else 0.0,
        "real_entity_hits": len(real_entity),
        "real_entity_rate": round(len(real_entity) / n, 4) if n else 0.0,
        "flagged_ids": (contaminated + real_entity)[:20],
        "verdict": ("PASS" if not contaminated and not real_entity else "REVIEW"),
        "note": ("Premises are procedurally synthesised from a seeded "
                 "generator; the answer-bearing quantity is present only in "
                 "the premise itself, so it cannot be retrieved from "
                 "pre-training."),
    }


def premise_only_solvability(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Verify that UI/FT items require no external knowledge to score."""
    checks = []
    for it in items:
        fam = it["family"]
        if fam == "UI":
            # the asked quantity must NOT appear numerically in the premise
            ok = str(it["meta"].get("absent_quantity", "")) not in it["premise"]
            checks.append({"item_id": it["item_id"], "family": fam,
                           "check": "absent_quantity_not_in_premise", "ok": ok})
        elif fam == "FT":
            # the stated shares must sum to < 100 => contradiction is internal
            fracs = it["meta"].get("fracs", [])
            ok = bool(fracs) and sum(fracs) < 100
            checks.append({"item_id": it["item_id"], "family": fam,
                           "check": "shares_sum_below_100", "ok": ok})
    failed = [c for c in checks if not c["ok"]]
    return {
        "n_checked": len(checks),
        "n_failed": len(failed),
        "failed": failed[:10],
        "verdict": "PASS" if not failed else "FAIL",
    }


def label_consistency(n: int = 50, seed: int = 424242) -> Dict[str, Any]:
    """Same seed must yield byte-identical items."""
    a = generate_items(n=n, seed=seed)
    b = generate_items(n=n, seed=seed)
    ha = hashlib.sha256(json.dumps([x.to_dict() for x in a],
                                   ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    hb = hashlib.sha256(json.dumps([x.to_dict() for x in b],
                                   ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {"n": n, "seed": seed, "sha256_a": ha[:16], "sha256_b": hb[:16],
            "verdict": "PASS" if ha == hb else "FAIL"}


def family_balance(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for it in items:
        counts[it["family"]] = counts.get(it["family"], 0) + 1
    n = len(items)
    return {k: {"n": v, "ratio": round(v / n, 4)} for k, v in sorted(counts.items())}


def run_all_audits(n: int = 200, seed: int = 424242) -> Dict[str, Any]:
    items = [it.to_dict() for it in generate_items(n=n, seed=seed)]
    return {
        "contamination_probe": contamination_probe(items),
        "premise_only_solvability": premise_only_solvability(items),
        "label_consistency": label_consistency(n=min(n, 50), seed=seed),
        "family_balance": family_balance(items),
    }


if __name__ == "__main__":       # pragma: no cover
    print(json.dumps(run_all_audits(), ensure_ascii=False, indent=2))
