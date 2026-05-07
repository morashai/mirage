"""Typer entry-points for the Mirage 5 CLI.

Two sortie types:
- ``chat`` — interactive REPL with the prompt_toolkit input box.
- ``run``  — fire-and-forget single-task strike (one task, no REPL).
"""
from __future__ import annotations

import uuid

import typer

from ..agents.graph import build_graph
from ..config import DEFAULT_MODEL
from .input_box import _prompt_input_box
from .render import print_status, print_welcome
from .session import handle_slash_command, run_agent


app = typer.Typer(
    help=(
        "MIRAGE 5 — multi-agent strike package, dressed in Royal Jordanian colors. "
        "A LangGraph delta-wing for product work: Project Manager (OPS), "
        "UX/UI Designer (Recce), Developer (Strike)."
    ),
    add_completion=False,
)


def _start_chat(thread_id: str | None, model: str) -> None:
    """Shared chat bootstrap used by both CLI command and default callback."""
    if not thread_id:
        thread_id = f"session-{uuid.uuid4().hex[:8]}"

    session = {
        "thread_id": thread_id,
        "model": model,
        "graph": build_graph(model),
    }

    print_welcome(session["thread_id"], session["model"])

    while True:
        try:
            user_input = _prompt_input_box(session["thread_id"], session["model"])
        except KeyboardInterrupt:
            print_status("goodbye", "info")
            break

        if user_input is None:
            print_status("goodbye", "info")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if handle_slash_command(user_input, session):
            continue

        try:
            run_agent(session["graph"], user_input, session["thread_id"])
        except KeyboardInterrupt:
            print_status("interrupted", "warn")
        except Exception as e:  # noqa: BLE001 — surface every error to the user
            print_status(f"error: {e}", "error")


@app.callback(invoke_without_command=True)
def _default_to_chat(ctx: typer.Context) -> None:
    """Run chat mode when no explicit subcommand is provided."""
    if ctx.invoked_subcommand is None:
        _start_chat(None, DEFAULT_MODEL)


@app.command()
def chat(
    thread_id: str = typer.Option(None, help="Thread ID for memory."),
    model: str = typer.Option(DEFAULT_MODEL, help="LLM model name."),
):
    """Start an interactive chat session with the multi-agent system."""
    _start_chat(thread_id, model)


@app.command()
def run(
    task: str,
    thread_id: str = typer.Option("multi-agent-session-1", help="Thread ID for memory."),
    model: str = typer.Option(DEFAULT_MODEL, help="LLM model name."),
):
    """Run a single task non-interactively."""
    print_welcome(thread_id, model)
    graph = build_graph(model)
    try:
        run_agent(graph, task, thread_id)
    except Exception as e:  # noqa: BLE001
        print_status(f"error: {e}", "error")
        raise typer.Exit(code=1)


def main() -> None:
    """Console-script entry point for installers (pip/pipx/uv/uvx)."""
    app()
