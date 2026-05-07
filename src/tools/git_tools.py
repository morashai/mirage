"""Read-focused git tools."""
from __future__ import annotations

import subprocess

from langchain_core.tools import tool


def _run_git(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or "git command failed"
            return f"Error: {stderr}"
        return completed.stdout.strip() or "(empty)"
    except FileNotFoundError:
        return "Error: git is not installed or not available in PATH."
    except Exception as exc:
        return f"Error: {exc}"


@tool
def git_status() -> str:
    """Return `git status --short --branch`."""
    return _run_git(["status", "--short", "--branch"])


@tool
def git_diff(target: str = "") -> str:
    """Return git diff for working tree or a target range."""
    args = ["diff"]
    if target.strip():
        args.append(target.strip())
    return _run_git(args)


@tool
def git_log(max_count: int = 20) -> str:
    """Return recent commit history."""
    count = max(1, max_count)
    return _run_git(["log", f"-{count}", "--oneline", "--decorate"])


@tool
def git_current_branch() -> str:
    """Return current branch name."""
    return _run_git(["rev-parse", "--abbrev-ref", "HEAD"])

