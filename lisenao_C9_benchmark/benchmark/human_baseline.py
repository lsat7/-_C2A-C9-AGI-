"""
MetaCal — Human Baseline Protocol
================================================================
Builds a self-contained HTML instrument for collecting human data under
exactly the same three-phase protocol the model faces:

    Phase 1  predict P̂  +  choose a strategy
    Phase 2  answer
    Phase 3  post-dict P_post

The form is a single file (no server, no dependencies). It exports a JSON
blob at the end which `human_baseline.score_submissions()` consumes, so
human and model data flow through the *same* grading code — this is what
makes the human comparison legitimate rather than anecdotal.

Author : lisenao (李思脑)
License: MIT
"""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List

# --------------------------------------------------------------------------
# HTML instrument
# --------------------------------------------------------------------------

_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MetaCal 人类基线 · 元认知自评任务</title>
<style>
 :root{{--bg:#f7f8fa;--card:#fff;--ink:#1b1f24;--muted:#65707c;
        --line:#e3e7ec;--accent:#1a6fd4;--accent-soft:#eaf2fd;}}
 *{{box-sizing:border-box}}
 body{{margin:0;font-family:-apple-system,"Segoe UI","PingFang SC",
      "Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);
      line-height:1.65}}
 .wrap{{max-width:760px;margin:0 auto;padding:28px 20px 80px}}
 h1{{font-size:21px;margin:0 0 6px}}
 .sub{{color:var(--muted);font-size:13px;margin-bottom:22px}}
 .card{{background:var(--card);border:1px solid var(--line);border-radius:12px;
       padding:22px;margin-bottom:18px;box-shadow:0 1px 2px rgba(16,24,40,.04)}}
 .phase{{font-size:12px;font-weight:600;letter-spacing:.06em;
        color:var(--accent);text-transform:uppercase;margin-bottom:10px}}
 .premise{{background:#fbfcfd;border-left:3px solid var(--accent);
          padding:12px 14px;border-radius:6px;font-size:14px;
          color:#333c46;margin:10px 0}}
 .q{{font-weight:600;margin:12px 0 14px;font-size:15px}}
 label.lbl{{display:block;font-size:13px;color:var(--muted);margin:14px 0 6px}}
 input[type=range]{{width:100%}}
 .val{{font-variant-numeric:tabular-nums;font-weight:600}}
 .opts{{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}}
 .opt{{flex:1 1 160px;border:1px solid var(--line);border-radius:8px;
      padding:10px 12px;cursor:pointer;font-size:13px;background:#fff;
      transition:.15s}}
 .opt:hover{{border-color:var(--accent);background:var(--accent-soft)}}
 .opt.sel{{border-color:var(--accent);background:var(--accent-soft);
          box-shadow:inset 0 0 0 1px var(--accent)}}
 textarea{{width:100%;min-height:70px;border:1px solid var(--line);
          border-radius:8px;padding:10px;font:inherit;font-size:14px;
          resize:vertical}}
 .bar{{position:fixed;left:0;right:0;bottom:0;background:#fff;
      border-top:1px solid var(--line);padding:12px 20px;display:flex;
      gap:14px;align-items:center;justify-content:center}}
 .bar .prog{{font-size:13px;color:var(--muted)}}
 button{{background:var(--accent);color:#fff;border:0;border-radius:8px;
        padding:10px 22px;font:inherit;font-weight:600;cursor:pointer}}
 button.ghost{{background:#fff;color:var(--accent);
              border:1px solid var(--accent)}}
 button:disabled{{opacity:.45;cursor:not-allowed}}
 .done{{display:none;text-align:center;padding:40px 10px}}
 .done h2{{color:#1a7f45}}
 .note{{font-size:12px;color:var(--muted);margin-top:10px}}
</style>
</head>
<body>
<div class="wrap">
  <h1>MetaCal 元认知自评任务</h1>
  <div class="sub">
    这是一个测量「你知道自己知道什么」的任务。每题分三步：<b>先预测</b>你能否答对，
    <b>再作答</b>，最后<b>再次评估</b>。请如实作答 —— 目标不是拿高分，
    而是让自评尽量准确。共 {N} 题，约需 {MINUTES} 分钟。
  </div>

  <div class="card">
    <label class="lbl">被试编号 / Participant ID（可填化名）</label>
    <input id="pid" style="width:100%;padding:9px;border:1px solid var(--line);
           border-radius:8px;font:inherit" placeholder="例如 P07">
    <label class="lbl">所在组别（用于人类基线分层）</label>
    <div class="opts" id="group">
      <div class="opt" data-v="undergrad">本科生</div>
      <div class="opt" data-v="grad">研究生</div>
      <div class="opt" data-v="expert">相关领域研究者 / 有统计训练</div>
    </div>
  </div>

  <div id="qarea"></div>

  <div class="done" id="done">
    <h2>✓ 全部完成</h2>
    <p>感谢参与。请点击下方按钮导出结果文件并发给研究者。</p>
    <button id="dl">下载结果 JSON</button>
    <div class="note" id="dlnote"></div>
  </div>
</div>

<div class="bar">
  <span class="prog" id="prog">第 0 / {N} 题</span>
  <button class="ghost" id="prev">上一题</button>
  <button id="next">下一题</button>
</div>

<script>
const ITEMS = {ITEMS_JSON};
const ANSWERS = {{}};
let idx = 0;
let group = null;

function cur(){{ return ITEMS[idx]; }}

function render(){{
  const it = cur();
  const a = ANSWERS[it.item_id] || {{pred:50, strategy:null, answer:"", post:50}};
  const area = document.getElementById('qarea');
  area.innerHTML = `
   <div class="card">
     <div class="phase">阶段 1 — 事前预测</div>
     <div class="premise">${{esc(it.premise)}}</div>
     <div class="q">${{esc(it.question)}}</div>
     <label class="lbl">a) 你答对本题的概率：<span class="val" id="pv">${{a.pred}}</span>%</label>
     <input type="range" id="pred" min="0" max="100" step="5" value="${{a.pred}}">
     <label class="lbl">b) 你的策略</label>
     <div class="opts" id="strat">
       <div class="opt" data-v="ANSWER">直接作答</div>
       <div class="opt" data-v="HEDGE">声明不确定，但仍给出答案</div>
       <div class="opt" data-v="ABSTAIN">拒答（无法确定）</div>
     </div>
   </div>
   <div class="card">
     <div class="phase">阶段 2 — 作答</div>
     <textarea id="ans" placeholder="写下你的答案；若拒答请留空。">${{esc(a.answer)}}</textarea>
   </div>
   <div class="card">
     <div class="phase">阶段 3 — 事后自评</div>
     <label class="lbl">现在你认为自己答对的概率：
       <span class="val" id="qv">${{a.post}}</span>%</label>
     <input type="range" id="post" min="0" max="100" step="5" value="${{a.post}}">
     <div class="note">提示：请独立判断，不要为了与阶段 1 一致而刻意对齐。</div>
   </div>`;

  const pr = document.getElementById('pred');
  pr.oninput = () => {{ document.getElementById('pv').textContent = pr.value; }};
  const po = document.getElementById('post');
  po.oninput = () => {{ document.getElementById('qv').textContent = po.value; }};

  const sr = document.getElementById('strat');
  sr.querySelectorAll('.opt').forEach(o => {{
    if (o.dataset.v === a.strategy) o.classList.add('sel');
    o.onclick = () => {{
      sr.querySelectorAll('.opt').forEach(x => x.classList.remove('sel'));
      o.classList.add('sel');
    }};
  }});

  document.getElementById('prog').textContent = `第 ${{idx+1}} / ${{ITEMS.length}} 题`;
  document.getElementById('prev').disabled = idx === 0;
  document.getElementById('next').textContent =
      idx === ITEMS.length - 1 ? '完成' : '下一题';
}}

function esc(s){{ return String(s).replace(/[&<>]/g,
  c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}})[c]); }}

function save(){{
  const it = cur();
  const sel = document.querySelector('#strat .opt.sel');
  ANSWERS[it.item_id] = {{
    pred: +document.getElementById('pred').value,
    strategy: sel ? sel.dataset.v : null,
    answer: document.getElementById('ans').value,
    post: +document.getElementById('post').value,
  }};
}}

document.getElementById('group').querySelectorAll('.opt').forEach(o => {{
  o.onclick = () => {{
    document.getElementById('group').querySelectorAll('.opt')
      .forEach(x => x.classList.remove('sel'));
    o.classList.add('sel'); group = o.dataset.v;
  }};
}});

document.getElementById('prev').onclick = () => {{ save(); idx--; render(); }};
document.getElementById('next').onclick = () => {{
  save();
  const a = ANSWERS[cur().item_id];
  if (!a.strategy) {{ alert('请先选择阶段 1 的策略。'); return; }}
  if (idx === ITEMS.length - 1) {{ finish(); return; }}
  idx++; render();
}};

function finish(){{
  document.getElementById('qarea').style.display = 'none';
  document.getElementById('done').style.display = 'block';
  document.querySelectorAll('.card').forEach(c => c.style.display = 'none');
  document.querySelector('.bar').style.display = 'none';
  window.__PAYLOAD = exportPayload();
}}

function exportPayload(){{
  return {{
    participant_id: document.getElementById('pid').value || 'anon',
    group: group || 'unspecified',
    submitted_at: new Date().toISOString(),
    answers: Object.entries(ANSWERS).map(([item_id, a]) => ({{
      item_id,
      strategy: a.strategy || 'ABSTAIN',
      answer: a.answer || '',
      pred: a.pred / 100,
      post: a.post / 100,
    }})),
  }};
}}

document.getElementById('dl').onclick = () => {{
  const blob = new Blob([JSON.stringify(window.__PAYLOAD, null, 2)],
                        {{type:'application/json'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `metacal_${{window.__PAYLOAD.participant_id}}.json`;
  a.click();
  document.getElementById('dlnote').textContent = '已下载：' + a.download;
}};

render();
</script>
</body>
</html>
"""


def build_form(items: List[Dict[str, Any]],
               est_minutes_per_item: float = 0.7) -> str:
    safe_items = [{k: it[k] for k in ("item_id", "family", "premise", "question")}
                  for it in items]
    return _TEMPLATE.format(
        N=len(items),
        MINUTES=int(len(items) * est_minutes_per_item),
        ITEMS_JSON=json.dumps(safe_items, ensure_ascii=False),
    )


# --------------------------------------------------------------------------
# Scoring collected human data with the SAME engine as model data
# --------------------------------------------------------------------------

def score_submissions(items: List[Dict[str, Any]],
                      submissions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Score one or more human submissions through the shared grader.

    Returns per-participant metrics plus the pooled human baseline, so the
    numbers are directly comparable to a model run in `results/`.
    """
    from benchmark.grade import grade_all, summarise

    by_id = {it["item_id"]: it for it in items}
    per_participant = []
    pooled_results = []

    for sub in submissions:
        answers = [a for a in sub.get("answers", []) if a.get("item_id") in by_id]
        item_order = [by_id[a["item_id"]] for a in answers]
        metrics = summarise(grade_all(item_order, answers))
        per_participant.append({
            "participant_id": sub.get("participant_id", "anon"),
            "group": sub.get("group", "unspecified"),
            "n_items": len(answers),
            **metrics,
        })
        pooled_results.extend(grade_all(item_order, answers))

    return {
        "n_participants": len(per_participant),
        "per_participant": per_participant,
        "pooled": summarise(pooled_results) if pooled_results else {},
    }


if __name__ == "__main__":       # pragma: no cover
    from benchmark.generate import generate_items
    its = [i.to_dict() for i in generate_items(n=40, seed=7)]
    open("human_form.html", "w", encoding="utf-8").write(build_form(its))
    print("wrote human_form.html")
