from __future__ import annotations

import unittest

from src.sessions.store import SessionRecord, resolve_session_selector


class SessionSelectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [
            SessionRecord(
                thread_id="session-abc12345",
                name="A",
                provider="openai",
                model="gpt-4.1-mini",
                created_at="",
                last_active_at="",
            ),
            SessionRecord(
                thread_id="session-def67890",
                name="B",
                provider="anthropic",
                model="claude-sonnet-4-5",
                created_at="",
                last_active_at="",
            ),
        ]

    def test_resolves_one_based_index(self) -> None:
        hit = resolve_session_selector("2", self.rows)
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.thread_id, "session-def67890")

    def test_returns_none_for_out_of_range_index(self) -> None:
        self.assertIsNone(resolve_session_selector("3", self.rows))

    def test_returns_none_for_ambiguous_prefix(self) -> None:
        self.assertIsNone(resolve_session_selector("session-", self.rows))


if __name__ == "__main__":
    unittest.main()
