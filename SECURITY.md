# Security Policy

Fathom runs commands and reads terminal output, so security reports are taken seriously.

## Reporting

Please **do not** open a public issue. Use GitHub's
[private vulnerability reporting](../../security/advisories/new) instead. You'll get a response
within 72 hours.

## Design principles

- **Nothing runs without a keypress.** Suggestions are never auto-executed.
- **Risk gating.** `caution` commands need `y`; `danger` commands need the word `yes`.
  The safety classifier runs on every suggestion, so a model can never downgrade risk.
- **Secrets are redacted** (API keys, tokens, passwords, private keys, credentials in URLs)
  before any output reaches a model — local or cloud.
- **Offline by default.** The default provider chain is local Ollama, then built-in rules.
  `--offline` / `FATHOM_OFFLINE=1` hard-disables every network provider.
- **Local-only memory.** Learned choices live in a plain JSONL file you can inspect or delete (`:forget`).
- **Prompt injection.** Log lines and command output are treated as data; suggestions from
  a model are shown, classified and confirmed — never executed blindly.
