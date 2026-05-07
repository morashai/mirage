"""Notebook read/edit tools."""
from __future__ import annotations

import json
from pathlib import Path

from langchain_core.tools import tool


@tool
def read_notebook(filepath: str) -> str:
    """Read a notebook and summarize its cells."""
    try:
        path = Path(filepath)
        data = json.loads(path.read_text(encoding="utf-8"))
        cells = data.get("cells", [])
        summary_lines = [f"cells={len(cells)}"]
        for idx, cell in enumerate(cells[:200]):
            cell_type = cell.get("cell_type", "unknown")
            source = "".join(cell.get("source", []))
            preview = source.replace("\n", " ")[:100]
            summary_lines.append(f"{idx}: {cell_type} | {preview}")
        return "\n".join(summary_lines)
    except Exception as exc:
        return f"Error: {exc}"


@tool
def edit_notebook_cell(
    filepath: str,
    cell_index: int,
    old_text: str,
    new_text: str,
) -> str:
    """Replace text in one notebook cell source."""
    try:
        path = Path(filepath)
        data = json.loads(path.read_text(encoding="utf-8"))
        cells = data.get("cells", [])
        if cell_index < 0 or cell_index >= len(cells):
            return f"Error: cell_index {cell_index} out of range."

        source = "".join(cells[cell_index].get("source", []))
        if old_text not in source:
            return "Error: old_text not found in selected cell."

        updated = source.replace(old_text, new_text)
        cells[cell_index]["source"] = updated.splitlines(keepends=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return f"Successfully updated cell {cell_index} in {filepath}"
    except Exception as exc:
        return f"Error: {exc}"

