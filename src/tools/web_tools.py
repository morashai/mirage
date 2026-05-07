"""Basic web fetch/search tools."""
from __future__ import annotations

import json
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from langchain_core.tools import tool


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _extract_related_topics(raw_topics: list[object]) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    stack = list(raw_topics)
    while stack:
        item = stack.pop(0)
        if not isinstance(item, dict):
            continue
        if "Topics" in item and isinstance(item["Topics"], list):
            stack = list(item["Topics"]) + stack
            continue
        first_url = _safe_text(item.get("FirstURL"))
        text = _safe_text(item.get("Text"))
        if first_url:
            results.append((text, first_url))
    return results


def _http_get(url: str, timeout_seconds: int = 20) -> str:
    request = Request(
        url,
        headers={"User-Agent": "mirage-cli/0.1 (+https://example.local)"},
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")


@tool
def web_fetch(url: str) -> str:
    """Fetch a URL and return response text."""
    try:
        return _http_get(url)
    except Exception as exc:
        return f"Error: {exc}"


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo instant answer API."""
    try:
        clean_query = query.strip()
        if not clean_query:
            return "Error: query cannot be empty."

        encoded = quote_plus(query)
        url = (
            "https://api.duckduckgo.com/"
            f"?q={encoded}&format=json&no_html=1&no_redirect=1"
        )
        raw = _http_get(url)
        data = json.loads(raw)
        lines = []
        abstract_url = _safe_text(data.get("AbstractURL"))
        if abstract_url:
            heading = _safe_text(data.get("Heading"), default="Result")
            lines.append(f"{heading} -> {abstract_url}")

        answer = _safe_text(data.get("Answer"))
        if answer:
            lines.append(f"Answer: {answer}")

        definition = _safe_text(data.get("Definition"))
        if definition:
            lines.append(f"Definition: {definition}")

        related = _extract_related_topics(data.get("RelatedTopics", []))
        for text, first_url in related:
            label = text if text else "(related result)"
            lines.append(f"{label} -> {first_url}")
            if len(lines) >= max(1, max_results):
                break

        return "\n".join(lines) if lines else "No results found."
    except Exception as exc:
        return f"Error: {exc}"

