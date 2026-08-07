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
openclaude plugin install project-memory@local-plugins
```

## Tools

| Tool | Description |
|---|---|
| `save` | Store a new memory in project MEMORY.md |
| `update` | Incrementally update existing memory via SEARCH/REPLACE |
| `search` | Find memories by substring with line numbers |
| `read` | Full read of memory file with line numbers |
| `dream` | Consolidate, deduplicate, and clean up memories |

## How It Works

- Memories are stored in `MEMORY.md` files in your project directory
- Auto-read hook loads memory on first prompt of each session
- Incremental updates via SEARCH/REPLACE patches (no full rewrites)
- Dream consolidation auto-cleans when file exceeds 50KB
- Size limit: 20K tokens per memory file
