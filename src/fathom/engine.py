"""Combine rules, memory and AI into one short, ranked, safety-checked list."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from fathom import providers, safety
from fathom.config import Settings
from fathom.memory import Memory
from fathom.models import Context, Suggestion
from fathom.rules import run_rules


@dataclass
class EngineResult:
    suggestions: List[Suggestion]
    ai_used: Optional[str] = None
    ai_error: Optional[str] = None


def _norm(cmd: str) -> str:
    return " ".join(cmd.split()).rstrip(";")


def merge(groups: List[List[Suggestion]], limit: int) -> List[Suggestion]:
    best: dict = {}
    for group in groups:
        for s in group:
            key = _norm(s.command)
            if not key:
                continue
            s.risk = safety.stricter(s.risk, safety.classify(s.command))
            if key in best:
                # Agreement between sources is a strong signal.
                best[key].score = min(1.0, max(best[key].score, s.score) + 0.1)
                if best[key].source != s.source and "+" not in best[key].source:
                    best[key].source += f"+{s.source.split(':')[0]}"
            else:
                best[key] = s
    ranked = sorted(best.values(), key=lambda x: (-x.score, {"safe": 0, "caution": 1, "danger": 2}[x.risk]))
    return ranked[:limit]


def suggest(ctx: Context, s: Settings, memory: Optional[Memory] = None, use_ai: bool = True) -> EngineResult:
    rule_s = run_rules(ctx)  # always on: the offline floor under every answer
    mem_s = memory.recall(ctx) if (memory and s.learn) else []
    ai_s: List[Suggestion] = []
    ai_used = ai_err = None
    wants_ai = use_ai and any(p != "rules" for p in s.providers)
    if wants_ai and (not ctx.result.ok or s.suggest_on_success):
        # Skip the model when rules are already confident about a failure fix.
        confident = any(x.score >= 0.9 for x in rule_s)
        if not confident or ctx.result.ok:
            ai_s, info = providers.ask_ai(ctx, s)
            if ai_s:
                ai_used = info
            else:
                ai_err = info
    return EngineResult(merge([mem_s, rule_s, ai_s], s.max_suggestions), ai_used, ai_err)
