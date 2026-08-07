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
openclaude plugin install project-memory@local-plugins
```

Then run `/reload-plugins` in your OpenClaude session.

## Usage

The plugin automatically reads your project's `MEMORY.md` file at the start of each session. You can also use these tools:

- `memory_save` - Save a new memory
- `memory_update` - Update existing memory
- `memory_search` - Search memories by keyword
- `memory_read` - Read full memory file
- `memory_dream` - Consolidate and clean up memories
