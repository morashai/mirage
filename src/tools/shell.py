"""Shell execution tools."""
from __future__ import annotations

import subprocess

from langchain_core.tools import tool


@tool
def run_shell_command(command: str, timeout_seconds: int = 30) -> str:
    """Run a shell command and return stdout/stderr with exit code."""
    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=max(1, timeout_seconds),
        )
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        return (
            f"exit_code={completed.returncode}\n"
            f"stdout:\n{stdout if stdout else '(empty)'}\n"
            f"stderr:\n{stderr if stderr else '(empty)'}"
        )
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout_seconds} seconds."
    except Exception as exc:
        return f"Error: {exc}"

