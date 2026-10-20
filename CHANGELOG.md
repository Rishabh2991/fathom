# Changelog

## 0.1.0 — 2026-10-20

First public release.

- Interactive shell with live output capture (PTY on macOS/Linux, pipes on Windows)
- 3-4 ranked next-step suggestions after every command; pick with a single key
- Offline rule engine covering git, Python, Node, Docker, Kubernetes, systemd, ports, DNS, permissions, missing commands and paths
- AI providers: Ollama, any OpenAI-compatible server (llama.cpp, LM Studio, vLLM), Anthropic
- `--offline` mode, secret redaction, risk gating, local learning from your choices
- `fathom watch` for log files and streams, `fathom explain` for piped output
- Shell hooks (zsh, bash, PowerShell) and `fathom suggest --json` for editors and GUIs
