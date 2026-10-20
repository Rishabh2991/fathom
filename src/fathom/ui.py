"""Terminal rendering. Uses `rich` when installed, plain ANSI otherwise (servers, CI)."""

from __future__ import annotations

import os
import sys
from typing import List

from fathom.models import Suggestion

_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None and os.environ.get("TERM") != "dumb"
if sys.platform == "win32" and _COLOR:  # enable VT processing on Windows 10+
    os.system("")


def c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def dim(t: str) -> str:
    return c(t, "2")


def bold(t: str) -> str:
    return c(t, "1")


RISK_BADGE = {"safe": ("", "32"), "caution": (" ⚠ caution", "33"), "danger": (" ⛔ danger", "31")}
SOURCE_TAG = {"rules": "offline", "memory": "learned"}


def render(suggestions: List[Suggestion], status: str = "") -> str:
    if not suggestions:
        return ""
    lines = [c("╭─ ", "36") + bold("next moves") + (dim(f"  · {status}") if status else "")]
    for i, s in enumerate(suggestions, 1):
        badge, color = RISK_BADGE.get(s.risk, ("", "0"))
        tag = "+".join(SOURCE_TAG.get(p, p.replace("ai:", "")) for p in s.source.split("+"))
        lines.append(c("│ ", "36") + c(f"[{i}] ", "36;1") + c(s.command, color if s.risk != "safe" else "1")
                     + c(badge, color))
        lines.append(c("│     ", "36") + dim(f"{s.why}  ({tag})"))
    lines.append(c("╰─ ", "36") + dim("1-4 run · e<n> edit · ? explain · enter skip"))
    return "\n".join(lines)


def prompt_str(cwd: str, branch: str | None, last_ok: bool | None) -> str:
    home = os.path.expanduser("~")
    path = "~" + cwd[len(home):] if cwd.startswith(home) else cwd
    mark = c("●", "32") if last_ok in (True, None) else c("●", "31")
    br = c(f" ({branch})", "35") if branch else ""
    # \001 \002 tell readline the escape codes take no width
    if _COLOR and sys.platform != "win32":
        def wrap(s: str) -> str:
            import re
            return re.sub(r"(\033\[[0-9;]*m)", "\001\\1\002", s)
    else:
        def wrap(s: str) -> str:
            return s
    return wrap(f"{mark} {c(path, '34;1')}{br} {c('fathom', '36')}{c('❯', '36;1')} ")
