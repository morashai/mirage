"""Runtime mode and permission policy definitions."""
from __future__ import annotations

from copy import deepcopy

Policy = dict[str, str]

BUILD_MODE = "build"
PLAN_MODE = "plan"

MODE_POLICIES: dict[str, Policy] = {
    BUILD_MODE: {
        "edit": "allow",
        "bash": "allow",
        "read": "allow",
        "question": "allow",
        "plan_enter": "allow",
        "plan_exit": "deny",
    },
    PLAN_MODE: {
        "edit": "deny",
        "bash": "ask",
        "read": "allow",
        "question": "allow",
        "plan_enter": "deny",
        "plan_exit": "allow",
    },
}


def policy_for_mode(mode: str) -> Policy:
    key = mode.strip().lower()
    return deepcopy(MODE_POLICIES.get(key, MODE_POLICIES[BUILD_MODE]))
