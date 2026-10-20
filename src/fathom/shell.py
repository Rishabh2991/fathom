"""The interactive Fathom shell."""

from __future__ import annotations

import os
import re
import sys
import threading
import time
from typing import List, Optional

from fathom import __version__, engine, providers, runner, ui
from fathom.config import Settings, config_dir, load_settings
from fathom.context import build_context
from fathom.memory import Memory
from fathom.models import CommandResult, Context, Suggestion

try:
    import readline  # noqa: F401  (POSIX; on Windows install pyreadline3 for history/editing)
    HAVE_READLINE = True
except ImportError:  # pragma: no cover
    HAVE_READLINE = False

HELP = f"""{ui.bold('Fathom')} {__version__} — type commands as usual; Fathom watches the output and suggests next moves.

  1-4         run suggestion n          e2   edit suggestion 2 before running
  ?           explain the last output   # <task>  describe a task in English, get commands
  !<cmd>      run without suggestions   :ai on|off  toggle the model (rules stay on)
  :doctor     check providers           :config     show config file path
  :forget     clear learned choices     :help       this help      exit   leave
"""


class Spinner:
    def __init__(self, text: str) -> None:
        self.text, self._stop = text, threading.Event()
        self._t = threading.Thread(target=self._spin, daemon=True)

    def _spin(self) -> None:
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        i = 0
        while not self._stop.wait(0.08):
            sys.stdout.write(f"\r{ui.c(frames[i % len(frames)], '36')} {ui.dim(self.text)}")
            sys.stdout.flush()
            i += 1

    def __enter__(self):
        if sys.stdout.isatty():
            self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._t.is_alive():
            self._t.join()
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()


def _prefill_input(prompt: str, text: str) -> str:
    if not HAVE_READLINE:
        print(ui.dim(f"  (edit) {text}"))
        return input(prompt) or text
    import readline as rl
    rl.set_startup_hook(lambda: rl.insert_text(text))
    try:
        return input(prompt)
    finally:
        rl.set_startup_hook()


