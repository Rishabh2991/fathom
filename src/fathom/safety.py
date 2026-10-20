"""Risk classification so a suggested command can never wreck a box with one keypress."""

from __future__ import annotations

import re

DANGER = [
    r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b.*(\s/\s*$|\s/\*|\s~\s*$|\s\$HOME)",
    r"\bmkfs(\.\w+)?\b",
    r"\bdd\b.*\bof=/dev/",
    r":\(\)\s*\{\s*:\|:&\s*\};:",
    r"\bchmod\s+-R\s+777\s+/",
    r"\b(shutdown|reboot|halt|poweroff)\b",
    r"(?i)\bdrop\s+(database|table)\b",
    r"(?i)\btruncate\s+table\b",
    r"\bformat\s+[a-zA-Z]:",
    r"(?i)\bRemove-Item\b.*-Recurse.*-Force.*[A-Z]:\\\s*$",
    r">\s*/dev/sd[a-z]",
    r"\bcurl\b[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b",
    r"\bwget\b[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b",
]

CAUTION = [
    r"\brm\b",
    r"\bsudo\b",
    r"\bgit\s+push\b.*(--force|-f\b)",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\b.*-[a-z]*f",
    r"\bkubectl\s+delete\b",
    r"\bdocker\s+(system\s+prune|rm|rmi)\b",
    r"\bterraform\s+(apply|destroy)\b",
    r"\bkill(all)?\b",
    r"\bchmod\b|\bchown\b",
    r"\bmv\b",
    r"(?i)\bRemove-Item\b",
    r"\bdel\b|\brmdir\b",
]


def classify(command: str) -> str:
    for p in DANGER:
        if re.search(p, command):
            return "danger"
    for p in CAUTION:
        if re.search(p, command):
            return "caution"
    return "safe"


def stricter(a: str, b: str) -> str:
    order = {"safe": 0, "caution": 1, "danger": 2}
    return a if order.get(a, 0) >= order.get(b, 0) else b
