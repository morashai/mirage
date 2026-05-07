"""Per-thread edit history for /undo and /redo."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileSnapshot:
    path: str
    before_exists: bool
    before_content: str
    after_exists: bool
    after_content: str


@dataclass
class EditTransaction:
    files: list[FileSnapshot] = field(default_factory=list)


@dataclass
class ThreadEditHistory:
    undo_stack: list[EditTransaction] = field(default_factory=list)
    redo_stack: list[EditTransaction] = field(default_factory=list)


_HISTORY: dict[str, ThreadEditHistory] = {}


def _bucket(thread_id: str) -> ThreadEditHistory:
    if thread_id not in _HISTORY:
        _HISTORY[thread_id] = ThreadEditHistory()
    return _HISTORY[thread_id]


def record_transaction(thread_id: str, transaction: EditTransaction) -> None:
    if not transaction.files:
        return
    bucket = _bucket(thread_id)
    bucket.undo_stack.append(transaction)
    bucket.redo_stack.clear()


def undo_last(thread_id: str) -> int:
    bucket = _bucket(thread_id)
    if not bucket.undo_stack:
        return 0
    tx = bucket.undo_stack.pop()
    for item in tx.files:
        p = Path(item.path)
        if item.before_exists:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(item.before_content, encoding="utf-8")
        elif p.exists():
            p.unlink()
    bucket.redo_stack.append(tx)
    return len(tx.files)


def redo_last(thread_id: str) -> int:
    bucket = _bucket(thread_id)
    if not bucket.redo_stack:
        return 0
    tx = bucket.redo_stack.pop()
    for item in tx.files:
        p = Path(item.path)
        if item.after_exists:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(item.after_content, encoding="utf-8")
        elif p.exists():
            p.unlink()
    bucket.undo_stack.append(tx)
    return len(tx.files)
