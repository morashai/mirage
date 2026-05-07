from __future__ import annotations

import unittest

from src.agents.routing import (
    detect_ping_pong_loop,
    detect_repeated_developer_output,
    resolve_next_route,
)


class Message:
    def __init__(self, content: str, name: str = "") -> None:
        self.content = content
        self.name = name


class AgentRoutingTests(unittest.TestCase):
    def test_finish_is_blocked_before_worker_reply(self) -> None:
        messages = [Message(content="hi")]
        choice = resolve_next_route("FINISH", messages, ["ProjectManager", "Developer"])
        self.assertEqual(choice, "ProjectManager")

    def test_detects_ping_pong_loop(self) -> None:
        messages = [
            Message(content="A", name="ProjectManager"),
            Message(content="B", name="Developer"),
            Message(content="A", name="ProjectManager"),
            Message(content="B", name="Developer"),
        ]
        self.assertTrue(detect_ping_pong_loop(messages, ["ProjectManager", "Developer"]))
        choice = resolve_next_route("Developer", messages, ["ProjectManager", "Developer"])
        self.assertEqual(choice, "FINISH")

    def test_detects_repeated_developer_output(self) -> None:
        messages = [
            Message(content="same", name="Developer"),
            Message(content="same", name="Developer"),
            Message(content="same", name="Developer"),
        ]
        self.assertTrue(detect_repeated_developer_output(messages))
        choice = resolve_next_route("ProjectManager", messages, ["ProjectManager", "Developer"])
        self.assertEqual(choice, "FINISH")


if __name__ == "__main__":
    unittest.main()
