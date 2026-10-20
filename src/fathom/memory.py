"""Local, private learning: remember which suggestion you picked in which situation.

Nothing here ever leaves the machine. The store is a plain JSONL file you can read,
grep or delete (~/.config/fathom/memory.jsonl).
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import List

from fathom.config import config_dir
from fathom.models import Context, Suggestion


def signature(ctx: Context) -> str:
    """A coarse fingerprint of the situation: tool + outcome + the error's shape."""
    cmd = ctx.result.command.strip().split()
    tool = " ".join(cmd[:2]) if cmd[:1] in (["git"], ["docker"], ["kubectl"], ["npm"], ["cargo"]) else (cmd[0] if cmd else "")
    err = ""
    for line in reversed(ctx.result.output.strip().splitlines()[-15:]):
        if re.search(r"(?i)error|fail|denied|not found|refused|cannot|fatal", line):
            err = re.sub(r"[\d/\\'\"`:]+", "", line.lower())[:60].strip()
            break
    return f"{tool}|{'ok' if ctx.result.ok else 'fail'}|{err}"


class Memory:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config_dir() / "memory.jsonl")

    def record(self, ctx: Context, chosen: Suggestion) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": int(time.time()), "sig": signature(ctx), "cmd": chosen.command,
                                 "why": chosen.why, "risk": chosen.risk}) + "\n")

    def recall(self, ctx: Context, limit: int = 2) -> List[Suggestion]:
        if not self.path.exists():
            return []
        sig = signature(ctx)
        counts: Counter = Counter()
        meta = {}
        try:
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if row.get("sig") == sig:
                        counts[row["cmd"]] += 1
                        meta[row["cmd"]] = row
        except OSError:
            return []
        out = []
        for cmd, n in counts.most_common(limit):
            row = meta[cmd]
            out.append(Suggestion(cmd, f"You chose this {n}x in this situation", row.get("risk", "safe"),
                                  "memory", min(0.95, 0.6 + 0.1 * n)))
        return out
