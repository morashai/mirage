"""Rich-based rendering for the Mirage 5 CLI.

The visual language is a Royal Jordanian Air Force overlay on the Mirage 5
silhouette: an aircraft roundel as the brand mark, a flight of three jets
in Jordanian flag colors (black/white/green/red), and a "strike package"
framing for the agent roster. Every renderer writes to the shared
``console`` from ``theme.py`` so output stays in lockstep with the
prompt_toolkit input box and the spinner.
"""
from __future__ import annotations

import os

from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from ..agents.state import MEMBERS
from ..config_store import MirageConfig, mask_secret
from ..llm.catalog import DEFAULT_BASE_URLS, PROVIDERS, list_models_for_provider
from ..sessions.store import SessionRecord
from ..theme import (
    ACCENT,
    AGENT_COLORS,
    AGENT_DISPLAY_NAMES,
    AGENT_GLYPHS,
    JORDAN_BLACK,
    JORDAN_GREEN,
    JORDAN_RED,
    JORDAN_WHITE,
    MUTED,
    SUBTLE,
    SUCCESS,
    SUPERVISOR_COLOR,
    console,
)


# Each member of the strike package gets a one-liner that nods to its role
# in an air-to-ground sortie while still describing its real job.
_TEAM_TAGLINES: dict[str, str] = {
    "ProjectManager": "OPS — plans the mission",
    "UXUIDesigner":   "Recce — UI/UX spec, hands off",
    "Developer":      "Strike — flies the code",
}


def _jordan_formation() -> Text:
    """A four-aircraft flight formation in the colors of the Jordanian flag.

    Reads left-to-right as the Jordan flag's four colors: black, white,
    green, red — the same order they appear on the flag (top-band black,
    middle-band white, bottom-band green, hoist-triangle red).
    """
    fmt = Text()
    fmt.append("✈ ", style=f"bold {JORDAN_BLACK}")
    fmt.append("✈ ", style=f"bold {JORDAN_WHITE}")
    fmt.append("✈ ", style=f"bold {JORDAN_GREEN}")
    fmt.append("✈", style=f"bold {JORDAN_RED}")
    return fmt


def _mirage_title() -> Text:
    """Brand mark: roundel + 'MIRAGE 5' inked in Jordan flag colors.

    Letter pairs are colored in the Jordan flag order — black, white,
    green — with the trailing ``5`` painted in the brand red so it visually
    echoes the hoist triangle.
    """
    title = Text()
    title.append("◎  ", style=f"bold {ACCENT}")
    title.append("MI", style=f"bold {JORDAN_BLACK}")
    title.append("RA", style=f"bold {JORDAN_WHITE}")
    title.append("GE", style=f"bold {JORDAN_GREEN}")
    title.append(" 5", style=f"bold {JORDAN_RED}")
    return title


def print_welcome(thread_id: str, model: str, provider: str | None = None) -> None:
    """Render the Mirage 5 welcome banner.

    Layout (colors apply in a real terminal):

        ◎  MIRAGE 5
            ✈ ✈ ✈ ✈   multi-agent strike package · LangGraph

            /help for help, /quit to exit
            cwd     <path>
            model   <model>
            thread  <thread>

            Strike package:
              ▣  Project Manager — OPS — plans the mission
              ◈  UX/UI Designer  — Recce — UI/UX spec, hands off
              ▲  Developer       — Strike — flies the code
    """
    title = _mirage_title()

    body = Text()
    body.append("\n   ")
    body.append(_jordan_formation())
    body.append("   multi-agent strike package", style=MUTED)
    body.append(" · ", style=SUBTLE)
    body.append("LangGraph", style=MUTED)
    body.append("\n\n")

    body.append("   /help", style=f"bold {ACCENT}")
    body.append(" for help, ", style="default")
    body.append("/quit", style=f"bold {ACCENT}")
    body.append(" to exit\n", style="default")

    body.append(f"   cwd      {os.getcwd()}\n", style=MUTED)
    if provider:
        body.append(f"   provider {provider}\n", style=MUTED)
    body.append(f"   model    {model}\n", style=MUTED)
    body.append(f"   thread   {thread_id}\n", style=MUTED)

    body.append("\n   Strike package:\n", style="default")
    for member in MEMBERS:
        color = AGENT_COLORS[member]
        glyph = AGENT_GLYPHS[member]
        display = AGENT_DISPLAY_NAMES[member]
        tagline = _TEAM_TAGLINES[member]
        body.append(f"     {glyph}  ", style=f"bold {color}")
        body.append(f"{display:<16}", style=color)
        body.append(f"— {tagline}\n", style=MUTED)

    panel = Panel(
        title + body,
        border_style=ACCENT,
        box=box.HEAVY,
        padding=(1, 2),
        expand=False,
    )
    console.print()
    console.print(panel)
    console.print()


def print_agent_message(name: str, content: str) -> None:
    """Render an agent response as a HUD-style indented message."""
    color = AGENT_COLORS.get(name, ACCENT)
    display = AGENT_DISPLAY_NAMES.get(name, name)
    glyph = AGENT_GLYPHS.get(name, "●")

    header = Text()
    header.append(f"{glyph} ", style=f"bold {color}")
    header.append(display, style=f"bold {color}")
    console.print()
    console.print(header)
    console.print(Padding(Markdown(content or "*(no content)*"), (0, 0, 0, 2)))


