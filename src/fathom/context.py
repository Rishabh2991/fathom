"""Gather the situational context a suggestion engine needs."""

from __future__ import annotations

import os
import platform
import subprocess
from typing import List

from fathom.models import CommandResult, Context
from fathom.runner import shell_name

PROJECT_MARKERS = {
    "package.json": "node",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "setup.py": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
    "Gemfile": "ruby",
    "composer.json": "php",
    "Dockerfile": "docker",
    "docker-compose.yml": "compose",
    "compose.yaml": "compose",
    "Makefile": "make",
    "main.tf": "terraform",
    "Chart.yaml": "helm",
    "kustomization.yaml": "kubernetes",
    ".git": "git",
}


def os_label() -> str:
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Windows":
        return "windows"
    if system == "Linux":
        try:
            with open("/etc/os-release", encoding="utf-8") as fh:
                info = dict(line.rstrip().split("=", 1) for line in fh if "=" in line)
            distro = info.get("ID", "linux").strip('"')
            return f"linux-{distro}"
        except OSError:
            return "linux"
    return system.lower()


def detect_projects(cwd: str) -> List[str]:
    found = []
    try:
        names = set(os.listdir(cwd))
    except OSError:
        return found
    for marker, kind in PROJECT_MARKERS.items():
        if marker in names and kind not in found:
            found.append(kind)
    return found


def _git(cwd: str, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=1.5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def build_context(result: CommandResult, recent: List[str] | None = None) -> Context:
    branch = _git(result.cwd, "rev-parse", "--abbrev-ref", "HEAD")
    dirty = bool(_git(result.cwd, "status", "--porcelain")) if branch else False
    return Context(
        result=result,
        os_name=os_label(),
        shell=shell_name(),
        project_types=detect_projects(result.cwd),
        git_branch=branch,
        git_dirty=dirty,
        recent_commands=(recent or [])[-8:],
    )
