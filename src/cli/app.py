"""Typer entry-points for the Mirage 5 CLI.

Two sortie types:
- ``chat`` — interactive REPL with the prompt_toolkit input box.
- ``run``  — fire-and-forget single-task strike (one task, no REPL).
"""
from __future__ import annotations

import json
import queue
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import typer
from rich.prompt import Confirm

from ..agents.graph import build_graph
from ..config_store import load_config, resolve_api_key, save_config
from ..llm.catalog import PROVIDERS
from ..llm.spec import LLMSpec
from ..sessions.store import SessionStore, new_thread_id, resolve_session_selector
from .input_box import _prompt_input_box
from .project_paths import ensure_mirage_scaffold, find_project_root
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
from .modes import BUILD_MODE, PLAN_MODE, policy_for_mode


app = typer.Typer(
    help=(
        "MIRAGE 5 — multi-agent strike package, dressed in Royal Jordanian colors. "
        "A LangGraph delta-wing for product work: Project Manager (OPS), "
        "UX/UI Designer (Recce), Developer (Strike)."
    ),
    add_completion=False,
)

models_app = typer.Typer(help="Browse curated model ids.", add_completion=False)


@models_app.callback(invoke_without_command=True)
def models_root(ctx: typer.Context, provider: str | None = typer.Argument(None)) -> None:
    """Mirage-style `models [provider]` root behavior."""
    if ctx.invoked_subcommand is not None:
        return
    prov = provider.strip().lower() if provider else None
    if prov and prov not in PROVIDERS:
        print_status(f"unknown provider: {prov}", "error")
        raise typer.Exit(code=1)
    print_models_table(prov)


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
# Mirage command alias.
app.add_typer(sessions_app, name="session")

auth_app = typer.Typer(help="Manage provider credentials.", add_completion=False)


@auth_app.command("login")
def auth_login(
    provider: str = typer.Option(..., "--provider", "-p", help="Provider key"),
    key: str = typer.Option(..., "--key", "-k", help="Provider API key"),
) -> None:
    prov = provider.strip().lower()
    if prov not in PROVIDERS:
        print_status(f"unknown provider: {prov}", "error")
        raise typer.Exit(code=1)
    cfg = load_config()
    cfg.provider_settings(prov).api_key = key.strip()
    save_config(cfg)
    print_status(f"✓ logged in to {prov}", "success")


@auth_app.command("list")
@auth_app.command("ls")
def auth_list() -> None:
    cfg = load_config()
    for prov in PROVIDERS:
        has_key = bool(cfg.provider_settings(prov).api_key or resolve_api_key(cfg, prov))
        status = "configured" if has_key else "missing"
        print_status(f"{prov}: {status}", "info")


@auth_app.command("logout")
def auth_logout(provider: str = typer.Argument(..., help="Provider key")) -> None:
    prov = provider.strip().lower()
    if prov not in PROVIDERS:
        print_status(f"unknown provider: {prov}", "error")
        raise typer.Exit(code=1)
    cfg = load_config()
    cfg.provider_settings(prov).api_key = None
    save_config(cfg)
    print_status(f"✓ logged out from {prov}", "success")


app.add_typer(auth_app, name="auth")

mcp_app = typer.Typer(help="MCP compatibility commands.", add_completion=False)


@mcp_app.command("list")
@mcp_app.command("ls")
def mcp_list() -> None:
    mcp_root = Path.home() / ".cursor" / "projects"
    print_status(f"mcp descriptors root: {mcp_root}", "info")
    print_status("use built-in MCP descriptor tools inside chat for full details", "info")


@mcp_app.command("auth")
def mcp_auth(name: str | None = typer.Argument(None, help="MCP server name")) -> None:
    target = name or "(interactive selection not implemented)"
    print_status(f"mcp auth requested for {target}", "info")


@mcp_app.command("logout")
def mcp_logout(name: str = typer.Argument(..., help="MCP server name")) -> None:
    print_status(f"mcp logout requested for {name}", "info")


@mcp_app.command("debug")
def mcp_debug(name: str = typer.Argument(..., help="MCP server name")) -> None:
    print_status(f"mcp debug requested for {name}", "info")


app.add_typer(mcp_app, name="mcp")


