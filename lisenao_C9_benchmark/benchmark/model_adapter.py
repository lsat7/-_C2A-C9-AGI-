"""
MetaCal — Model Adapters
================================================================
Three ways to run MetaCal against a model:

1. `OpenAICompatAdapter` — any OpenAI-compatible chat endpoint
   (OpenAI, DeepSeek, Moonshot, vLLM, Ollama, ...). Set base_url + api_key.

2. `AnthropicAdapter` — Anthropic Messages API.

3. `SimulatedAdapter` — a *behavioural simulator* used for pipeline
   self-test, synthetic baselines, and CI. It is NOT a substitute for a real
   model run; every simulated run is stamped as such in the output.

All adapters expose `respond(prompt) -> raw_text`, and the runner handles
parsing + grading.

Author : lisenao (李思脑)
License: MIT
"""

from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from benchmark.prompt import SYSTEM_PROMPT


class BaseAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def respond(self, prompt: str) -> str:  # pragma: no cover
        ...

    def respond_batch(self, prompts: List[str],
                      sleep: float = 0.0) -> List[str]:
        out = []
        for p in prompts:
            out.append(self.respond(p))
            if sleep:
                time.sleep(sleep)
        return out


# --------------------------------------------------------------------------
# 1. OpenAI-compatible
# --------------------------------------------------------------------------

