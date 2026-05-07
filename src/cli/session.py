"""Slash-command dispatcher and the multi-agent stream loop."""
from __future__ import annotations

import os
import sys
from dataclasses import replace

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
from .runtime_state import RuntimeSessionState, RuntimeSessionStore
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


def _build_session_graph(provider: str, model: str):
    cfg = load_config()
    spec = LLMSpec(provider=provider, model=model)
    graph = build_graph(llm_spec=spec, cfg=cfg)
    return cfg, graph


def _derive_runtime_state(
    previous: RuntimeSessionState,
    candidate: RuntimeSessionState,
) -> RuntimeSessionState:
    needs_graph_refresh = (
        previous.provider != candidate.provider
        or previous.model != candidate.model
        or candidate.graph is None
    )
    if not needs_graph_refresh:
        return candidate
    cfg, graph = _build_session_graph(candidate.provider, candidate.model)
    return replace(candidate, cfg=cfg, graph=graph)


def _on_change_runtime_state(new_state: RuntimeSessionState, old_state: RuntimeSessionState) -> None:
    if (
        new_state.thread_id != old_state.thread_id
        or new_state.session_name != old_state.session_name
        or new_state.provider != old_state.provider
        or new_state.model != old_state.model
    ):
        new_state.session_store.ensure_session(
            new_state.thread_id,
            name=new_state.session_name or new_state.thread_id,
            provider=new_state.provider,
            model=new_state.model,
        )


def create_runtime_session_store(
    *,
    thread_id: str,
    provider: str,
    model: str,
    session_store: SessionStore,
    session_name: str | None = None,
) -> RuntimeSessionStore:
    cfg, graph = _build_session_graph(provider, model)
    initial = RuntimeSessionState(
        thread_id=thread_id,
        provider=provider,
        model=model,
        session_name=(session_name or thread_id).strip() or thread_id,
        session_store=session_store,
        cfg=cfg,
        graph=graph,
    )
    return RuntimeSessionStore(
        initial_state=initial,
        derive_state=_derive_runtime_state,
        on_change=_on_change_runtime_state,
    )


def refresh_session_graph(session: RuntimeSessionStore) -> None:
    """Rebuild the compiled graph from current provider/model + disk config."""
    state = session.get_state()
    session.set_state(lambda prev: replace(prev, cfg=state.cfg, graph=None))


def sync_session_index(session: RuntimeSessionStore) -> None:
    state = session.get_state()
    state.session_store.ensure_session(
        state.thread_id,
        name=state.session_name or state.thread_id,
        provider=state.provider,
        model=state.model,
    )


def ensure_api_key_or_prompt(session: RuntimeSessionStore) -> bool:
    """If no API key is available for the active provider, open the model form."""
    state = session.get_state()
    cfg = load_config()
    if resolve_api_key(cfg, state.provider):
        return True
    print_status(f"no API key for provider '{state.provider}' — configure now", "warn")
    res = run_model_form(
        cfg,
        initial_provider=state.provider,
        initial_model=state.model,
    )
    if not res:
        return False
    session.set_state(
        lambda prev: replace(
            prev,
            provider=str(res["provider"]),
            model=str(res["model"]),
        )
    )
    print_status("✓ credentials saved", "success")
    return True


def open_model_configuration(session: RuntimeSessionStore, arg: str | None = None) -> None:
    """Open the interactive configuration form (optional ``provider:model`` arg)."""
    state = session.get_state()
    cfg = load_config()
    parsed_prov, parsed_model = parse_model_arg(arg)
    initial_provider = parsed_prov or state.provider
    initial_model = parsed_model or state.model
    res = run_model_form(
        cfg,
        initial_provider=initial_provider,
        initial_model=initial_model or cfg.default_model,
    )
    if not res:
        print_status("cancelled", "info")
        return
    session.set_state(
        lambda prev: replace(
            prev,
            provider=str(res["provider"]),
            model=str(res["model"]),
        )
    )
    new_state = session.get_state()
    print_status(f"✓ model · {new_state.provider}:{new_state.model}", "success")


