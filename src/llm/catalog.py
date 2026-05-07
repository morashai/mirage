"""Curated model ids per provider (free-form ids are still accepted)."""
from __future__ import annotations

PROVIDERS: tuple[str, ...] = ("openai", "anthropic", "google")

# Shown as placeholders in the model form; APIs may use env defaults when URL is empty.
DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "google": "",
}

OPENAI_MODELS: list[str] = [
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o",
    "gpt-4o-mini",
    "o3",
    "o3-mini",
    "o4-mini",
]

ANTHROPIC_MODELS: list[str] = [
    "claude-opus-4-5",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
    "claude-3-7-sonnet-latest",
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-latest",
    "claude-3-opus-latest",
]

GOOGLE_MODELS: list[str] = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]

_CATALOG: dict[str, list[str]] = {
    "openai": OPENAI_MODELS,
    "anthropic": ANTHROPIC_MODELS,
    "google": GOOGLE_MODELS,
}


def list_models_for_provider(provider: str) -> list[str]:
    """Return curated model ids for a Mirage provider key."""
    return list(_CATALOG.get(provider, []))
