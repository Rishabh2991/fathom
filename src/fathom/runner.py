"""Run a command while streaming it to the terminal and capturing its output.

On macOS/Linux the command runs inside a pseudo-terminal, so colours, progress bars and
interactive programs (vim, top, ssh) behave normally while Fathom still sees the output.
On Windows (or when stdin is not a TTY) it falls back to pipes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

from fathom.models import CommandResult

MAX_CAPTURE = 200_000  # bytes kept in memory; only the tail is ever sent to a model


def default_shell() -> list:
    override = os.environ.get("FATHOM_SHELL")
    if sys.platform == "win32":
        name = override or ("pwsh" if shutil.which("pwsh") else "powershell")
        if name.lower() in ("cmd", "cmd.exe"):
            return ["cmd.exe", "/d", "/c"]
        return [name, "-NoLogo", "-NoProfile", "-Command"]
    sh = override or os.environ.get("SHELL") or "/bin/sh"
    if not shutil.which(sh) and not os.path.exists(sh):
        sh = "/bin/sh"
    return [sh, "-c"]


def shell_name() -> str:
    return os.path.basename(default_shell()[0]).replace(".exe", "")


class _Tail:
    def __init__(self) -> None:
        self.buf = bytearray()

    def add(self, data: bytes) -> None:
        self.buf.extend(data)
        if len(self.buf) > MAX_CAPTURE:
            del self.buf[: len(self.buf) - MAX_CAPTURE]

    def text(self) -> str:
        return strip_ansi(self.buf.decode("utf-8", errors="replace"))


def strip_ansi(text: str) -> str:
    import re

    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text)
    text = re.sub(r"\x1b\][^\x07]*(\x07|\x1b\\)", "", text)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _run_pty(argv: list, tail: _Tail) -> int:
    import pty

    def read(fd):
        data = os.read(fd, 4096)
        tail.add(data)
        return data

    status = pty.spawn(argv, read)
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return 1


def _run_pipe(argv: list, tail: _Tail, echo: bool) -> int:
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
    assert proc.stdout is not None
    try:
        while True:
            chunk = proc.stdout.read(4096)
            if not chunk:
                break
            tail.add(chunk)
            if echo:
                sys.stdout.buffer.write(chunk)
                sys.stdout.flush()
    except KeyboardInterrupt:
        proc.terminate()
    return proc.wait()


def run(command: str, echo: bool = True, use_pty: bool | None = None) -> CommandResult:
    argv = default_shell() + [command]
    tail = _Tail()
    if use_pty is None:
        use_pty = sys.platform != "win32" and echo and sys.stdin.isatty() and sys.stdout.isatty()
    start = time.time()
    try:
        code = _run_pty(argv, tail) if use_pty else _run_pipe(argv, tail, echo)
    except KeyboardInterrupt:
        code = 130
    except FileNotFoundError as exc:
        tail.add(str(exc).encode())
        code = 127
    return CommandResult(command=command, exit_code=code, output=tail.text(), cwd=os.getcwd(),
                         duration=time.time() - start)


def handle_builtin(command: str) -> CommandResult | None:
    """Builtins that must change Fathom's own process state (cd, export)."""
    stripped = command.strip()
    parts = stripped.split(None, 1)
    if not parts:
        return None
    head = parts[0]
    if head == "cd":
        target = os.path.expanduser(os.path.expandvars(parts[1].strip().strip('"\''))) if len(parts) > 1 \
            else os.path.expanduser("~")
        if target == "-":
            target = os.environ.get("OLDPWD", os.getcwd())
        try:
            prev = os.getcwd()
            os.chdir(target)
            os.environ["OLDPWD"] = prev
            return CommandResult(command, 0, "", os.getcwd())
        except OSError as exc:
            return CommandResult(command, 1, f"cd: {exc.strerror}: {target}", os.getcwd())
    if head == "export" and len(parts) > 1 and "=" in parts[1]:
        key, _, value = parts[1].partition("=")
        os.environ[key.strip()] = os.path.expandvars(value.strip().strip('"\''))
        return CommandResult(command, 0, "", os.getcwd())
    return None
