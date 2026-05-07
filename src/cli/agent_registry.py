from __future__ import annotations

from dataclasses import dataclass, field

from .mirage_compat import load_custom_agents
from .modes import BUILD_MODE, PLAN_MODE, policy_for_mode


@dataclass
class AgentProfile:
    name: str
    description: str
    mode: str = "primary"  # primary | subagent | all
    native: bool = False
    hidden: bool = False
    runtime_mode: str | None = None  # build | plan
    model: str | None = None
    permission: dict[str, str] = field(default_factory=dict)


def _merge_policy(*policies: dict[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for policy in policies:
        for key, value in policy.items():
            merged[key] = value
    return merged


def built_in_agents() -> dict[str, AgentProfile]:
    defaults = {"edit": "allow", "bash": "allow", "read": "allow"}
    build_perm = _merge_policy(defaults, policy_for_mode(BUILD_MODE), {"question": "allow"})
    plan_perm = _merge_policy(
        defaults,
        policy_for_mode(PLAN_MODE),
        {"question": "allow", "plan_exit": "allow"},
    )
    return {
        "build": AgentProfile(
            name="build",
            description="The default agent. Executes tools based on configured permissions.",
            mode="primary",
            native=True,
            runtime_mode=BUILD_MODE,
            permission=build_perm,
        ),
        "plan": AgentProfile(
            name="plan",
            description="Plan mode. Read-only analysis with strict edit permissions.",
            mode="primary",
            native=True,
            runtime_mode=PLAN_MODE,
            permission=plan_perm,
        ),
        "general": AgentProfile(
            name="general",
            description="General-purpose subagent for complex searches and multistep tasks.",
            mode="subagent",
            native=True,
            runtime_mode=BUILD_MODE,
            permission=_merge_policy(defaults, {"todowrite": "deny"}),
        ),
    }


def load_agent_registry() -> dict[str, AgentProfile]:
    registry = built_in_agents()
    for name, custom in load_custom_agents().items():
        existing = registry.get(name)
        runtime_mode = (custom.mode or "").strip().lower()
        if runtime_mode not in {BUILD_MODE, PLAN_MODE}:
            runtime_mode = existing.runtime_mode if existing else BUILD_MODE
        profile = AgentProfile(
            name=name,
            description=custom.description or (existing.description if existing else ""),
            mode=(existing.mode if existing else "all"),
            native=False if existing is None else existing.native,
            hidden=False if existing is None else existing.hidden,
            runtime_mode=runtime_mode,
            model=custom.model or (existing.model if existing else None),
            permission=dict(existing.permission) if existing else policy_for_mode(runtime_mode),
        )
        if custom.permission:
            profile.permission["edit"] = custom.permission
        registry[name] = profile
    return registry


def list_primary_agents() -> list[AgentProfile]:
    return [agent for agent in load_agent_registry().values() if agent.mode != "subagent" and not agent.hidden]


def default_primary_agent() -> AgentProfile:
    visible = list_primary_agents()
    if not visible:
        raise ValueError("no primary visible agent found")
    build = next((item for item in visible if item.name == "build"), None)
    return build or visible[0]

