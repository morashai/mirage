"""Process-wide configuration: env loading + default knobs."""
from __future__ import annotations

import os

from .config_store import load_config

RECURSION_LIMIT: int = int(os.getenv("MIRAGE_CLI_RECURSION_LIMIT", "75"))

_cfg = load_config()
DEFAULT_MODEL: str = _cfg.default_model
DEFAULT_PROVIDER: str = _cfg.default_provider