def handle_slash_command(raw: str, session: RuntimeSessionStore) -> bool:
    """Returns True if a slash command was handled (and should not be sent to the agent)."""
    if not raw.startswith("/"):
        return False

    state = session.get_state()
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
            state.thread_id,
            state.model,
            provider=state.provider,
        )
        return True

    store = state.session_store

    if cmd in ("/reset", "/new"):
        name = arg.strip() if arg else ""
        new_tid = new_thread_id()
        session.set_state(
            lambda prev: replace(
                prev,
                thread_id=new_tid,
                session_name=name or new_tid,
            )
        )
        print_status(f"✓ new session: {new_tid}", "success")
        return True

    if cmd == "/thread":
        if arg:
            new_tid = arg.strip()
            session.set_state(
                lambda prev: replace(
                    prev,
                    thread_id=new_tid,
                    session_name=new_tid,
                )
            )
            print_status(f"✓ switched thread: {new_tid}", "success")
        else:
            print_status(f"current thread: {state.thread_id}", "info")
        return True

    if cmd == "/model":
        open_model_configuration(session, arg)
        return True

    if cmd == "/provider":
        prov = arg.strip().lower() if arg else state.provider
        if prov not in PROVIDERS:
            print_status(f"unknown provider: {prov}", "error")
            return True
        cfg = load_config()
        res = run_model_form(
            cfg,
            initial_provider=prov,
            initial_model=state.model,
        )
        if not res:
            print_status("cancelled", "info")
            return True
        session.set_state(
            lambda prev: replace(
                prev,
                provider=str(res["provider"]),
                model=str(res["model"]),
            )
        )
        new_state = session.get_state()
        print_status(f"✓ model · {new_state.provider}:{new_state.model}", "success")
        return True

    if cmd == "/config":
        cfg = load_config()
        sub = (arg or "").strip().lower()
        if sub == "edit":
            open_model_configuration(session, f"{state.provider}:{state.model}")
        else:
            print_config_form(cfg, active_provider=state.provider)
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
        print_sessions_table(rows, active_id=state.thread_id)
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
        session.set_state(
            lambda prev: replace(
                prev,
                thread_id=hit.thread_id,
                session_name=hit.name,
                provider=hit.provider,
                model=hit.model,
            )
        )
        store.touch(hit.thread_id)
        print_status(f"✓ switched to session {hit.thread_id}", "success")
        return True

    if cmd == "/rename":
        if not arg:
            print_status("usage: /rename <name>", "error")
            return True
        new_name = arg.strip()
        current = session.get_state()
        session.set_state(lambda prev: replace(prev, session_name=new_name))
        store.rename(current.thread_id, new_name)
        print_status(f"✓ renamed to {new_name}", "success")
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
        if tid == state.thread_id:
            new_tid = new_thread_id()
            session.set_state(
                lambda prev: replace(prev, thread_id=new_tid, session_name=new_tid)
            )
            print_status(f"started fresh thread {new_tid}", "info")
        return True

    print_status(f"unknown command: {cmd}  (try /help)", "error")
    return True


def run_agent(
    graph,
    task: str,
    thread_id: str,
    session: RuntimeSessionStore | None = None,
) -> None:
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
    last_sig: tuple[str, str] | None = None
    stagnant_repeats = 0

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
                    content = getattr(msg, "content", "") or ""
                    print_agent_message(node_name, content)

                    # Runtime loop guard: break if identical output repeats.
                    normalized = " ".join(content.split()).strip().lower()
                    sig = (node_name, normalized)
                    if normalized and sig == last_sig:
                        stagnant_repeats += 1
                    else:
                        stagnant_repeats = 0
                    last_sig = sig

                    if stagnant_repeats >= 3:
                        print_status(
                            "auto-stopped: repeated identical agent output (possible loop)",
                            "warn",
                        )
                        return
        if session is not None:
            session.get_state().session_store.touch(thread_id)
    finally:
        if spinner_running:
            spinner.stop()
