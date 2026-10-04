"""
MetaCal — Unified CLI
================================================================
One entry point for the four things a user actually wants to do:

    python metacal.py generate --n 200 --seed 42 --out data/items.json
    python metacal.py audit    --n 200 --seed 42
    python metacal.py test     --model openai:gpt-4o-mini --n 200 --out results
    python metacal.py human    --n 40 --seed 7 --out human_form.html

Author : lisenao (李思脑)
License: MIT
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from benchmark.audit import run_all_audits                          # noqa: E402
from benchmark.generate import generate_items                       # noqa: E402
from benchmark.human_baseline import build_form                     # noqa: E402


def cmd_generate(a) -> int:
    items = [it.to_dict() for it in generate_items(n=a.n, seed=a.seed)]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=2)
    fams = {}
    for it in items:
        fams[it["family"]] = fams.get(it["family"], 0) + 1
    print(f"wrote {len(items)} items to {a.out}  |  families: {fams}")
    return 0


def cmd_audit(a) -> int:
    audits = run_all_audits(n=a.n, seed=a.seed)
    print(json.dumps(audits, ensure_ascii=False, indent=2))
    ok = all(audits[k]["verdict"] == "PASS"
             for k in ("contamination_probe", "premise_only_solvability",
                       "label_consistency"))
    return 0 if ok else 1


def cmd_test(a) -> int:
    from run_metacal import main as run_main
    argv = []
    for m in a.model:
        argv += ["--model", m]
    argv += ["--n", str(a.n), "--seed", str(a.seed), "--out", a.out]
    if a.limit:
        argv += ["--limit", str(a.limit)]
    if a.sleep:
        argv += ["--sleep", str(a.sleep)]
    if a.api_key:
        argv += ["--api-key", a.api_key]
    return run_main(argv)


def cmd_human(a) -> int:
    items = [it.to_dict() for it in generate_items(n=a.n, seed=a.seed)]
    html = build_form(items)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"wrote human-baseline form ({len(items)} items) to {a.out}")
    return 0


def cmd_selftest(a) -> int:
    import subprocess
    return subprocess.call([sys.executable, "self_test.py"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="metacal",
        description="MetaCal — Predictive Metacognition Calibration Benchmark")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("generate", help="generate an item set")
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--seed", type=int, default=424242)
    p.add_argument("--out", default="data/items.json")
    p.set_defaults(fn=cmd_generate)

    p = sub.add_parser("audit", help="run contamination / validity audits")
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--seed", type=int, default=424242)
    p.set_defaults(fn=cmd_audit)

    p = sub.add_parser("test", help="run the benchmark against a model")
    p.add_argument("--model", action="append", required=True)
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--seed", type=int, default=424242)
    p.add_argument("--out", default="results")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--sleep", type=float, default=0.0)
    p.add_argument("--api-key", default=None)
    p.set_defaults(fn=cmd_test)

    p = sub.add_parser("human", help="build a human-baseline form")
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", default="human_form.html")
    p.set_defaults(fn=cmd_human)

    p = sub.add_parser("selftest", help="run the offline test suite")
    p.set_defaults(fn=cmd_selftest, n=0, seed=0)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
