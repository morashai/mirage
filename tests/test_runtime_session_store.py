from __future__ import annotations

import unittest
from dataclasses import replace

from src.cli.runtime_state import RuntimeSessionState, RuntimeSessionStore
from src.cli.modes import BUILD_MODE, policy_for_mode
from src.sessions.store import SessionStore


class RuntimeSessionStoreTests(unittest.TestCase):
    def _initial_state(self) -> RuntimeSessionState:
        return RuntimeSessionState(
            thread_id="session-a1",
            provider="openai",
            model="gpt-4.1-mini",
            session_name="session-a1",
            session_store=SessionStore(),
            mode=BUILD_MODE,
            permission_policy=policy_for_mode(BUILD_MODE),
            cfg=object(),
            graph=object(),
        )

    def test_derive_and_on_change_hooks_run(self) -> None:
        events: list[tuple[str, str]] = []

        def derive(prev: RuntimeSessionState, nxt: RuntimeSessionState) -> RuntimeSessionState:
            if prev.model != nxt.model:
                return replace(nxt, cfg="cfg2", graph="graph2")
            return nxt

        def on_change(new_state: RuntimeSessionState, old_state: RuntimeSessionState) -> None:
            events.append((old_state.model, new_state.model))

        store = RuntimeSessionStore(
            self._initial_state(),
            derive_state=derive,
            on_change=on_change,
        )
        store.set_state(lambda prev: replace(prev, model="gpt-4.1"))
        state = store.get_state()
        self.assertEqual(state.cfg, "cfg2")
        self.assertEqual(state.graph, "graph2")
        self.assertEqual(events, [("gpt-4.1-mini", "gpt-4.1")])

    def test_invalid_provider_is_rejected(self) -> None:
        store = RuntimeSessionStore(self._initial_state())
        with self.assertRaises(ValueError):
            store.set_state(lambda prev: replace(prev, provider="invalid-provider"))


if __name__ == "__main__":
    unittest.main()
