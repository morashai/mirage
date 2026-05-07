"""Wire every agent into a compiled LangGraph ``StateGraph``.

This is the single place where:
- each agent's *tool wiring* is declared,
- workers are connected back to the supervisor, and
- the supervisor's structured-output decision is mapped to a graph edge.

To add a new worker agent:
1. Add a builder module beside ``project_manager.py`` etc.
2. Append its name to ``MEMBERS`` in ``state.py``.
3. Update the ``RouteResponse`` Literal in ``supervisor.py``.
4. Construct it inside ``_build_agents`` and add it to the returned dict.
"""
from __future__ import annotations

import warnings

from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
# LangGraph currently triggers a pending-deprecation warning from
# langchain_core.load.Reviver defaults during import. Suppress that one
# known warning category/message so normal CLI output stays clean.
warnings.filterwarnings(
    "ignore",
    category=LangChainPendingDeprecationWarning,
    message=(
        "The default value of `allowed_objects` will change in a future version\\..*"
    ),
)

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from ..tools import DEVELOPER_TOOLS, READ_ONLY_TOOLS
from .developer import build_developer
from .factory import make_node
from .project_manager import build_project_manager
from .state import AgentState, MEMBERS
from .supervisor import build_supervisor_chain
from .ux_ui_designer import build_ux_ui_designer


def _build_agents(model_name: str):
    """Instantiate every agent + the supervisor and return them as nodes.

    Returns a dict keyed by graph node name (matching ``MEMBERS`` plus
    ``"supervisor"``) so ``build_graph`` can wire them up directly.
    """
    llm = ChatOpenAI(model=model_name)

    pm_tools = list(READ_ONLY_TOOLS)
    project_manager_agent = build_project_manager(llm, pm_tools)

    # Designer is read-only by design — it plans and hands off; only the
    # Developer is allowed to create or modify code or files.
    designer_tools = list(READ_ONLY_TOOLS)
    designer_agent = build_ux_ui_designer(llm, designer_tools)

    developer_tools = list(DEVELOPER_TOOLS)
    developer_agent = build_developer(llm, developer_tools)

    supervisor_chain = build_supervisor_chain(llm)

    project_manager_node = make_node(project_manager_agent, "ProjectManager")
    ux_ui_designer_node = make_node(designer_agent, "UXUIDesigner")
    developer_node = make_node(developer_agent, "Developer")

    def supervisor_node(state: AgentState):
        result = supervisor_chain.invoke({"messages": state["messages"]})
        chosen = result.next

        # Guardrail: never terminate before any worker has responded.
        has_worker_reply = any(
            isinstance(msg, AIMessage) and getattr(msg, "name", "") in MEMBERS
            for msg in state["messages"]
        )
        if not has_worker_reply and chosen == "FINISH":
            chosen = "ProjectManager"

        return {"next": chosen}

    return {
        "ProjectManager": project_manager_node,
        "UXUIDesigner": ux_ui_designer_node,
        "Developer": developer_node,
        "supervisor": supervisor_node,
    }


def build_graph(model_name: str = "gpt-4o"):
    """Compile the multi-agent ``StateGraph`` with an in-memory checkpointer."""
    nodes = _build_agents(model_name)

    workflow = StateGraph(AgentState)
    for member in MEMBERS:
        workflow.add_node(member, nodes[member])
    workflow.add_node("supervisor", nodes["supervisor"])

    # Workers always loop back through the supervisor.
    for member in MEMBERS:
        workflow.add_edge(member, "supervisor")

    # Supervisor's routing decision goes directly to the chosen worker
    # (or END). Agents handle the full handoff flow autonomously — no
    # human review gate.
    workflow.add_conditional_edges(
        "supervisor",
        lambda x: x["next"],
        {**{m: m for m in MEMBERS}, "FINISH": END},
    )
    workflow.add_edge(START, "supervisor")

    memory = InMemorySaver()
    return workflow.compile(checkpointer=memory)
