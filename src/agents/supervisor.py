"""Compatibility shim for legacy supervisor imports."""
from __future__ import annotations

from typing import Any, Literal

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel


class RouteResponse(BaseModel):
    """Structured-output schema retained for compatibility."""

    next: Literal["Build", "FINISH"]


def build_supervisor_chain(llm: Any):
    """Return a fixed Build routing chain (legacy compatibility)."""
    sup_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "Route to Build for runtime execution."),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                "Given the conversation above, who should act next? "
                "Choose exactly one of: ['Build', 'FINISH'].",
            ),
        ]
    )

    return sup_prompt | llm.with_structured_output(RouteResponse)
