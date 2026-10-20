"""The offline brain: pattern rules that need no model, no network, no GPU.

Each rule looks at the command, exit code, output and environment and returns
suggestions. Rules are cheap, deterministic and run first; an LLM (if available)
adds to them rather than replacing them. Contributions of new rules are the
easiest way to help the project — see CONTRIBUTING.md.
"""

from __future__ import annotations

import re
import shlex
from typing import Callable, List

from fathom.models import Context, Suggestion

RuleFn = Callable[[Context], List[Suggestion]]
RULES: List[RuleFn] = []


def rule(fn: RuleFn) -> RuleFn:
    RULES.append(fn)
    return fn


def S(command: str, why: str, risk: str = "safe", score: float = 0.6) -> Suggestion:
    return Suggestion(command=command, why=why, risk=risk, source="rules", score=score)


def _first_word(cmd: str) -> str:
    try:
        parts = shlex.split(cmd)
    except ValueError:
        parts = cmd.split()
    while parts and (parts[0] in ("sudo", "time", "env") or "=" in parts[0]):
        parts = parts[1:]
    return parts[0] if parts else ""


def _install_cmd(ctx: Context, pkg: str) -> str:
    os_name = ctx.os_name
    if os_name == "macos":
        return f"brew install {pkg}"
    if os_name == "windows":
        return f"winget install {pkg}"
    if any(d in os_name for d in ("ubuntu", "debian", "pop", "mint", "kali")):
        return f"sudo apt install -y {pkg}"
    if any(d in os_name for d in ("fedora", "rhel", "centos", "rocky", "alma", "amzn")):
        return f"sudo dnf install -y {pkg}"
    if "arch" in os_name or "manjaro" in os_name:
        return f"sudo pacman -S {pkg}"
    if "alpine" in os_name:
        return f"sudo apk add {pkg}"
    return f"sudo apt install -y {pkg}"


# Binaries whose package name differs from the command.
PKG_ALIASES = {"rg": "ripgrep", "fd": "fd-find", "batcat": "bat", "http": "httpie", "nvim": "neovim",
               "pip": "python3-pip", "python": "python3", "node": "nodejs", "kubectl": "kubectl"}


@rule
def command_not_found(ctx: Context) -> List[Suggestion]:
    out = ctx.result.output
    name = ""
    for pat in (r"command not found:\s*(\S+)",  # zsh
                r"'(\S+)' is not recognized as (?:an internal or external command|the name of a cmdlet)",  # windows
                r"(?:^|\s)(\S+): command not found",  # bash: rg: command not found
                r"(?:^|\s)(\S+): not found"):  # sh
        hits = [h for h in re.findall(pat, out, re.M) if h.rstrip(":") not in ("bash", "zsh", "sh", "fish")]
        if hits:
            name = hits[-1]
            break
    if not name and ctx.result.exit_code != 127:
        return []
    name = name or _first_word(ctx.result.command)
    name = name.strip("'\":")
    if not name:
        return []
    out_s = [S(_install_cmd(ctx, PKG_ALIASES.get(name, name)), f"`{name}` isn't installed; install it",
               "caution", 0.8)]
    which = "where" if ctx.os_name == "windows" else "type -a"
    hint = re.search(r"(?:Did you mean|similar)[^\n]*?['`\"]?([a-z][\w-]+)['`\"]?", out, re.I)
    if hint and hint.group(1) != name:
        fixed = ctx.result.command.replace(name, hint.group(1), 1)
        out_s.insert(0, S(fixed, f"Probably a typo for `{hint.group(1)}`", "safe", 0.9))
    out_s.append(S(f"{which} {name}", "Check whether it exists elsewhere on your PATH", "safe", 0.4))
    return out_s


