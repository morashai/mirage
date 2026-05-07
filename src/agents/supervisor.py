"""Supervisor — chooses which teammate should act next.

Uses ``llm.with_structured_output(RouteResponse)`` to force a JSON-shaped
decision rather than free-form text.
"""
from __future__ import annotations

from typing import Any, Literal

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel

from .prompts import supervisor_system_prompt
from .state import ROUTE_OPTIONS


class RouteResponse(BaseModel):
    """Structured-output schema for the supervisor's routing decision."""

    next: Literal["ProjectManager", "UXUIDesigner", "Developer", "FINISH"]


def build_supervisor_chain(llm: Any):
    """Compose the prompt + structured-output chain that the supervisor uses."""
    sup_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", supervisor_system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                "Given the conversation above, who should act next? "
                f"Choose exactly one of: {ROUTE_OPTIONS}.",
            ),
        ]
    )

    return sup_prompt | llm.with_structured_output(RouteResponse)