def _ensure_project_scaffold() -> None:
    root = find_project_root()
    if ensure_mirage_scaffold(root):
        return
    print_status("project scaffold skipped (non-project or read-only target)", "warn")


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
    _ensure_project_scaffold()
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

    task_queue: queue.Queue[str | None] = queue.Queue()
    stop_worker = threading.Event()

    def _worker_loop() -> None:
        while not stop_worker.is_set():
            item = task_queue.get()
            if item is None:
                task_queue.task_done()
                break
            try:
                print_status("[WORKING] Mirage agents are running...", "working")
                current_state = session.get_state()
                run_agent(
                    current_state.graph,
                    item,
                    current_state.thread_id,
                    session=session,
                )
            except KeyboardInterrupt:
                print_status("interrupted", "warn")
            except Exception as e:  # noqa: BLE001
                print_status(f"error: {e}", "error")
            finally:
                print_status("[IDLE] Mirage agents finished.", "idle")
                task_queue.task_done()

    worker_thread = threading.Thread(
        target=_worker_loop,
        name="mirage-agent-worker",
        daemon=True,
    )
    worker_thread.start()

    try:
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

            task_queue.put(user_input)
            pending = task_queue.qsize()
            if pending > 1:
                print_status(f"[queued] task accepted ({pending} pending)", "event")
            else:
                print_status("[queued] task accepted", "event")
    finally:
        stop_worker.set()
        task_queue.put(None)
        worker_thread.join(timeout=2.0)


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
    continue_last: bool = typer.Option(
        False, "--continue", "-c", help="Continue most recent session."
    ),
    session: str | None = typer.Option(None, "--session", "-s", help="Session id to resume."),
    fork: bool = typer.Option(False, "--fork", help="Fork session into a new thread id."),
    file: list[str] = typer.Option([], "--file", "-f", help="Attach file path(s) to prompt."),
    format: str = typer.Option("default", "--format", help="Output format: default|json."),
    title: str | None = typer.Option(None, "--title", help="Optional session title."),
    agent: str | None = typer.Option(None, "--agent", help="Agent selector compatibility flag."),
    attach: str | None = typer.Option(None, "--attach", help="Attach to remote Mirage server URL."),
):
    """Run a single task non-interactively."""
    _ensure_project_scaffold()
    cfg = load_config()
    prov = (provider or "").strip().lower() if provider else cfg.default_provider
    mdl = (model or "").strip() if model else cfg.default_model
    if prov not in PROVIDERS:
        print_status(f"unknown provider: {prov}", "error")
        raise typer.Exit(code=1)
    selected_thread = thread_id
    store = SessionStore()
    if session:
        rec = store.get(session.strip())
        if not rec:
            print_status(f"unknown session id: {session}", "error")
            raise typer.Exit(code=1)
        selected_thread = rec.thread_id
        if provider is None:
            prov = rec.provider
        if model is None:
            mdl = rec.model
    elif continue_last:
        rows = store.list_sessions()
        if rows:
            selected_thread = rows[0].thread_id
            if provider is None:
                prov = rows[0].provider
            if model is None:
                mdl = rows[0].model
    if fork:
        selected_thread = new_thread_id()

    if file:
        attachments = "\n".join(f"- {p}" for p in file)
        task = f"{task}\n\nAttached files:\n{attachments}"

    spec = LLMSpec(provider=prov, model=mdl)
    if not resolve_api_key(cfg, prov):
        print_status(
            "no API key for this provider — set env var or `mirage config set-key`",
            "error",
        )
        raise typer.Exit(code=1)
    if attach:
        print_status(f"attach requested: {attach} (local fallback mode)", "warn")
    execution_policy = policy_for_mode(BUILD_MODE)
    if agent:
        desired = agent.strip().lower()
        if desired in {BUILD_MODE, PLAN_MODE}:
            execution_policy = policy_for_mode(desired)
            print_status(f"agent override requested: {desired}", "info")
        else:
            print_status(f"unknown agent override '{agent}', using build mode policy", "warn")
    if title:
        store.ensure_session(
            selected_thread,
            name=title.strip(),
            provider=spec.provider,
            model=spec.model,
        )
    print_welcome(selected_thread, spec.model, provider=spec.provider)
    graph = build_graph(llm_spec=spec, cfg=cfg)
    try:
        run_agent(graph, task, selected_thread, session=None, execution_policy=execution_policy)
    except Exception as e:  # noqa: BLE001
        print_status(f"error: {e}", "error")
        raise typer.Exit(code=1)
    if format == "json":
        payload = {"thread_id": selected_thread, "provider": spec.provider, "model": spec.model}
        print(json.dumps(payload))


