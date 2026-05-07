"""Shared LangGraph state schema for single-agent runtime."""
from __future__ import annotations

import operator
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """The state object that flows through every node."""

    messages: Annotated[Sequence[BaseMessage], operator.add]


# Single primary worker agent (Build/Plan behavior).
MEMBERS: list[str] = ["Build"]

