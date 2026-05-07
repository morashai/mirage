"""Load Mirage instruction files for prompt context."""
from __future__ import annotations

from pathlib import Path


def _find_upwards(start: Path, names: tuple[str, ...]) -> Path | None:
    for current in (start, *start.parents):
        for name in names:
            candidate = current / name
            if candidate.is_file():
                return candidate
    return None


def _read_text(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def load_instruction_context(start_dir: Path | None = None) -> str:
    """Compose instruction context using Mirage precedence.

    Order:
    - Local ``AGENTS.md`` (fallback ``CLAUDE.md``) discovered by upward traversal
    - Global ``~/.mirage/AGENTS.md`` (fallback ``~/.claude/CLAUDE.md``)
    """
    start = (start_dir or Path.cwd()).resolve()

    local_agents = _find_upwards(start, ("AGENTS.md",))
    local_claude = _find_upwards(start, ("CLAUDE.md",)) if local_agents is None else None

    global_agents = Path.home() / ".mirage" / "AGENTS.md"
    global_claude = Path.home() / ".claude" / "CLAUDE.md"
    global_file = global_agents if global_agents.is_file() else (
        global_claude if global_claude.is_file() else None
    )

    sections: list[str] = []
    local_text = _read_text(local_agents or local_claude)
    if local_text:
        sections.append("## Project Instructions\n" + local_text)
    global_text = _read_text(global_file)
    if global_text:
        sections.append("## Global Instructions\n" + global_text)
    return "\n\n".join(sections).strip()
