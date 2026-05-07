"""Typer entry-points for the Mirage 5 CLI.

Two sortie types:
- ``chat`` — interactive REPL with the prompt_toolkit input box.
- ``run``  — fire-and-forget single-task strike (one task, no REPL).
"""
from __future__ import annotations

import sys

import typer
from rich.prompt import Confirm

from ..agents.graph import build_graph
from ..config_store import load_config, resolve_api_key, save_config
from ..llm.catalog import PROVIDERS
from ..llm.spec import LLMSpec
from ..sessions.store import SessionStore, new_thread_id, resolve_session_selector
from .input_box import _prompt_input_box
from .render import (
    print_config_form,
    print_models_table,
    print_sessions_table,
    print_status,
    print_welcome,
)
from .session import (
    create_runtime_session_store,
    ensure_api_key_or_prompt,
    handle_slash_command,
    run_agent,
)


app = typer.Typer(
    help=(
        "MIRAGE 5 — multi-agent strike package, dressed in Royal Jordanian colors. "
        "A LangGraph delta-wing for product work: Project Manager (OPS), "
        "UX/UI Designer (Recce), Developer (Strike)."
    ),
    add_completion=False,
)

models_app = typer.Typer(help="Browse curated model ids.", add_completion=False)


@models_app.command("list")
def models_list(
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="Filter by provider key (openai, anthropic, google).",
    ),
):
    prov = provider.strip().lower() if provider else None
    if prov and prov not in PROVIDERS:
        print_status(f"unknown provider: {prov}", "error")
        raise typer.Exit(code=1)
    print_models_table(prov)


app.add_typer(models_app, name="models")

config_app = typer.Typer(help="Manage Mirage API configuration.", add_completion=False)


@config_app.command("show")
def config_show() -> None:
    cfg = load_config()
    print_config_form(cfg, active_provider=cfg.default_provider)


@config_app.command("set-key")
def config_set_key(
    provider: str = typer.Argument(..., help="openai | anthropic | google"),
    key: str = typer.Argument(..., help="API key to store in ~/.mirage/config.json"),
) -> None:
    prov = provider.strip().lower()
    if prov not in PROVIDERS:
        print_status(f"unknown provider: {prov}", "error")
        raise typer.Exit(code=1)
    cfg = load_config()
    cfg.provider_settings(prov).api_key = key
    save_config(cfg)
    print_status(f"✓ saved API key for {prov}", "success")


@config_app.command("set-url")
def config_set_url(
    provider: str = typer.Argument(...),
    url: str = typer.Argument(..., help="Custom API base URL (empty clears)"),
) -> None:
    prov = provider.strip().lower()
    if prov not in PROVIDERS:
        print_status(f"unknown provider: {prov}", "error")
        raise typer.Exit(code=1)
    cfg = load_config()
    cfg.provider_settings(prov).base_url = url.strip() or None
    save_config(cfg)
    print_status(f"✓ saved base URL for {prov}", "success")


@config_app.command("set-default")
def config_set_default(
    provider: str = typer.Argument(...),
    model: str = typer.Argument(...),
) -> None:
    prov = provider.strip().lower()
    if prov not in PROVIDERS:
        print_status(f"unknown provider: {prov}", "error")
        raise typer.Exit(code=1)
    cfg = load_config()
    cfg.default_provider = prov
    cfg.default_model = model.strip()
    save_config(cfg)
    print_status(f"✓ defaults · {prov}:{cfg.default_model}", "success")


app.add_typer(config_app, name="config")

sessions_app = typer.Typer(help="Manage saved chat sessions.", add_completion=False)


@sessions_app.command("list")
def sessions_list_cmd() -> None:
    rows = SessionStore().list_sessions()
    print_sessions_table(rows)


@sessions_app.command("new")
def sessions_new(name: str | None = typer.Argument(None, help="Optional session label")) -> None:
    cfg = load_config()
    tid = new_thread_id()
    store = SessionStore()
    store.ensure_session(
        tid,
        name=name.strip() if name else tid,
        provider=cfg.default_provider,
        model=cfg.default_model,
    )
    print_status(f"✓ created session {tid}", "success")


@sessions_app.command("delete")
def sessions_delete(selector: str = typer.Argument(..., help="Thread id or list index")) -> None:
    store = SessionStore()
    rows = store.list_sessions()
    hit = resolve_session_selector(selector, rows)
    if not hit:
        print_status(f"session not found: {selector}", "error")
        raise typer.Exit(code=1)
    store.delete(hit.thread_id)
    print_status(f"✓ deleted {hit.thread_id}", "success")


