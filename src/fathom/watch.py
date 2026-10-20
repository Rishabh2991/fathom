"""`fathom watch`: tail logs and suggest actions when errors appear."""

from __future__ import annotations

import os
import re
import sys
import time
from typing import Iterator, List, TextIO

from fathom import engine, ui
from fathom.config import Settings
from fathom.context import build_context
from fathom.models import CommandResult

ERROR_RE = re.compile(
    r"(?i)\b(error|fatal|critical|panic|exception|traceback|segfault|oom|out of memory|killed|"
    r"refused|timed? ?out|denied|unhealthy|crashloop)\b|\s5\d\d\s"
)


def follow(fh: TextIO, from_start: bool = False) -> Iterator[str]:
    if not from_start and fh is not sys.stdin:
        fh.seek(0, os.SEEK_END)
    while True:
        line = fh.readline()
        if line:
            yield line
            continue
        if fh is sys.stdin:
            return
        time.sleep(0.25)


def watch(path: str, s: Settings, burst_window: float = 2.0, context_lines: int = 30,
          from_start: bool = False, once: bool = False) -> int:
    fh = sys.stdin if path == "-" else open(path, encoding="utf-8", errors="replace")
    label = "stdin" if path == "-" else path
    print(ui.dim(f"watching {label} for errors · Ctrl-C to stop"))
    buf: List[str] = []
    burst: List[str] = []
    burst_start = 0.0
    last_sig = ""

    def flush() -> bool:
        nonlocal burst, last_sig
        if not burst:
            return False
        window = "".join(buf[-context_lines:])
        first = burst[0]
        sig = re.sub(r"\d+", "#", first)[:120]
        burst = []
        if sig == last_sig:  # don't repeat ourselves for the same recurring error
            return False
        last_sig = sig
        result = CommandResult(command=f"tail -f {label}", exit_code=1, output=window, cwd=os.getcwd(), source="log")
        res = engine.suggest(build_context(result), s, None)
        print(ui.c("\n▲ ", "31") + ui.bold("error detected: ") + first.strip()[:120])
        print(ui.render(res.suggestions, f"ai: {res.ai_used}" if res.ai_used else "offline rules"))
        return True

    try:
        for line in follow(fh, from_start):
            buf.append(line)
            buf = buf[-500:]
            if ERROR_RE.search(line):
                if not burst:
                    burst_start = time.time()
                burst.append(line)
            if burst and time.time() - burst_start > burst_window:
                if flush() and once:
                    return 0
        if flush() and once:
            return 0
    except KeyboardInterrupt:
        print()
    finally:
        if fh is not sys.stdin:
            fh.close()
    return 0
