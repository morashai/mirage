"""Simple runtime session event stream for CLI parity output."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class SessionEvent:
    type: str
    session_id: str
    data: dict[str, Any]
    timestamp: int


def make_event(event_type: str, session_id: str, **data: Any) -> SessionEvent:
    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    return SessionEvent(type=event_type, session_id=session_id, data=data, timestamp=ts)

