"""UX/UI Designer agent — read-only spec author.

Plans the UI/UX and produces a written specification. Hands off to the
Developer for implementation. NEVER writes code or files.
"""
from __future__ import annotations

from typing import Any, Sequence

from langgraph.prebuilt import create_react_agent

from .prompts import ux_ui_designer_prompt


def build_ux_ui_designer(llm: Any, tools: Sequence[Any]):
    """Construct the UX/UI Designer react agent.

    The caller is expected to pass only read-only tools — the Developer is
    the sole agent allowed to write code or files.
    """
    return create_react_agent(llm, tools=list(tools), prompt=ux_ui_designer_prompt)
