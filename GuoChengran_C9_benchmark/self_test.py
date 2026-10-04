"""
MetaCal — Self-Test Suite
================================================================
Runs fully offline (no API key, no network). Verifies:

  * generator determinism and family balance
  * every family's grader accepts the gold answer
  * every family's grader rejects a plausible wrong answer
  * response parser robustness (fences, prose, 0-100 vs 0-1 scales)
  * metric identities (ΔE bounds, Brier bounds, AUROC range)
  * the benchmark separates a naive profile from an expert profile

Run:  python -m pytest -q        (or)  python self_test.py
Author: GuoChengran (郭承然)  License: MIT
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from benchmark.audit import run_all_audits                          # noqa: E402
from benchmark.generate import generate_items                       # noqa: E402
from benchmark.grade import grade_all, summarise                    # noqa: E402
from benchmark.model_adapter import SimulatedAdapter                # noqa: E402
from benchmark.prompt import build_prompt, parse_response           # noqa: E402


# ---------------------------------------------------------------- generator

def test_family_balance():
    items = generate_items(n=200, seed=1)
    fams = {}
    for it in items:
        fams[it.family] = fams.get(it.family, 0) + 1
    assert fams == {"SI": 50, "UI": 50, "FT": 50, "TK": 50}, fams


def test_determinism():
    a = [i.to_dict() for i in generate_items(n=40, seed=7)]
    b = [i.to_dict() for i in generate_items(n=40, seed=7)]
    assert a == b


def test_different_seeds_differ():
    a = [i.to_dict() for i in generate_items(n=40, seed=7)]
    b = [i.to_dict() for i in generate_items(n=40, seed=8)]
    assert a != b


def test_all_items_have_required_fields():
    for it in generate_items(n=40, seed=3):
        assert it.item_id and it.family and it.premise and it.question
        assert it.gold_answer and it.gold_strategy in ("ANSWER", "ABSTAIN")
        assert it.grader in ("tolerant", "exact", "abstain", "conflict")


# ---------------------------------------------------------------- grading

def test_gold_answers_are_graded_correct():
    items = [i.to_dict() for i in generate_items(n=120, seed=11)]
    responses = []
    for it in items:
        if it["gold_strategy"] == "ABSTAIN":
            responses.append({"item_id": it["item_id"], "strategy": "ABSTAIN",
                              "answer": "无法确定", "pred": 0.2, "post": 0.2})
        else:
            responses.append({"item_id": it["item_id"], "strategy": "ANSWER",
                              "answer": it["gold_answer"], "pred": 0.9, "post": 0.9})
    graded = grade_all(items, responses)
    assert all(g.correct for g in graded), [
        (g.item_id, g.family) for g in graded if not g.correct][:5]
    assert all(g.strategy_ok for g in graded)


def test_wrong_answers_are_graded_incorrect():
    items = [i.to_dict() for i in generate_items(n=120, seed=12)]
    responses = []
    for it in items:
        # Always answer confidently with a number -> must fail UI and FT,
        # and will almost surely fail SI/TK too.
        responses.append({"item_id": it["item_id"], "strategy": "ANSWER",
                          "answer": "42", "pred": 0.95, "post": 0.9})
    graded = grade_all(items, responses)
    ui = [g for g in graded if g.family == "UI"]
    ft = [g for g in graded if g.family == "FT"]
    assert not any(g.correct for g in ui)
    assert not any(g.correct for g in ft)


def test_grader_tolerates_verbose_answers():
    items = [i.to_dict() for i in generate_items(n=60, seed=13)]
    by_id = {i["item_id"]: i for i in items}
    responses = []
    for it in items:
        if it["gold_strategy"] == "ABSTAIN":
            ans = "题面没有提供相关信息，我无法确定。"
        else:
            ans = f"根据题面计算，答案是 {it['gold_answer']}。"
        responses.append({"item_id": it["item_id"], "strategy":
                          "ABSTAIN" if it["gold_strategy"] == "ABSTAIN" else "ANSWER",
                          "answer": ans, "pred": 0.8, "post": 0.8})
    graded = grade_all(items, responses)
    assert all(g.correct for g in graded), [
        (g.item_id, g.family, responses[i]) for i, g in enumerate(graded)
        if not g.correct][:5]


# ---------------------------------------------------------------- parser

def test_parse_plain_json():
    r = parse_response('{"pred": 80, "strategy": "ANSWER", "answer": "12", "post": 70}')
    assert abs(r["pred"] - 0.8) < 1e-6 and abs(r["post"] - 0.7) < 1e-6
    assert r["strategy"] == "ANSWER" and r["answer"] == "12"


def test_parse_fenced_json():
    raw = 'Sure!\n```json\n{"pred": 60, "strategy": "HEDGE", "answer": "maybe", "post": 55}\n```'
    r = parse_response(raw)
    assert r["strategy"] == "HEDGE" and abs(r["pred"] - 0.6) < 1e-6


def test_parse_unit_scale():
    r = parse_response('{"pred": 0.7, "strategy": "ANSWER", "answer": "1", "post": 0.5}')
    assert abs(r["pred"] - 0.7) < 1e-6 and abs(r["post"] - 0.5) < 1e-6


def test_parse_garbage_does_not_crash():
    r = parse_response("I cannot answer this.")
    assert r["parse_failed"] is True
    assert r["strategy"] in ("ANSWER", "HEDGE", "ABSTAIN")


# ---------------------------------------------------------------- metrics

def test_metric_bounds():
    items = [i.to_dict() for i in generate_items(n=80, seed=21)]
    ad = SimulatedAdapter(profile="sim-calibrated", seed=5)
    responses = []
    for it in items:
        ad.set_context(it["family"], it["gold_answer"])
        r = parse_response(ad.respond(build_prompt(it)))
        r["item_id"] = it["item_id"]
        responses.append(r)
    m = summarise(grade_all(items, responses))
    o = m["overall"]
    assert 0.0 <= o["accuracy"] <= 1.0
    assert 0.0 <= o["delta_E"] <= 1.0
    assert 0.0 <= o["brier"] <= 1.0
    assert 0.0 <= o["ece_pred"] <= 1.0
    assert o["auroc_pred"] is None or 0.0 <= o["auroc_pred"] <= 1.0
    assert 0.0 <= m["metacal_score"] <= 1.0


def test_benchmark_discriminates_profiles():
    """The core validity claim: a metacognitively strong profile must
    outscore a metacognitively weak one, and the gap must be material."""
    items = [i.to_dict() for i in generate_items(n=240, seed=31)]

    def score(profile):
        ad = SimulatedAdapter(profile=profile, seed=99)
        responses = []
        for it in items:
            ad.set_context(it["family"], it["gold_answer"])
            r = parse_response(ad.respond(build_prompt(it)))
            r["item_id"] = it["item_id"]
            responses.append(r)
        return summarise(grade_all(items, responses))

    naive = score("sim-naive")
    expert = score("sim-expert")
    assert expert["metacal_score"] > naive["metacal_score"] + 0.10
    # and the ordering must hold on the metacognitive panel, not just accuracy
    assert expert["overall"]["strategy_rationality"] > \
        naive["overall"]["strategy_rationality"] + 0.15
    assert expert["overall"]["ece_pred"] < naive["overall"]["ece_pred"]


# ---------------------------------------------------------------- audits

def test_audits_all_pass():
    audits = run_all_audits(n=120, seed=41)
    assert audits["contamination_probe"]["verdict"] == "PASS"
    assert audits["premise_only_solvability"]["verdict"] == "PASS"
    assert audits["label_consistency"]["verdict"] == "PASS"


if __name__ == "__main__":       # pragma: no cover
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            failed += 1
        except Exception as e:                                    # noqa: BLE001
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed, {len(fns)} total")
    raise SystemExit(1 if failed else 0)
