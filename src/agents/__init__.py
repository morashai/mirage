"""Agent graph definitions."""
from __future__ import annotations

__all__ = [
    "AgentState",
    "MEMBERS",
    "build_graph",
]


def __getattr__(name: str):
    if name == "build_graph":
        from .graph import build_graph
        return build_graph
    if name in {"AgentState", "MEMBERS"}:
        from .state import AgentState, MEMBERS

        return {
            "AgentState": AgentState,
            "MEMBERS": MEMBERS,
        }[name]
    raise AttributeError(f"module 'src.agents' has no attribute {name!r}")
