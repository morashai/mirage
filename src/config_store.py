"""Persistent Mirage CLI configuration (~/.mirage/config.json)."""
from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .llm.catalog import PROVIDERS

load_dotenv()

CONFIG_VERSION = 1
DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL_FALLBACK = os.getenv("MIRAGE_CLI_MODEL", "gpt-4.1-mini")


def mirage_dir() -> Path:
    """Directory for Mirage config, session index, and SQLite checkpoints."""
    return Path.home() / ".mirage"


def config_path() -> Path:
    return mirage_dir() / "config.json"


def sessions_db_path() -> Path:
    return mirage_dir() / "sessions.db"


def sessions_index_path() -> Path:
    return mirage_dir() / "sessions.json"


@dataclass
class ProviderSettings:
    api_key: str | None = None
    base_url: str | None = None


@dataclass
class MirageConfig:
    """Runtime configuration loaded from disk + env defaults."""

    version: int = CONFIG_VERSION
    default_provider: str = DEFAULT_PROVIDER
    default_model: str = DEFAULT_MODEL_FALLBACK
    providers: dict[str, ProviderSettings] = field(default_factory=dict)

    def provider_settings(self, provider: str) -> ProviderSettings:
        if provider not in self.providers:
            self.providers[provider] = ProviderSettings()
        return self.providers[provider]


def _umask_safe_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    try:
        mode = stat.S_IRUSR | stat.S_IWUSR
        os.chmod(path, mode)
    except (NotImplementedError, OSError, PermissionError):
        pass


def _default_providers_blob() -> dict[str, dict[str, Any]]:
    return {p: {"api_key": None, "base_url": None} for p in PROVIDERS}


def _migrate_env_into_blob(blob: dict[str, Any]) -> None:
    providers = blob.setdefault("providers", {})
    if not isinstance(providers, dict):
        providers.clear()
    for p in PROVIDERS:
        providers.setdefault(p, {"api_key": None, "base_url": None})

    env_keys = {
        "openai": os.getenv("OPENAI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
        "google": os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
    }
    for prov, key in env_keys.items():
        if key and not providers.get(prov, {}).get("api_key"):
            entry = providers.setdefault(prov, {"api_key": None, "base_url": None})
            entry["api_key"] = key


def load_config() -> MirageConfig:
    """Load ``config.json`` or create defaults + migrate env vars once."""
    path = config_path()
    if not path.is_file():
        blob: dict[str, Any] = {
            "version": CONFIG_VERSION,
            "default_provider": DEFAULT_PROVIDER,
            "default_model": DEFAULT_MODEL_FALLBACK,
            "providers": _default_providers_blob(),
        }
        _migrate_env_into_blob(blob)
        save_config_blob(blob)
        return _blob_to_cfg(blob)

    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        blob = {
            "version": CONFIG_VERSION,
            "default_provider": DEFAULT_PROVIDER,
            "default_model": DEFAULT_MODEL_FALLBACK,
            "providers": _default_providers_blob(),
        }

    blob.setdefault("version", CONFIG_VERSION)
    blob.setdefault("default_provider", DEFAULT_PROVIDER)
    blob.setdefault("default_model", DEFAULT_MODEL_FALLBACK)
    blob.setdefault("providers", _default_providers_blob())
    _migrate_env_into_blob(blob)

    # Normalize provider keys
    prov = blob["providers"]
    for p in PROVIDERS:
        prov.setdefault(p, {"api_key": None, "base_url": None})

    return _blob_to_cfg(blob)


def _blob_to_cfg(blob: dict[str, Any]) -> MirageConfig:
    providers: dict[str, ProviderSettings] = {}
    raw = blob.get("providers") or {}
    for name in PROVIDERS:
        entry = raw.get(name) or {}
        providers[name] = ProviderSettings(
            api_key=entry.get("api_key"),
            base_url=entry.get("base_url"),
        )
    return MirageConfig(
        version=int(blob.get("version", CONFIG_VERSION)),
        default_provider=str(blob.get("default_provider", DEFAULT_PROVIDER)),
        default_model=str(blob.get("default_model", DEFAULT_MODEL_FALLBACK)),
        providers=providers,
    )


def save_config(cfg: MirageConfig) -> None:
    """Persist configuration to disk."""
    blob = {
        "version": cfg.version,
        "default_provider": cfg.default_provider,
        "default_model": cfg.default_model,
        "providers": {
            p: {
                "api_key": cfg.providers[p].api_key,
                "base_url": cfg.providers[p].base_url,
            }
            for p in PROVIDERS
        },
    }
    save_config_blob(blob)


def save_config_blob(blob: dict[str, Any]) -> None:
    path = config_path()
    text = json.dumps(blob, indent=2, sort_keys=True) + "\n"
    _umask_safe_write(path, text)


def resolve_api_key(cfg: MirageConfig, provider: str) -> str | None:
    """Stored key wins; otherwise standard env vars."""
    stored = cfg.provider_settings(provider).api_key
    if stored:
        return stored
    env_map = {
        "openai": os.getenv("OPENAI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
        "google": os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
    }
    return env_map.get(provider)


def resolve_base_url(cfg: MirageConfig, provider: str) -> str | None:
    """Return custom base URL from store only (empty means SDK default)."""
    url = cfg.provider_settings(provider).base_url
    if url and str(url).strip():
        return str(url).strip()
    return None


def mask_secret(secret: str | None, *, keep_prefix: int = 4, keep_suffix: int = 4) -> str:
    """Mask an API key for display."""
    if not secret:
        return "(not set)"
    s = secret.strip()
    if len(s) <= keep_prefix + keep_suffix:
        return "***"
    return f"{s[:keep_prefix]}***…{s[-keep_suffix:]}"


def parse_model_arg(arg: str | None) -> tuple[str | None, str | None]:
    """Parse ``provider:model`` or bare ``model``."""
    if not arg:
        return None, None
    arg = arg.strip()
    if ":" in arg:
        prov, _, rest = arg.partition(":")
        prov = prov.strip().lower()
        rest = rest.strip()
        if prov in PROVIDERS and rest:
            return prov, rest
    return None, arg