@app.command("export")
def export_session(
    session_id: str | None = typer.Argument(None, help="Session id (defaults to most recent)"),
) -> None:
    rows = SessionStore().list_sessions()
    if not rows:
        print_status("no sessions found", "warn")
        return
    rec = SessionStore().get(session_id) if session_id else rows[0]
    if rec is None:
        print_status(f"session not found: {session_id}", "error")
        raise typer.Exit(code=1)
    out_path = Path.cwd() / f"mirage-session-{rec.thread_id}.json"
    out_path.write_text(json.dumps(rec.__dict__, indent=2) + "\n", encoding="utf-8")
    print_status(f"✓ exported session metadata to {out_path}", "success")


@app.command("import")
def import_session(path: str = typer.Argument(..., help="JSON file path")) -> None:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = ("thread_id", "name", "provider", "model")
    if not all(k in data for k in required):
        print_status("invalid import payload", "error")
        raise typer.Exit(code=1)
    rec = SessionStore().ensure_session(
        str(data["thread_id"]),
        name=str(data["name"]),
        provider=str(data["provider"]),
        model=str(data["model"]),
    )
    print_status(f"✓ imported session {rec.thread_id}", "success")


@app.command("stats")
def stats(days: int | None = typer.Option(None, "--days", help="Reserved compatibility flag")) -> None:
    rows = SessionStore().list_sessions()
    print_status(f"sessions: {len(rows)}", "info")
    providers: dict[str, int] = {}
    for row in rows:
        providers[row.provider] = providers.get(row.provider, 0) + 1
    for provider, count in sorted(providers.items()):
        print_status(f"{provider}: {count}", "info")
    if days is not None:
        print_status(f"--days={days} filter is currently informational only", "warn")


def _start_headless_server(hostname: str, port: int) -> None:
    _ensure_project_scaffold()
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/run":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                payload = json.loads(body)
                message = str(payload.get("message") or "")
                provider = str(payload.get("provider") or load_config().default_provider)
                model = str(payload.get("model") or load_config().default_model)
            except Exception:  # noqa: BLE001
                self.send_response(400)
                self.end_headers()
                return
            cfg = load_config()
            spec = LLMSpec(provider=provider, model=model)
            graph = build_graph(llm_spec=spec, cfg=cfg)
            thread_id = str(payload.get("thread_id") or new_thread_id())
            try:
                run_agent(graph, message, thread_id, session=None)
                resp = {"ok": True, "thread_id": thread_id}
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode("utf-8"))
            except Exception as e:  # noqa: BLE001
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))

    httpd = ThreadingHTTPServer((hostname, port), _Handler)
    print_status(f"Mirage server listening on http://{hostname}:{port}", "success")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print_status("server stopped", "info")


@app.command("serve")
def serve(
    port: int = typer.Option(4096, "--port", help="Port to listen on"),
    hostname: str = typer.Option("127.0.0.1", "--hostname", help="Host to listen on"),
) -> None:
    _start_headless_server(hostname, port)


@app.command("web")
def web(
    port: int = typer.Option(4096, "--port", help="Port to listen on"),
    hostname: str = typer.Option("127.0.0.1", "--hostname", help="Host to listen on"),
) -> None:
    url = f"http://{hostname}:{port}/health"
    webbrowser.open(url)
    _start_headless_server(hostname, port)


@app.command("attach")
def attach(
    url: str = typer.Argument(..., help="Remote server URL"),
    continue_last: bool = typer.Option(False, "--continue", "-c", help="Continue latest session"),
) -> None:
    print_status(f"attached to {url} (compat mode)", "success")
    _start_chat(
        thread_id=None,
        session_id=None,
        model=None,
        provider=None,
    )


def main() -> None:
    """Console-script entry point for installers (pip/pipx/uv/uvx)."""
    app()