@rule
def permission_denied(ctx: Context) -> List[Suggestion]:
    out = ctx.result.output
    if ctx.result.ok or not re.search(r"(?i)permission denied|operation not permitted|EACCES|access is denied", out):
        return []
    cmd = ctx.result.command
    res = []
    path = re.search(r"(?:permission denied[:,]?\s*'?|open\s+'?)(/[\w./-]+)", out, re.I)
    if path and path.group(1).endswith((".sh", ".py")) or cmd.startswith("./"):
        target = path.group(1) if path else cmd.split()[0]
        res.append(S(f"chmod +x {target} && {cmd}", "The script isn't executable", "caution", 0.85))
    if ctx.os_name != "windows" and not cmd.startswith("sudo "):
        res.append(S(f"sudo {cmd}", "Re-run with elevated privileges", "caution", 0.7))
    if "docker" in cmd and "docker.sock" in out:
        res.append(S("sudo usermod -aG docker $USER && newgrp docker",
                     "Add yourself to the docker group so sudo isn't needed", "caution", 0.75))
    if path:
        res.append(S(f"ls -l {path.group(1)}", "Inspect ownership and permissions", "safe", 0.4))
    return res


@rule
def git_rules(ctx: Context) -> List[Suggestion]:
    cmd, out, ok = ctx.result.command.strip(), ctx.result.output, ctx.result.ok
    if not cmd.startswith("git") and "not a git repository" not in out:
        return []
    res: List[Suggestion] = []
    if "not a git repository" in out:
        res += [S("git init", "Turn this folder into a repository", "safe", 0.8)]
    if "has no upstream branch" in out:
        m = re.search(r"git push --set-upstream (\S+) (\S+)", out)
        up = f"git push --set-upstream {m.group(1)} {m.group(2)}" if m else "git push -u origin HEAD"
        res.append(S(up, "Publish this branch and track it", "safe", 0.95))
    if re.search(r"\[rejected\].*\(fetch first\)|non-fast-forward|Updates were rejected", out):
        res += [S("git pull --rebase", "Remote has new commits; rebase yours on top", "safe", 0.9),
                S("git fetch && git log --oneline HEAD..@{u}", "See what's new on the remote first", "safe", 0.6),
                S("git push --force-with-lease", "Overwrite remote (only if you rewrote history on purpose)",
                  "caution", 0.3)]
    if "CONFLICT" in out or "fix conflicts" in out:
        res += [S("git status", "List the conflicted files", "safe", 0.9),
                S("git mergetool", "Resolve conflicts in a merge tool", "safe", 0.6),
                S("git merge --abort" if "merge" in cmd else "git rebase --abort",
                  "Back out and return to where you were", "caution", 0.5)]
    if "Please tell me who you are" in out:
        res.append(S('git config --global user.name "Your Name" && git config --global user.email "you@example.com"',
                     "Set your commit identity", "safe", 0.95))
    if "nothing added to commit but untracked files" in out or "Changes not staged" in out and "commit" in cmd:
        res.append(S("git add -A && git commit", "Stage everything and commit", "safe", 0.85))
    if "did not match any file(s) known to git" in out or "invalid reference" in out:
        res += [S("git branch -a", "List local and remote branches", "safe", 0.8),
                S("git fetch --all", "Fetch branches you may not have yet", "safe", 0.6)]
    if ok:
        if re.match(r"git (add|stage)\b", cmd):
            res += [S('git commit -m ""', "Commit what you staged", "safe", 0.9),
                    S("git diff --staged", "Review what's staged", "safe", 0.6)]
        elif re.match(r"git commit\b", cmd):
            res += [S("git push", "Push the commit", "safe", 0.9),
                    S("git log --oneline -5", "Check recent history", "safe", 0.4)]
        elif re.match(r"git (clone)\b", cmd):
            m = re.search(r"Cloning into '([^']+)'", out)
            if m:
                res.append(S(f"cd {m.group(1)}", "Enter the cloned repository", "safe", 0.95))
        elif re.match(r"git (status)\b", cmd):
            if "Changes not staged" in out or "Untracked files" in out:
                res += [S("git add -A", "Stage all changes", "safe", 0.7), S("git diff", "See the changes", "safe", 0.6)]
            if "Your branch is ahead" in out:
                res.append(S("git push", "Push your local commits", "safe", 0.8))
            if "Your branch is behind" in out:
                res.append(S("git pull", "Bring in the remote commits", "safe", 0.8))
        elif re.match(r"git (pull|fetch)\b", cmd):
            res.append(S("git log --oneline -10", "See what came in", "safe", 0.5))
        elif re.match(r"git (checkout -b|switch -c)\b", cmd):
            res.append(S("git push -u origin HEAD", "Publish the new branch", "safe", 0.6))
    return res


