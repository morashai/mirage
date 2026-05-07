"""Backward-compatible shim for smoke tests and script-style imports."""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from src.agents.graph import _build_agents, build_graph
from src.agents.state import MEMBERS, AgentState
from src.cli.input_box import _prompt_input_box
from src.cli.session import handle_slash_command, run_agent

__all__ = [
    "AIMessage",
    "AgentState",
    "HumanMessage",
    "MEMBERS",
    "_build_agents",
    "_prompt_input_box",
    "build_graph",
    "handle_slash_command",
    "run_agent",
]