class OpenAICompatAdapter(BaseAdapter):
    """Works with OpenAI / DeepSeek / Moonshot / vLLM / Ollama / LM Studio."""

    def __init__(self, model: str, base_url: str = "https://api.openai.com/v1",
                 api_key: Optional[str] = None, temperature: float = 0.0,
                 max_tokens: int = 400, timeout: int = 90,
                 name: Optional[str] = None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.name = name or f"openai-compat:{model}"

    def respond(self, prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:                 # pragma: no cover
            detail = e.read().decode("utf-8", "ignore")[:300]
            raise RuntimeError(f"HTTP {e.code} from {url}: {detail}") from e


# --------------------------------------------------------------------------
# 2. Anthropic
# --------------------------------------------------------------------------

class AnthropicAdapter(BaseAdapter):
    def __init__(self, model: str = "claude-sonnet-4-20250514",
                 api_key: Optional[str] = None, temperature: float = 0.0,
                 max_tokens: int = 400, timeout: int = 90,
                 name: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.name = name or f"anthropic:{model}"

    def respond(self, prompt: str) -> str:
        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return "".join(b.get("text", "") for b in body.get("content", []))
        except urllib.error.HTTPError as e:                 # pragma: no cover
            detail = e.read().decode("utf-8", "ignore")[:300]
            raise RuntimeError(f"HTTP {e.code} from {url}: {detail}") from e


# --------------------------------------------------------------------------
# 3. Simulated behavioural baselines
# --------------------------------------------------------------------------

# Each profile encodes a behavioural prior: base accuracy per family, the
# confidence gap (pred − realised accuracy) and the probability of choosing
# the appropriate strategy. These numbers are *literature-motivated orderings*
# chosen to span the plausible frontier-model range so the pipeline can be
# validated end-to-end. They are synthetic and must never be reported as
# measurements of a real model.
SIM_PROFILES: Dict[str, Dict[str, Any]] = {
    "sim-naive": {
        "desc": "Uniformly overconfident; answers everything, never abstains.",
        "acc": {"SI": 0.88, "UI": 0.05, "FT": 0.08, "TK": 0.18},
        "conf": {"SI": 0.96, "UI": 0.90, "FT": 0.88, "TK": 0.85},
        "strategy_ok": {"SI": 0.95, "UI": 0.05, "FT": 0.08, "TK": 0.60},
        "post_gap": 0.06,
    },
    "sim-hedger": {
        "desc": "Hedges constantly; moderate calibration, poor discrimination.",
        "acc": {"SI": 0.82, "UI": 0.22, "FT": 0.26, "TK": 0.28},
        "conf": {"SI": 0.70, "UI": 0.62, "FT": 0.64, "TK": 0.60},
        "strategy_ok": {"SI": 0.60, "UI": 0.42, "FT": 0.45, "TK": 0.62},
        "post_gap": 0.05,
    },
    "sim-calibrated": {
        "desc": "Well-calibrated; abstains when premise is insufficient.",
        "acc": {"SI": 0.94, "UI": 0.62, "FT": 0.55, "TK": 0.42},
        "conf": {"SI": 0.92, "UI": 0.58, "FT": 0.52, "TK": 0.48},
        "strategy_ok": {"SI": 0.90, "UI": 0.86, "FT": 0.82, "TK": 0.78},
        "post_gap": 0.07,
    },
    "sim-expert": {
        "desc": "Strong metacognition; accurate prediction and behaviour.",
        "acc": {"SI": 0.97, "UI": 0.82, "FT": 0.78, "TK": 0.58},
        "conf": {"SI": 0.95, "UI": 0.80, "FT": 0.76, "TK": 0.60},
        "strategy_ok": {"SI": 0.94, "UI": 0.93, "FT": 0.91, "TK": 0.88},
        "post_gap": 0.05,
    },
}


class SimulatedAdapter(BaseAdapter):
    """Behavioural simulator. Emits well-formed MetaCal JSON."""

    def __init__(self, profile: str = "sim-calibrated", seed: int = 7,
                 name: Optional[str] = None):
        if profile not in SIM_PROFILES:
            raise ValueError(f"unknown profile {profile!r}; "
                             f"choose from {list(SIM_PROFILES)}")
        self.profile_key = profile
        self.p = SIM_PROFILES[profile]
        self.rng = random.Random(seed)
        self.name = name or profile
        self._item_family: Optional[str] = None

    # the runner injects the current item so the simulator can branch on family
    def set_context(self, family: str, gold: str) -> None:
        self._item_family = family
        self._gold = gold

    def respond(self, prompt: str) -> str:
        fam = self._item_family or "SI"
        rng = self.rng
        p = self.p

        answered_correctly = rng.random() < p["acc"][fam]
        wants_ok_strategy = rng.random() < p["strategy_ok"][fam]

        correct_strategy = "ANSWER" if fam in ("SI", "TK") else "ABSTAIN"
        if wants_ok_strategy:
            strategy = correct_strategy
        else:
            strategy = rng.choice([s for s in ("ANSWER", "HEDGE", "ABSTAIN")
                                   if s != correct_strategy])

        if strategy == "ABSTAIN":
            answer = "无法确定"
        elif answered_correctly:
            answer = self._gold
        else:
            answer = self._wrong_answer(fam)

        base = p["conf"][fam]
        jitter = rng.uniform(-0.10, 0.10)
        pred = min(max(base + jitter, 0.02), 0.99)
        post = min(max(pred - p["post_gap"] + rng.uniform(-0.05, 0.05), 0.02), 0.99)

        return json.dumps({
            "pred": int(round(pred * 100)),
            "strategy": strategy,
            "answer": answer,
            "post": int(round(post * 100)),
        }, ensure_ascii=False)

    def _wrong_answer(self, fam: str) -> str:
        if fam == "SI":
            return str(self.rng.randint(8, 400))
        if fam == "UI":
            return str(self.rng.randint(1, 40))
        if fam == "FT":
            return f"{self.rng.randint(1, 30)}%"
        return str(self.rng.randint(1, 40))


# --------------------------------------------------------------------------
# Factory
# --------------------------------------------------------------------------

def make_adapter(spec: str, **kwargs) -> BaseAdapter:
    """Build an adapter from a CLI spec.

    spec examples:
        sim:sim-calibrated
        openai:gpt-4o-mini
        deepseek:deepseek-chat
        anthropic:claude-sonnet-4-20250514
        https://my.endpoint/v1|my-model
    """
    if spec.startswith("sim:"):
        kwargs.pop("temperature", None)
        kwargs.pop("api_key", None)
        return SimulatedAdapter(profile=spec.split(":", 1)[1], **kwargs)

    if spec.startswith("openai:"):
        return OpenAICompatAdapter(model=spec.split(":", 1)[1],
                                   base_url="https://api.openai.com/v1", **kwargs)

    if spec.startswith("deepseek:"):
        return OpenAICompatAdapter(model=spec.split(":", 1)[1],
                                   base_url="https://api.deepseek.com/v1", **kwargs)

    if spec.startswith("moonshot:"):
        return OpenAICompatAdapter(model=spec.split(":", 1)[1],
                                   base_url="https://api.moonshot.cn/v1", **kwargs)

    if spec.startswith("anthropic:"):
        return AnthropicAdapter(model=spec.split(":", 1)[1], **kwargs)

    if "|" in spec:
        base_url, model = spec.split("|", 1)
        return OpenAICompatAdapter(model=model, base_url=base_url, **kwargs)

    raise ValueError(f"unrecognised adapter spec: {spec!r}")
