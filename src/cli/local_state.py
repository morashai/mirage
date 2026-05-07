"""Local persisted runtime preferences (model recents/favorites/variants)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..config_store import mirage_dir


@dataclass
class LocalModelState:
    recent: list[str] = field(default_factory=list)
    favorite: list[str] = field(default_factory=list)
    variant: dict[str, str] = field(default_factory=dict)


def _state_path():
    return mirage_dir() / "model_state.json"


def load_local_model_state() -> LocalModelState:
    path = _state_path()
    if not path.is_file():
        return LocalModelState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return LocalModelState()
    recent = [str(x) for x in payload.get("recent", []) if isinstance(x, str)]
    favorite = [str(x) for x in payload.get("favorite", []) if isinstance(x, str)]
    variant_raw = payload.get("variant", {})
    variant = (
        {str(k): str(v) for k, v in variant_raw.items()}
        if isinstance(variant_raw, dict)
        else {}
    )
    return LocalModelState(recent=recent, favorite=favorite, variant=variant)


def save_local_model_state(state: LocalModelState) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "recent": state.recent,
        "favorite": state.favorite,
        "variant": state.variant,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def touch_recent_model(provider: str, model: str) -> None:
    key = f"{provider}/{model}"
    st = load_local_model_state()
    items = [key] + [x for x in st.recent if x != key]
    st.recent = items[:10]
    save_local_model_state(st)