@rule
def python_rules(ctx: Context) -> List[Suggestion]:
    out, cmd = ctx.result.output, ctx.result.command
    res = []
    m = re.search(r"ModuleNotFoundError: No module named '([\w.]+)'", out)
    if m:
        mod = m.group(1).split(".")[0]
        pkg = {"cv2": "opencv-python", "yaml": "pyyaml", "PIL": "pillow", "sklearn": "scikit-learn",
               "bs4": "beautifulsoup4", "dotenv": "python-dotenv"}.get(mod, mod)
        res.append(S(f"python3 -m pip install {pkg}", f"Install the missing `{pkg}` package", "safe", 0.9))
        if "requirements.txt" in str(ctx.project_types) or "python" in ctx.project_types:
            res.append(S("python3 -m pip install -r requirements.txt", "Install all project dependencies", "safe", 0.6))
        res.append(S("python3 -m venv .venv && . .venv/bin/activate", "Use an isolated virtualenv", "safe", 0.4))
    if "externally-managed-environment" in out:
        res += [S("python3 -m venv .venv && . .venv/bin/activate", "Create a virtualenv (recommended)", "safe", 0.9),
                S(f"pipx install {cmd.split()[-1]}", "Install the CLI tool with pipx", "safe", 0.6)]
    if re.search(r"^(FAILED|ERROR) .*::", out, re.M) or re.search(r"=+ \d+ failed", out):
        res += [S("pytest --lf -x", "Re-run only the failed tests, stop at first failure", "safe", 0.85),
                S("pytest --lf -x -vv --pdb", "Debug the first failure interactively", "safe", 0.5)]
    m = re.search(r'File "([^"]+)", line (\d+)', out)
    if m and "Traceback" in out and "site-packages" not in m.group(1):
        last = re.findall(r'File "([^"]+)", line (\d+)', out)
        own = [f for f in last if "site-packages" not in f[0] and "<" not in f[0]]
        if own:
            f, ln = own[-1]
            res.append(S(f"${{EDITOR:-vi}} +{ln} {f}", f"Open the failing line ({f}:{ln})", "safe", 0.55))
    return res


@rule
def node_rules(ctx: Context) -> List[Suggestion]:
    out, cmd = ctx.result.output, ctx.result.command
    res = []
    m = re.search(r"Cannot find module '([^']+)'", out)
    if m and not m.group(1).startswith((".", "/")):
        res.append(S(f"npm install {m.group(1)}", f"Install the missing `{m.group(1)}` module", "safe", 0.85))
    if "node_modules" not in out and re.search(r"(Cannot find module|sh: \S+: not found)", out) \
            and "node" in ctx.project_types:
        res.append(S("npm install", "Dependencies look missing; install them", "safe", 0.8))
    if "ERESOLVE" in out:
        res.append(S("npm install --legacy-peer-deps", "Work around the peer-dependency conflict", "caution", 0.7))
    if re.search(r'Missing script: "?(\w+)', out):
        res.append(S("npm run", "List the scripts this package defines", "safe", 0.9))
    if ctx.result.ok and re.match(r"(npm|pnpm|yarn)( install| i|$)", cmd.strip()) and "node" in ctx.project_types:
        tool = cmd.split()[0]
        res += [S(f"{tool} run dev", "Start the dev server", "safe", 0.7),
                S(f"{tool} test", "Run the test suite", "safe", 0.5)]
    return res


