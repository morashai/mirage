"""Visual theme for the Mirage 5 CLI.

Inspired by the Dassault Mirage 5 — a delta-wing fighter — and dressed in
the colors of the Royal Jordanian Armed Forces. The brand red echoes the
keffiyeh and officer beret; Pan-Arab green carries the radar / AWACS cue;
desert tan reflects RJAF airframe camouflage; warm desert greys replace
the cooler HUD palette of an earlier iteration.

Typography conventions:
- ``ACCENT`` is the brand color (frame borders, prompts, banner mark).
- Per-agent colors map each role to a distinct cue so an operator can
  identify the speaker at a glance.

This module also owns the single shared ``rich.Console`` so output stays
in lockstep across the welcome banner, agent messages, and the slash-
command status lines.
"""
from __future__ import annotations

from rich.console import Console

# ---------------------------------------------------------------------------
# Jordanian national colors (Pan-Arab + flag of Jordan)
# ---------------------------------------------------------------------------
# Note: pure black is rendered as a warm dark grey so it stays visible on a
# typical dark terminal background.
JORDAN_BLACK = "#5a5a5a"
JORDAN_WHITE = "#e8e8e8"
JORDAN_GREEN = "#3a9560"
JORDAN_RED = "#ce1126"

# ---------------------------------------------------------------------------
# Desert / RJAF camo accents
# ---------------------------------------------------------------------------
DESERT_TAN = "#c9a876"
KHAKI = "#a89968"

# ---------------------------------------------------------------------------
# Base palette — Jordanian military identity
# ---------------------------------------------------------------------------
ACCENT = JORDAN_GREEN          # brand color (set to green per request)
ACCENT_DIM = "#1f5a3a"         # darker Jordan green
MUTED = "#8a8470"              # warm desert grey for secondary text
SUBTLE = "#2a2622"             # warm near-black panel borders
SUCCESS = JORDAN_GREEN         # radar lock-on / Pan-Arab green
INFO = JORDAN_GREEN            # alias of SUCCESS for semantic clarity
WARN_AMBER = "#d6a96c"         # caution amber
DANGER_RED = "#d96b6b"         # bright warning red (RWR / threat)

# ---------------------------------------------------------------------------
# Per-agent colors — single primary agent runtime
# ---------------------------------------------------------------------------
DEVELOPER_COLOR = "#d6a35b"              # afterburner amber / strike pilot

AGENT_COLORS: dict[str, str] = {
    "Build": DEVELOPER_COLOR,
}

AGENT_DISPLAY_NAMES: dict[str, str] = {
    "Build": "Build",
}

# Aviation glyphs:
#   ▲  delta wing                 — primary runtime agent
AGENT_GLYPHS: dict[str, str] = {
    "Build":          "▲",
}

# Single shared Rich console used everywhere we render to the terminal.
console: Console = Console()
