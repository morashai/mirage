"""Mirage-compatible config, command, and agent loaders."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .project_paths import find_project_root


@dataclass
class CustomCommand:
    name: str
    description: str
    template: str
    agent: str | None = None
    model: str | None = None
    subtask: bool = False


@dataclass
class CustomAgent:
    name: str
    description: str
    mode: str | None = None
    model: str | None = None
    prompt: str = ""
    permission: str | None = None


_NULLISH = {"", "null", "none", "~"}


def _norm_optional(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    if clean.lower() in _NULLISH:
        return None
    return clean


def _parse_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    text = markdown.strip()
    if not text.startswith("---"):
        return {}, markdown
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, markdown
    front = parts[1]
    body = parts[2].strip()
    out: dict[str, str] = {}
    for raw in front.splitlines():
        if ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        out[key.strip().lower()] = value.strip()
    return out, body


def load_custom_commands(root: Path | None = None) -> dict[str, CustomCommand]:
    base = root or find_project_root()
    commands: dict[str, CustomCommand] = {}
    for folder in (base / ".mirage" / "commands",):
        if not folder.is_dir():
            continue
        for md in sorted(folder.glob("*.md")):
            text = md.read_text(encoding="utf-8")
            front, body = _parse_frontmatter(text)
            name = md.stem.strip().lower()
            commands[name] = CustomCommand(
                name=name,
                description=front.get("description", ""),
                template=body.strip(),
                agent=_norm_optional(front.get("agent")),
                model=_norm_optional(front.get("model")),
                subtask=front.get("subtask", "").strip().lower() in {"true", "1", "yes", "on"},
            )
    return commands


def apply_command_template(template: str, args: str) -> str:
    argv = [part for part in re.split(r"\s+", args.strip()) if part]
    out = template.replace("$ARGUMENTS", args.strip())
    for idx, value in enumerate(argv, start=1):
        out = out.replace(f"${idx}", value)
    return out


def load_custom_agents(root: Path | None = None) -> dict[str, CustomAgent]:
    base = root or find_project_root()
    agents: dict[str, CustomAgent] = {}
    folder = base / ".mirage" / "agents"
    if not folder.is_dir():
        return agents
    for md in sorted(folder.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        front, _ = _parse_frontmatter(text)
        name = md.stem.strip().lower()
        agents[name] = CustomAgent(
            name=name,
            description=front.get("description", ""),
            mode=_norm_optional(front.get("mode")),
            model=_norm_optional(front.get("model")),
            prompt=text.split("---", 2)[2].strip() if text.strip().startswith("---") and text.count("---") >= 2 else text.strip(),
            permission=_norm_optional(front.get("permission")),
        )
    return agents


def load_mirage_project_defaults(root: Path | None = None) -> dict[str, str]:
    base = root or find_project_root()
    path = base / "mirage.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, str] = {}
    model = str(data.get("model") or "").strip()
    if "/" in model:
        prov, _, mod = model.partition("/")
        if prov and mod:
            out["provider"] = prov.strip().lower()
            out["model"] = mod.strip()
    return out
