"""Primary agent builder (Build/Plan)."""
from __future__ import annotations

from typing import Any, Sequence

from langgraph.prebuilt import create_react_agent

from .prompts import build_primary_prompt


def build_primary_agent(llm: Any, tools: Sequence[Any], *, mode: str = "build"):
    """Construct the primary react agent for Mirage runtime."""
    prompt = build_primary_prompt(mode)
    return create_react_agent(llm, tools=list(tools), prompt=prompt)
