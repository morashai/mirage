"""Developer agent — the only agent allowed to write code or files."""
from __future__ import annotations

from typing import Any, Sequence

from langgraph.prebuilt import create_react_agent

from .prompts import developer_prompt


def build_developer(llm: Any, tools: Sequence[Any]):
    """Construct the Developer react agent.

    The caller passes the full toolset (read + write). This is the only
    agent permitted to mutate files.
    """
    return create_react_agent(llm, tools=list(tools), prompt=developer_prompt)
