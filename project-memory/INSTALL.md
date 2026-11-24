# Install Project Memory Plugin

## Prerequisites

This plugin requires `uv` (Python package manager) to be installed **and available in your system PATH**.

### Step 1: Install uv

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

### Step 2: Verify uvx is in PATH

The installer puts `uv.exe`/`uvx.exe` in `%USERPROFILE%\.local\bin` and adds it to your user PATH **automatically**.

Open a **NEW terminal** and verify:

```bash
uvx --version
```

If it fails with "command not found", add the path manually:

**Windows (PowerShell):**
```powershell
[Environment]::SetEnvironmentVariable("Path", "$env:USERPROFILE\.local\bin;" + [Environment]::GetEnvironmentVariable("Path", "User"), "User")
```

**macOS / Linux (add to ~/.bashrc or ~/.zshrc):**
```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then restart your terminal.

### Step 3: Restart OpenClaude

Close and reopen OpenClaude **after** uv is in PATH — OpenClaude reads PATH only when it starts. This is the #1 cause of "plugin fails to load but uv is installed".

### Step 4: Install Plugin

```bash
openclaude plugin install project-memory@mahdyarief
```

Then run `/reload-plugins` in your OpenClaude session.

## Usage

At the start of each session the `SessionStart` hook checks the project root for
`MEMORY.md`. If it is missing, the hook creates it with a section scaffold
(Architecture & Why, Conventions, Gotchas, Key files, Recent Sessions) and tells
the session it was created. If it exists, the hook injects a short digest — line
and byte counts plus section headings — so the agent knows what is available
without loading the whole file.

Then use these MCP tools (all take `project_path`):

- `get_project_memory` - Read the file; `head_only=True` for TOC, `offset`/`limit` for chunks
- `search_project_memory` - Search by substring with line numbers
- `update_project_memory` - Patch via one SEARCH/REPLACE block (preferred)
- `set_project_memory` - Full write, for new files or complete rewrites

### Opting out of auto-create

```bash
set PROJECT_MEMORY_AUTOCREATE=0   # Windows: setx PROJECT_MEMORY_AUTOCREATE 0
```

Auto-create never runs in the home directory or in folders without a project
marker (`.git`, `package.json`, `pyproject.toml`, `CLAUDE.md`, `.trail`, …).

### Troubleshooting

- **`FileNotFoundError … MEMORY.md`** — the file did not exist. The hook creates
  it on the next session start; to create it now, call `set_project_memory`.
- **`PermissionError … not in allowed directories`** — the server accepts only
  paths under the directory it was started in (the session project). Start the
  session in that project.
