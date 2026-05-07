"""Slash-command dispatcher and the multi-agent stream loop."""
from __future__ import annotations

import os
import sys

from langchain_core.messages import HumanMessage
from rich.text import Text

from ..agents.graph import build_graph
from ..config import RECURSION_LIMIT
from ..config_store import load_config, parse_model_arg, resolve_api_key
from ..llm.catalog import PROVIDERS
from ..llm.spec import LLMSpec
from ..sessions.store import SessionStore, new_thread_id, resolve_session_selector
from ..theme import ACCENT, console
from .model_form import run_model_form
from .render import (
    print_agent_message,
    print_config_form,
    print_models_table,
    print_sessions_table,
    print_status,
    print_supervisor_routing,
    print_welcome,
    show_help,
)


def refresh_session_graph(session: dict) -> None:
    """Rebuild the compiled graph from current provider/model + disk config."""
    cfg = load_config()
    session["cfg"] = cfg
    spec = LLMSpec(provider=session["provider"], model=session["model"])
    session["graph"] = build_graph(llm_spec=spec, cfg=cfg)


def sync_session_index(session: dict) -> None:
    store: SessionStore = session["session_store"]
    store.ensure_session(
        session["thread_id"],
        name=session.get("session_name") or session["thread_id"],
        provider=session["provider"],
        model=session["model"],
    )


def ensure_api_key_or_prompt(session: dict) -> bool:
    """If no API key is available for the active provider, open the model form."""
    cfg = load_config()
    session["cfg"] = cfg
    if resolve_api_key(cfg, session["provider"]):
        return True
    print_status(f"no API key for provider '{session['provider']}' — configure now", "warn")
    res = run_model_form(
        cfg,
        initial_provider=session["provider"],
        initial_model=session["model"],
    )
    if not res:
        return False
    session["provider"] = str(res["provider"])
    session["model"] = str(res["model"])
    refresh_session_graph(session)
    sync_session_index(session)
    print_status("✓ credentials saved", "success")
    return True


def open_model_configuration(session: dict, arg: str | None = None) -> None:
    """Open the interactive configuration form (optional ``provider:model`` arg)."""
    cfg = load_config()
    session["cfg"] = cfg
    parsed_prov, parsed_model = parse_model_arg(arg)
    initial_provider = parsed_prov or session["provider"]
    initial_model = parsed_model or session["model"]
    res = run_model_form(
        cfg,
        initial_provider=initial_provider,
        initial_model=initial_model or cfg.default_model,
    )
    if not res:
        print_status("cancelled", "info")
        return
    session["provider"] = str(res["provider"])
    session["model"] = str(res["model"])
    refresh_session_graph(session)
    sync_session_index(session)
    print_status(f"✓ model · {session['provider']}:{session['model']}", "success")


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
        print_welcome(
            session["thread_id"],
            session["model"],
            provider=session["provider"],
        )
        return True

    store: SessionStore = session["session_store"]

    if cmd in ("/reset", "/new"):
        name = arg.strip() if arg else ""
        session["thread_id"] = new_thread_id()
        session["session_name"] = name or session["thread_id"]
        refresh_session_graph(session)
        sync_session_index(session)
        print_status(f"✓ new session: {session['thread_id']}", "success")
        return True

    if cmd == "/thread":
        if arg:
            session["thread_id"] = arg.strip()
            refresh_session_graph(session)
            sync_session_index(session)
            print_status(f"✓ switched thread: {session['thread_id']}", "success")
        else:
            print_status(f"current thread: {session['thread_id']}", "info")
        return True

    if cmd == "/model":
        open_model_configuration(session, arg)
        return True

    if cmd == "/provider":
        prov = arg.strip().lower() if arg else session["provider"]
        if prov not in PROVIDERS:
            print_status(f"unknown provider: {prov}", "error")
            return True
        cfg = load_config()
        session["cfg"] = cfg
        res = run_model_form(
            cfg,
            initial_provider=prov,
            initial_model=session["model"],
        )
        if not res:
            print_status("cancelled", "info")
            return True
        session["provider"] = str(res["provider"])
        session["model"] = str(res["model"])
        refresh_session_graph(session)
        sync_session_index(session)
        print_status(f"✓ model · {session['provider']}:{session['model']}", "success")
        return True

    if cmd == "/config":
        cfg = load_config()
        session["cfg"] = cfg
        sub = (arg or "").strip().lower()
        if sub == "edit":
            open_model_configuration(session, f"{session['provider']}:{session['model']}")
        else:
            print_config_form(cfg, active_provider=session["provider"])
        return True

    if cmd == "/models":
        prov = arg.strip().lower() if arg else None
        if prov and prov not in PROVIDERS:
            print_status(f"unknown provider: {prov}", "error")
            return True
        print_models_table(prov)
        return True

    if cmd == "/sessions":
        rows = store.list_sessions()
        print_sessions_table(rows, active_id=session["thread_id"])
        return True

    if cmd == "/session":
        if not arg:
            print_status("usage: /session <id or list index>", "error")
            return True
        rows = store.list_sessions()
        hit = resolve_session_selector(arg, rows)
        if not hit:
            print_status(f"session not found: {arg}", "error")
            return True
        session["thread_id"] = hit.thread_id
        session["session_name"] = hit.name
        session["provider"] = hit.provider
        session["model"] = hit.model
        refresh_session_graph(session)
        sync_session_index(session)
        store.touch(hit.thread_id)
        print_status(f"✓ switched to session {hit.thread_id}", "success")
        return True

    if cmd == "/rename":
        if not arg:
            print_status("usage: /rename <name>", "error")
            return True
        session["session_name"] = arg.strip()
        store.rename(session["thread_id"], session["session_name"])
        print_status(f"✓ renamed to {session['session_name']}", "success")
        return True

    if cmd == "/delete":
        if not arg:
            print_status("usage: /delete <id or list index>", "error")
            return True
        rows = store.list_sessions()
        hit = resolve_session_selector(arg, rows)
        if not hit:
            print_status(f"session not found: {arg}", "error")
            return True
        tid = hit.thread_id
        store.delete(tid)
        print_status(f"✓ deleted session {tid}", "success")
        if tid == session["thread_id"]:
            session["thread_id"] = new_thread_id()
            session["session_name"] = session["thread_id"]
            refresh_session_graph(session)
            sync_session_index(session)
            print_status(f"started fresh thread {session['thread_id']}", "info")
        return True

    print_status(f"unknown command: {cmd}  (try /help)", "error")
    return True


def run_agent(graph, task: str, thread_id: str, session: dict | None = None) -> None:
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
        if session is not None:
            session["session_store"].touch(thread_id)
    finally:
        if spinner_running:
            spinner.stop()
