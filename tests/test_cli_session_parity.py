from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.sessions.store import SessionStore


class CLISessionParityTests(unittest.TestCase):
    def test_fork_preserves_parent_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(path=Path(tmpdir) / "sessions.json")
            parent = store.ensure_session(
                "session-parent",
                name="Parent",
                provider="openai",
                model="gpt-4.1-mini",
                permission_policy={"edit": "deny"},
            )
            child = store.fork(parent.thread_id, name="Child")
            self.assertEqual(child.parent_thread_id, parent.thread_id)
            self.assertEqual(child.provider, parent.provider)
            self.assertEqual(child.model, parent.model)
            self.assertEqual(child.permission_policy, {"edit": "deny"})

    def test_set_permission_and_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(path=Path(tmpdir) / "sessions.json")
            rec = store.ensure_session(
                "session-a",
                name="A",
                provider="openai",
                model="gpt-4.1-mini",
            )
            self.assertTrue(store.set_permission(rec.thread_id, {"edit": "deny", "bash": "ask"}))
            self.assertTrue(store.set_archived(rec.thread_id, True))
            loaded = store.get(rec.thread_id)
            assert loaded is not None
            self.assertEqual(loaded.permission_policy, {"edit": "deny", "bash": "ask"})
            self.assertIsNotNone(loaded.archived_at)


if __name__ == "__main__":
    unittest.main()

