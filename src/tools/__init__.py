"""Tool registry with deduplication guard and capability groupings."""
from __future__ import annotations

from .catalog import DEVELOPER_EXTRA_CAPABILITIES, READ_ONLY_CAPABILITIES, TOOL_CATALOG
from .filesystem import edit_file, list_directory, read_file, write_file
from .git_tools import git_current_branch, git_diff, git_log, git_status
from .mcp_tools import call_mcp_tool, list_mcp_servers, list_mcp_tools, read_mcp_tool_schema
from .notebook_tools import edit_notebook_cell, read_notebook
from .search import glob_search, ripgrep_search
from .shell import run_shell_command
from .web_tools import web_fetch, web_search

ALL_TOOLS = [
    list_directory,
    read_file,
    write_file,
    edit_file,
    run_shell_command,
    glob_search,
    ripgrep_search,
    git_status,
    git_diff,
    git_log,
    git_current_branch,
    web_fetch,
    web_search,
    read_notebook,
    edit_notebook_cell,
    list_mcp_servers,
    list_mcp_tools,
    read_mcp_tool_schema,
    call_mcp_tool,
]

_TOOL_BY_NAME = {t.name: t for t in ALL_TOOLS}
if len(_TOOL_BY_NAME) != len(ALL_TOOLS):
    names = [t.name for t in ALL_TOOLS]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    raise RuntimeError(f"Duplicate tool names detected: {duplicates}")

if set(TOOL_CATALOG.values()) != set(_TOOL_BY_NAME.keys()):
    missing = sorted(set(TOOL_CATALOG.values()) - set(_TOOL_BY_NAME.keys()))
    extra = sorted(set(_TOOL_BY_NAME.keys()) - set(TOOL_CATALOG.values()))
    raise RuntimeError(
        f"Catalog mismatch. missing={missing if missing else []}, extra={extra if extra else []}"
    )

READ_ONLY_TOOLS = [_TOOL_BY_NAME[TOOL_CATALOG[c]] for c in READ_ONLY_CAPABILITIES]
DEVELOPER_TOOLS = READ_ONLY_TOOLS + [
    _TOOL_BY_NAME[TOOL_CATALOG[c]] for c in DEVELOPER_EXTRA_CAPABILITIES
]

__all__ = [
    "ALL_TOOLS",
    "READ_ONLY_TOOLS",
    "DEVELOPER_TOOLS",
    "TOOL_CATALOG",
    "list_directory",
    "read_file",
    "write_file",
    "edit_file",
    "run_shell_command",
    "glob_search",
    "ripgrep_search",
    "git_status",
    "git_diff",
    "git_log",
    "git_current_branch",
    "web_fetch",
    "web_search",
    "read_notebook",
    "edit_notebook_cell",
    "list_mcp_servers",
    "list_mcp_tools",
    "read_mcp_tool_schema",
    "call_mcp_tool",
]
