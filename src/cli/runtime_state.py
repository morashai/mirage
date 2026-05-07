"""Runtime session state store for Mirage CLI chat sessions."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from ..llm.catalog import PROVIDERS
from ..sessions.store import SessionStore


@dataclass(frozen=True)
class RuntimeSessionState:
    """Mutable-at-runtime session state, updated through ``RuntimeSessionStore``."""

    thread_id: str
    provider: str
    model: str
    session_name: str
    session_store: SessionStore
    mode: str
    permission_policy: dict[str, str]
    cfg: object
    graph: object
    spec_driven_enabled: bool = False


Listener = Callable[[], None]
Updater = Callable[[RuntimeSessionState], RuntimeSessionState]
Derive = Callable[[RuntimeSessionState, RuntimeSessionState], RuntimeSessionState]
OnChange = Callable[[RuntimeSessionState, RuntimeSessionState], None]


def validate_runtime_state(state: RuntimeSessionState) -> None:
    """Enforce invariants for production-safe runtime state transitions."""
    if not state.thread_id.strip():
        raise ValueError("thread_id must be non-empty")
    if state.provider not in PROVIDERS:
        raise ValueError(f"unknown provider: {state.provider}")
    if not state.model.strip():
        raise ValueError("model must be non-empty")
    if not state.session_name.strip():
        raise ValueError("session_name must be non-empty")
    if not state.mode.strip():
        raise ValueError("mode must be non-empty")


class RuntimeSessionStore:
    """Tiny external store inspired by Claude CLI's state store pattern."""

    def __init__(
        self,
        initial_state: RuntimeSessionState,
        *,
        derive_state: Derive | None = None,
        on_change: OnChange | None = None,
    ) -> None:
        validate_runtime_state(initial_state)
        self._state = initial_state
        self._derive_state = derive_state
        self._on_change = on_change
        self._listeners: set[Listener] = set()

    def get_state(self) -> RuntimeSessionState:
        return self._state

    def set_state(self, updater: Updater) -> None:
        prev = self._state
        candidate = updater(prev)
        validate_runtime_state(candidate)
        next_state = self._derive_state(prev, candidate) if self._derive_state else candidate
        validate_runtime_state(next_state)
        if next_state == prev:
            return
        self._state = next_state
        if self._on_change is not None:
            self._on_change(next_state, prev)
        for listener in tuple(self._listeners):
            listener()

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        self._listeners.add(listener)

        def _unsubscribe() -> None:
            self._listeners.discard(listener)

        return _unsubscribe


def with_state(
    state: RuntimeSessionState,
    *,
    thread_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    session_name: str | None = None,
    session_store: SessionStore | None = None,
    mode: str | None = None,
    permission_policy: dict[str, str] | None = None,
    cfg: object | None = None,
    graph: object | None = None,
    spec_driven_enabled: bool | None = None,
) -> RuntimeSessionState:
    """Convenience helper for immutable updates with optional field overrides."""
    return replace(
        state,
        thread_id=thread_id if thread_id is not None else state.thread_id,
        provider=provider if provider is not None else state.provider,
        model=model if model is not None else state.model,
        session_name=session_name if session_name is not None else state.session_name,
        session_store=session_store if session_store is not None else state.session_store,
        mode=mode if mode is not None else state.mode,
        permission_policy=(
            permission_policy if permission_policy is not None else state.permission_policy
        ),
        cfg=cfg if cfg is not None else state.cfg,
        graph=graph if graph is not None else state.graph,
        spec_driven_enabled=(
            spec_driven_enabled
            if spec_driven_enabled is not None
            else state.spec_driven_enabled
        ),
    )
