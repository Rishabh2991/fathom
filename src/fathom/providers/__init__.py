"""LLM providers. All use only the standard library (urllib) so Fathom installs offline."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import List, Optional

from fathom.config import Settings
from fathom.models import Context, Suggestion
from fathom.redact import redact

SYSTEM_PROMPT = """You are Fathom, an expert terminal co-pilot embedded in a user's shell.
You see the last command, its exit code and the tail of its output.
Predict what the user most likely wants to do NEXT and return 3-4 distinct options.
Rules:
- Each option is ONE runnable command for the user's OS and shell. No placeholders unless unavoidable.
- Order by likelihood. Prefer fixing an error over unrelated actions.
- Prefer safe, read-only diagnostics before destructive actions. Never suggest data-destroying commands
  unless the user's intent clearly requires it; label risk honestly.
- "why" is <= 12 words, plain English.
Reply with ONLY a JSON object, no prose:
{"suggestions":[{"command":"...","why":"...","risk":"safe|caution|danger"}]}"""


def build_prompt(ctx: Context, s: Settings) -> str:
    r = ctx.result
    tail = r.output[-s.output_tail_chars:]
    if s.redact:
        tail = redact(tail)
    recent = "\n".join(ctx.recent_commands[-5:]) or "(none)"
    cmd = redact(r.command) if s.redact else r.command
    return (
        f"OS: {ctx.os_name}\nShell: {ctx.shell}\nCWD: {r.cwd}\n"
        f"Project: {', '.join(ctx.project_types) or 'unknown'}\n"
        f"Git: {ctx.git_branch or 'n/a'}{' (dirty)' if ctx.git_dirty else ''}\n"
        f"Recent commands:\n{recent}\n\n"
        f"Last command ({r.source}): {cmd}\nExit code: {r.exit_code}\n"
        f"Output tail:\n```\n{tail}\n```"
    )


def parse_suggestions(text: str, source: str) -> List[Suggestion]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    items = data.get("suggestions", data if isinstance(data, list) else [])
    out = []
    for i, item in enumerate(items[:6]):
        if not isinstance(item, dict) or not str(item.get("command", "")).strip():
            continue
        risk = str(item.get("risk", "safe")).lower()
        out.append(Suggestion(
            command=str(item["command"]).strip().strip("`"),
            why=str(item.get("why", "")).strip(),
            risk=risk if risk in ("safe", "caution", "danger") else "safe",
            source=source,
            score=0.75 - i * 0.05,
        ))
    return out


def _post(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


class ProviderError(Exception):
    pass


def ask_ollama(prompt: str, s: Settings, system: str = SYSTEM_PROMPT, json_mode: bool = True) -> str:
    cfg = s.ollama
    data = _post(f"{cfg['host'].rstrip('/')}/api/chat", {
        "model": cfg["model"], "stream": False, **({"format": "json"} if json_mode else {}),
        "options": {"temperature": 0.2},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
    }, {}, s.timeout)
    return data.get("message", {}).get("content", "")


def ask_openai(prompt: str, s: Settings, system: str = SYSTEM_PROMPT, json_mode: bool = True) -> str:
    cfg = s.openai
    key = os.environ.get(cfg.get("api_key_env", "OPENAI_API_KEY"), "")
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    data = _post(f"{cfg['base_url'].rstrip('/')}/chat/completions", {
        "model": cfg["model"], "temperature": 0.2,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
    }, headers, s.timeout)
    return data["choices"][0]["message"]["content"]


def ask_anthropic(prompt: str, s: Settings, system: str = SYSTEM_PROMPT, json_mode: bool = True) -> str:
    cfg = s.anthropic
    key = os.environ.get(cfg.get("api_key_env", "ANTHROPIC_API_KEY"))
    if not key:
        raise ProviderError("ANTHROPIC_API_KEY not set")
    data = _post("https://api.anthropic.com/v1/messages", {
        "model": cfg["model"], "max_tokens": 800, "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }, {"x-api-key": key, "anthropic-version": "2023-06-01"}, s.timeout)
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


PROVIDERS = {"ollama": ask_ollama, "openai": ask_openai, "openai-local": ask_openai, "anthropic": ask_anthropic}


EXPLAIN_PROMPT = """You are Fathom, a terminal co-pilot. Explain in plain English, in at most 6 short lines,
what the command output means and the most likely root cause if it failed. No markdown headers."""

INTENT_PROMPT = """You are Fathom, a terminal co-pilot. The user describes a task in natural language.
Return 3 alternative commands for their OS and shell that accomplish it, safest first.
Reply with ONLY JSON: {"suggestions":[{"command":"...","why":"...","risk":"safe|caution|danger"}]}"""


def complete(prompt: str, s: Settings, system: str, json_mode: bool) -> tuple[str, Optional[str]]:
    """Run a free-form completion against the first provider that answers."""
    last_err = "no AI provider configured (rules-only mode)"
    for name in s.providers:
        fn = PROVIDERS.get(name)
        if not fn:
            continue
        try:
            text = fn(prompt, s, system, json_mode)
            if text.strip():
                return text, name
        except (urllib.error.URLError, OSError, ProviderError, KeyError, ValueError) as exc:
            last_err = f"{name}: {getattr(exc, 'reason', exc)}"
    return "", last_err


def explain(ctx: Context, s: Settings) -> tuple[str, Optional[str]]:
    return complete(build_prompt(ctx, s), s, EXPLAIN_PROMPT, False)


def from_intent(intent: str, ctx: Context, s: Settings) -> tuple[List[Suggestion], Optional[str]]:
    prompt = f"OS: {ctx.os_name}\nShell: {ctx.shell}\nCWD: {ctx.result.cwd}\n" \
             f"Project: {', '.join(ctx.project_types) or 'unknown'}\nTask: {intent}"
    text, info = complete(prompt, s, INTENT_PROMPT, True)
    return (parse_suggestions(text, f"ai:{info}"), info) if text else ([], info)


def ask_ai(ctx: Context, s: Settings) -> tuple[List[Suggestion], Optional[str]]:
    """Try configured AI providers in order. Returns (suggestions, provider_used_or_error)."""
    prompt = build_prompt(ctx, s)
    last_err = None
    for name in s.providers:
        fn = PROVIDERS.get(name)
        if not fn:
            continue
        try:
            text = fn(prompt, s)
            sugg = parse_suggestions(text, f"ai:{name}")
            if sugg:
                return sugg, name
            last_err = f"{name}: unparseable reply"
        except (urllib.error.URLError, OSError, ProviderError, KeyError, ValueError) as exc:
            last_err = f"{name}: {getattr(exc, 'reason', exc)}"
    return [], last_err


def check_provider(name: str, s: Settings) -> str:
    """Health check used by `fathom doctor`."""
    try:
        if name == "ollama":
            req = urllib.request.Request(f"{s.ollama['host'].rstrip('/')}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                models = [m["name"] for m in json.loads(resp.read()).get("models", [])]
            want = s.ollama["model"]
            if not any(m == want or m.startswith(want + ":") for m in models):
                return f"running, but model '{want}' not pulled -> ollama pull {want}"
            return f"ok ({want})"
        if name in ("openai", "openai-local"):
            req = urllib.request.Request(f"{s.openai['base_url'].rstrip('/')}/models")
            key = os.environ.get(s.openai.get("api_key_env", ""), "")
            if key:
                req.add_header("Authorization", f"Bearer {key}")
            urllib.request.urlopen(req, timeout=3).close()
            return "ok"
        if name == "anthropic":
            return "ok (key set)" if os.environ.get(s.anthropic.get("api_key_env", "")) else "ANTHROPIC_API_KEY not set"
        if name == "rules":
            return "ok (built in, always offline)"
    except Exception as exc:  # noqa: BLE001
        return f"unreachable ({getattr(exc, 'reason', exc)})"
    return "unknown provider"
