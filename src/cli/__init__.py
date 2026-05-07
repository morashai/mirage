"""Terminal interface: Typer commands, Rich rendering, and the
prompt_toolkit input box.
"""
from __future__ import annotations

__all__ = ["app"]


def __getattr__(name: str):
    if name == "app":
        from .app import app

        return app
    raise AttributeError(f"module 'src.cli' has no attribute {name!r}")
