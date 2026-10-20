"""Core data types shared across Fathom."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class CommandResult:
    command: str
    exit_code: int
    output: str  # combined stdout+stderr tail
    cwd: str
    duration: float = 0.0
    source: str = "shell"  # shell | pipe | log

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass
class Suggestion:
    command: str
    why: str
    risk: str = "safe"  # safe | caution | danger
    source: str = "rules"  # rules | ai:<provider> | memory
    score: float = 0.5

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Context:
    result: CommandResult
    os_name: str
    shell: str
    project_types: List[str] = field(default_factory=list)
    git_branch: Optional[str] = None
    git_dirty: bool = False
    recent_commands: List[str] = field(default_factory=list)