class FathomShell:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.s = settings or load_settings()
        self.memory = Memory()
        self.ai_enabled = True
        self.recent: List[str] = []
        self.pending: List[Suggestion] = []
        self.last_ctx: Optional[Context] = None
        self.last_ok: Optional[bool] = None
        self._setup_history()

    # ---------- plumbing ----------
    def _setup_history(self) -> None:
        if not HAVE_READLINE:
            return
        import atexit
        import readline as rl
        hist = config_dir() / "history"
        try:
            hist.parent.mkdir(parents=True, exist_ok=True)
            if hist.exists():
                rl.read_history_file(str(hist))
            rl.set_history_length(5000)
            atexit.register(lambda: rl.write_history_file(str(hist)))
        except OSError:
            pass

    def _status(self, res: engine.EngineResult) -> str:
        if res.ai_used:
            return f"ai: {res.ai_used}"
        if not self.ai_enabled or not any(p != "rules" for p in self.s.providers):
            return "offline rules"
        return "offline rules · model unavailable"

    # ---------- core loop ----------
    def execute(self, command: str, suggest: bool = True) -> CommandResult:
        result = runner.handle_builtin(command)
        if result is not None:
            if result.output:
                print(result.output)
        else:
            result = runner.run(command)
        self.recent.append(command)
        self.last_ok = result.ok
        ctx = build_context(result, self.recent[:-1])
        self.last_ctx = ctx
        self.pending = []
        if suggest:
            self.suggest(ctx)
        return result

    def suggest(self, ctx: Context) -> None:
        with Spinner("reading the output…"):
            res = engine.suggest(ctx, self.s, self.memory, use_ai=self.ai_enabled)
        self.pending = res.suggestions
        if self.pending:
            print(ui.render(self.pending, self._status(res)))

    def pick(self, idx: int, edit: bool = False) -> None:
        if not (1 <= idx <= len(self.pending)) or not self.last_ctx:
            print(ui.dim("no such suggestion"))
            return
        s = self.pending[idx - 1]
        cmd = s.command
        needs_edit = edit or bool(re.search(r'""|<[A-Z_a-z]+>|PORT\b', cmd))
        if needs_edit:
            cmd = _prefill_input(ui.dim("  edit ❯ "), cmd).strip()
            if not cmd:
                return
        elif s.risk == "danger":
            ans = input(ui.c(f"  ⛔ '{cmd}' is destructive. Type 'yes' to run: ", "31"))
            if ans.strip().lower() != "yes":
                print(ui.dim("  cancelled"))
                return
        elif s.risk == "caution":
            ans = input(ui.c(f"  ⚠ run '{cmd}'? [y/N] ", "33"))
            if ans.strip().lower() not in ("y", "yes"):
                print(ui.dim("  cancelled"))
                return
        else:
            print(ui.dim(f"  ❯ {cmd}"))
        if self.s.learn:
            self.memory.record(self.last_ctx, Suggestion(cmd, s.why, s.risk, s.source))
        if HAVE_READLINE:
            import readline as rl
            rl.add_history(cmd)
        self.execute(cmd)

    def explain(self) -> None:
        if not self.last_ctx:
            print(ui.dim("run a command first"))
            return
        with Spinner("explaining…"):
            text, info = providers.explain(self.last_ctx, self.s) if self.ai_enabled else ("", "AI is off")
        if text:
            print(ui.c("│ ", "36") + text.strip().replace("\n", "\n" + ui.c("│ ", "36")))
        else:
            print(ui.dim(f"  explanation needs a model ({info}). Offline hints:"))
            for s in self.pending:
                print(ui.dim(f"  • {s.why}"))

    def intent(self, text: str) -> None:
        ctx = build_context(CommandResult(f"# {text}", 0, "", os.getcwd(), source="intent"), self.recent)
        self.last_ctx = ctx
        with Spinner("thinking…"):
            sugg, info = providers.from_intent(text, ctx, self.s)
        if not sugg:
            print(ui.dim(f"  natural-language mode needs a model ({info}). Try: ollama pull {self.s.ollama['model']}"))
            return
        self.pending = engine.merge([sugg], self.s.max_suggestions)
        print(ui.render(self.pending, f"ai: {info}"))

    def meta(self, line: str) -> bool:
        cmd, *args = line[1:].split()
        if cmd == "help":
            print(HELP)
        elif cmd == "ai":
            self.ai_enabled = (args[:1] != ["off"])
            print(ui.dim(f"  AI {'on' if self.ai_enabled else 'off (offline rules only)'}"))
        elif cmd == "doctor":
            from fathom.cli import doctor
            doctor(self.s)
        elif cmd == "config":
            print(f"  {config_dir() / 'config.toml'}")
        elif cmd == "forget":
            try:
                self.memory.path.unlink()
            except FileNotFoundError:
                pass
            print(ui.dim("  learned choices cleared"))
        else:
            print(ui.dim(f"  unknown :{cmd} — try :help"))
        return True

    def handle(self, line: str) -> bool:
        """Process one input line. Returns False to exit."""
        stripped = line.strip()
        if not stripped:
            self.pending = []
            return True
        if stripped in ("exit", "quit", "logout"):
            return False
        m = re.fullmatch(r"(e)?([1-9])", stripped)
        if m and self.pending:
            self.pick(int(m.group(2)), edit=bool(m.group(1)))
            return True
        if stripped == "?":
            self.explain()
            return True
        if stripped.startswith("#"):
            self.intent(stripped.lstrip("# "))
            return True
        if stripped.startswith(":"):
            return self.meta(stripped)
        if stripped.startswith("!"):
            self.execute(stripped[1:], suggest=False)
            return True
        self.execute(stripped)
        return True

    def loop(self) -> int:
        print(ui.dim(f"Fathom {__version__} · :help for keys · providers: {', '.join(self.s.providers)}"
                     f"{' · OFFLINE' if self.s.offline else ''}"))
        while True:
            branch = self.last_ctx.git_branch if self.last_ctx else None
            try:
                line = input(ui.prompt_str(os.getcwd(), branch, self.last_ok))
            except EOFError:
                print()
                return 0
            except KeyboardInterrupt:
                print()
                self.pending = []
                continue
            try:
                if not self.handle(line):
                    return 0
            except KeyboardInterrupt:
                print()
            time.sleep(0)