app.add_typer(sessions_app, name="sessions")


def _resolve_chat_thread(
    *,
    thread_id: str | None,
    session_id: str | None,
    model: str | None,
    provider: str | None,
) -> tuple[str, str, str]:
    """Return ``(thread_id, provider, model)`` after applying CLI flags + resume prompt."""
    cfg = load_config()
    store = SessionStore()
    prov = (provider or "").strip().lower() if provider else None
    mdl = (model or "").strip() if model else None
    prov = prov or cfg.default_provider
    mdl = mdl or cfg.default_model
    tid: str | None = thread_id

    if session_id:
        rec = store.get(session_id.strip())
        if not rec:
            print_status(f"unknown session id: {session_id}", "error")
            raise typer.Exit(code=1)
        tid = rec.thread_id
        if provider is None:
            prov = rec.provider
        if model is None:
            mdl = rec.model
    elif tid is None:
        rows = store.list_sessions()
        if rows and sys.stdin.isatty():
            if Confirm.ask("Resume most recent chat session?", default=True):
                tid = rows[0].thread_id
                if provider is None:
                    prov = rows[0].provider
                if model is None:
                    mdl = rows[0].model
        if tid is None:
            tid = new_thread_id()

    assert tid is not None

    rec = store.get(tid)
    if rec:
        if provider is None:
            prov = rec.provider
        if model is None:
            mdl = rec.model

    return tid, prov, mdl


def _start_chat(
    thread_id: str | None,
    session_id: str | None,
    model: str | None,
    provider: str | None,
) -> None:
    tid, prov, mdl = _resolve_chat_thread(
        thread_id=thread_id,
        session_id=session_id,
        model=model,
        provider=provider,
    )

    session = create_runtime_session_store(
        thread_id=tid,
        provider=prov,
        model=mdl,
        session_store=SessionStore(),
        session_name=tid,
    )

    if not ensure_api_key_or_prompt(session):
        print_status("cannot chat without API credentials", "error")
        raise typer.Exit(code=1)

    state = session.get_state()
    print_welcome(state.thread_id, state.model, provider=state.provider)

    while True:
        state = session.get_state()
        try:
            user_input = _prompt_input_box(
                state.thread_id,
                state.model,
                provider=state.provider,
            )
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
            state = session.get_state()
            run_agent(state.graph, user_input, state.thread_id, session=session)
        except KeyboardInterrupt:
            print_status("interrupted", "warn")
        except Exception as e:  # noqa: BLE001 — surface every error to the user
            print_status(f"error: {e}", "error")


@app.callback(invoke_without_command=True)
def _default_to_chat(ctx: typer.Context) -> None:
    """Run chat mode when no explicit subcommand is provided."""
    if ctx.invoked_subcommand is None:
        _start_chat(None, None, None, None)


@app.command()
def chat(
    thread_id: str | None = typer.Option(
        None,
        "--thread-id",
        "-t",
        help="Thread ID for LangGraph memory.",
    ),
    session_id: str | None = typer.Option(
        None,
        "--session-id",
        "-s",
        help="Resume a session from ~/.mirage/sessions.json by thread id.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="Model id (defaults to configured default).",
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="Provider key: openai | anthropic | google.",
    ),
):
    """Start an interactive chat session with the multi-agent system."""
    _start_chat(thread_id, session_id, model, provider)


@app.command()
def run(
    task: str,
    thread_id: str = typer.Option("multi-agent-session-1", help="Thread ID for memory."),
    model: str | None = typer.Option(None, help="LLM model name."),
    provider: str | None = typer.Option(None, help="openai | anthropic | google"),
):
    """Run a single task non-interactively."""
    cfg = load_config()
    prov = (provider or "").strip().lower() if provider else cfg.default_provider
    mdl = (model or "").strip() if model else cfg.default_model
    if prov not in PROVIDERS:
        print_status(f"unknown provider: {prov}", "error")
        raise typer.Exit(code=1)
    spec = LLMSpec(provider=prov, model=mdl)
    if not resolve_api_key(cfg, prov):
        print_status(
            "no API key for this provider — set env var or `mirage config set-key`",
            "error",
        )
        raise typer.Exit(code=1)
    print_welcome(thread_id, spec.model, provider=spec.provider)
    graph = build_graph(llm_spec=spec, cfg=cfg)
    try:
        run_agent(graph, task, thread_id, session=None)
    except Exception as e:  # noqa: BLE001
        print_status(f"error: {e}", "error")
        raise typer.Exit(code=1)


def main() -> None:
    """Console-script entry point for installers (pip/pipx/uv/uvx)."""
    app()
