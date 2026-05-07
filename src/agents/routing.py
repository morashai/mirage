"""Pure routing helpers for supervisor next-node decisions."""
from __future__ import annotations

from typing import Any, Sequence


def normalize_content(content: str) -> str:
    return " ".join((content or "").split()).strip().lower()


def _message_name(message: Any) -> str:
    return str(getattr(message, "name", "") or "")


def worker_messages(messages: Sequence[Any], members: Sequence[str]) -> list[Any]:
    return [
        msg
        for msg in messages
        if _message_name(msg) in members
    ]


def has_worker_reply(messages: Sequence[Any], members: Sequence[str]) -> bool:
    return bool(worker_messages(messages, members))


def detect_ping_pong_loop(messages: Sequence[Any], members: Sequence[str]) -> bool:
    workers = worker_messages(messages, members)
    if len(workers) < 4:
        return False
    sig = [
        (m.name, normalize_content(getattr(m, "content", "") or ""))
        for m in workers[-4:]
    ]
    return sig[0] == sig[2] and sig[1] == sig[3]


def detect_repeated_developer_output(
    messages: Sequence[Any],
    *,
    required_repeats: int = 3,
) -> bool:
    workers = [
        msg
        for msg in messages
        if _message_name(msg) == "Developer"
    ]
    if len(workers) < required_repeats:
        return False
    last = workers[-required_repeats:]
    normalized = [normalize_content(getattr(m, "content", "") or "") for m in last]
    return bool(normalized[0]) and all(n == normalized[0] for n in normalized[1:])


def resolve_next_route(
    supervisor_choice: str,
    messages: Sequence[Any],
    members: Sequence[str],
) -> str:
    chosen = supervisor_choice
    if chosen == "FINISH" and not has_worker_reply(messages, members):
        return "ProjectManager"
    if detect_ping_pong_loop(messages, members):
        return "FINISH"
    if detect_repeated_developer_output(messages):
        return "FINISH"
    return chosen
