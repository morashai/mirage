"""Stable console entrypoint for Mirage CLI installs."""
from __future__ import annotations

import sys

from src.cli.app import app


def main() -> None:
    """Run Mirage CLI, defaulting to interactive chat when no args are passed."""
    if len(sys.argv) == 1:
        sys.argv.append("chat")
    app()


if __name__ == "__main__":
    main()

