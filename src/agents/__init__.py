"""Multi-agent definitions."""
from __future__ import annotations

__all__ = [
    "AgentState",
    "MEMBERS",
    "ROUTE_OPTIONS",
    "build_graph",
    "_build_agents",
]


def __getattr__(name: str):
    if name in {"build_graph", "_build_agents"}:
        from .graph import _build_agents, build_graph

        return {"build_graph": build_graph, "_build_agents": _build_agents}[name]
    if name in {"AgentState", "MEMBERS", "ROUTE_OPTIONS"}:
        from .state import AgentState, MEMBERS, ROUTE_OPTIONS

        return {
            "AgentState": AgentState,
            "MEMBERS": MEMBERS,
            "ROUTE_OPTIONS": ROUTE_OPTIONS,
        }[name]
    raise AttributeError(f"module 'src.agents' has no attribute {name!r}")
