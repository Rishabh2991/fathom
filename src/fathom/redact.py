"""Scrub secrets from text before it is shown to any model."""

from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[PRIVATE_KEY]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[AWS_ACCESS_KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"), "[GITHUB_TOKEN]"),
    (re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_\-]{20,}\b"), "[API_KEY]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "[SLACK_TOKEN]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "[JWT]"),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-]{16,}"), r"\1 [TOKEN]"),
    (re.compile(r"(?i)((?:password|passwd|pwd|secret|token|api[_-]?key)\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)"),
     r"\1[REDACTED]"),
    (re.compile(r"([a-z][a-z0-9+.-]*://[^:/\s@]+:)[^@\s]+(@)", re.I), r"\1[REDACTED]\2"),
]


def redact(text: str) -> str:
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text
