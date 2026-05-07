"""Shared helpers for turning a LangGraph react agent into a graph node."""
from __future__ import annotations

from typing import Any, Callable

from langchain_core.messages import AIMessage

from .state import AgentState


def make_node(agent: Any, name: str) -> Callable[[AgentState], dict]:
    """Wrap a react agent so it conforms to a LangGraph node callable.

    The returned function invokes ``agent`` on the current state and emits an
    ``AIMessage`` named after the agent so downstream consumers (rendering,
    routing) can identify the speaker.
    """

    def node(state: AgentState):
        result = agent.invoke(state)
        last = result["messages"][-1]
        return {"messages": [AIMessage(content=last.content, name=name)]}

    node.__name__ = f"{name.lower()}_node"
    return node
