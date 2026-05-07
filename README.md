# MIRAGE  CLI

Mirage is an open-source coding agent CLI, similar in spirit to Claude-style terminal agents, built on top of **LangChain** and **LangGraph**.


It runs a 3-agent product team:
- `ProjectManager` (planning, read-only)
- `UXUIDesigner` (UI/UX specification, read-only)
- `Developer` (the only code-writing agent)

The interface is themed as **MIRAGE** (Jordanian military palette + aviation styling), but the core is a practical autonomous coding workflow.

---

## Features

- Multi-agent orchestration via LangGraph supervisor routing
- Interactive chat mode with a bordered prompt input box
- Non-interactive single-task mode
- Thread-aware memory (via LangGraph checkpointer)
- Slash commands for session control (`/help`, `/thread`, `/model`, etc.)
- Installable package with console scripts:
  - `mirage`
  - `mirage-cli`

---

## Requirements

- Python `>=3.11`
- An OpenAI-compatible API key in environment:
  - `OPENAI_API_KEY`

Optional tools:
- `uv` (recommended for fast dependency management)
- `pipx` or `uvx` (for isolated CLI execution)

---

## Project layout

```text
.
├─ main.py                  # Backward-compatible shim
├─ pyproject.toml
├─ scratch_test.py          # smoke tests
└─ src/
   ├─ __main__.py           # supports python -m and uv run .\src\
   ├─ config.py
   ├─ theme.py
   ├─ tools/
   │  └─ filesystem.py
   ├─ agents/
   │  ├─ prompts.py
   │  ├─ state.py
   │  ├─ supervisor.py
   │  ├─ graph.py
   │  └─ ...
   └─ cli/
      ├─ app.py
      ├─ session.py
      ├─ input_box.py
      └─ render.py
```

---

## Quick start (recommended: uv)

```bash
# from repo root
uv pip install -e . --python ".venv/Scripts/python.exe"
```

Set your API key:

```bash
# PowerShell
$env:OPENAI_API_KEY="your-key-here"
```

Run:

```bash
mirage --help
mirage chat
```

---

## Installation options

### 1) pip (from source)

```bash
python -m pip install -e .
```

Then:

```bash
mirage --help
```

### 2) uv (from source)

```bash
uv pip install -e . --python ".venv/Scripts/python.exe"
```

Then:

```bash
mirage --help
```

### 3) pipx (isolated CLI install)

```bash
pipx install .
```

Then:

```bash
mirage --help
```

### 4) uvx (ephemeral run)

```bash
uvx --from . mirage --help
uvx --from . mirage chat
```

---

## Running without installing

You can still run from source directly:

```bash
python -m src --help
python main.py --help
uv run .\src\ --help
```

> Note: `uv run mirage` with no subcommand will show "Missing command."  
Use `mirage chat` or `mirage run "task"`.

---

## CLI usage

### Interactive mode

```bash
mirage chat
```

Options:
- `--thread-id TEXT` (optional; auto-generated if omitted)
- `--model TEXT` (defaults to `MIRAGE_CLI_MODEL` env or fallback model)

Example:

```bash
mirage chat --model gpt-4o
```

### One-shot mode

```bash
mirage run "build a hello world FastAPI app"
```

Options:
- `--thread-id TEXT` (default: `multi-agent-session-1`)
- `--model TEXT`

---

## Slash commands (inside chat)

- `/help` — show command help
- `/clear` — clear terminal and repaint welcome panel
- `/reset` — create a new thread id
- `/thread [id]` — show or switch active thread
- `/model [name]` — show or switch model (rebuilds graph)
- `/exit`, `/quit` — exit

---

## Configuration

`src/config.py` loads environment via `python-dotenv`.

Supported env vars:

- `OPENAI_API_KEY` — required for model calls
- `MIRAGE_CLI_MODEL` — default model for commands (default in code)
- `MIRAGE_CLI_RECURSION_LIMIT` — LangGraph recursion limit (default: `75`)

PowerShell example:

```bash
$env:OPENAI_API_KEY="..."
$env:MIRAGE_CLI_MODEL="gpt-4o"
$env:MIRAGE_CLI_RECURSION_LIMIT="75"
```

---

## Packaging details

`pyproject.toml` includes:

- Build backend: `setuptools.build_meta`
- Distribution name: `mirage-cli`
- Console scripts:
  - `mirage = "src.cli.app:main"`
  - `mirage-cli = "src.cli.app:main"`

This enables installation via `pip`, `uv`, `pipx`, and execution through `uvx --from .`.

---

## Development workflow

Install editable:

```bash
uv pip install -e . --python ".venv/Scripts/python.exe"
```

Run smoke tests:

```bash
python scratch_test.py
```

The smoke suite validates:
- prompt input behavior (`Enter`, `Esc+Enter`, `Ctrl+D`)
- slash command handling
- graph topology (`ProjectManager`, `UXUIDesigner`, `Developer`, `supervisor`)
- no executor / no HITL artifacts
- autonomous handoff flow

---

## Troubleshooting

### `ImportError: attempted relative import with no known parent package`

Use one of:

```bash
python -m src
uv run .\src\
mirage chat
```

`src/__main__.py` contains fallback import handling for script-style execution.

### `No module named pip` in `.venv`

Use `uv` instead:

```bash
uv pip install -e . --python ".venv/Scripts/python.exe"
```

### `pipx` not found

Install `pipx` first, or use `uvx`:

```bash
uvx --from . mirage --help
```

### `Missing command` when running `mirage`

This is expected without a subcommand. Use:

```bash
mirage chat
# or
mirage run "your task"
```

---

## License

This project is open source and licensed under the **MIT License**.