"""Process-wide configuration: env loading + default knobs."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL: str = os.getenv("MIRAGE_CLI_MODEL", "gpt-4.1-mini")
RECURSION_LIMIT: int = int(os.getenv("MIRAGE_CLI_RECURSION_LIMIT", "75"))
