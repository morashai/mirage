"""Wire Mirage primary agent into a compiled LangGraph ``StateGraph``."""
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
from .developer import build_primary_agent
from .factory import make_node
from .state import AgentState

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


def _build_primary_node(llm):
    """Build the single primary runtime node."""
    # Build mode gets full tool access; plan restrictions are enforced by policy.
    tools = list(READ_ONLY_TOOLS) + list(DEVELOPER_TOOLS)
    primary = build_primary_agent(llm, tools, mode="build")
    return make_node(primary, "Build")


def build_graph(
    model_name: str | None = None,
    *,
    llm_spec: LLMSpec | None = None,
    provider: str | None = None,
    cfg: MirageConfig | None = None,
):
    """Compile the single-agent ``StateGraph`` with a SQLite checkpointer.

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

    primary_node = _build_primary_node(llm)

    workflow = StateGraph(AgentState)
    workflow.add_node("Build", primary_node)
    workflow.add_edge(START, "Build")
    workflow.add_edge("Build", END)

    memory = _get_checkpointer()
    return workflow.compile(checkpointer=memory)
