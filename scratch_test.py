"""Smoke tests for the prompt_toolkit input box and run_agent in main.py.

Drives the actual prompt_toolkit Application via a fake input pipe and a
dummy output, so we can verify Enter-to-send / Esc+Enter-newline /
Ctrl+C-cancel behavior without a real TTY. Also runs run_agent against a
synthetic graph to make sure the streaming/spinner/output pipeline works
end-to-end. Verifies graph topology and tool wiring (Designer/PM read-only,
Developer is the only code-writer).
"""
from __future__ import annotations

import os as _os
import tempfile
import time
from pathlib import Path

from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

import main


def run_box_with(keys: str) -> str | None:
    """Run the bordered input box, feeding `keys` as if typed."""
    with create_pipe_input() as inp:
        inp.send_text(keys)
        with create_app_session(input=inp, output=DummyOutput()):
            return main._prompt_input_box(thread_id="t-test", model="gpt-4o")


class FakeGraph:
    """Minimal stand-in for a compiled LangGraph graph.

    Yields the same shape `graph.stream(..., stream_mode='updates')` produces
    so we can verify run_agent's rendering logic without hitting an LLM.
    Exercises ALL three team members + supervisor to verify the full pipeline.
    """

    def stream(self, _input, _config, stream_mode: str = "updates"):
        time.sleep(0.05)  # let the spinner render briefly

        yield {"supervisor": {"next": "ProjectManager"}}
        yield {
            "ProjectManager": {
                "messages": [
                    main.AIMessage(
                        name="ProjectManager",
                        content=(
                            "### Goal\nBuild a hello-world web page.\n\n"
                            "### Plan\n1. **UXUIDesigner** — design `index.html`\n"
                            "2. **Developer** — implement it\n\n"
                            "### Hand-off\n`UXUIDesigner`"
                        ),
                    )
                ]
            }
        }

        yield {"supervisor": {"next": "UXUIDesigner"}}
        yield {
            "UXUIDesigner": {
                "messages": [
                    main.AIMessage(
                        name="UXUIDesigner",
                        content=(
                            "### Hand-off to Developer\n"
                            "- Create `index.html` with a single `<h1>Hello</h1>` and a `Reload` button.\n"
                            "- Use the design tokens above for spacing & color.\n"
                            "- Acceptance: page renders the heading and button is keyboard-focusable.\n"
                        ),
                    )
                ]
            }
        }

        yield {"supervisor": {"next": "Developer"}}
        yield {
            "Developer": {
                "messages": [
                    main.AIMessage(
                        name="Developer",
                        content="Created `index.html` based on the design spec.",
                    )
                ]
            }
        }

        yield {"supervisor": {"next": "FINISH"}}


def test_input_box() -> None:
    result = run_box_with("hello world\r")
    assert result == "hello world", f"Enter-submit failed: {result!r}"
    print("PASS: Enter submits text:", repr(result))

    result = run_box_with("line1\x1b\rline2\r")
    assert result == "line1\nline2", f"Esc+Enter newline failed: {result!r}"
    print("PASS: Esc+Enter inserts newline:", repr(result))

    result = run_box_with("\x04")
    assert result is None, f"Ctrl+D-empty failed: {result!r}"
    print("PASS: Ctrl+D on empty exits:", repr(result))

    result = run_box_with("/help\r")
    assert result == "/help", f"Slash command submit failed: {result!r}"
    print("PASS: Slash command submitted:", repr(result))


def test_run_agent() -> None:
    """run_agent must stream + render the whole synthetic flow."""
    print("\n--- run_agent end-to-end render ---")
    main.run_agent(FakeGraph(), task="please build hello.py and run it", thread_id="t-test")
    print("--- end run_agent ---\n")
    print("PASS: run_agent streamed and rendered without errors.")


def test_graph_topology() -> None:
    """Compile the real graph and verify the three remaining members + supervisor
    are wired, that the Executor is GONE, and that there is NO human_review node
    (agents decide autonomously).
    """
    _os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-called")  # build only — no calls
    graph = main.build_graph(model_name="gpt-4o-mini")

    nodes = set(graph.nodes.keys())
    expected = {"ProjectManager", "UXUIDesigner", "Developer", "supervisor", "__start__"}
    missing = expected - nodes
    assert not missing, f"missing nodes in compiled graph: {missing}  (have: {nodes})"

    assert "Executor" not in nodes, "Executor node should be REMOVED"
    assert "human_review" not in nodes, (
        "human_review node should be REMOVED — agents handle handoffs autonomously"
    )
    print("PASS: compiled graph nodes:", sorted(n for n in nodes if not n.startswith("__")))
    print("PASS: no Executor node (executor agent removed)")
    print("PASS: no human_review node (autonomous handoff)")

    expected_members = {"ProjectManager", "UXUIDesigner", "Developer"}
    assert set(main.MEMBERS) == expected_members, main.MEMBERS
    assert "Executor" not in main.MEMBERS, main.MEMBERS
    print("PASS: MEMBERS list:", main.MEMBERS)


