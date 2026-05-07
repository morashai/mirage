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
    },
    PLAN_MODE: {
        "edit": "ask",
        "bash": "ask",
        "read": "allow",
    },
}


def policy_for_mode(mode: str) -> Policy:
    key = mode.strip().lower()
    return deepcopy(MODE_POLICIES.get(key, MODE_POLICIES[BUILD_MODE]))
