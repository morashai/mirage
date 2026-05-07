# Mirage Parity Matrix

This matrix tracks Mirage CLI/TUI parity behaviors.

## CLI command parity

| Mirage command | Status | Notes |
|---|---|---|
| `mirage` (default TUI) | Implemented | Defaults to chat. |
| `mirage run` | Implemented | Extended flags available (`--session`, `--continue`, `--fork`, `--file`, `--format`, `--title`, `--agent`, `--attach`) with parity validation (`--fork` requires session context), auto session creation, and JSON event output. |
| `mirage models [provider]` | Implemented | Root `models` behavior plus `models list`. |
| `mirage session list/delete` | Implemented | `session` aliases `sessions`; parity extensions include `session list --format json` and `session fork`. |
| `mirage export` / `import` | Implemented | Session export/import commands available. |
| `mirage stats` | Implemented (local) | Local session index stats scaffold. |
| `mirage auth login/list/logout` | Implemented | Uses Mirage provider key config. |
| `mirage mcp list/auth` | Implemented (scaffold) | Lists local MCP descriptor root and auth guidance command. |
| `mirage serve` | Implemented (minimal) | HTTP JSON endpoint for run requests. |
| `mirage web` | Implemented (minimal) | Starts server and opens browser URL. |
| `mirage attach` | Implemented (minimal) | Starts local TUI session in attach compatibility mode. |

## TUI slash parity

| Mirage slash | Status | Notes |
|---|---|---|
| `/help` | Implemented | Existing. |
| `/new` / `/clear` | Implemented | Existing aliases. |
| `/sessions` | Implemented | Existing. |
| `/models` | Implemented | Existing. |
| `/undo` / `/redo` | Implemented | Edit snapshot restore/apply. |
| `/compact` / `/summarize` | Implemented | Writes compaction artifacts under `.mirage/compactions`. |
| `/details` | Implemented | Toggle tool detail display mode. |
| `/thinking` | Implemented | Toggle thinking block visibility state. |
| `/editor` | Implemented | Opens message draft in external editor. |
| `/export` | Implemented | Exports session markdown shell. |
| `/share` / `/unshare` | Implemented (local) | Local share files under `.mirage/shares`. |
| `/themes` | Implemented (list) | Lists available Mirage themes. |
| `/mode` | Implemented | Switches runtime mode (`build`/`plan`) with permission policy updates. |
| `/agent` | Implemented | Selects built-in/custom agent profile via registry (`primary`/`subagent`) and merged permission policy. |

## Config compatibility

| Mirage config surface | Status | Notes |
|---|---|---|
| `mirage.json` project file | Implemented | Read via nearest project-root search and map core fields into runtime defaults. |
| `.mirage/commands/*.md` | Implemented | Loaded as custom slash commands. |
| `.mirage/agents/*.md` | Implemented | Parsed for metadata and used by `/agent` profile switching. |
| env-based config override | Implemented (partial) | Added `MIRAGE_CONFIG_PATH` and `MIRAGE_CONFIG_CONTENT` support. |
| local model state (`recent`/`favorite`/`variant`) | Implemented (partial) | Stored under `~/.mirage/model_state.json`; runtime currently updates recents. |
| project scaffold bootstrap | Implemented | `mirage` auto-creates `.mirage/agents` and `.mirage/commands` in project runs. |

## Non-goals in this pass

- Full remote sharing backend.
- Full Mirage HTTP API surface.
- Plugin installation runtime.
