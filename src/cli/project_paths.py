"""Project path resolution and Mirage scaffold helpers."""
from __future__ import annotations

import os
from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    """Walk upward and return the nearest plausible project root."""
    cur = (start or Path.cwd()).resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / ".git").exists():
            return candidate
        if (candidate / "mirage.json").is_file():
            return candidate
        if (candidate / ".mirage").is_dir():
            return candidate
    return cur


def _is_bad_scaffold_target(root: Path) -> bool:
    try:
        if root == Path.home():
            return True
        if root.parent == root:
            return True
        windir = os.getenv("WINDIR")
        if windir and root.resolve() == Path(windir).resolve():
            return True
    except Exception:  # noqa: BLE001
        return True
    return False


def ensure_mirage_scaffold(root: Path | None = None) -> bool:
    """Create `.mirage` folder skeleton safely and idempotently."""
    project_root = (root or find_project_root()).resolve()
    if _is_bad_scaffold_target(project_root):
        return False
    try:
        (project_root / ".mirage").mkdir(parents=True, exist_ok=True)
        (project_root / ".mirage" / "agents").mkdir(parents=True, exist_ok=True)
        (project_root / ".mirage" / "commands").mkdir(parents=True, exist_ok=True)
        (project_root / ".mirage" / "plans").mkdir(parents=True, exist_ok=True)
        (project_root / ".mirage" / "specs").mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False
