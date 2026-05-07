"""Typed LLM selection passed into the multi-agent graph."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMSpec:
    """Provider + model id used to construct chat models for all agents."""

    provider: str  # openai | anthropic | google
    model: str
