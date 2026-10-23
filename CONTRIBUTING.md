# Contributing to Fathom

Thanks for helping! Fathom is deliberately easy to hack on: pure Python, zero required
dependencies, and the most valuable contributions are small.

## Setup

```bash
git clone https://github.com/Rishabh2991/fathom && cd fathom
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q && ruff check src tests
```

## The easiest high-impact contribution: a rule

Rules live in `src/fathom/rules.py`. They are the offline brain — they work with no model,
on any server, instantly. If you've ever hit an error and thought "the fix is always X",
that's a rule.

```python
@rule
def terraform_lock(ctx: Context) -> List[Suggestion]:
    if "Error acquiring the state lock" not in ctx.result.output:
        return []
    m = re.search(r"ID:\s+(\S+)", ctx.result.output)
    return [S(f"terraform force-unlock {m.group(1) if m else 'LOCK_ID'}",
              "A previous run left the state locked", "caution", 0.85)]
```

Guidelines:

- Add a test in `tests/` using a **real** error message (paste it in).
- Score 0.9+ only when the fix is near-certain. Rules scoring ≥ 0.9 on a failure skip the model call.
- Be honest about `risk` — the safety layer will escalate it anyway, but never downplay.
- Make it OS-aware where it matters (`ctx.os_name` is `macos`, `windows`, or `linux-<distro>`).

## Other good first issues

Look for the [`good first issue`](../../labels/good%20first%20issue) and `new-rule` labels.

## Pull requests

- One logical change per PR, with tests.
- Run `pytest -q` and `ruff check src tests` before pushing; CI runs both on Linux, macOS and Windows.
- Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `rule:`) so the changelog writes itself.

## Code of conduct

Be kind. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