@rule
def network_and_ports(ctx: Context) -> List[Suggestion]:
    out = ctx.result.output
    res = []
    m = re.search(r"(?:EADDRINUSE|address already in use|port is already allocated|"
                  r"Address already in use)[^\d]*(?:[:\s](\d{2,5}))?", out, re.I)
    if m:
        port = m.group(1)
        if not port:
            pm = re.search(r":(\d{2,5})\b", out)
            port = pm.group(1) if pm else "PORT"
        if ctx.os_name == "windows":
            res.append(S(f"netstat -ano | findstr :{port}", f"Find what's using port {port}", "safe", 0.9))
        else:
            res += [S(f"lsof -i :{port}", f"Find what's using port {port}", "safe", 0.9),
                    S(f"kill $(lsof -t -i :{port})", f"Stop the process holding port {port}", "caution", 0.6)]
    if re.search(r"(?i)could not resolve host|name or service not known|temporary failure in name resolution", out):
        res += [S("ping -c 3 1.1.1.1", "Check raw connectivity (is it DNS or the network?)", "safe", 0.7),
                S("cat /etc/resolv.conf", "Inspect DNS configuration", "safe", 0.5)]
    if re.search(r"(?i)connection refused", out):
        hp = re.search(r"(?i)connection refused[^\n]*?(\d{1,3}(?:\.\d{1,3}){3}|localhost|[\w.-]+\.\w+):(\d{2,5})", out)
        if hp:
            res.append(S(f"nc -zv {hp.group(1)} {hp.group(2)}", f"Is anything accepting on {hp.group(1)}:{hp.group(2)}?",
                         "safe", 0.8))
        res.append(S("ss -tlnp" if ctx.os_name.startswith("linux") else "netstat -an | grep LISTEN",
                     "See which services are listening", "safe", 0.7))
    if re.search(r"(?i)ssl|certificate verify failed|x509", out) and not ctx.result.ok:
        res.append(S("date", "Check the system clock (skew breaks TLS)", "safe", 0.4))
    return res


@rule
def docker_k8s(ctx: Context) -> List[Suggestion]:
    out, cmd = ctx.result.output, ctx.result.command
    res = []
    if re.search(r"Cannot connect to the Docker daemon|docker daemon is not running|error during connect", out):
        if ctx.os_name == "macos":
            res.append(S("open -a Docker", "Start Docker Desktop", "safe", 0.9))
        elif ctx.os_name == "windows":
            res.append(S('Start-Process "Docker Desktop"', "Start Docker Desktop", "safe", 0.9))
        else:
            res.append(S("sudo systemctl start docker", "Start the Docker daemon", "caution", 0.9))
    if "no space left on device" in out.lower():
        res += [S("df -h", "See which filesystem is full", "safe", 0.9),
                S("docker system df", "See how much space Docker uses", "safe", 0.6),
                S("du -xh / 2>/dev/null | sort -rh | head -20", "Find the biggest directories", "safe", 0.6)]
    if cmd.startswith("kubectl"):
        bad = re.findall(r"^(?:pod/)?(\S+)\s+\S+\s+(CrashLoopBackOff|Error|ImagePullBackOff|ErrImagePull|"
                         r"Pending|OOMKilled)\b", out, re.M)
        for name, state in bad[:1]:
            res += [S(f"kubectl describe pod {name}", f"`{name}` is {state}; see events", "safe", 0.9),
                    S(f"kubectl logs {name} --previous", "Logs from the crashed container", "safe", 0.8)]
        if "Unable to connect to the server" in out or "connection to the server" in out:
            res.append(S("kubectl config get-contexts", "Check which cluster you're pointed at", "safe", 0.8))
    if ctx.result.ok and re.match(r"docker (compose |-compose )?up -d", cmd):
        res += [S("docker compose ps", "Check the containers came up", "safe", 0.8),
                S("docker compose logs -f --tail=50", "Follow the logs", "safe", 0.7)]
    if ctx.result.ok and re.match(r"docker build", cmd):
        m = re.search(r"(?:naming to|Successfully tagged)\s+(\S+)", out)
        if m:
            res.append(S(f"docker run --rm -it {m.group(1).split('/')[-1] if 'docker.io' in m.group(1) else m.group(1)}",
                         "Run the image you just built", "safe", 0.8))
    return res


