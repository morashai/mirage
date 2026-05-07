# MIRAGE  CLI

Mirage is an open-source coding agent CLI, similar in spirit to Claude-style terminal agents, built on top of **LangChain** and **LangGraph**.

![Mirage CLI preview](./image.png)


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
- Deduplicated Claude-style core toolset for filesystem, shell, search, git, web, notebook, and MCP descriptor discovery
- Installable package with console scripts:
  - `mirage`
  - `mirage-cli`

---

## Tool catalog (core)

Mirage now ships a canonical, deduplicated core tool registry under `src/tools/`.

- **Read-only tools** (ProjectManager + UXUIDesigner):
  - filesystem: `list_directory`, `read_file`
  - search: `glob_search`, `ripgrep_search`
  - git: `git_status`, `git_diff`, `git_log`, `git_current_branch`
  - web: `web_fetch`, `web_search`
  - notebook: `read_notebook`
  - mcp descriptors: `list_mcp_servers`, `list_mcp_tools`, `read_mcp_tool_schema`
- **Developer-only extras**:
  - filesystem write: `write_file`, `edit_file`
  - execution: `run_shell_command`
  - notebook edit: `edit_notebook_cell`
  - MCP call placeholder: `call_mcp_tool`

Deduplication is enforced at startup. If duplicate tool ids are exported, Mirage fails fast.

Intentionally skipped in this pass:
- team/task orchestration-style tooling
- scheduling/cron and remote-trigger style tooling

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
   │  ├─ catalog.py
   │  ├─ filesystem.py
   │  ├─ shell.py
   │  ├─ search.py
   │  ├─ git_tools.py
   │  ├─ web_tools.py
   │  ├─ notebook_tools.py
   │  └─ mcp_tools.py
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

### `ModuleNotFoundError: No module named 'src'` when running `mirage`

This usually means the `mirage` launcher on your `PATH` was created by a
different Python environment than the one where you installed this project.

Reinstall with the same interpreter you use to run `mirage`:

```bash
python -m pip uninstall -y mirage-cli
python -m pip install -e .
python -m mirage_cli
```

If `python` points to a different version than your launcher, use the exact
interpreter explicitly (for example `py -3.13 -m pip install -e .`).

---

## License

This project is open source and licensed under the **MIT License**.