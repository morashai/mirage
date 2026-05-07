"""Session index and checkpoint helpers."""
from __future__ import annotations

__all__ = ["SessionRecord", "SessionStore"]


def __getattr__(name: str):
    if name in {"SessionRecord", "SessionStore"}:
        from .store import SessionRecord, SessionStore

        return {"SessionRecord": SessionRecord, "SessionStore": SessionStore}[name]
    raise AttributeError(f"module 'src.sessions' has no attribute {name!r}")