def test_only_developer_writes_code() -> None:
    """Only the Developer agent may have write_file / edit_file tools.
    Designer + ProjectManager must be read-only.
    """
    from src.tools import DEVELOPER_TOOLS, READ_ONLY_TOOLS

    write_tools = {"write_file", "edit_file"}
    read_names = {t.name for t in READ_ONLY_TOOLS}
    dev_names = {t.name for t in DEVELOPER_TOOLS}

    for tool in write_tools:
        assert tool not in read_names, f"read-only toolset must not include {tool}"

    for tool in write_tools:
        assert tool in dev_names, f"Developer toolset must include {tool}"

    import inspect

    source = inspect.getsource(main._build_agents)
    assert "executor_tools = [" not in source, "Executor tool wiring should be removed"

    print("PASS: only Developer has write_file / edit_file tools")
    print("       ProjectManager: read-only")
    print("       UXUIDesigner:   read-only")
    print("       Developer:      writes (write_file, edit_file)")
    print("       (no Executor)")


def test_slash_commands() -> None:
    from unittest.mock import patch

    from src.sessions.store import SessionStore

    idx_path = Path(tempfile.mkdtemp()) / "sessions.json"
    session = {
        "thread_id": "abc",
        "model": "gpt-4o",
        "provider": "openai",
        "session_name": "abc",
        "session_store": SessionStore(path=idx_path),
        "graph": FakeGraph(),
    }

    with patch("src.cli.session.refresh_session_graph", lambda _s: None):
        handled = main.handle_slash_command("/thread newthread", session)
    assert handled and session["thread_id"] == "newthread"
    print("PASS: /thread switches thread:", session["thread_id"])

    with patch("src.cli.session.refresh_session_graph", lambda _s: None):
        handled = main.handle_slash_command("/reset", session)
    assert handled and session["thread_id"].startswith("session-")
    print("PASS: /reset generates new thread:", session["thread_id"])

    handled = main.handle_slash_command("/notacommand", session)
    assert handled
    print("PASS: unknown slash command handled gracefully")


def test_no_hitl_artifacts() -> None:
    """Defensive check that all HITL surface area is gone from main."""
    for name in (
        "print_review_panel",
        "_ask_review_action",
        "_ask_agent_choice",
        "_ask_feedback_message",
        "handle_interrupt",
    ):
        assert not hasattr(main, name), f"main.{name} should be removed (HITL leftover)"

    assert "hitl_enabled" not in main.AgentState.__annotations__, (
        "AgentState.hitl_enabled should be removed"
    )
    print("PASS: no HITL helpers, no hitl_enabled state field")


def test_autonomous_handoff_runs_to_completion() -> None:
    """With HITL removed, a real compiled graph driven by stubbed
    supervisor/worker nodes must stream every step end-to-end without
    any interrupt() pause."""
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import InMemorySaver

    _os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-called")

    picks = iter(["ProjectManager", "UXUIDesigner", "Developer", "FINISH"])

    def supervisor(state):
        try:
            return {"next": next(picks)}
        except StopIteration:
            return {"next": "FINISH"}

    def make_worker(name: str):
        def worker(state):
            return {"messages": [main.AIMessage(name=name, content=f"{name} done.")]}
        return worker

    workflow = StateGraph(main.AgentState)
    workflow.add_node("supervisor", supervisor)
    for m in main.MEMBERS:
        workflow.add_node(m, make_worker(m))
        workflow.add_edge(m, "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        lambda x: x["next"],
        {**{m: m for m in main.MEMBERS}, "FINISH": END},
    )
    workflow.add_edge(START, "supervisor")
    graph = workflow.compile(checkpointer=InMemorySaver())

    config = {"configurable": {"thread_id": "auton-1"}, "recursion_limit": 50}

    workers_ran: list[str] = []
    saw_interrupt = False
    for event in graph.stream(
        {"messages": [main.HumanMessage(content="ship it")]},
        config,
        stream_mode="updates",
    ):
        if "__interrupt__" in event:
            saw_interrupt = True
            break
        for node, _ in event.items():
            if node in main.MEMBERS:
                workers_ran.append(node)

    assert not saw_interrupt, "graph must run autonomously — no interrupt should fire"
    assert workers_ran == ["ProjectManager", "UXUIDesigner", "Developer"], workers_ran
    print("PASS: autonomous handoff ran all 3 agents in order:", workers_ran)


if __name__ == "__main__":
    test_input_box()
    test_slash_commands()
    test_graph_topology()
    test_only_developer_writes_code()
    test_no_hitl_artifacts()
    test_autonomous_handoff_runs_to_completion()
    test_run_agent()

    print("\nAll smoke tests passed.")
