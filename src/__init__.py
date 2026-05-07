"""src — Mirage, a multi-agent LangGraph CLI.

Public surface re-exported for convenient imports:

    from src import app, build_graph, AgentState, MEMBERS
"""
from .agents.graph import build_graph
from .agents.state import AgentState, MEMBERS, ROUTE_OPTIONS
from .cli.app import app

__all__ = ["app", "build_graph", "AgentState", "MEMBERS", "ROUTE_OPTIONS"]
