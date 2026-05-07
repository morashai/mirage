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

import sqlite3
import warnings
from typing import TYPE_CHECKING, Any

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

from langgraph.graph import END, START, StateGraph

from ..config_store import MirageConfig, load_config, resolve_api_key, resolve_base_url
from ..llm.factory import make_llm
from ..llm.spec import LLMSpec
from ..tools import DEVELOPER_TOOLS, READ_ONLY_TOOLS
from .developer import build_developer
from .factory import make_node
from .project_manager import build_project_manager
from .routing import resolve_next_route
from .state import AgentState, MEMBERS
from .supervisor import build_supervisor_chain
from .ux_ui_designer import build_ux_ui_designer

if TYPE_CHECKING:
    from langgraph.checkpoint.sqlite import SqliteSaver

_sqlite_checkpointer: Any | None = None
_sqlite_conn: sqlite3.Connection | None = None


def _get_checkpointer():
    """Use SQLite persistence for all LangGraph checkpoints."""
    global _sqlite_checkpointer, _sqlite_conn
    if _sqlite_checkpointer is None:
        from ..config_store import sessions_db_path
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver

            path = sessions_db_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            _sqlite_conn = sqlite3.connect(str(path), check_same_thread=False)
            _sqlite_checkpointer = SqliteSaver(_sqlite_conn)
            _sqlite_checkpointer.setup()
        except Exception as e:
            raise RuntimeError(
                "SQLite checkpoint persistence is required but unavailable. "
                "Install dependency: `py -m pip install langgraph-checkpoint-sqlite`."
            ) from e
    return _sqlite_checkpointer


def _build_agents(llm):
    """Instantiate every agent + the supervisor and return them as nodes.

    Returns a dict keyed by graph node name (matching ``MEMBERS`` plus
    ``"supervisor"``) so ``build_graph`` can wire them up directly.
    """
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
        chosen = resolve_next_route(result.next, state["messages"], MEMBERS)
        return {"next": chosen}

    return {
        "ProjectManager": project_manager_node,
        "UXUIDesigner": ux_ui_designer_node,
        "Developer": developer_node,
        "supervisor": supervisor_node,
    }


def build_graph(
    model_name: str | None = None,
    *,
    llm_spec: LLMSpec | None = None,
    provider: str | None = None,
    cfg: MirageConfig | None = None,
):
    """Compile the multi-agent ``StateGraph`` with a SQLite checkpointer.

    ``model_name`` is kept for backward compatibility; when ``llm_spec`` is
    omitted, it is combined with ``provider`` (or configured default).
    """
    cfg = cfg or load_config()
    if llm_spec is None:
        llm_spec = LLMSpec(
            provider=provider or cfg.default_provider,
            model=model_name or cfg.default_model,
        )

    api_key = resolve_api_key(cfg, llm_spec.provider)
    base_url = resolve_base_url(cfg, llm_spec.provider)
    llm = make_llm(
        llm_spec.provider,
        llm_spec.model,
        api_key=api_key,
        base_url=base_url,
    )

    nodes = _build_agents(llm)

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

    memory = _get_checkpointer()
    return workflow.compile(checkpointer=memory)
