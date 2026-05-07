"""Slash-command dispatcher and the multi-agent stream loop."""
from __future__ import annotations

import os
import sys
import uuid

from langchain_core.messages import HumanMessage
from rich.text import Text

from ..agents.graph import build_graph
from ..config import RECURSION_LIMIT
from ..theme import ACCENT, console
from .render import (
    print_agent_message,
    print_status,
    print_supervisor_routing,
    print_welcome,
    show_help,
)


def handle_slash_command(raw: str, session: dict) -> bool:
    """Returns True if a slash command was handled (and should not be sent to the agent)."""
    if not raw.startswith("/"):
        return False

    parts = raw.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else None

    if cmd in ("/exit", "/quit"):
        print_status("goodbye", "info")
        sys.exit(0)

    if cmd == "/help":
        show_help()
        return True

    if cmd == "/clear":
        os.system("cls" if os.name == "nt" else "clear")
        print_welcome(session["thread_id"], session["model"])
        return True

    if cmd == "/reset":
        new_id = f"session-{uuid.uuid4().hex[:8]}"
        session["thread_id"] = new_id
        print_status(f"✓ new thread: {new_id}", "success")
        return True

    if cmd == "/thread":
        if arg:
            session["thread_id"] = arg
            print_status(f"✓ switched to thread: {arg}", "success")
        else:
            print_status(f"current thread: {session['thread_id']}", "info")
        return True

    if cmd == "/model":
        if arg:
            session["model"] = arg
            session["graph"] = build_graph(arg)
            print_status(f"✓ switched to model: {arg}", "success")
        else:
            print_status(f"current model: {session['model']}", "info")
        return True

    print_status(f"unknown command: {cmd}  (try /help)", "error")
    return True


def run_agent(graph, task: str, thread_id: str) -> None:
    """Stream the multi-agent workflow autonomously. Agents decide every
    handoff themselves — there is no human-in-the-loop gate.
    """
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}

    spinner = console.status(
        Text("thinking…", style=f"italic {ACCENT}"),
        spinner="dots",
        spinner_style=ACCENT,
    )
    spinner.start()
    spinner_running = True

    try:
        for event in graph.stream(
            {"messages": [HumanMessage(content=task)]},
            config,
            stream_mode="updates",
        ):
            if spinner_running:
                spinner.stop()
                spinner_running = False

            for node_name, node_state in event.items():
                if node_name == "supervisor":
                    proposed = (
                        node_state.get("next", "UNKNOWN")
                        if isinstance(node_state, dict)
                        else "UNKNOWN"
                    )
                    print_supervisor_routing(proposed)
                elif (
                    isinstance(node_state, dict)
                    and node_state.get("messages")
                ):
                    msg = node_state["messages"][-1]
                    print_agent_message(node_name, getattr(msg, "content", "") or "")
    finally:
        if spinner_running:
            spinner.stop()
