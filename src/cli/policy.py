"""Global runtime permission policy for tool execution gates."""
from __future__ import annotations

import sys
from copy import deepcopy

_ACTIVE_POLICY: dict[str, str] = {"edit": "allow", "bash": "allow", "read": "allow"}


def get_policy() -> dict[str, str]:
    return deepcopy(_ACTIVE_POLICY)


def set_policy(policy: dict[str, str]) -> None:
    global _ACTIVE_POLICY
    _ACTIVE_POLICY = deepcopy(policy)


def _resolve_action(action: str) -> str:
    return (_ACTIVE_POLICY.get(action) or "allow").strip().lower()


def can_execute(action: str, label: str) -> tuple[bool, str | None]:
    mode = _resolve_action(action)
    if mode == "allow":
        return True, None
    if mode == "deny":
        return False, f"Error: blocked by Mirage policy ({action} denied): {label}"
    if mode != "ask":
        return True, None
    if not sys.stdin or not sys.stdin.isatty():
        return False, f"Error: blocked by Mirage policy ({action} requires approval): {label}"
    try:
        answer = input(f"[Mirage approval] allow {action} action '{label}'? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False, f"Error: blocked by Mirage policy ({action} approval cancelled): {label}"
    if answer in {"y", "yes"}:
        return True, None
    return False, f"Error: blocked by Mirage policy ({action} not approved): {label}"
