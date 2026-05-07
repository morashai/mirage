"""src — Mirage LangGraph CLI.

Public surface re-exported for convenient imports:

    from src import app, build_graph, AgentState, MEMBERS
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agents.state import AgentState

__all__ = ["app", "build_graph", "AgentState", "MEMBERS"]


def __getattr__(name: str):
    if name == "app":
        from .cli.app import app

        return app
    if name == "build_graph":
        from .agents.graph import build_graph

        return build_graph
    if name in {"AgentState", "MEMBERS"}:
        from .agents.state import AgentState, MEMBERS

        mapping = {
            "AgentState": AgentState,
            "MEMBERS": MEMBERS,
        }
        return mapping[name]
    raise AttributeError(f"module 'src' has no attribute {name!r}")
