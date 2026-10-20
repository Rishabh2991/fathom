<div align="center">

# 🧭 Fathom

**The shell that reads the room.**
Run a command. Fathom reads the output, figures out what just happened, and offers your next 3–4 moves. Press a number.

Works on your laptop and on a headless server over SSH. Works with no internet, no GPU and no model at all.

[![CI](https://github.com/YOUR_GITHUB_USERNAME/fathom/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_GITHUB_USERNAME/fathom/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/fathom-shell)](https://pypi.org/project/fathom-shell/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Platforms](https://img.shields.io/badge/platforms-linux%20%7C%20macOS%20%7C%20windows-informational)
![Offline](https://img.shields.io/badge/works-offline-success)

<!-- Record with: vhs docs/demo.tape  → docs/demo.gif -->
<img src="docs/demo.gif" alt="Fathom demo" width="760">

</div>

```text
● ~/api (main) fathom❯ git push
fatal: The current branch feature/login has no upstream branch.
╭─ next moves  · ai: ollama
│ [1] git push --set-upstream origin feature/login
│     Publish this branch and track it  (offline+ai)
│ [2] git log --oneline origin/main..HEAD
│     See which commits you're about to push  (ollama)
│ [3] gh pr create --fill
│     Open a pull request once it's pushed  (ollama)
╰─ 1-4 run · e<n> edit · ? explain · enter skip
● ~/api (main) fathom❯ 1
```

## Why Fathom

Most AI terminal tools want you to switch to their terminal app, sign in, and send your output to a cloud model. That's a non-starter on a production box, inside a bank, or on a plane.

Fathom is a **shell layer**, not a terminal app:

- 🖥️ **Runs anywhere Python runs** — or as a single static binary. macOS, Linux, Windows, over SSH, inside tmux, in a container.
- ✈️ **Offline first.** Default brain is a local model via [Ollama](https://ollama.com) or any llama.cpp/LM Studio/vLLM server. With no model at all, a built-in rule engine still covers the everyday errors (git, Python, Node, Docker, Kubernetes, systemd, ports, DNS, permissions).
- 🔒 **Private by design.** Secrets are redacted before output reaches *any* model. `--offline` hard-blocks the network. Nothing is ever executed without a keypress.
- 🛡️ **Risk gating.** Every suggestion is classified `safe` / `caution` / `danger` by a local classifier. A model cannot talk its way past it: `rm -rf /` needs you to type `yes`.
- 🧠 **Learns you, locally.** Pick the same fix twice in the same situation and it rises to the top next time. Stored in a plain JSONL file you own.
- 📜 **Watches logs, not just commands.** `fathom watch /var/log/app.log` tails a file and proposes actions when errors burst.
- 🧩 **Zero required dependencies.** Standard library only, so it installs on air-gapped machines.

## Install

```bash
pipx install fathom-shell          # or: pip install fathom-shell
```

No Python on the box? Grab a single binary from [Releases](../../releases) (Linux x86_64/arm64, macOS, Windows).

Optional local AI (recommended):

```bash
# https://ollama.com/download, then:
ollama pull qwen2.5-coder:3b       # small, fast, good at shell
fathom doctor                      # confirms everything is wired up
```

## Use it

| You type | What happens |
|---|---|
| `fathom` | Start the interactive shell. Use it like your normal shell. |
| `1`…`4` | Run that suggestion (with confirmation if risky). |
| `e2` | Edit suggestion 2 before running it. |
| `?` | Plain-English explanation of the last output. |
| `# find files over 1GB modified this week` | Natural language → 3 candidate commands. |
| `!cmd` | Run without suggestions. |
| `:ai off` | Rules only for this session. |
| `fathom run -- make deploy` | One-shot: run, then suggest. |
| `make 2>&1 \| fathom explain` | Explain piped output from any shell. |
| `fathom watch /var/log/nginx/error.log` | Tail a log and suggest fixes when errors appear. |
| `journalctl -fu api \| fathom watch -` | Same, from a stream. |
| `eval "$(fathom hook zsh)"` | **Lite mode**: suggestions after failures in your *existing* zsh/bash/PowerShell. |
| `fathom suggest --cmd "npm test" --exit 1 --json < out.txt` | JSON API for editors, IDEs and GUIs. |

### Air-gapped / offline

```bash
fathom --offline           # or export FATHOM_OFFLINE=1
```

Only on-machine providers (Ollama, local OpenAI-compatible server, rules) are used. Everything else is skipped, never attempted.

## Configure

`fathom init` writes `~/.config/fathom/config.toml` (`%APPDATA%\fathom` on Windows):

```toml
providers = ["ollama", "rules"]     # tried in order; "rules" is the offline floor
max_suggestions = 4
redact = true
learn = true

[ollama]
host = "http://localhost:11434"
model = "qwen2.5-coder:3b"

[openai]          # OpenAI, llama.cpp server, LM Studio, vLLM...
base_url = "http://localhost:8080/v1"
model = "local-model"

[anthropic]
model = "claude-haiku-5-5"
```

Cloud providers are opt-in: add `"anthropic"` or `"openai"` to `providers` and set the API key env var.

## How it works

```
command ─► runner (PTY: colours & interactive apps keep working)
              │ exit code + output tail
              ▼
          context (OS, shell, git branch, project type, recent commands)
              │
      ┌───────┼────────────────┐
      ▼       ▼                ▼
   memory   rules (offline)   model (local or cloud, secrets redacted)
      └───────┬────────────────┘
              ▼
   merge → dedupe → agreement boost → safety classifier → top 3-4
```

When the rules are already ≥90% sure about a failure, the model call is skipped entirely — so common errors get instant answers.

## Compared with

| | Fathom | Terminal apps with AI | Chat-style CLI wrappers | `thefuck` |
|---|---|---|---|---|
| Proactive suggestions after every command | ✅ | varies | ❌ you ask | after failures only |
| Works on headless servers / over SSH | ✅ | ❌ desktop app | ✅ | ✅ |
| Works with no model at all | ✅ rules | ❌ | ❌ | ✅ |
| Local models | ✅ | varies | varies | n/a |
| Tails logs | ✅ | ❌ | ❌ | ❌ |
| Learns your choices locally | ✅ | ❌ | ❌ | ❌ |

## Contributing

The fastest way to help is to teach Fathom a new error: one function, one test. See [CONTRIBUTING.md](CONTRIBUTING.md) and the [`new-rule`](../../labels/new-rule) issues. Roadmap: [ROADMAP.md](ROADMAP.md).

If Fathom saved you a trip to Stack Overflow, a ⭐ helps others find it.

## License

[MIT](LICENSE)
