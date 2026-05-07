"""Entrypoint for running Mirage CLI as a module or script path.

Supports both:
- ``python -m src`` (package context)
- ``uv run .\\src\\`` / direct script-style execution (no package context)
"""
import sys

try:
    # Normal package execution path.
    from .cli.app import app
except ImportError:
    # Fallback for script-style execution where ``__package__`` is empty.
    from src.cli.app import app


def _main() -> None:
    if len(sys.argv) == 1:
        sys.argv.append("chat")
    app()


if __name__ == "__main__":
    _main()
