"""LLM catalog and factory for Mirage CLI."""
from __future__ import annotations

from .catalog import DEFAULT_BASE_URLS, PROVIDERS, list_models_for_provider
from .factory import make_llm
from .spec import LLMSpec

__all__ = [
    "DEFAULT_BASE_URLS",
    "LLMSpec",
    "PROVIDERS",
    "list_models_for_provider",
    "make_llm",
]
