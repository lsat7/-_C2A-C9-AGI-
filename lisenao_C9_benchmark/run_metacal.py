"""
MetaCal — Main Runner
================================================================
Generates items, queries a model, grades every item, and writes a full
result bundle (raw responses + item-level scores + aggregate metrics).

Usage
-----
    # full run against an OpenAI-compatible endpoint
    python run_metacal.py --model openai:gpt-4o-mini --n 200 --seed 424242 \
        --out results/gpt-4o-mini

    # offline pipeline self-test (no API key needed)
    python run_metacal.py --model sim:sim-calibrated --n 200 --out results/sim

    # compare several models in one go
    python run_metacal.py --model sim:sim-naive --model sim:sim-calibrated \
        --model sim:sim-expert --n 120 --out results/sims

Author : lisenao (李思脑)
License: MIT
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import os
import sys
import traceback
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from benchmark.generate import generate_items                      # noqa: E402
from benchmark.grade import grade_all, summarise, looks_like_abstention  # noqa: E402
from benchmark.model_adapter import make_adapter, SimulatedAdapter  # noqa: E402
from benchmark.prompt import build_prompt, parse_response           # noqa: E402

METACAL_VERSION = "1.0.0"
PROMPT_VERSION = "mc-p1-1.0"


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def _write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        return
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def run_one(model_spec: str, n: int, seed: int, out_dir: str,
            sleep: float = 0.0, limit: int | None = None,
            temperature: float = 0.0,
            api_key: str | None = None) -> Dict[str, Any]:
    """Run a single model over the benchmark and persist the result bundle."""

    items = generate_items(n=n, seed=seed)
    if limit:
        items = items[:limit]
    item_dicts = [it.to_dict() for it in items]

    adapter = make_adapter(model_spec, temperature=temperature,
                          **({"api_key": api_key} if api_key else {}))

    raw_responses: List[Dict[str, Any]] = []
    parsed: List[Dict[str, Any]] = []

    for i, it in enumerate(item_dicts, 1):
        prompt = build_prompt(it)
        if isinstance(adapter, SimulatedAdapter):
            adapter.set_context(it["family"], it["gold_answer"])
        try:
            raw = adapter.respond(prompt)
        except Exception as exc:                                  # noqa: BLE001
            raw = f'{{"pred":0,"strategy":"ABSTAIN","answer":"ERROR","post":0}}'
            print(f"  [{i}/{len(item_dicts)}] ERROR on {it['item_id']}: {exc}",
                  file=sys.stderr)
        resp = parse_response(raw)
        resp["item_id"] = it["item_id"]
        raw_responses.append({"item_id": it["item_id"], "raw": raw})
        parsed.append(resp)
        if i % 20 == 0 or i == len(item_dicts):
            print(f"  [{adapter.name}] {i}/{len(item_dicts)} done")
        if sleep:
            import time
            time.sleep(sleep)

    graded = grade_all(item_dicts, parsed)
    metrics = summarise(graded)

    # ---- persist ---------------------------------------------------------
    os.makedirs(out_dir, exist_ok=True)
    _write_json(os.path.join(out_dir, "items.json"), item_dicts)
    _write_json(os.path.join(out_dir, "raw_responses.json"), raw_responses)
    _write_json(os.path.join(out_dir, "responses.json"), parsed)
    _write_json(os.path.join(out_dir, "per_item_scores.json"),
                [g.to_dict() for g in graded])
    _write_json(os.path.join(out_dir, "metrics.json"), {
        "benchmark": "MetaCal / PMCB",
        "version": METACAL_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model": adapter.name,
        "model_spec": model_spec,
        "is_simulated": isinstance(adapter, SimulatedAdapter),
        "n_items": len(item_dicts),
        "seed": seed,
        "temperature": temperature,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "metrics": metrics,
    })

    rows = []
    gold_by_id = {it["item_id"]: it for it in item_dicts}
    for g, p in zip(graded, parsed):
        it = gold_by_id[g.item_id]
        rows.append({
            "item_id": g.item_id,
            "family": g.family,
            "domain": it["domain"],
            "strategy": g.strategy,
            "gold_strategy": it["gold_strategy"],
            "strategy_ok": int(g.strategy_ok),
            "answer": p.get("answer", ""),
            "gold_answer": it["gold_answer"],
            "correct": int(g.correct),
            "pred": g.pred,
            "post": g.post,
            "delta_e": g.delta_e,
            "overconfidence": g.overconfidence,
            "brier": g.brier,
        })
    _write_csv(os.path.join(out_dir, "per_item_scores.csv"), rows)

    return {"model": adapter.name, "out_dir": out_dir,
            "is_simulated": isinstance(adapter, SimulatedAdapter),
            **metrics}


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="MetaCal — Predictive Metacognition Calibration Benchmark")
    ap.add_argument("--model", action="append", required=True,
                    help="model spec; repeat for multi-model comparison. "
                         "e.g. openai:gpt-4o-mini | anthropic:claude-... | "
                         "sim:sim-calibrated")
    ap.add_argument("--n", type=int, default=200, help="items per model")
    ap.add_argument("--seed", type=int, default=424242)
    ap.add_argument("--out", default="results", help="output directory")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap items (smoke test)")
    ap.add_argument("--sleep", type=float, default=0.0,
                    help="seconds between API calls (rate limiting)")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--api-key", default=None)
    args = ap.parse_args(argv)

    summaries = []
    for spec in args.model:
        print(f"\n=== Running {spec} (n={args.n}, seed={args.seed}) ===")
        safe = spec.replace(":", "_").replace("/", "_").replace("|", "_")
        out_dir = os.path.join(args.out, safe)
        try:
            summaries.append(run_one(spec, args.n, args.seed, out_dir,
                                     sleep=args.sleep, limit=args.limit,
                                     temperature=args.temperature,
                                     api_key=args.api_key))
        except Exception:                                          # noqa: BLE001
            traceback.print_exc()
            print(f"!! {spec} failed; continuing", file=sys.stderr)

    if len(summaries) > 1:
        _write_json(os.path.join(args.out, "comparison.json"), summaries)
        print("\n================ MetaCal Leaderboard ================")
        print(f"{'model':<34}{'score':>8}{'acc':>8}{'dE':>8}"
              f"{'over':>8}{'AUROC':>8}{'stratOK':>9}")
        for s in sorted(summaries, key=lambda x: -x["metacal_score"]):
            o = s["overall"]
            print(f"{s['model']:<34}{s['metacal_score']:>8.4f}"
                  f"{o['accuracy']:>8.3f}{o['delta_E']:>8.3f}"
                  f"{o['overconfidence']:>+8.3f}"
                  f"{(o['auroc_pred'] or float('nan')):>8.3f}"
                  f"{o['strategy_rationality']:>9.3f}")
    elif summaries:
        _write_json(os.path.join(args.out, "summary.json"), summaries[0])
        print(json.dumps(summaries[0], ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