@rule
def systemd_logs(ctx: Context) -> List[Suggestion]:
    cmd, out = ctx.result.command, ctx.result.output
    m = re.search(r"systemctl\s+(?:start|restart|status|enable)\s+([\w@.-]+)", cmd)
    if not m:
        return []
    unit = m.group(1)
    if not ctx.result.ok or re.search(r"failed|inactive \(dead\)|activating \(auto-restart\)", out):
        return [S(f"journalctl -u {unit} -n 50 --no-pager", f"Recent logs for {unit}", "safe", 0.9),
                S(f"systemctl cat {unit}", "Inspect the unit file", "safe", 0.5)]
    return [S(f"journalctl -u {unit} -f", f"Follow {unit} logs", "safe", 0.6)]


@rule
def generic_success(ctx: Context) -> List[Suggestion]:
    if not ctx.result.ok:
        return []
    cmd = ctx.result.command.strip()
    m = re.match(r"mkdir\s+(?:-p\s+)?(\S+)$", cmd)
    if m:
        return [S(f"cd {m.group(1)}", "Enter the new directory", "safe", 0.9)]
    m = re.match(r"(?:tar\s+-?x\S*|unzip)\s+(\S+)", cmd)
    if m:
        return [S("ls -la", "See what was extracted", "safe", 0.6)]
    if re.match(r"(make|cargo build|go build|mvn package|gradle build)\b", cmd):
        tool = cmd.split()[0]
        nxt = {"make": "make test", "cargo": "cargo run", "go": "go test ./...", "mvn": "mvn test",
               "gradle": "gradle test"}[tool]
        return [S(nxt, "Build passed; run it / test it", "safe", 0.7)]
    return []


@rule
def missing_path(ctx: Context) -> List[Suggestion]:
    if ctx.result.ok:
        return []
    m = re.search(r"'?([~./\w-]*/?[\w.-]+)'?: No such file or directory|cannot access '([^']+)': No such file", ctx.result.output)
    if not m:
        return []
    import posixpath
    path = m.group(1) or m.group(2)
    parent = posixpath.dirname(path.rstrip("/")) or "."
    base = posixpath.basename(path.rstrip("/"))
    res = [S(f"ls -la {parent}", f"See what actually exists in {parent}", "safe", 0.7)]
    if base:
        res.append(S(f"find . -iname '*{base}*' 2>/dev/null | head", f"Search for something named like '{base}'",
                     "safe", 0.6))
    return res


@rule
def generic_failure(ctx: Context) -> List[Suggestion]:
    """Fallback when nothing specific matched a failure."""
    if ctx.result.ok or ctx.result.exit_code in (127, 130) or ctx.result.source == "log":
        return []
    first = _first_word(ctx.result.command)
    if not first:
        return []
    res = []
    if ctx.os_name != "windows":
        res.append(S(f"{first} --help | less", f"Check `{first}` usage", "safe", 0.25))
    else:
        res.append(S(f"{first} --help", f"Check `{first}` usage", "safe", 0.25))
    return res


def run_rules(ctx: Context) -> List[Suggestion]:
    out: List[Suggestion] = []
    for fn in RULES:
        try:
            out.extend(fn(ctx))
        except Exception:  # a broken rule must never break the shell
            continue
    return out
