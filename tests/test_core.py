import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from fathom import engine, providers, safety
from fathom.config import Settings, load_settings
from fathom.memory import Memory
from fathom.models import CommandResult, Context, Suggestion
from fathom.redact import redact
from fathom.rules import run_rules
from fathom.runner import handle_builtin, run, strip_ansi


def ctx(command, output="", code=1, os_name="linux-ubuntu", projects=None):
    return Context(CommandResult(command, code, output, "/tmp"), os_name, "bash", projects or [])


def cmds(ctx_, **kw):
    return [s.command for s in run_rules(ctx_)]


# ---------------- rules ----------------
def test_command_not_found_suggests_install_per_os():
    assert "sudo apt install -y ripgrep" in cmds(ctx("rg foo", "bash: rg: command not found", 127))
    assert "brew install ripgrep" in cmds(ctx("rg foo", "zsh: command not found: rg", 127, "macos"))
    win = ctx("rg foo", "'rg' is not recognized as an internal or external command", 1, "windows")
    assert "winget install ripgrep" in cmds(win)


def test_git_no_upstream():
    out = "fatal: no upstream\n    git push --set-upstream origin feat/x\nhas no upstream branch"
    assert cmds(ctx("git push", out))[0] == "git push --set-upstream origin feat/x"


def test_git_rejected_offers_rebase_first():
    out = " ! [rejected]        main -> main (fetch first)\nUpdates were rejected"
    sugg = run_rules(ctx("git push", out))
    assert sugg[0].command == "git pull --rebase"


def test_git_success_flow():
    assert 'git commit -m ""' in cmds(ctx("git add .", "", 0))
    assert "git push" in cmds(ctx('git commit -m "x"', "1 file changed", 0))
    assert "cd demo" in cmds(ctx("git clone https://x/demo.git", "Cloning into 'demo'...", 0))


def test_python_missing_module_maps_package_names():
    assert "python3 -m pip install opencv-python" in cmds(
        ctx("python a.py", "ModuleNotFoundError: No module named 'cv2'"))


def test_port_in_use():
    out = "Error: listen EADDRINUSE: address already in use :::3000"
    assert "lsof -i :3000" in cmds(ctx("npm start", out))


def test_docker_daemon_down_macos():
    out = "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?"
    assert "open -a Docker" in cmds(ctx("docker ps", out, 1, "macos"))


def test_kubectl_crashloop():
    out = "NAME            READY   STATUS             RESTARTS\napi-7d9-xk2     0/1     CrashLoopBackOff   5"
    c = cmds(ctx("kubectl get pods", out, 0))
    assert "kubectl describe pod api-7d9-xk2" in c
    assert "kubectl logs api-7d9-xk2 --previous" in c


def test_mkdir_then_cd():
    assert cmds(ctx("mkdir -p build", "", 0)) == ["cd build"]


def test_broken_rule_does_not_crash(monkeypatch):
    from fathom import rules

    def boom(_):
        raise RuntimeError

    monkeypatch.setattr(rules, "RULES", [boom] + rules.RULES)
    assert isinstance(run_rules(ctx("ls", "", 0)), list)


# ---------------- safety & redaction ----------------
@pytest.mark.parametrize("cmd,risk", [
    ("rm -rf /", "danger"), ("sudo rm -rf / ", "danger"), ("mkfs.ext4 /dev/sda1", "danger"),
    ("curl https://x.sh | sudo bash", "danger"), ("DROP TABLE users;", "danger"),
    ("rm build.log", "caution"), ("git push --force", "caution"), ("kubectl delete pod x", "caution"),
    ("ls -la", "safe"), ("git status", "safe"),
])
def test_classify(cmd, risk):
    assert safety.classify(cmd) == risk


def test_redaction():
    text = ("AKIAABCDEFGHIJKLMNOP password=hunter2 ghp_" + "a" * 36 +
            " postgres://bob:s3cret@db/x Authorization: Bearer abcdefghijklmnopqrstuv")
    out = redact(text)
    for secret in ("AKIAABCDEFGHIJKLMNOP", "hunter2", "ghp_aaaa", "s3cret", "abcdefghijklmnopqrstuv"):
        assert secret not in out


