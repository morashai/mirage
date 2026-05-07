from __future__ import annotations

import unittest

from src.cli.agent_registry import default_primary_agent, load_agent_registry
from src.cli.local_state import LocalModelState
from src.cli.modes import BUILD_MODE, PLAN_MODE, policy_for_mode


class CLIRunParityTests(unittest.TestCase):
    def test_default_primary_agent_is_build(self) -> None:
        agent = default_primary_agent()
        self.assertEqual(agent.name, "build")
        self.assertEqual(agent.runtime_mode, BUILD_MODE)

    def test_registry_has_primary_and_subagent_modes(self) -> None:
        registry = load_agent_registry()
        self.assertIn("build", registry)
        self.assertIn("plan", registry)
        self.assertIn("general", registry)
        self.assertEqual(registry["general"].mode, "subagent")

    def test_mode_policies_match_parity_expectations(self) -> None:
        build = policy_for_mode(BUILD_MODE)
        plan = policy_for_mode(PLAN_MODE)
        self.assertEqual(build["edit"], "allow")
        self.assertEqual(plan["edit"], "deny")
        self.assertEqual(plan["plan_exit"], "allow")

    def test_local_state_shape(self) -> None:
        state = LocalModelState()
        self.assertEqual(state.recent, [])
        self.assertEqual(state.favorite, [])
        self.assertEqual(state.variant, {})


if __name__ == "__main__":
    unittest.main()

