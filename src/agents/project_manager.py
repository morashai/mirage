"""Project Manager agent — read-only planner.

Breaks a user request into a structured plan and recommends the next agent.
"""
from __future__ import annotations

from typing import Any, Sequence

from langgraph.prebuilt import create_react_agent

from .prompts import project_manager_prompt


def build_project_manager(llm: Any, tools: Sequence[Any]):
    """Construct the Project Manager react agent.

    The caller is expected to pass only read-only tools (the supervisor's
    contract treats this agent as read-only).
    """
    return create_react_agent(llm, tools=list(tools), prompt=project_manager_prompt)
