"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys

from fathom import __version__, engine, providers, ui
from fathom.config import ensure_config, load_settings
from fathom.context import build_context
from fathom.memory import Memory
from fathom.models import CommandResult

HOOKS = {
    "zsh": r'''# Fathom lite mode for zsh: suggestions after a failing command in your normal shell.
# Add to ~/.zshrc:  eval "$(fathom hook zsh)"
__fathom_preexec() { __fathom_last="$1"; }
__fathom_precmd() {
  local code=$?
  [[ $code -ne 0 && -n "$__fathom_last" && $code -ne 130 ]] && fathom suggest --cmd "$__fathom_last" --exit $code --rerun
  __fathom_last=""
}
autoload -Uz add-zsh-hook; add-zsh-hook preexec __fathom_preexec; add-zsh-hook precmd __fathom_precmd
''',
    "bash": r'''# Fathom lite mode for bash. Add to ~/.bashrc:  eval "$(fathom hook bash)"
__fathom_precmd() {
  local code=$?
  local last; last=$(HISTTIMEFORMAT= history 1 | sed 's/^ *[0-9]* *//')
  [[ $code -ne 0 && $code -ne 130 && "$last" != "$__fathom_prev" ]] && fathom suggest --cmd "$last" --exit $code --rerun
  __fathom_prev="$last"
}
PROMPT_COMMAND="__fathom_precmd${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
''',
    "powershell": r'''# Fathom lite mode for PowerShell. Add to $PROFILE:  fathom hook powershell | Out-String | Invoke-Expression
$global:__fathomOrigPrompt = $function:prompt
function global:prompt {
  $ok = $?; $code = $LASTEXITCODE
  if (-not $ok) {
    $last = (Get-History -Count 1).CommandLine
    if ($last -and $last -ne $global:__fathomPrev) { fathom suggest --cmd "$last" --exit ($code ?? 1) --rerun }
    $global:__fathomPrev = $last
  }
  & $global:__fathomOrigPrompt
}
''',
}


def doctor(s=None) -> int:
    s = s or load_settings()
    print(ui.bold("Fathom doctor"))
    print(f"  version   {__version__}")
    print(f"  python    {sys.version.split()[0]} on {sys.platform}")
    print(f"  config    {ensure_config()}")
    print(f"  offline   {'yes (FATHOM_OFFLINE)' if s.offline else 'no'}")
    for name in s.providers:
        print(f"  {name:<9} {providers.check_provider(name, s)}")
    return 0


def cmd_run(args, s) -> int:
    from fathom.shell import FathomShell
    sh = FathomShell(s)
    command = " ".join(args.command)
    result = sh.execute(command)
    if sh.pending and sys.stdin.isatty():
        try:
            choice = input(ui.dim("pick ❯ ")).strip()
            if choice:
                sh.handle(choice)
        except (EOFError, KeyboardInterrupt):
            print()
    return result.exit_code


def cmd_explain(args, s) -> int:
    if sys.stdin.isatty():
        print("pipe output in, e.g.:  make 2>&1 | fathom explain", file=sys.stderr)
        return 2
    data = sys.stdin.read()
    result = CommandResult(command=args.cmd or "(piped output)", exit_code=args.exit, output=data,
                           cwd=os.getcwd(), source="pipe")
    ctx = build_context(result)
    text, info = providers.explain(ctx, s)
    if text:
        print(text.strip())
    res = engine.suggest(ctx, s, Memory())
    print(ui.render(res.suggestions, f"ai: {res.ai_used}" if res.ai_used else "offline rules"))
    return 0


def cmd_suggest(args, s) -> int:
    output = ""
    if args.rerun:
        output = ""  # lite mode: we only know the command and exit code
    elif not sys.stdin.isatty():
        output = sys.stdin.read()
    result = CommandResult(command=args.cmd, exit_code=args.exit, output=output, cwd=os.getcwd())
    ctx = build_context(result)
    res = engine.suggest(ctx, s, Memory(), use_ai=not args.no_ai)
    if args.json:
        print(json.dumps({"suggestions": [x.to_dict() for x in res.suggestions], "ai": res.ai_used,
                          "ai_error": res.ai_error}, indent=2))
    elif res.suggestions:
        print(ui.render(res.suggestions, f"ai: {res.ai_used}" if res.ai_used else "offline rules"), file=sys.stderr)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="fathom", description="An AI-native shell that suggests your next move.")
    p.add_argument("--version", action="version", version=f"fathom {__version__}")
    p.add_argument("--offline", action="store_true", help="never use network providers")
    p.add_argument("--provider", help="comma-separated provider order, e.g. ollama,rules")
    sub = p.add_subparsers(dest="sub")
    r = sub.add_parser("run", help="run one command, then suggest next moves")
    r.add_argument("command", nargs=argparse.REMAINDER)
    e = sub.add_parser("explain", help="explain piped output:  cmd 2>&1 | fathom explain")
    e.add_argument("--cmd", default="")
    e.add_argument("--exit", type=int, default=1)
    w = sub.add_parser("watch", help="tail a log file (or - for stdin) and suggest fixes on errors")
    w.add_argument("path")
    w.add_argument("--from-start", action="store_true")
    w.add_argument("--once", action="store_true", help="exit after the first error report")
    sg = sub.add_parser("suggest", help="machine-friendly suggestions (used by hooks, editors, GUIs)")
    sg.add_argument("--cmd", required=True)
    sg.add_argument("--exit", type=int, default=1)
    sg.add_argument("--json", action="store_true")
    sg.add_argument("--no-ai", action="store_true")
    sg.add_argument("--rerun", action="store_true", help=argparse.SUPPRESS)
    h = sub.add_parser("hook", help="print shell integration for zsh, bash or powershell")
    h.add_argument("shell", choices=sorted(HOOKS))
    sub.add_parser("doctor", help="check configuration and AI providers")
    sub.add_parser("init", help="write a default config file")

    args = p.parse_args(argv)
    if args.offline:
        os.environ["FATHOM_OFFLINE"] = "1"
    if args.provider:
        os.environ["FATHOM_PROVIDERS"] = args.provider
    s = load_settings()

    if args.sub == "run":
        if not args.command:
            p.error("run needs a command")
        return cmd_run(args, s)
    if args.sub == "explain":
        return cmd_explain(args, s)
    if args.sub == "watch":
        from fathom.watch import watch
        return watch(args.path, s, from_start=args.from_start, once=args.once)
    if args.sub == "suggest":
        return cmd_suggest(args, s)
    if args.sub == "hook":
        print(HOOKS[args.shell])
        return 0
    if args.sub == "doctor":
        return doctor(s)
    if args.sub == "init":
        print(ensure_config())
        return 0
    from fathom.shell import FathomShell
    return FathomShell(s).loop()
