# Roadmap

Fathom's bet: **the best terminal AI is the one you can run everywhere** — on a laptop, a
bastion host, a CI runner, an air-gapped cluster — and that gets *proactively* useful without
you having to ask. Everything below is chosen to widen that gap.

## v0.2 — Desktop GUI (shares the same engine)

- **Fathom Desktop**: a Tauri app (small, native, offline) embedding a real terminal (xterm.js)
  with a side panel of suggestion cards, an "explain" drawer and a timeline of the session.
  It talks to the engine through `fathom suggest --json`, so the CLI and GUI never diverge.
- Click-to-run cards, drag a suggestion into the prompt to edit it.
- Bundled small model download on first run, so the GUI is offline out of the box.

## Standout features (what nobody else combines)

### 1. Runbooks that write themselves
Fathom already sees every command and its outcome. `fathom record` turns a session into a
**replayable runbook** (Markdown + steps that can be re-run with confirmation). Incidents become
documentation automatically; `fathom replay incident-0412.md` walks the next on-call through it.

### 2. Team knowledge packs (offline, shareable)
Export your learned memory and custom rules as a signed pack: `fathom pack export --team sre`.
Ship it to every server in your fleet via Ansible. New hires get the team's muscle memory on day one —
with no SaaS, no data leaving the company.

### 3. "What changed?" diffing
When a command that used to succeed now fails, Fathom diffs the environment between the last
good run and now (package versions, env vars, git HEAD, config files, disk, ports) and leads with
the most suspicious change. This is the single most common debugging question and nobody automates it.

### 4. Dry-run previews
For `caution` commands, show a preview before you confirm: files `rm` would delete, the
`terraform plan` summary, the `kubectl diff`, the rows a SQL `DELETE` would touch.

### 5. Multi-host awareness
Over SSH, Fathom on your laptop and Fathom on the server cooperate: the remote side captures output,
the local side runs the bigger model. Your GPU helps your servers without the servers needing one.

### 6. Log anomaly baselining
`fathom watch` learns what "normal" looks like for a log (rate, templates) and alerts on
new error *shapes* rather than every ERROR line. Optional webhook/Slack/ntfy notification.

### 7. Plugin rules in any language
Rules as small executables on `$PATH` (`fathom-rule-*`) that read JSON on stdin and return
suggestions — so a Go shop or a Rust shop can contribute without writing Python.

### 8. MCP server
Expose Fathom as a Model Context Protocol server so coding agents and IDEs can ask "what should
happen next in this terminal?" and get safety-classified answers.

### 9. Policy mode for enterprises
A signed `policy.toml` that admins push: forbidden commands, required confirmations, providers
allowed (e.g. "local only"), audit log of every executed suggestion. This is what gets Fathom
approved inside regulated companies.

### 10. Accessibility & teaching mode
Screen-reader-friendly output, and a "teach me" mode that explains *why* each suggestion works —
turning Fathom into a terminal tutor for students and new engineers.

## Smaller items

- [ ] `pyreadline3` auto-install on Windows for history/editing
- [ ] fish and nushell hooks
- [ ] Rule packs: Terraform, Ansible, AWS CLI, gcloud, Helm, Postgres, Rust/cargo, Go, Java/Maven
- [ ] Streaming model output so the first suggestion appears sooner
- [ ] Homebrew tap, Scoop/winget manifests, `.deb`/`.rpm`, Docker image, Nix flake
- [ ] Benchmark suite: a corpus of real errors with expected fixes, scored per model — publish the leaderboard
- [ ] i18n of explanations
