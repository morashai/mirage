"""Read/write filesystem tools used by the agents.

Only the Developer agent is allowed to use the write tools (``write_file``,
``edit_file``); the Project Manager and UX/UI Designer get only the
read-only tools. This is enforced at agent-construction time in
``src.agents``.
"""
from __future__ import annotations

import os

from langchain_core.tools import tool


@tool
def list_directory(path: str) -> str:
    """Lists the files and directories in the given path."""
    try:
        items = os.listdir(path)
        return "\n".join(items) if items else "Directory is empty."
    except Exception as e:
        return f"Error: {e}"


@tool
def read_file(filepath: str) -> str:
    """Reads the content of a file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error: {e}"


@tool
def write_file(filepath: str, content: str) -> str:
    """Writes content to a new file. Automatically creates parent directories.
    DO NOT use this tool to update existing files; use edit_file instead."""
    try:
        if os.path.isdir(filepath) or filepath.endswith("/") or filepath.endswith("\\"):
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

        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {filepath}"
    except Exception as e:
        return f"Error: {e}"


@tool
def edit_file(filepath: str, target_string: str, replacement_string: str) -> str:
    """Edits an existing file by replacing an exact target string with a replacement string.
    The target_string MUST match exactly what is in the file.
    Use this instead of write_file for modifying existing code.
    """
    try:
        if not os.path.exists(filepath):
            return f"Error: File '{filepath}' does not exist. Use write_file to create it."

        with open(filepath, "r", encoding="utf-8") as f:
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
                f"Error: target_string not found in {filepath}. "
                "Please ensure you matched the file's exact spacing and content."
            )

        new_content = content.replace(target_string, replacement_string)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"Successfully updated {filepath}"
    except Exception as e:
        return f"Error: {e}"
