"""Slash-command dispatcher and runtime stream loop."""
from __future__ import annotations

import os
import re
import shlex
import sys
import tempfile
from pathlib import Path
from dataclasses import replace
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage

from ..agents.graph import build_graph
from ..config import RECURSION_LIMIT
from ..config_store import (
    MCPServerConfig,
    delete_mcp_server,
    disable_mcp_server,
    list_mcp_servers_merged,
    load_config,
    parse_model_arg,
    resolve_api_key,
    resolve_base_url,
    save_mcp_server,
)
from ..llm.catalog import PROVIDERS
from ..llm.factory import make_llm
from ..llm.spec import LLMSpec
from ..sessions.store import SessionStore, new_thread_id, resolve_session_selector
from .model_form import run_model_form
from .edit_history import EditTransaction, FileSnapshot, record_transaction, redo_last, undo_last
from .mirage_compat import apply_command_template, load_custom_agents, load_custom_commands
from .modes import BUILD_MODE, PLAN_MODE, policy_for_mode
from .policy import get_policy, set_policy
from .project_paths import find_project_root
from .runtime_state import RuntimeSessionState, RuntimeSessionStore
from .render import (
    print_agent_message,
    print_config_form,
    print_models_table,
    print_sessions_table,
    print_status,
    print_welcome,
    show_help,
)


_FILE_WRITE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Successfully wrote to (?P<path>.+)$"),
    re.compile(r"Successfully updated (?P<path>.+)$"),
)

_HITL_HINT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bplease clarify\b", re.IGNORECASE),
    re.compile(r"\bcould you clarify\b", re.IGNORECASE),
    re.compile(r"\bcan you clarify\b", re.IGNORECASE),
    re.compile(r"\bplease confirm\b", re.IGNORECASE),
    re.compile(r"\bwhich (?:one|option|approach)\b", re.IGNORECASE),
    re.compile(r"\bdo you want\b", re.IGNORECASE),
    re.compile(r"\bshould (?:it|we|i)\b", re.IGNORECASE),
    re.compile(r"\bonce you provide\b", re.IGNORECASE),
)

_DETAILS_VISIBLE = True
_THINKING_VISIBLE = False
_SHARED_SESSIONS: set[str] = set()


def _parse_flag_map(arg: str | None) -> tuple[list[str], dict[str, list[str]]]:
    tokens = shlex.split(arg or "")
    positionals: list[str] = []
    flags: dict[str, list[str]] = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--"):
            key = tok[2:].strip().lower()
            if not key:
                i += 1
                continue
            value = ""
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                value = tokens[i + 1]
                i += 1
            flags.setdefault(key, []).append(value)
        else:
            positionals.append(tok)
        i += 1
    return positionals, flags


