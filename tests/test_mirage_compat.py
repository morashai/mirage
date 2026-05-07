from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.cli.edit_history import EditTransaction, FileSnapshot, record_transaction, redo_last, undo_last
from src.cli.policy import can_execute, set_policy
from src.cli.project_paths import ensure_mirage_scaffold, find_project_root
from src.cli.mirage_compat import (
    apply_command_template,
    load_custom_agents,
    load_custom_commands,
    load_mirage_project_defaults,
)


class MirageCompatTests(unittest.TestCase):
    def test_apply_command_template_arguments(self) -> None:
        rendered = apply_command_template("Run $1 and $ARGUMENTS now", "tests unit")
        self.assertEqual(rendered, "Run tests and tests unit now")

    def test_load_custom_command_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cmd_dir = root / ".mirage" / "commands"
            cmd_dir.mkdir(parents=True, exist_ok=True)
            (cmd_dir / "test.md").write_text(
                "---\n"
                "description: Run tests\n"
                "agent: build\n"
                "subtask: true\n"
                "---\n"
                "echo $ARGUMENTS\n",
                encoding="utf-8",
            )
            commands = load_custom_commands(root)
            self.assertIn("test", commands)
            self.assertEqual(commands["test"].agent, "build")
            self.assertTrue(commands["test"].subtask)

    def test_load_custom_agents_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            agents_dir = root / ".mirage" / "agents"
            agents_dir.mkdir(parents=True, exist_ok=True)
            (agents_dir / "review.md").write_text(
                "---\n"
                "description: Reviewer\n"
                "mode: subagent\n"
                "model: openai/gpt-5\n"
                "---\n"
                "Prompt\n",
                encoding="utf-8",
            )
            agents = load_custom_agents(root)
            self.assertIn("review", agents)
            self.assertEqual(agents["review"].mode, "subagent")
            self.assertIn("Prompt", agents["review"].prompt)

    def test_project_default_model_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "mirage.json").write_text('{"model":"openai/gpt-4.1-mini"}', encoding="utf-8")
            parsed = load_mirage_project_defaults(root)
            self.assertEqual(parsed["provider"], "openai")
            self.assertEqual(parsed["model"], "gpt-4.1-mini")

    def test_edit_history_undo_redo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "x.txt"
            file_path.write_text("before", encoding="utf-8")
            tx = EditTransaction(
                files=[
                    FileSnapshot(
                        path=str(file_path),
                        before_exists=True,
                        before_content="before",
                        after_exists=True,
                        after_content="after",
                    )
                ]
            )
            record_transaction("thread-a", tx)
            self.assertEqual(undo_last("thread-a"), 1)
            self.assertEqual(file_path.read_text(encoding="utf-8"), "before")
            self.assertEqual(redo_last("thread-a"), 1)
            self.assertEqual(file_path.read_text(encoding="utf-8"), "after")

    def test_scaffold_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.assertTrue(ensure_mirage_scaffold(root))
            self.assertTrue((root / ".mirage").is_dir())
            self.assertTrue((root / ".mirage" / "agents").is_dir())
            self.assertTrue((root / ".mirage" / "commands").is_dir())

    def test_find_project_root_with_mirage_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "mirage.json").write_text("{}", encoding="utf-8")
            nested = root / "a" / "b"
            nested.mkdir(parents=True, exist_ok=True)
            self.assertEqual(find_project_root(nested), root)

    def test_permission_policy_deny(self) -> None:
        set_policy({"edit": "deny", "bash": "allow", "read": "allow"})
        allowed, reason = can_execute("edit", "edit_file:test.txt")
        self.assertFalse(allowed)
        self.assertIn("blocked by Mirage policy", reason or "")
        set_policy({"edit": "allow", "bash": "allow", "read": "allow"})


if __name__ == "__main__":
    unittest.main()
