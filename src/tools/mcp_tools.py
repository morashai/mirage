"""MCP descriptor helpers and placeholder call tool."""
from __future__ import annotations

import json
import os
from pathlib import Path

from langchain_core.tools import tool

from ..config_store import list_mcp_servers_merged


def _mcps_root() -> Path:
    env_root = os.getenv("MIRAGE_MCPS_ROOT")
    if env_root:
        return Path(env_root)
    # Fallback to standard Cursor MCP folder layout relative to workspace.
    return Path.cwd() / "mcps"


@tool
def list_mcp_servers() -> str:
    """List available MCP servers from local descriptor folder."""
    try:
        root = _mcps_root()
        descriptor_servers: list[str] = []
        if root.exists():
            descriptor_servers = sorted([p.name for p in root.iterdir() if p.is_dir()])
        configured = list_mcp_servers_merged()
        configured_names = [s.name for s in configured]
        all_names = sorted(set(descriptor_servers + configured_names))
        if not all_names:
            return f"No MCP servers found (descriptors root: {root})."
        lines: list[str] = []
        configured_map = {s.name: s for s in configured}
        descriptor_set = set(descriptor_servers)
        for name in all_names:
            tags: list[str] = []
            if name in descriptor_set:
                tags.append("descriptor")
            if name in configured_map:
                tags.append(
                    f"configured:{'enabled' if configured_map[name].enabled else 'disabled'}"
                )
            tag_text = f" ({', '.join(tags)})" if tags else ""
            lines.append(f"{name}{tag_text}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error: {exc}"


@tool
def list_mcp_tools(server: str) -> str:
    """List tools for one MCP server from descriptor files."""
    try:
        tools_dir = _mcps_root() / server / "tools"
        if not tools_dir.exists():
            return f"Error: tools folder not found for server '{server}'."
        names = sorted([p.stem for p in tools_dir.glob("*.json")])
        return "\n".join(names) if names else "No tools found."
    except Exception as exc:
        return f"Error: {exc}"


@tool
def read_mcp_tool_schema(server: str, tool_name: str) -> str:
    """Read MCP tool descriptor JSON for one tool."""
    try:
        path = _mcps_root() / server / "tools" / f"{tool_name}.json"
        if not path.exists():
            return f"Error: tool descriptor not found at {path}"
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        return f"Error: {exc}"


@tool
def call_mcp_tool(server: str, tool_name: str, arguments_json: str = "{}") -> str:
    """Placeholder MCP call bridge.

    This project currently exposes descriptor discovery only.
    """
    try:
        json.loads(arguments_json)
    except Exception:
        return "Error: arguments_json must be valid JSON."

    return (
        "Not supported in local Mirage runtime yet. "
        f"server={server}, tool={tool_name}. "
        "Use list_mcp_servers/list_mcp_tools/read_mcp_tool_schema for now."
    )

