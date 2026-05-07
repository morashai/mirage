"""Search tools (glob and ripgrep wrappers)."""
from __future__ import annotations

import glob
import subprocess
from pathlib import Path

from langchain_core.tools import tool


@tool
def glob_search(pattern: str, root: str = ".") -> str:
    """Search file paths by glob pattern."""
    try:
        base = Path(root)
        matches = sorted(glob.glob(str(base / pattern), recursive=True))
        if not matches:
            return "No matches found."
        return "\n".join(matches[:500])
    except Exception as exc:
        return f"Error: {exc}"


@tool
def ripgrep_search(pattern: str, root: str = ".", max_results: int = 200) -> str:
    """Search content with ripgrep and return matching lines."""
    try:
        cmd = [
            "rg",
            "--line-number",
            "--with-filename",
            "--max-count",
            str(max(1, max_results)),
            pattern,
            root,
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True)
        if completed.returncode not in (0, 1):
            stderr = completed.stderr.strip() or "unknown rg error"
            return f"Error: {stderr}"
        output = completed.stdout.strip()
        return output if output else "No matches found."
    except FileNotFoundError:
        return "Error: `rg` is not installed or not available in PATH."
    except Exception as exc:
        return f"Error: {exc}"