# ---------------- engine ----------------
def test_merge_dedupes_boosts_and_escalates_risk():
    a = [Suggestion("git status", "x", source="rules", score=0.5)]
    b = [Suggestion("git  status", "y", source="ai:ollama", score=0.5),
         Suggestion("rm -rf /", "bad", risk="safe", source="ai:ollama", score=0.4)]
    merged = engine.merge([a, b], 4)
    assert merged[0].command == "git status" and merged[0].score == pytest.approx(0.6)
    assert merged[0].source == "rules+ai"
    assert next(s for s in merged if s.command == "rm -rf /").risk == "danger"  # model can't downplay risk


def test_parse_suggestions_tolerates_chatter():
    text = 'Sure! {"suggestions":[{"command":"`ls`","why":"look","risk":"SAFE"},{"command":""}]} hope it helps'
    out = providers.parse_suggestions(text, "ai:x")
    assert [s.command for s in out] == ["ls"] and out[0].risk == "safe"


# ---------------- AI provider against a fake Ollama ----------------
class FakeOllama(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.last = body
        reply = {"message": {"content": json.dumps({"suggestions": [
            {"command": "make test", "why": "verify", "risk": "safe"},
            {"command": "make clean", "why": "reset", "risk": "caution"}]})}}
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def ollama():
    srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_ai_suggestions_and_redaction_on_the_wire(ollama):
    s = Settings(providers=["ollama", "rules"])
    s.ollama["host"] = ollama
    c = ctx("make", "error: token=supersecret123 failed", 2)
    res = engine.suggest(c, s, None)
    assert res.ai_used == "ollama"
    assert "make test" in [x.command for x in res.suggestions]
    assert "supersecret123" not in json.dumps(FakeOllama.last)


def test_model_down_falls_back_to_rules():
    s = Settings(providers=["ollama", "rules"], timeout=1)
    s.ollama["host"] = "http://127.0.0.1:9"
    res = engine.suggest(ctx("rg x", "rg: command not found", 127), s, None)
    assert res.suggestions and res.ai_used is None


def test_offline_env_strips_cloud(monkeypatch, tmp_path):
    monkeypatch.setenv("FATHOM_HOME", str(tmp_path))
    monkeypatch.setenv("FATHOM_OFFLINE", "1")
    monkeypatch.setenv("FATHOM_PROVIDERS", "anthropic,openai,ollama,rules")
    assert load_settings().providers == ["ollama", "rules"]


# ---------------- memory ----------------
def test_memory_learns_choice(tmp_path):
    m = Memory(tmp_path / "mem.jsonl")
    c = ctx("npm start", "Error: listen EADDRINUSE: address already in use :::3000")
    m.record(c, Suggestion("npx kill-port 3000", "free it"))
    m.record(c, Suggestion("npx kill-port 3000", "free it"))
    got = m.recall(c)
    assert got[0].command == "npx kill-port 3000" and got[0].source == "memory"


# ---------------- runner ----------------
@pytest.mark.skipif(os.name == "nt", reason="posix shell")
def test_run_captures_output_and_exit_code():
    r = run("echo hello; echo oops >&2; exit 3", echo=False, use_pty=False)
    assert r.exit_code == 3 and "hello" in r.output and "oops" in r.output


def test_builtin_cd(tmp_path):
    cwd = os.getcwd()
    try:
        assert handle_builtin(f"cd {tmp_path}").exit_code == 0
        assert os.path.samefile(os.getcwd(), tmp_path)
        assert handle_builtin("cd /definitely/not/here").exit_code == 1
    finally:
        os.chdir(cwd)


def test_strip_ansi():
    assert strip_ansi("\x1b[31mred\x1b[0m\r\n") == "red\n"


def test_missing_path():
    c = cmds(ctx("ls /nope/dir", "ls: cannot access '/nope/dir': No such file or directory", 2))
    assert "ls -la /nope" in c and any("find ." in x for x in c)
