# Install Documents Reader Plugin

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

### Step 2: Verify uv is in PATH

The installer puts `uv.exe`/`uvx.exe` in `%USERPROFILE%\.local\bin` and adds it to your user PATH **automatically**.

Open a **NEW terminal** and verify:

```bash
uv --version
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
openclaude plugin install documents-reader@local-plugins
```

Then run `/reload-plugins` in your OpenClaude session.

## Tools

| Tool | Description |
|---|---|
| `read_document` | Read any supported document (PDF, DOCX, Excel, TXT) |
| `read_pdf` | Extract text from PDF files |
| `read_docx` | Extract text from Word documents |
| `read_excel` | Extract data from Excel spreadsheets |
| `read_txt` | Read plain text files |

## Usage

Just ask Claude to read a document file:
- "Baca file report.pdf"
- "Extract data dari data.xlsx"
- "Read this Word document"