def print_supervisor_routing(target: str) -> None:
    """Render the supervisor's routing decision as an AWACS tasking line."""
    text = Text()
    text.append("  ⎿ ", style=MUTED)
    text.append("◎ Flight Lead → ", style=f"italic {SUPERVISOR_COLOR}")
    if target == "FINISH":
        text.append("RTB", style=f"italic {MUTED}")
    else:
        target_color = AGENT_COLORS.get(target, SUPERVISOR_COLOR)
        target_display = AGENT_DISPLAY_NAMES.get(target, target)
        target_glyph = AGENT_GLYPHS.get(target, "●")
        text.append(f"{target_glyph} ", style=f"italic bold {target_color}")
        text.append(target_display, style=f"italic bold {target_color}")
    console.print(text)


def print_status(message: str, kind: str = "info") -> None:
    """Print a one-line dimmed status message."""
    color = {
        "info": MUTED,
        "success": SUCCESS,
        "error": "#d96b6b",
        "warn": "#d6a96c",
        "event": ACCENT,
        "working": JORDAN_RED,
        "idle": JORDAN_GREEN,
    }.get(kind, MUTED)
    console.print(Text(f"  {message}", style=f"{color}"))


def show_help() -> None:
    """Render the cockpit / help panel listing slash commands and key bindings."""
    table = Table(
        show_header=False,
        show_edge=False,
        box=None,
        padding=(0, 2),
    )
    table.add_column(style=f"bold {ACCENT}", no_wrap=True)
    table.add_column(style="default")

    rows = [
        ("/help", "show this help"),
        ("/clear", "clear the screen"),
        ("/reset", "alias · start a new session"),
        ("/new [name]", "create a new chat session"),
        ("/sessions", "list saved sessions"),
        ("/session <id|#>", "switch session"),
        ("/rename <name>", "rename current session"),
        ("/delete <id|#>", "delete a session"),
        ("/thread [id]", "show or switch raw thread id"),
        ("/model [name]", "model & API configuration form"),
        ("/provider [name]", "same form · pre-select provider"),
        ("/config", "show configuration form"),
        ("/config edit", "edit configuration"),
        ("/models [provider]", "list curated model ids"),
        ("/exit, /quit", "RTB · exit the CLI"),
        ("", ""),
        ("Enter", "transmit · submit message"),
        ("Esc + Enter", "insert a newline"),
        ("Ctrl+C", "abort input · exit"),
    ]
    for k, v in rows:
        table.add_row(k, v)

    panel = Panel(
        table,
        title=Text("Cockpit · commands & shortcuts", style=f"bold {ACCENT}"),
        title_align="left",
        border_style=SUBTLE,
        box=box.HEAVY,
        padding=(1, 2),
        expand=False,
    )
    console.print()
    console.print(panel)
    console.print()


def print_models_table(provider: str | None = None) -> None:
    """Print curated model ids as a Rich table."""
    table = Table(title="Curated models", box=box.ROUNDED, header_style=f"bold {ACCENT}")
    table.add_column("Provider", style=MUTED)
    table.add_column("Model id", style="default")

    provs = [provider] if provider in PROVIDERS else list(PROVIDERS)
    for p in provs:
        for m in list_models_for_provider(p):
            table.add_row(p, m)

    console.print()
    console.print(table)
    console.print()


def print_sessions_table(rows: list[SessionRecord], *, active_id: str | None = None) -> None:
    """List saved sessions (most recent first)."""
    table = Table(title="Chat sessions", box=box.ROUNDED, header_style=f"bold {ACCENT}")
    table.add_column("#", justify="right", style=MUTED)
    table.add_column("Name")
    table.add_column("Thread")
    table.add_column("Provider / model", style=MUTED)
    table.add_column("Last active", style=MUTED)

    for i, r in enumerate(rows, start=1):
        mark = "● " if active_id and r.thread_id == active_id else ""
        table.add_row(
            str(i),
            f"{mark}{r.name}",
            r.thread_id,
            f"{r.provider}:{r.model}",
            r.last_active_at[:19] if r.last_active_at else "",
        )

    console.print()
    console.print(table)
    console.print()


def print_config_form(cfg: MirageConfig, *, active_provider: str | None = None) -> None:
    """Render stored provider keys and URLs as a read-only form."""
    console.print()
    for prov in PROVIDERS:
        st = cfg.provider_settings(prov)
        header_style = f"bold {ACCENT}" if prov == active_provider else SUBTLE
        tbl = Table(show_header=False, box=box.HEAVY_EDGE, padding=(0, 2), expand=False)
        tbl.add_column("Field", style=MUTED, no_wrap=True)
        tbl.add_column("Value", style="default")

        def_url = DEFAULT_BASE_URLS.get(prov, "") or "(SDK default)"
        tbl.add_row("API key", mask_secret(st.api_key))
        url_disp = (
            str(st.base_url).strip()
            if st.base_url and str(st.base_url).strip()
            else f"(not set — default {def_url})"
        )
        tbl.add_row("Base URL", url_disp)

        title = Text()
        title.append(prov.upper(), style=header_style)
        if prov == active_provider:
            title.append("  (active)", style=SUCCESS)

        console.print(Panel(tbl, title=title, border_style=header_style, expand=False))

    foot = Table(show_header=False, box=None, padding=(0, 2))
    foot.add_column(style=MUTED)
    foot.add_column(style="default")
    foot.add_row("Default provider", cfg.default_provider)
    foot.add_row("Default model", cfg.default_model)
    console.print(Panel(foot, title="Defaults", border_style=SUBTLE, expand=False))
    console.print()
