from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config_store import (
    MCPServerConfig,
    delete_mcp_server,
    disable_mcp_server,
    list_mcp_servers,
    list_mcp_servers_merged,
    save_mcp_server,
)


class MCPManagementTests(unittest.TestCase):
    def test_layered_user_project_merge_and_disable(self) -> None:
        with tempfile.TemporaryDirectory() as home_tmp, tempfile.TemporaryDirectory() as proj_tmp:
            project = Path(proj_tmp)
            (project / ".mirage").mkdir(parents=True, exist_ok=True)
            env = {"USERPROFILE": home_tmp, "HOME": home_tmp}
            with patch.dict(os.environ, env, clear=False):
                cwd = Path.cwd()
                try:
                    os.chdir(project)
                    save_mcp_server(
                        MCPServerConfig(
                            name="github",
                            enabled=True,
                            kind="local",
                            command="npx",
                            args=["-y"],
                        ),
                        "user",
                    )
                    save_mcp_server(
                        MCPServerConfig(
                            name="github",
                            enabled=False,
                            kind="local",
                            command="npx",
                            args=["-y", "@modelcontextprotocol/server-github"],
                        ),
                        "project",
                    )
                    save_mcp_server(
                        MCPServerConfig(
                            name="linear",
                            enabled=True,
                            kind="remote",
                            url="https://mcp.linear.app",
                        ),
                        "project",
                    )

                    merged = {s.name: s for s in list_mcp_servers_merged()}
                    self.assertIn("github", merged)
                    self.assertIn("linear", merged)
                    self.assertFalse(merged["github"].enabled)
                    self.assertEqual(merged["linear"].kind, "remote")

                    self.assertTrue(disable_mcp_server("linear", "project"))
                    project_rows = {s.name: s for s in list_mcp_servers("project")}
                    self.assertFalse(project_rows["linear"].enabled)
                finally:
                    os.chdir(cwd)

    def test_delete_mcp_server_removes_entry(self) -> None:
        with tempfile.TemporaryDirectory() as home_tmp, tempfile.TemporaryDirectory() as proj_tmp:
            project = Path(proj_tmp)
            (project / ".mirage").mkdir(parents=True, exist_ok=True)
            env = {"USERPROFILE": home_tmp, "HOME": home_tmp}
            with patch.dict(os.environ, env, clear=False):
                cwd = Path.cwd()
                try:
                    os.chdir(project)
                    save_mcp_server(
                        MCPServerConfig(
                            name="linear",
                            enabled=True,
                            kind="remote",
                            url="https://mcp.linear.app",
                        ),
                        "project",
                    )
                    self.assertTrue(delete_mcp_server("linear", "project"))
                    rows = {s.name: s for s in list_mcp_servers("project")}
                    self.assertNotIn("linear", rows)
                    self.assertFalse(delete_mcp_server("linear", "project"))
                finally:
                    os.chdir(cwd)

if __name__ == "__main__":
    unittest.main()
