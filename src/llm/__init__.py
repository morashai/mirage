"""LLM catalog and factory for Mirage CLI."""
from __future__ import annotations

__all__ = [
    "DEFAULT_BASE_URLS",
    "LLMSpec",
    "PROVIDERS",
    "list_models_for_provider",
    "make_llm",
]


def __getattr__(name: str):
    if name in {"DEFAULT_BASE_URLS", "PROVIDERS", "list_models_for_provider"}:
        from .catalog import DEFAULT_BASE_URLS, PROVIDERS, list_models_for_provider

        return {
            "DEFAULT_BASE_URLS": DEFAULT_BASE_URLS,
            "PROVIDERS": PROVIDERS,
            "list_models_for_provider": list_models_for_provider,
        }[name]
    if name == "LLMSpec":
        from .spec import LLMSpec

        return LLMSpec
    if name == "make_llm":
        from .factory import make_llm

        return make_llm
    raise AttributeError(f"module 'src.llm' has no attribute {name!r}")
