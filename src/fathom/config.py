"""Configuration: ~/.config/fathom/config.toml, overridable by FATHOM_* env vars."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

try:  # Python 3.11+
    import tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def config_dir() -> Path:
    if os.environ.get("FATHOM_HOME"):
        return Path(os.environ["FATHOM_HOME"])
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "fathom"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "fathom"


def normalize_localhost(url: str) -> str:
    if not url:
        return url
    return re.sub(r"(?<=://)localhost(?=[:/]|$)", "127.0.0.1", url)


DEFAULT_TOML = """# Fathom configuration
# Providers are tried in order; the first one that answers wins.
# "rules" is the built-in offline engine and needs no model at all.
providers = ["ollama", "rules"]

# Max suggestions shown after each command (3-4 recommended)
max_suggestions = 4

# Ask the AI after successful commands too (not just failures)
suggest_on_success = true

# Characters of output tail sent to the model
output_tail_chars = 4000

# Redact secrets (keys, tokens, passwords) before anything leaves the machine
redact = true

# Remember which suggestions you pick and rank them higher next time (stored locally)
learn = true

[ollama]
host = "http://127.0.0.1:11434"
model = "qwen2.5-coder:3b"

[openai]   # any OpenAI-compatible server: OpenAI, llama.cpp server, LM Studio, vLLM
base_url = "http://127.0.0.1:8080/v1"
model = "local-model"
api_key_env = "OPENAI_API_KEY"

[anthropic]
model = "claude-haiku-5-5"
api_key_env = "ANTHROPIC_API_KEY"
"""


@dataclass
class Settings:
    providers: List[str] = field(default_factory=lambda: ["ollama", "rules"])
    max_suggestions: int = 4
    suggest_on_success: bool = True
    output_tail_chars: int = 4000
    redact: bool = True
    learn: bool = True
    timeout: float = 20.0
    ollama: dict = field(default_factory=lambda: {"host": "http://127.0.0.1:11434", "model": "qwen2.5-coder:3b"})
    openai: dict = field(default_factory=lambda: {
        "base_url": "http://127.0.0.1:8080/v1", "model": "local-model", "api_key_env": "OPENAI_API_KEY"})
    anthropic: dict = field(default_factory=lambda: {"model": "claude-haiku-5-5", "api_key_env": "ANTHROPIC_API_KEY"})

    def __post_init__(self):
        self.ollama["host"] = normalize_localhost(self.ollama.get("host", "http://127.0.0.1:11434"))
        self.openai["base_url"] = normalize_localhost(self.openai.get("base_url", "http://127.0.0.1:8080/v1"))

    @property
    def offline(self) -> bool:
        return os.environ.get("FATHOM_OFFLINE", "").lower() in ("1", "true", "yes")


def config_path() -> Path:
    return config_dir() / "config.toml"


def ensure_config() -> Path:
    path = config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_TOML, encoding="utf-8")
    return path


def load_settings(path: Path | None = None) -> Settings:
    s = Settings()
    path = path or config_path()
    if path.exists():
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
        for key, value in data.items():
            if hasattr(s, key):
                current = getattr(s, key)
                if isinstance(current, dict) and isinstance(value, dict):
                    current.update(value)
                else:
                    setattr(s, key, value)
    env_providers = os.environ.get("FATHOM_PROVIDERS")
    if env_providers:
        s.providers = [p.strip() for p in env_providers.split(",") if p.strip()]
    if os.environ.get("FATHOM_MODEL"):
        s.ollama["model"] = os.environ["FATHOM_MODEL"]
    s.__post_init__()
    if s.offline:
        # Offline mode: only providers that never leave the machine.
        s.providers = [p for p in s.providers if p in ("ollama", "rules", "openai-local")] or ["rules"]
    return s
