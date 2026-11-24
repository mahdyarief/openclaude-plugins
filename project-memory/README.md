# Project Memory Plugin

Persistent project memory via MEMORY.md files. Store, search, and incrementally update project knowledge across sessions.

## Prerequisites

This plugin requires `uvx` (part of `uv` Python package manager) to be installed and available in your system PATH.

### Install `uv`

**Windows (PowerShell):**
```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Via pip:**
```bash
pip install uv
```

After installation, restart your terminal or reload your shell to ensure `uvx` is in PATH.

Verify with:
```bash
uvx --version
```

## Install Plugin

```bash
openclaude plugin install project-memory@mahdyarief
```

## Tools

| Tool | Description |
|---|---|
| `get_project_memory` | Read MEMORY.md (`head_only=True` for a size + section TOC; `offset`/`limit` for chunks) |
| `search_project_memory` | Find memories by substring with line numbers |
| `update_project_memory` | Incremental update via one SEARCH/REPLACE block (preferred) |
| `set_project_memory` | Full write — for new files or complete rewrites |

## How It Works

- Memories are stored in `MEMORY.md` at the project root
- A `SessionStart` hook auto-creates the file (with a section scaffold) when a
  project has none, then injects a bounded digest (line/byte count + headings) —
  never the whole file, so context cost stays small
- Auto-create only runs in directories that look like a project (`.git`,
  `package.json`, `pyproject.toml`, `CLAUDE.md`, `.trail`, …) and never in the
  home directory; disable with `PROJECT_MEMORY_AUTOCREATE=0`
- Incremental updates via SEARCH/REPLACE patches (no full rewrites)
- Size limit: 20K tokens per memory file

## Troubleshooting

- **`FileNotFoundError … MEMORY.md`** — the file did not exist. The hook creates
  it on the next session start; to create it immediately, call
  `set_project_memory` with a starter document.
- **`PermissionError … not in allowed directories`** — the server only accepts
  paths under the directory it was started in (the session project). Start the
  session in that project, or pass the session project's own path.
