"""Multi-agent definitions.

Public surface:
- ``AgentState`` — the LangGraph state schema shared by every node.
- ``MEMBERS`` — ordered list of worker-agent names.
- ``ROUTE_OPTIONS`` — every value the supervisor may pick (``MEMBERS`` + ``"FINISH"``).
- ``build_graph(model_name)`` — compiles the multi-agent ``StateGraph``.

To add a new agent:
1. Add its system prompt to ``prompts.py``.
2. Add its name to ``MEMBERS`` in ``state.py`` (and update the supervisor's
   ``RouteResponse`` Literal in ``supervisor.py``).
3. Add a ``build_<agent>(llm)`` builder module beside the existing ones.
4. Wire it into ``graph._build_agents``.
"""
from .graph import _build_agents, build_graph
from .state import AgentState, MEMBERS, ROUTE_OPTIONS

__all__ = [
    "AgentState",
    "MEMBERS",
    "ROUTE_OPTIONS",
    "build_graph",
    "_build_agents",
]
