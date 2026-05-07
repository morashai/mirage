"""Persistent chat session metadata + checkpoint deletion."""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config_store import PROVIDERS, sessions_db_path, sessions_index_path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class SessionRecord:
    thread_id: str
    name: str
    provider: str
    model: str
    created_at: str
    last_active_at: str


INDEX_VERSION = 1


class SessionStore:
    """JSON index of sessions; LangGraph state lives in ``sessions.db``."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or sessions_index_path()

    def _load_blob(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {"version": INDEX_VERSION, "sessions": []}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"version": INDEX_VERSION, "sessions": []}

    def _save_blob(self, blob: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(blob, indent=2, sort_keys=True) + "\n"
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(self._path)

    def list_sessions(self) -> list[SessionRecord]:
        blob = self._load_blob()
        rows = blob.get("sessions") or []
        out: list[SessionRecord] = []
        for row in rows:
            try:
                out.append(
                    SessionRecord(
                        thread_id=str(row["thread_id"]),
                        name=str(row.get("name") or ""),
                        provider=str(row.get("provider") or "openai"),
                        model=str(row.get("model") or ""),
                        created_at=str(row.get("created_at") or ""),
                        last_active_at=str(row.get("last_active_at") or ""),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        out.sort(key=lambda r: r.last_active_at or "", reverse=True)
        return out

    def get(self, thread_id: str) -> SessionRecord | None:
        for s in self.list_sessions():
            if s.thread_id == thread_id:
                return s
        return None

    def ensure_session(
        self,
        thread_id: str,
        *,
        name: str,
        provider: str,
        model: str,
    ) -> SessionRecord:
        """Insert or update metadata for a thread so it appears in listings."""
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}")
        blob = self._load_blob()
        blob.setdefault("version", INDEX_VERSION)
        sessions: list[dict[str, Any]] = list(blob.get("sessions") or [])
        now = _utc_now_iso()
        for row in sessions:
            if row.get("thread_id") == thread_id:
                row["name"] = name or row.get("name") or thread_id
                row["provider"] = provider
                row["model"] = model
                row["last_active_at"] = now
                blob["sessions"] = sessions
                self._save_blob(blob)
                return SessionRecord(
                    thread_id=thread_id,
                    name=str(row["name"]),
                    provider=str(row["provider"]),
                    model=str(row["model"]),
                    created_at=str(row.get("created_at") or now),
                    last_active_at=now,
                )

        rec = {
            "thread_id": thread_id,
            "name": name or thread_id,
            "provider": provider,
            "model": model,
            "created_at": now,
            "last_active_at": now,
        }
        sessions.append(rec)
        blob["sessions"] = sessions
        self._save_blob(blob)
        return SessionRecord(
            thread_id=thread_id,
            name=str(rec["name"]),
            provider=provider,
            model=model,
            created_at=now,
            last_active_at=now,
        )

    def touch(self, thread_id: str) -> None:
        blob = self._load_blob()
        sessions: list[dict[str, Any]] = list(blob.get("sessions") or [])
        now = _utc_now_iso()
        for row in sessions:
            if row.get("thread_id") == thread_id:
                row["last_active_at"] = now
                blob["sessions"] = sessions
                self._save_blob(blob)
                return

    def rename(self, thread_id: str, new_name: str) -> bool:
        blob = self._load_blob()
        sessions: list[dict[str, Any]] = list(blob.get("sessions") or [])
        for row in sessions:
            if row.get("thread_id") == thread_id:
                row["name"] = new_name.strip() or row["thread_id"]
                blob["sessions"] = sessions
                self._save_blob(blob)
                return True
        return False

    def delete(self, thread_id: str) -> bool:
        blob = self._load_blob()
        sessions: list[dict[str, Any]] = list(blob.get("sessions") or [])
        new_list = [r for r in sessions if r.get("thread_id") != thread_id]
        if len(new_list) == len(sessions):
            return False
        blob["sessions"] = new_list
        self._save_blob(blob)
        delete_checkpoint_thread(thread_id)
        return True


def delete_checkpoint_thread(thread_id: str) -> None:
    """Remove all SQLite checkpoint rows for a thread id."""
    db_path = sessions_db_path()
    if not db_path.is_file():
        return
    conn = sqlite3.connect(str(db_path))
    try:
        # Order respects typical FK chains in LangGraph sqlite schema.
        for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            try:
                conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (thread_id,))
            except sqlite3.OperationalError:
                continue
        conn.commit()
    finally:
        conn.close()


def new_thread_id() -> str:
    return f"session-{uuid.uuid4().hex[:8]}"


def resolve_session_selector(
    selector: str,
    ordered: list[SessionRecord],
) -> SessionRecord | None:
    """Resolve ``1``-based index or exact ``thread_id`` (prefix match)."""
    sel = selector.strip()
    if sel.isdigit():
        idx = int(sel)
        if 1 <= idx <= len(ordered):
            return ordered[idx - 1]
        return None
    # Exact match
    for r in ordered:
        if r.thread_id == sel:
            return r
    # Prefix match
    matches = [r for r in ordered if r.thread_id.startswith(sel)]
    if len(matches) == 1:
        return matches[0]
    return None
