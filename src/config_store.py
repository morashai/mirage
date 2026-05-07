"""Persistent Mirage CLI configuration (~/.mirage/config.json)."""
from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .cli.project_paths import find_project_root
from .llm.catalog import PROVIDERS

load_dotenv()

CONFIG_VERSION = 1
DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL_FALLBACK = os.getenv("MIRAGE_CLI_MODEL", "gpt-4.1-mini")


def mirage_dir() -> Path:
    """Directory for Mirage config, session index, and SQLite checkpoints."""
    return Path.home() / ".mirage"


def config_path() -> Path:
    env_override = os.getenv("MIRAGE_CONFIG_PATH")
    if env_override:
        maybe = Path(env_override).expanduser()
        if maybe.is_file():
            return maybe
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


@dataclass
class MCPServerConfig:
    name: str
    enabled: bool
    kind: str  # local | remote
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None


def user_mcp_servers_path() -> Path:
    return mirage_dir() / "mcp_servers.json"


def project_mcp_servers_path() -> Path:
    return find_project_root() / ".mirage" / "mcp_servers.json"


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


def _load_mcp_blob(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"servers": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"servers": []}
    if not isinstance(payload, dict):
        return {"servers": []}
    payload.setdefault("servers", [])
    if not isinstance(payload["servers"], list):
        payload["servers"] = []
    return payload


def _save_mcp_blob(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    _umask_safe_write(path, text)


def _row_to_mcp_server(row: dict[str, Any]) -> MCPServerConfig | None:
    try:
        name = str(row.get("name") or "").strip()
        kind = str(row.get("kind") or "").strip().lower()
        if not name or kind not in {"local", "remote"}:
            return None
        enabled = bool(row.get("enabled", True))
        command = str(row.get("command") or "").strip() or None
        url = str(row.get("url") or "").strip() or None
        raw_args = row.get("args") if isinstance(row.get("args"), list) else []
        args = [str(x) for x in raw_args]
        return MCPServerConfig(
            name=name,
            enabled=enabled,
            kind=kind,
            command=command,
            args=args,
            url=url,
        )
    except Exception:  # noqa: BLE001
        return None


def list_mcp_servers(scope: str) -> list[MCPServerConfig]:
    target = user_mcp_servers_path() if scope == "user" else project_mcp_servers_path()
    payload = _load_mcp_blob(target)
    servers: list[MCPServerConfig] = []
    for row in payload.get("servers", []):
        if not isinstance(row, dict):
            continue
        parsed = _row_to_mcp_server(row)
        if parsed:
            servers.append(parsed)
    return servers


def list_mcp_servers_merged() -> list[MCPServerConfig]:
    merged: dict[str, MCPServerConfig] = {}
    for server in list_mcp_servers("user"):
        merged[server.name] = server
    for server in list_mcp_servers("project"):
        merged[server.name] = server
    return sorted(merged.values(), key=lambda x: x.name.lower())


def save_mcp_server(server: MCPServerConfig, scope: str) -> None:
    target = user_mcp_servers_path() if scope == "user" else project_mcp_servers_path()
    payload = _load_mcp_blob(target)
    rows = [r for r in payload.get("servers", []) if isinstance(r, dict)]
    updated = False
    for idx, row in enumerate(rows):
        if str(row.get("name") or "").strip() == server.name:
            rows[idx] = asdict(server)
            updated = True
            break
    if not updated:
        rows.append(asdict(server))
    payload["servers"] = rows
    _save_mcp_blob(target, payload)


def disable_mcp_server(name: str, scope: str) -> bool:
    target = user_mcp_servers_path() if scope == "user" else project_mcp_servers_path()
    payload = _load_mcp_blob(target)
    rows = [r for r in payload.get("servers", []) if isinstance(r, dict)]
    changed = False
    found = False
    for row in rows:
        if str(row.get("name") or "").strip() == name:
            found = True
            if bool(row.get("enabled", True)):
                row["enabled"] = False
                changed = True
    if not found:
        return False
    if changed:
        payload["servers"] = rows
        _save_mcp_blob(target, payload)
    return True


def delete_mcp_server(name: str, scope: str) -> bool:
    target = user_mcp_servers_path() if scope == "user" else project_mcp_servers_path()
    payload = _load_mcp_blob(target)
    rows = [r for r in payload.get("servers", []) if isinstance(r, dict)]
    new_rows = [r for r in rows if str(r.get("name") or "").strip() != name]
    if len(new_rows) == len(rows):
        return False
    payload["servers"] = new_rows
    _save_mcp_blob(target, payload)
    return True


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

    cfg = _blob_to_cfg(blob)
    _apply_mirage_inline_overrides(cfg)
    _apply_mirage_project_defaults(cfg)
    return cfg


def _apply_mirage_project_defaults(cfg: MirageConfig) -> None:
    """Apply lightweight project-level defaults from ``mirage.json`` when present."""
    project_file = find_project_root() / "mirage.json"
    if not project_file.is_file():
        return
    try:
        raw = json.loads(project_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    model = str(raw.get("model") or "").strip()
    if "/" in model:
        prov, _, mdl = model.partition("/")
        prov = prov.strip().lower()
        mdl = mdl.strip()
        if prov in PROVIDERS and mdl:
            cfg.default_provider = prov
            cfg.default_model = mdl


def _apply_mirage_inline_overrides(cfg: MirageConfig) -> None:
    """Apply MIRAGE_CONFIG_CONTENT model/provider hints when available."""
    raw = os.getenv("MIRAGE_CONFIG_CONTENT")
    if not raw:
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return
    model = str(data.get("model") or "").strip()
    if "/" in model:
        prov, _, mdl = model.partition("/")
        prov = prov.strip().lower()
        mdl = mdl.strip()
        if prov in PROVIDERS and mdl:
            cfg.default_provider = prov
            cfg.default_model = mdl


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
