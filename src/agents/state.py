"""Shared LangGraph state schema and routing constants."""
from __future__ import annotations

import operator
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """The state object that flows through every node of the multi-agent graph."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str


# Worker agents that the supervisor can route to. Order matters for display
# in the welcome banner.
MEMBERS: list[str] = ["ProjectManager", "UXUIDesigner", "Developer"]

# Every value the supervisor's structured-output ``RouteResponse`` may pick.
ROUTE_OPTIONS: list[str] = ["FINISH"] + MEMBERS
