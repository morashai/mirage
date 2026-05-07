"""Construct chat models for OpenAI, Anthropic, and Google GenAI."""
from __future__ import annotations

from typing import Any

from langchain.chat_models import init_chat_model

# Map Mirage CLI provider keys -> init_chat_model model_provider values.
_INIT_PROVIDER: dict[str, str] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google_genai",
}


def make_llm(
    provider: str,
    model: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Any:
    """Return a LangChain chat model instance.

    When ``api_key`` / ``base_url`` are omitted, underlying SDKs read from
    environment variables (e.g. ``OPENAI_API_KEY``).
    """
    mp = _INIT_PROVIDER.get(provider)
    if mp is None:
        raise ValueError(f"Unknown provider: {provider!r}. Expected one of {list(_INIT_PROVIDER)}.")

    kwargs: dict[str, Any] = {}
    if api_key:
        if mp == "google_genai":
            kwargs["google_api_key"] = api_key
        else:
            kwargs["api_key"] = api_key

    if base_url and base_url.strip():
        bu = base_url.strip()
        if mp in ("openai", "anthropic"):
            kwargs["base_url"] = bu
        # google_genai: omit unless the integration adds explicit support.

    try:
        return init_chat_model(model, model_provider=mp, **kwargs)
    except ImportError as e:
        missing = {
            "openai": "langchain-openai",
            "anthropic": "langchain-anthropic",
            "google_genai": "langchain-google-genai",
        }.get(mp, "the provider integration package")
        raise ImportError(
            f"Provider {provider!r} requires {missing}. Install dependencies and retry."
        ) from e