def _live_stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _detect_project_stack(root: Path) -> str:
    if (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file():
        return "Python"
    if (root / "package.json").is_file():
        return "Node.js"
    if (root / "Cargo.toml").is_file():
        return "Rust"
    if (root / "go.mod").is_file():
        return "Go"
    return "Unknown"


def _init_agents_md(root: Path) -> tuple[Path, str]:
    target = root / "AGENTS.md"
    stack = _detect_project_stack(root)
    project_name = root.name
    section = (
        "## Mirage Project Instructions\n"
        f"- Project: {project_name}\n"
        f"- Stack: {stack}\n"
        "- Follow existing repository conventions before introducing new patterns.\n"
        "- Keep changes minimal and scoped to the request.\n"
        "- Run targeted tests/lint for touched areas when feasible.\n"
        "- For risky changes, explain assumptions and validation steps clearly.\n"
    )
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if "## Mirage Project Instructions" in existing:
            return target, "already-configured"
        target.write_text(existing.rstrip() + "\n\n" + section + "\n", encoding="utf-8")
        return target, "updated"
    seed = (
        "# AGENTS\n\n"
        "Project-specific instructions for Mirage agent behavior.\n\n"
        f"{section}\n"
    )
    target.write_text(seed, encoding="utf-8")
    return target, "created"


def _safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-").lower()
    return cleaned or "untitled"


def _project_context_snapshot(root: Path) -> str:
    top_entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
    top_names = [p.name for p in top_entries[:24]]
    stack = _detect_project_stack(root)
    return (
        f"Project: {root.name}\n"
        f"Stack: {stack}\n"
        f"Top-level entries: {', '.join(top_names)}\n"
    )


def _llm_markdown_draft(
    *,
    provider: str,
    model: str,
    prompt: str,
) -> str:
    cfg = load_config()
    api_key = resolve_api_key(cfg, provider)
    base_url = resolve_base_url(cfg, provider)
    llm = make_llm(provider, model, api_key=api_key, base_url=base_url)
    msg = llm.invoke(prompt)
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            elif isinstance(item, str) and item.strip():
                parts.append(item.strip())
        return "\n\n".join(parts).strip()
    return str(content).strip()


def _create_project_spec(root: Path, title: str, *, provider: str, model: str) -> Path:
    specs_dir = root / ".mirage" / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    slug = _safe_slug(title)
    path = specs_dir / f"{slug}.md"
    if path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        path = specs_dir / f"{slug}-{stamp}.md"
    context = _project_context_snapshot(root)
    try:
        body = _llm_markdown_draft(
            provider=provider,
            model=model,
            prompt=(
                "Create a concise, implementation-ready project specification in Markdown.\n"
                "Use these sections exactly: Title, Goal, Scope, Functional requirements, "
                "Non-functional requirements, Acceptance criteria, Risks and assumptions.\n"
                "Prefer concrete details inferred from context and avoid placeholders.\n\n"
                f"Requested feature: {title}\n\n"
                f"{context}"
            ),
        )
    except Exception:  # noqa: BLE001
        body = (
            f"# Spec\n\n## Title\n{title}\n\n## Goal\n- Define the target outcome.\n\n"
            "## Scope\n- In scope\n- Out of scope\n\n## Functional requirements\n- TBD\n\n"
            "## Non-functional requirements\n- TBD\n\n## Acceptance criteria\n- [ ] TBD\n\n"
            "## Risks and assumptions\n- TBD\n"
        )
    path.write_text(body.rstrip() + "\n", encoding="utf-8")
    return path


def _latest_spec_file(root: Path) -> Path | None:
    specs_dir = root / ".mirage" / "specs"
    if not specs_dir.is_dir():
        return None
    files = [p for p in specs_dir.glob("*.md") if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _latest_plan_file(root: Path) -> Path | None:
    plans_dir = root / ".mirage" / "plans"
    if not plans_dir.is_dir():
        return None
    files = [p for p in plans_dir.glob("*.md") if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _create_project_plan(
    root: Path,
    title: str,
    *,
    provider: str,
    model: str,
    spec_path: Path,
) -> Path:
    plans_dir = root / ".mirage" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    slug = _safe_slug(title)
    path = plans_dir / f"{slug}.md"
    if path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        path = plans_dir / f"{slug}-{stamp}.md"
    spec_text = spec_path.read_text(encoding="utf-8")
    context = _project_context_snapshot(root)
    try:
        body = _llm_markdown_draft(
            provider=provider,
            model=model,
            prompt=(
                "Create a spec-driven implementation plan in Markdown from the provided spec.\n"
                "Use these sections exactly: Title, Milestones, Task breakdown, Validation strategy, Rollback strategy.\n"
                "Task breakdown must be actionable checkboxes grouped by milestone and file touchpoints.\n"
                "Do not restate generic advice; anchor tasks to the spec details.\n\n"
                f"Plan title: {title}\n\n"
                f"{context}\n"
                f"Source spec path: {spec_path}\n\n"
                "Source spec:\n"
                f"{spec_text}\n"
            ),
        )
    except Exception:  # noqa: BLE001
        body = (
            f"# Plan\n\n## Title\n{title}\n\n## Milestones\n1. Implementation\n2. Verification\n\n"
            "## Task breakdown\n- [ ] Implement per spec\n- [ ] Add tests\n\n"
            "## Validation strategy\n- Run targeted tests\n\n## Rollback strategy\n- Revert change set\n"
        )
    path.write_text(body.rstrip() + "\n", encoding="utf-8")
    return path


def _prepare_spec_driven_task(
    raw_task: str,
    *,
    provider: str,
    model: str,
) -> tuple[str, Path, Path]:
    """Ensure spec+plan exist and return an enriched task prompt."""
    root = find_project_root()
    spec_path = _latest_spec_file(root)
    if spec_path is None:
        spec_path = _create_project_spec(
            root,
            raw_task[:80] or "Project Spec",
            provider=provider,
            model=model,
        )

    plan_path = _latest_plan_file(root)
    if plan_path is None or plan_path.stat().st_mtime < spec_path.stat().st_mtime:
        plan_path = _create_project_plan(
            root,
            raw_task[:80] or "Project Plan",
            provider=provider,
            model=model,
            spec_path=spec_path,
        )

    project_context = _project_context_snapshot(root)
    spec_text = spec_path.read_text(encoding="utf-8").strip()
    plan_text = plan_path.read_text(encoding="utf-8").strip()
    enriched = (
        "Use the following project context and plan as the source of truth.\n"
        "If implementation details are missing, update the plan first, then execute.\n\n"
        "## Project context\n"
        f"{project_context}\n"
        "## Active spec\n"
        f"path: {spec_path}\n\n"
        f"{spec_text}\n\n"
        "## Active plan\n"
        f"path: {plan_path}\n\n"
        f"{plan_text}\n\n"
        "## User request\n"
        f"{raw_task}\n"
    )
    return enriched, spec_path, plan_path


_OPEN_CHECKBOX_RE = re.compile(r"^(\s*[-*]\s+\[ \]\s+)(.+?)\s*$")


def _list_open_plan_items(plan_path: Path) -> list[str]:
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    items: list[str] = []
    for line in lines:
        m = _OPEN_CHECKBOX_RE.match(line)
        if m:
            items.append(m.group(2).strip())
    return items


def _mark_plan_item_done(plan_path: Path, item_text: str) -> bool:
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    needle = item_text.strip()
    for i, line in enumerate(lines):
        m = _OPEN_CHECKBOX_RE.match(line)
        if not m:
            continue
        if m.group(2).strip() != needle:
            continue
        prefix = m.group(1).replace("[ ]", "[x]", 1)
        lines[i] = f"{prefix}{m.group(2).strip()}"
        plan_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return True
    return False


def _classify_tool_action(tool_name: str) -> str:
    """Return a human label for tool actions in live logs."""
    name = tool_name.lower()
    if name in {"write_file"}:
        return "create-file"
    if name in {"edit_file", "edit_notebook_cell"}:
        return "update-file"
    if name in {"read_file", "list_directory", "glob_search", "ripgrep_search"}:
        return "read/search"
    if name in {"run_shell_command", "git_status", "git_diff", "git_log", "git_current_branch"}:
        return "shell/git"
    return "tool"


def _tool_result_kind(content: str) -> str:
    """Map tool result content to status kind."""
    text = content.strip().lower()
    if text.startswith("error:") or "traceback" in text:
        return "error"
    return "info"


def _is_human_input_request(content: str) -> bool:
    """Heuristic: detect agent messages that ask user clarification."""
    text = " ".join((content or "").split()).strip()
    if not text:
        return False
    if "?" not in text:
        return False
    return any(pattern.search(text) for pattern in _HITL_HINT_PATTERNS)


def _extract_tool_args_path(tool_call: dict) -> str | None:
    """Best-effort file path extraction from tool call args."""
    args = tool_call.get("args")
    if isinstance(args, dict):
        for key in ("filepath", "path", "file_path", "filename"):
            value = args.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _extract_written_file(content: str) -> str | None:
    """Parse tool result text and return a written/updated path when present."""
    if not content:
        return None
    for line in content.splitlines():
        text = line.strip()
        for pattern in _FILE_WRITE_PATTERNS:
            match = pattern.match(text)
            if match:
                return match.group("path").strip()
    return None


def _iter_live_stream_events(graph, payload, config):
    """Yield normalized ``(mode, data)`` events from LangGraph stream APIs.

    Prefer richer multi-mode streaming so CLI can expose granular activity.
    Fallback to plain ``updates`` mode when multi-mode is unavailable.
    """
    try:
        stream = graph.stream(
            payload,
            config,
            stream_mode=["updates", "values"],
        )
        for item in stream:
            if (
                isinstance(item, tuple)
                and len(item) == 2
                and isinstance(item[0], str)
            ):
                yield item[0], item[1]
            else:
                yield "updates", item
    except TypeError:
        # Older LangGraph versions may not accept multi-mode lists.
        for item in graph.stream(payload, config, stream_mode="updates"):
            yield "updates", item


def _emit_live_message_events(
    state_snapshot: dict,
    *,
    seen_message_keys: set[str],
    seen_live_events: set[str],
    pending_tool_calls: dict[str, tuple[str, str | None]],
) -> None:
    """Render newly-seen messages from the state snapshot."""
    if not isinstance(state_snapshot, dict):
        return
    messages = state_snapshot.get("messages")
    if not isinstance(messages, list):
        return

    for index, msg in enumerate(messages):
        msg_id = getattr(msg, "id", None)
        message_key = str(msg_id) if msg_id else f"idx:{index}:{type(msg).__name__}"
        if message_key in seen_message_keys:
            continue
        seen_message_keys.add(message_key)

        msg_type = str(getattr(msg, "type", "")).lower()
        name = str(getattr(msg, "name", "") or "")
        content = getattr(msg, "content", "") or ""

        tool_calls = getattr(msg, "tool_calls", None) or []
        if tool_calls:
            for tool_call in tool_calls:
                tool_name = str(tool_call.get("name", "tool"))
                tool_call_id = str(tool_call.get("id", "") or "")
                target = _extract_tool_args_path(tool_call)
                event_key = f"call:{tool_name}:{target or ''}:{tool_call_id}"
                if event_key in seen_live_events:
                    continue
                seen_live_events.add(event_key)
                if tool_call_id:
                    pending_tool_calls[tool_call_id] = (tool_name, target)
                label = _classify_tool_action(tool_name)
                if target:
                    print_status(
                        f"[live {_live_stamp()}] {label}: {tool_name} ({target})",
                        "event",
                    )
                else:
                    print_status(f"[live {_live_stamp()}] {label}: {tool_name}", "event")

        if msg_type == "tool":
            text = str(content).strip()
            tool_call_id = str(getattr(msg, "tool_call_id", "") or "")
            tool_context = pending_tool_calls.pop(tool_call_id, None) if tool_call_id else None
            if text:
                preview = text if len(text) <= 240 else f"{text[:240]}..."
                if tool_context:
                    tool_name, target = tool_context
                    if target:
                        prefix = f"[live] result <- {tool_name} ({target})"
                    else:
                        prefix = f"[live] result <- {tool_name}"
                else:
                    prefix = f"[live {_live_stamp()}] tool result"
                print_status(f"{prefix}: {preview}", _tool_result_kind(text))
            written_file = _extract_written_file(str(content))
            if written_file:
                event_key = f"file:{written_file}"
                if event_key not in seen_live_events:
                    seen_live_events.add(event_key)
                    print_status(f"[live {_live_stamp()}] file updated: {written_file}", "success")
            continue

        if msg_type in {"ai", "assistant"}:
            # Only render substantive assistant turns, skip pure tool-call wrappers.
            if str(content).strip():
                display_name = name if name else "Build"
                print_agent_message(display_name, str(content))


def _seed_seen_message_keys_from_history(
    graph,
    config: dict,
    *,
    seen_message_keys: set[str],
) -> None:
    """Mark existing checkpointed messages as already-seen.

    Without this seed, each new run may replay older thread messages when the
    graph streams full state snapshots.
    """
    try:
        snapshot = graph.get_state(config)
        values = getattr(snapshot, "values", None)
        if not isinstance(values, dict):
            return
        messages = values.get("messages")
        if not isinstance(messages, list):
            return
        for index, msg in enumerate(messages):
            msg_id = getattr(msg, "id", None)
            message_key = str(msg_id) if msg_id else f"idx:{index}:{type(msg).__name__}"
            seen_message_keys.add(message_key)
    except Exception:  # noqa: BLE001
        # Older LangGraph builds or missing checkpoint state should not block run.
        return


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
    mode = BUILD_MODE
    initial = RuntimeSessionState(
        thread_id=thread_id,
        provider=provider,
        model=model,
        session_name=(session_name or thread_id).strip() or thread_id,
        session_store=session_store,
        mode=mode,
        permission_policy=policy_for_mode(mode),
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

    if cmd in ("/exit", "/quit", "/q"):
        print_status("goodbye", "info")
        sys.exit(0)

    if cmd == "/help":
        show_help()
        return True

    if cmd == "/connect":
        # Mirage equivalent for provider onboarding: open model+credentials form.
        open_model_configuration(session)
        return True

    if cmd == "/init":
        agents_path, status = _init_agents_md(find_project_root())
        if status == "created":
            print_status(f"✓ created {agents_path}", "success")
        elif status == "updated":
            print_status(f"✓ updated {agents_path}", "success")
        else:
            print_status("AGENTS.md already configured", "info")
        return True

    if cmd == "/spec":
        title = (arg or "Project Spec").strip() or "Project Spec"
        spec_path = _create_project_spec(
            find_project_root(),
            title,
            provider=state.provider,
            model=state.model,
        )
        session.set_state(
            lambda prev: replace(
                prev,
                mode=PLAN_MODE,
                permission_policy=policy_for_mode(PLAN_MODE),
            )
        )
        print_status(f"✓ created spec: {spec_path}", "success")
        print_status("mode switched to plan", "info")
        return True

    if cmd == "/plan":
        title = (arg or "Project Plan").strip() or "Project Plan"
        root = find_project_root()
        spec_path = _latest_spec_file(root)
        if spec_path is None:
            print_status("no spec found. create one first with /spec <title>", "error")
            return True
        plan_path = _create_project_plan(
            root,
            title,
            provider=state.provider,
            model=state.model,
            spec_path=spec_path,
        )
        session.set_state(
            lambda prev: replace(
                prev,
                mode=PLAN_MODE,
                permission_policy=policy_for_mode(PLAN_MODE),
            )
        )
        print_status(f"✓ created plan: {plan_path}", "success")
        print_status(f"source spec: {spec_path}", "info")
        print_status("mode switched to plan", "info")
        return True

    if cmd == "/clear":
        os.system("cls" if os.name == "nt" else "clear")
        print_welcome(
            state.thread_id,
            state.model,
            provider=state.provider,
        )
        return True

    if cmd in ("/undo", "/redo"):
        if cmd == "/undo":
            count = undo_last(state.thread_id)
            if count:
                print_status(f"✓ undo restored {count} file(s)", "success")
            else:
                print_status("nothing to undo", "warn")
        else:
            count = redo_last(state.thread_id)
            if count:
                print_status(f"✓ redo restored {count} file(s)", "success")
            else:
                print_status("nothing to redo", "warn")
        return True

    if cmd in ("/compact", "/summarize"):
        compact_dir = find_project_root() / ".mirage" / "compactions"
        compact_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = compact_dir / f"{state.thread_id}-{stamp}.md"
        out.write_text(
            "# Mirage Session Compaction\n\n"
            f"- thread: {state.thread_id}\n"
            f"- provider: {state.provider}\n"
            f"- model: {state.model}\n"
            f"- mode: {state.mode}\n"
            "\nCompaction placeholder: summarize key decisions from this thread.\n",
            encoding="utf-8",
        )
        print_status(f"✓ compacted session marker written to {out}", "success")
        return True

    if cmd == "/details":
        global _DETAILS_VISIBLE
        _DETAILS_VISIBLE = not _DETAILS_VISIBLE
        print_status(f"tool details: {'on' if _DETAILS_VISIBLE else 'off'}", "info")
        return True

    if cmd == "/thinking":
        global _THINKING_VISIBLE
        _THINKING_VISIBLE = not _THINKING_VISIBLE
        print_status(f"thinking blocks: {'visible' if _THINKING_VISIBLE else 'hidden'}", "info")
        return True

    if cmd == "/themes":
        print_status("available themes: mirage-default", "info")
        return True

    if cmd == "/editor":
        editor = os.getenv("EDITOR") or ("notepad" if os.name == "nt" else "nano")
        with tempfile.NamedTemporaryFile(
            mode="w+", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp:
            tmp_path = Path(tmp.name)
        try:
            os.system(f'{editor} "{tmp_path}"')
            draft = tmp_path.read_text(encoding="utf-8").strip()
            if draft:
                print_status("draft ready; submit by sending the edited text manually", "info")
            else:
                print_status("editor closed with empty draft", "warn")
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
        return True

    if cmd == "/export":
        export_path = find_project_root() / f"mirage-chat-{state.thread_id}.md"
        export_path.write_text(
            f"# Mirage Session\n\n- thread: {state.thread_id}\n- provider: {state.provider}\n- model: {state.model}\n",
            encoding="utf-8",
        )
        print_status(f"✓ exported session shell to {export_path}", "success")
        return True

    if cmd == "/share":
        _SHARED_SESSIONS.add(state.thread_id)
        share_dir = find_project_root() / ".mirage" / "shares"
        share_dir.mkdir(parents=True, exist_ok=True)
        share_file = share_dir / f"{state.thread_id}.share"
        share_file.write_text(f"mirage://share/{state.thread_id}\n", encoding="utf-8")
        print_status(f"✓ session shared locally: {share_file}", "success")
        return True

    if cmd == "/unshare":
        _SHARED_SESSIONS.discard(state.thread_id)
        share_file = find_project_root() / ".mirage" / "shares" / f"{state.thread_id}.share"
        if share_file.exists():
            share_file.unlink()
        print_status(f"✓ session unshared locally: {state.thread_id}", "success")
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

    if cmd == "/mode":
        desired = (arg or "").strip().lower()
        if not desired:
            print_status(f"current mode: {state.mode}", "info")
            return True
        if desired not in {BUILD_MODE, PLAN_MODE}:
            print_status("usage: /mode <build|plan>", "error")
            return True
        session.set_state(
            lambda prev: replace(
                prev,
                mode=desired,
                permission_policy=policy_for_mode(desired),
            )
        )
        print_status(f"✓ mode set to {desired}", "success")
        return True

    if cmd == "/agent":
        if not arg:
            print_status("usage: /agent <name>", "error")
            return True
        name = arg.strip().lower()
        if name in {BUILD_MODE, PLAN_MODE}:
            session.set_state(
                lambda prev: replace(
                    prev,
                    mode=name,
                    permission_policy=policy_for_mode(name),
                )
            )
            print_status(f"✓ active agent mode: {name}", "success")
            return True
        agents = load_custom_agents()
        hit = agents.get(name)
        if not hit:
            print_status(f"agent not found: {name}", "error")
            return True
        new_mode = (hit.mode or BUILD_MODE).strip().lower()
        if new_mode not in {BUILD_MODE, PLAN_MODE}:
            new_mode = BUILD_MODE
        session.set_state(
            lambda prev: replace(
                prev,
                mode=new_mode,
                permission_policy=policy_for_mode(new_mode),
                model=(hit.model.split("/", 1)[1] if hit.model and "/" in hit.model else prev.model),
                provider=(hit.model.split("/", 1)[0] if hit.model and "/" in hit.model else prev.provider),
                graph=None,
            )
        )
        print_status(f"✓ selected agent {name} (mode={new_mode})", "success")
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

    if cmd == "/mcp":
        pos, flags = _parse_flag_map(arg)
        if not pos:
            print_status("usage: /mcp <list|add|delete|disable> [...]", "error")
            return True
        sub = pos[0].lower()
        if sub == "list":
            rows = list_mcp_servers_merged()
            if not rows:
                print_status("no configured MCP servers", "info")
                return True
            for row in rows:
                detail = (
                    f"command={row.command} args={row.args}"
                    if row.kind == "local"
                    else f"url={row.url}"
                )
                print_status(
                    f"{row.name}: kind={row.kind} enabled={row.enabled} {detail}",
                    "info",
                )
            return True
        if sub == "add":
            name = (flags.get("name") or [""])[0].strip()
            command = (flags.get("command") or [""])[0].strip()
            url = (flags.get("url") or [""])[0].strip()
            scope = (flags.get("scope") or ["project"])[0].strip().lower()
            args = [v for v in flags.get("arg", []) if v]
            if not name:
                print_status("usage: /mcp add --name <name> (--command <cmd> [--arg ...] | --url <url>) [--scope user|project]", "error")
                return True
            if scope not in {"user", "project"}:
                print_status("scope must be user or project", "error")
                return True
            has_local = bool(command)
            has_remote = bool(url)
            if has_local == has_remote:
                print_status("provide exactly one of --command or --url", "error")
                return True
            if has_local:
                server = MCPServerConfig(
                    name=name,
                    enabled=True,
                    kind="local",
                    command=command,
                    args=args,
                    url=None,
                )
            else:
                server = MCPServerConfig(
                    name=name,
                    enabled=True,
                    kind="remote",
                    command=None,
                    args=[],
                    url=url,
                )
            save_mcp_server(server, scope)
            print_status(f"✓ MCP server saved: {name} ({server.kind}, scope={scope})", "success")
            return True
        if sub in {"disable", "delete"}:
            name = pos[1].strip() if len(pos) > 1 else (flags.get("name") or [""])[0].strip()
            scope = (flags.get("scope") or ["project"])[0].strip().lower()
            if not name:
                print_status(f"usage: /mcp {sub} <name> [--scope user|project]", "error")
                return True
            if scope not in {"user", "project"}:
                print_status("scope must be user or project", "error")
                return True
            if sub == "disable":
                if not disable_mcp_server(name, scope):
                    print_status(f"MCP server not found in {scope} scope: {name}", "error")
                    return True
                print_status(f"✓ MCP server disabled: {name} (scope={scope})", "success")
            else:
                if not delete_mcp_server(name, scope):
                    print_status(f"MCP server not found in {scope} scope: {name}", "error")
                    return True
                print_status(f"✓ MCP server deleted: {name} (scope={scope})", "success")
            return True
        print_status("usage: /mcp <list|add|delete|disable> [...]", "error")
        return True

    if cmd == "/models":
        prov = arg.strip().lower() if arg else None
        if prov and prov not in PROVIDERS:
            print_status(f"unknown provider: {prov}", "error")
            return True
        print_models_table(prov)
        return True

    if cmd in ("/sessions", "/resume", "/continue"):
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

    custom_cmd = cmd.lstrip("/")
    loaded = load_custom_commands()
    if custom_cmd in loaded:
        template = loaded[custom_cmd]
        expanded = apply_command_template(template.template, arg or "")
        print_status(f"running custom command /{custom_cmd}", "event")
        current_state = session.get_state()
        target_graph = current_state.graph
        target_provider = current_state.provider
        target_model = current_state.model
        target_policy = current_state.permission_policy
        if template.agent:
            desired_mode = template.agent.strip().lower()
            if desired_mode in {BUILD_MODE, PLAN_MODE}:
                target_policy = policy_for_mode(desired_mode)
        if template.model:
            raw = template.model.strip()
            if "/" in raw:
                target_provider, _, target_model = raw.partition("/")
            else:
                target_model = raw
            _, target_graph = _build_session_graph(target_provider, target_model)
        target_thread = new_thread_id() if template.subtask else current_state.thread_id
        run_agent(
            target_graph,
            expanded,
            target_thread,
            session=session,
            execution_policy=target_policy,
        )
        return True

    if cmd == "/agents":
        agents = load_custom_agents()
        if not agents:
            print_status("no custom agents found in .mirage/agents", "info")
            return True
        for name, data in agents.items():
            print_status(
                f"{name}: mode={data.mode or 'all'} model={data.model or '(default)'} permission={data.permission or '(mode default)'}",
                "info",
            )
        return True

    print_status(f"unknown command: {cmd}  (try /help)", "error")
    return True


def run_agent(
    graph,
    task: str,
    thread_id: str,
    session: RuntimeSessionStore | None = None,
    execution_policy: dict[str, str] | None = None,
) -> None:
    """Stream the runtime workflow autonomously."""
    if session is not None:
        st = session.get_state()
        try:
            task, spec_path, plan_path = _prepare_spec_driven_task(
                task,
                provider=st.provider,
                model=st.model,
            )
            print_status(f"[spec-driven] using spec: {spec_path}", "info")
            print_status(f"[spec-driven] using plan: {plan_path}", "info")
        except Exception as e:  # noqa: BLE001
            print_status(f"[spec-driven] fallback to raw task ({e})", "warn")

    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    previous_policy = get_policy()
    if execution_policy is not None:
        set_policy(execution_policy)
    elif session is not None:
        set_policy(session.get_state().permission_policy)
    touched_files_before: dict[str, tuple[bool, str]] = {}

    plan_path_local = locals().get("plan_path")
    open_plan_items: list[str] = []
    if isinstance(plan_path_local, Path) and plan_path_local.is_file():
        try:
            open_plan_items = _list_open_plan_items(plan_path_local)
        except Exception:  # noqa: BLE001
            open_plan_items = []

    iteration_tasks = [task]
    if open_plan_items:
        iteration_tasks = [
            (
                f"{task}\n\n"
                f"## Current plan task ({idx}/{len(open_plan_items)})\n"
                f"- {item}\n\n"
                "Complete this task now. Keep changes scoped to this task."
            )
            for idx, item in enumerate(open_plan_items, start=1)
        ]
        print_status(f"[spec-driven] iterating {len(open_plan_items)} plan tasks", "info")

    try:
        for task_idx, current_task in enumerate(iteration_tasks):
            last_sig: tuple[str, str] | None = None
            stagnant_repeats = 0
            seen_live_events: set[str] = set()
            seen_message_keys: set[str] = set()
            pending_tool_calls: dict[str, tuple[str, str | None]] = {}
            _seed_seen_message_keys_from_history(
                graph,
                config,
                seen_message_keys=seen_message_keys,
            )
            should_stop = False
            for mode, event in _iter_live_stream_events(
                graph,
                {"messages": [HumanMessage(content=current_task)]},
                config,
            ):
                if mode == "updates" and isinstance(event, dict):
                    for node_name, node_state in event.items():
                        if isinstance(node_state, dict):
                            msgs = node_state.get("messages")
                            if isinstance(msgs, list) and msgs:
                                _emit_live_message_events(
                                    {"messages": msgs},
                                    seen_message_keys=seen_message_keys,
                                    seen_live_events=seen_live_events,
                                    pending_tool_calls=pending_tool_calls,
                                )
                                content = getattr(msgs[-1], "content", "") or ""
                                if _is_human_input_request(str(content)):
                                    print_status(
                                        "[HITL] Agent requested clarification. Waiting for your input...",
                                        "warn",
                                    )
                                    should_stop = True
                                    break
                                normalized = " ".join(str(content).split()).strip().lower()
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
                                    should_stop = True
                                    break
                    if should_stop:
                        break
                elif mode == "values":
                    _emit_live_message_events(
                        event,
                        seen_message_keys=seen_message_keys,
                        seen_live_events=seen_live_events,
                        pending_tool_calls=pending_tool_calls,
                    )
                    if isinstance(event, dict):
                        messages = event.get("messages")
                        if isinstance(messages, list):
                            for msg in messages:
                                if str(getattr(msg, "type", "")).lower() == "tool":
                                    written = _extract_written_file(str(getattr(msg, "content", "") or ""))
                                    if written and written not in touched_files_before:
                                        p = Path(written)
                                        if p.exists():
                                            touched_files_before[written] = (
                                                True,
                                                p.read_text(encoding="utf-8"),
                                            )
                                        else:
                                            touched_files_before[written] = (False, "")

            if (
                not should_stop
                and open_plan_items
                and isinstance(plan_path_local, Path)
                and plan_path_local.is_file()
            ):
                item = open_plan_items[task_idx]
                if _mark_plan_item_done(plan_path_local, item):
                    print_status(f"[spec-driven] marked done: {item}", "success")
            if should_stop:
                break
    finally:
        set_policy(previous_policy)
    if session is not None:
        session.get_state().session_store.touch(thread_id)
    if touched_files_before:
        snapshots: list[FileSnapshot] = []
        for path, (before_exists, before_content) in touched_files_before.items():
            p = Path(path)
            if p.exists():
                after_exists = True
                after_content = p.read_text(encoding="utf-8")
            else:
                after_exists = False
                after_content = ""
            snapshots.append(
                FileSnapshot(
                    path=path,
                    before_exists=before_exists,
                    before_content=before_content,
                    after_exists=after_exists,
                    after_content=after_content,
                )
            )
        record_transaction(thread_id, EditTransaction(files=snapshots))
