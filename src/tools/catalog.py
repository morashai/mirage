"""Canonical deduplicated tool catalog for Mirage.

This file defines the single source of truth for tool identifiers that are
exported to LangChain/LangGraph agents. Keep one capability per tool id.
"""
from __future__ import annotations

from typing import Dict, Tuple

# capability -> canonical tool id
TOOL_CATALOG: Dict[str, str] = {
    # Filesystem
    "filesystem.list": "list_directory",
    "filesystem.read": "read_file",
    "filesystem.write": "write_file",
    "filesystem.edit": "edit_file",
    # Shell / process
    "shell.exec": "run_shell_command",
    # Search
    "search.glob": "glob_search",
    "search.rg": "ripgrep_search",
    # Git
    "git.status": "git_status",
    "git.diff": "git_diff",
    "git.log": "git_log",
    "git.branch": "git_current_branch",
    # Web
    "web.fetch": "web_fetch",
    "web.search": "web_search",
    # Notebook
    "notebook.read": "read_notebook",
    "notebook.edit_cell": "edit_notebook_cell",
    # MCP (local descriptors + placeholder call)
    "mcp.list_servers": "list_mcp_servers",
    "mcp.list_tools": "list_mcp_tools",
    "mcp.read_schema": "read_mcp_tool_schema",
    "mcp.call_tool": "call_mcp_tool",
}


READ_ONLY_CAPABILITIES: Tuple[str, ...] = (
    "filesystem.list",
    "filesystem.read",
    "search.glob",
    "search.rg",
    "git.status",
    "git.diff",
    "git.log",
    "git.branch",
    "web.fetch",
    "web.search",
    "notebook.read",
    "mcp.list_servers",
    "mcp.list_tools",
    "mcp.read_schema",
)


DEVELOPER_EXTRA_CAPABILITIES: Tuple[str, ...] = (
    "filesystem.write",
    "filesystem.edit",
    "shell.exec",
    "notebook.edit_cell",
    "mcp.call_tool",
)

