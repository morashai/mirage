"""Read/write filesystem tools used by the agents.

Only the Developer agent is allowed to use the write tools (``write_file``,
``edit_file``); the Project Manager and UX/UI Designer get only the
read-only tools. This is enforced at agent-construction time in
``src.agents``.
"""
from __future__ import annotations

import os
from pathlib import Path

from langchain_core.tools import tool

from ..cli.policy import can_execute


def _workspace_root() -> Path:
    env_root = os.getenv("MIRAGE_WORKSPACE_ROOT")
    return Path(env_root).resolve() if env_root else Path.cwd().resolve()


def _resolve_safe(path_value: str) -> Path:
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = _workspace_root() / candidate
    resolved = candidate.resolve()
    root = _workspace_root()
    if not str(resolved).startswith(str(root)):
        raise ValueError(f"path is outside workspace root: {resolved}")
    return resolved


@tool
def list_directory(path: str) -> str:
    """Lists the files and directories in the given path."""
    try:
        target = _resolve_safe(path)
        items = sorted(os.listdir(target))
        return "\n".join(items) if items else "Directory is empty."
    except Exception as exc:
        return f"Error: {exc}"


@tool
def read_file(filepath: str) -> str:
    """Reads the content of a file."""
    try:
        path = _resolve_safe(filepath)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as exc:
        return f"Error: {exc}"


@tool
def write_file(filepath: str, content: str) -> str:
    """Writes content to a new file. Automatically creates parent directories.
    DO NOT use this tool to update existing files; use edit_file instead."""
    try:
        allowed, reason = can_execute("edit", f"write_file:{filepath}")
        if not allowed:
            return reason or "Error: write not allowed."
        path = _resolve_safe(filepath)
        path_str = str(path)
        if os.path.isdir(path) or path_str.endswith("/") or path_str.endswith("\\"):
            return (
                f"Error: '{filepath}' is a directory. "
                "You must specify a complete file path including the file name."
            )

        content = content.strip()
        if (content.startswith('"') and content.endswith('"')) or (
            content.startswith("'") and content.endswith("'")
        ):
            content = content[1:-1]

        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines)

        os.makedirs(path.parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as exc:
        return f"Error: {exc}"


@tool
def edit_file(filepath: str, target_string: str, replacement_string: str) -> str:
    """Edits an existing file by replacing an exact target string with a replacement string.
    The target_string MUST match exactly what is in the file.
    Use this instead of write_file for modifying existing code.
    """
    try:
        allowed, reason = can_execute("edit", f"edit_file:{filepath}")
        if not allowed:
            return reason or "Error: edit not allowed."
        path = _resolve_safe(filepath)
        if not os.path.exists(path):
            return f"Error: File '{filepath}' does not exist. Use write_file to create it."

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if replacement_string.startswith("```"):
            lines = replacement_string.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            replacement_string = "\n".join(lines)

        if target_string not in content:
            return (
                f"Error: target_string not found in {path}. "
                "Please ensure you matched the file's exact spacing and content."
            )

        new_content = content.replace(target_string, replacement_string)

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"Successfully updated {path}"
    except Exception as exc:
        return f"Error: {exc}"
