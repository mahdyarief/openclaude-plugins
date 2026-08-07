# office-mcp

> **MCP server for managing Word, Excel, and PowerPoint documents via stdio JSON-RPC.**

`office-mcp` is a [Model Context Protocol](https://modelcontextprotocol.io/)
server written in Python that lets an MCP-compatible agent (Claude
Desktop, MCP Inspector, a custom agent) **read, write, edit, format,
and export** modern Microsoft Office files (`.docx`, `.xlsx`,
`.pptx`) over the standard `stdio` JSON-RPC transport.

The server is **stateless**: every `tools/call` opens the file,
performs the operation, saves, and returns. There is no in-memory
cache, no background thread, and no database.

* **47 tools** across four modules (4 unprefixed general tools
  + 14 Word + 15 Excel + 14 PowerPoint tools).
* **PDF / HTML / CSV export** for every supported format.
  `docx → html` is pure-Python (via `mammoth`); everything else
  uses LibreOffice headless.
* **Cross-platform** — Windows, macOS, Linux. The codebase never
  shells out; LibreOffice is invoked as a subprocess with argument
  lists.
* **UTF-8 end-to-end** with explicit
  `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` so non-ASCII content
  survives every tool call.

## Table of contents

* [Install](#install)
* [Quick start](#quick-start)
* [Claude Desktop registration](#claude-desktop-registration)
* [The 47 tools](#the-47-tools)
* [Usage examples](#usage-examples)
* [Architecture overview](#architecture-overview)
* [Configuration](#configuration)
* [Troubleshooting](#troubleshooting)
* [Development commands](#development-commands)
* [License](#license)

## Install

### 1. Requirements

* **Python 3.10+** (tested on 3.12). The pre-built virtual
  environment in `.venv/` already targets 3.12.
* **LibreOffice 7+** for `*.pdf` and `.xlsx` / `.pptx → .html`
  export. The classic install paths are auto-detected; on Windows
  the installer places `soffice.exe` at
  `C:\Program Files\LibreOffice\program\soffice.exe`. The
  `headless` mode used by `office-mcp` does not require a display
  or a running LibreOffice instance.
* All Python dependencies are listed in `pyproject.toml` and
  pre-installed in `.venv/`: `mcp[cli]>=1.27,<2`, `python-docx`,
  `openpyxl`, `python-pptx`, `xlsxwriter`, `mammoth`, `defusedxml`,
  `pydantic`. The optional `Pillow` is used for sample
  image generation only.

### 2. One-time setup

`init.sh` is idempotent: it sets the right environment variables,
adds LibreOffice to `PATH`, activates the venv, and verifies every
required Python package. Run it once from the project root
**in a Bash-compatible shell** (Git Bash, WSL, or `bash` on
macOS / Linux):

```bash
bash init.sh
```

What it does:

1. `export PYTHONUTF8=1` and `export PYTHONIOENCODING=utf-8` so
   Unicode survives every subprocess boundary.
2. Prepends the LibreOffice program directory to `PATH` (no
   effect if it is already there).
3. Activates `.venv/` (`Scripts/activate` on Windows,
   `bin/activate` elsewhere). If `.venv/` is missing it
   bootstraps a fresh one.
4. Imports every required package and prints a confirmation line.
5. Prints `soffice --version` (or a warning if LibreOffice is
   missing — export tools will then raise
   `ERR_LIBREOFFICE_MISSING` at call time, not at server start).

If you do not want to source `init.sh`, set the same variables
manually before launching the server:

```bash
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export PATH="/c/Program Files/LibreOffice/program:$PATH"   # Windows Git Bash
.venv/Scripts/python.exe server.py
```

### 3. Re-install / re-provision the venv (optional)

```bash
# from the project root
.venv/Scripts/python.exe -m pip install -e .
```

The `.[dev]` extra pulls in `pytest`, `pytest-asyncio`, and
`pyflakes`.

## Quick start

```bash
# 1. Activate venv + set encoding + add LibreOffice to PATH
bash init.sh

# 2. Launch the server (talks JSON-RPC on stdio)
python server.py
```

The server prints nothing on success — it owns stdin/stdout for
the JSON-RPC stream. All diagnostic output goes to `stderr`. To
see the negotiated session, run the server under the MCP
Inspector:

```bash
.venv/Scripts/python.exe -m mcp.cli inspector server.py
```

To verify the server from a clean shell **without** an agent,
use the manual smoke test:

```bash
# Spawns the server over stdio, runs `initialize` + `tools/list`,
# prints the registered tool count, and exits.
.venv/Scripts/python.exe smoke_server.py
```

Expected last line: `OK  initialize -> tools/list  (47 tools)`.

## Claude Desktop registration

Add the following to your `claude_desktop_config.json`. On
Windows the file lives at
`%APPDATA%\Claude\claude_desktop_config.json`; on macOS at
`~/Library/Application Support/Claude/claude_desktop_config.json`.

```json
{
  "mcpServers": {
    "office-mcp": {
      "command": "python",
      "args": ["E:/PROJECT FILE/Dengan Hati/PROJECT IDEA/office-mcp/server.py"],
      "env": {
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "OFFICE_MCP_DEFAULT_FOLDER": "E:/Documents"
      }
    }
  }
}
```

Notes:

* `args[0]` must be the **absolute path** to `server.py` for your
  checkout. The forward slashes in the example work on Windows;
  use backslashes only if you escape them.
* `OFFICE_MCP_DEFAULT_FOLDER` is the directory the server will
  resolve **relative** file paths against. Any tool that accepts
  a `folder` argument overrides this default for that call.
* If you prefer the venv's Python, set `command` to the full path
  (e.g. `E:/PROJECT FILE/Dengan Hati/PROJECT IDEA/office-mcp/.venv/Scripts/python.exe`)
  — both work because the venv already has the server's
  dependencies on its `sys.path`.
* Restart Claude Desktop after editing the config so it re-reads
  the file.

## The 47 tools

`architecture.md` §3 is the authoritative description; the table
below is the index. Format-specific tools are prefixed
(`word_*`, `excel_*`, `pptx_*`); the four general tools have no
prefix.

### General (4)

| Tool                | Purpose                                                              |
|---------------------|----------------------------------------------------------------------|
| `list_documents`    | Non-recursive folder scan; returns one entry per `.docx`/`.xlsx`/`.pptx`. |
| `get_document_info` | Auto-detect format by extension; dispatch to the format-specific `*_get_info`. |
| `search_text`       | Cross-format text search with locations `paragraph:N` / `cell:<coord>` / `slide:N:shape:M`. |
| `convert_document`  | Dispatch to the right exporter based on source extension and `target_format` (`pdf` / `html` / `csv`). |

### Word (15)

| Tool                     | Purpose                                              |
|--------------------------|------------------------------------------------------|
| `word_create_document`   | Create a new `.docx`, optionally with a title.       |
| `word_get_info`          | Counts of paragraphs / sections / tables / images + core properties. |
| `word_list_paragraphs`   | All paragraphs with index, style, text, runs.        |
| `word_read_paragraph`    | One paragraph by index.                              |
| `word_add_paragraph`     | Append a paragraph (optional style).                 |
| `word_add_heading`       | Append a heading at a level (1-9).                   |
| `word_find_replace`      | Find and replace text (case-sensitive toggle).       |
| `word_format_run`        | Update a run's bold / italic / size / font / color.  |
| `word_add_table`         | Append a table (rows × cols, optional data + style). |
| `word_add_image`         | Embed an image (optional width_inches).              |
| `word_add_header`        | Set the text of a section's header.                  |
| `word_add_footer`        | Set the text of a section's footer.                  |
| `word_set_section`       | Configure a section's orientation + page size.       |
| `word_export_pdf`        | Convert a `.docx` to PDF via LibreOffice.            |
| `word_export_html`       | Convert a `.docx` to HTML via `mammoth`.             |

### Excel (14)

| Tool                     | Purpose                                              |
|--------------------------|------------------------------------------------------|
| `excel_create_workbook`  | Create a new `.xlsx` (optionally with a custom sheet name). |
| `excel_get_info`         | Sheet count + names + per-sheet dimensions.          |
| `excel_list_sheets`      | Names + indices + dimensions of all sheets.         |
| `excel_read_sheet`       | Read a sheet (or an `A1:C3`-style range) as a 2-D list. |
| `excel_write_cell`       | Write a single cell (string, number, or `=formula`). |
| `excel_write_range`      | Write a 2-D list of values starting at a cell.       |
| `excel_create_sheet`     | Append a new sheet.                                  |
| `excel_delete_sheet`     | Remove a sheet (refuse to delete the last).          |
| `excel_rename_sheet`     | Rename a sheet (refuse duplicates).                  |
| `excel_format_cells`     | Apply font / fill / border / number-format to a range. |
| `excel_add_chart`        | Add a `bar` / `line` / `pie` / `area` / `scatter` chart. |
| `excel_export_csv`       | Export a sheet to CSV (pure Python).                 |
| `excel_export_pdf`       | Export a workbook to PDF via LibreOffice.            |
| `excel_export_html`      | Export a workbook to HTML via LibreOffice.           |

### PowerPoint (14)

| Tool                        | Purpose                                              |
|-----------------------------|------------------------------------------------------|
| `pptx_create_presentation`  | Create a new `.pptx` with an optional title slide.   |
| `pptx_get_info`             | Slide count + layouts + slide dimensions.            |
| `pptx_list_slides`          | All slides with index, title, layout, shape count.   |
| `pptx_read_slide`           | One slide's title + shapes.                          |
| `pptx_add_slide`            | Add a slide (layout index, optional title).          |
| `pptx_delete_slide`         | Remove a slide (refuse to delete the last).           |
| `pptx_reorder_slides`       | Move a slide to a new index (move, not swap).        |
| `pptx_add_text_box`         | Add a text box (x / y / w / h in inches, optional font). |
| `pptx_add_image`            | Embed an image (x / y / w / h).                      |
| `pptx_add_shape`            | Add an MSO shape (type, x / y / w / h, optional text). |
| `pptx_add_table`            | Add a table (rows / cols / data, x / y / w / h).     |
| `pptx_add_chart`            | Add a chart (type, data dict, x / y / w / h).        |
| `pptx_export_pdf`           | Export to PDF via LibreOffice.                       |
| `pptx_export_html`          | Export to HTML via LibreOffice.                      |

## Usage examples

Each example assumes the server is registered with your MCP
agent (see [Claude Desktop registration](#claude-desktop-registration))
or that you are calling the tool functions directly from Python
(via `mcp._tool_manager._tools["..."].fn`).

### General tools

A typical agent workflow starts with a folder scan: ask the
agent to "list the Office files in `~/Documents`". The
`list_documents` tool returns one entry per file with its type
(`word` / `excel` / `pptx`), its on-disk size, and an ISO-8601
`modified` timestamp. The agent can then dispatch per-file
operations. `get_document_info` is the next step: it returns
format-specific metadata (paragraphs / sections for Word,
sheet count and dimensions for Excel, slide count and layouts
for PowerPoint) so the agent can plan a sequence of edits
without opening the file. `search_text` is the cross-format
text search — give it a substring and it returns every
paragraph, cell, or shape that contains the match, with a
small surrounding context window. `convert_document` is the
end-of-pipeline tool: pass the source path and
`target_format` (`"pdf"`, `"html"`, or `"csv"` for Excel only)
and an optional `output` path; the output lands next to the
source if you omit `output`.

### Word tools

`word_create_document` is the typical entry point. Pass a
`path` (absolute or relative to `folder` / the default folder)
and an optional `title`; the tool refuses to overwrite an
existing file (`ERR_INVALID_PARAMS`) so it is safe to re-call
on a fresh scratch path. Once a document exists the agent can
chain `word_add_heading`, `word_add_paragraph`, and
`word_add_table` to build the body; `word_format_run` then
applies bold / italic / font / size / color to a specific run
in a specific paragraph (the contract is that an all-`None`
call is a true no-op — the file SHA256 is preserved).
`word_find_replace` is the bulk-edit hammer: pass `find`,
`replace`, and `case_sensitive`; the tool returns the total
replacement count and rewrites the file in place.
`word_add_image` accepts PNG / JPEG / GIF / TIFF and either
embeds the picture at its native size or scales it to
`width_inches` (aspect ratio is preserved automatically).
`word_add_header` / `word_add_footer` / `word_set_section`
configure the section-level metadata; `word_set_section`
takes `"portrait"` or `"landscape"` and a page size
(`"A4"`, `"Letter"`, `"Legal"`, `"A5"`, `"Tabloid"`, `"B5"`).
Finally, `word_export_pdf` and `word_export_html` produce the
deliverable: the first uses LibreOffice, the second uses the
pure-Python `mammoth` library so it works even on a machine
without LibreOffice installed.

### Excel tools

`excel_create_workbook` returns the absolute path of a new
`.xlsx` with a single default sheet (`"Sheet1"`) — pass
`sheet_name` to use something more descriptive from the start.
`excel_write_cell` is the small-scale writer: it accepts
strings, numbers, and `"=...`" formulas; the cell reference
is parsed by the helper that also powers `excel_write_range`
so `"A1"`, `"B2"`, `"AA10"` all work, and malformed refs
raise `ERR_CELL_PARSE` (-32008). For bulk writes use
`excel_write_range` with `start_cell` and a 2-D `data` list
in row-major order. `excel_create_sheet` / `excel_delete_sheet`
/ `excel_rename_sheet` manage the workbook's sheet list;
`excel_delete_sheet` refuses to remove the only remaining
sheet. `excel_format_cells` applies font / fill / border /
number-format to a range (the `range` argument accepts the
same `"A1:C3"` syntax as `excel_read_sheet`).
`excel_add_chart` writes an `openpyxl` chart of type `bar`,
`line`, `pie`, `area`, or `scatter` anchored at `target_cell`
— a typical call looks like
`excel_add_chart(path, sheet, "bar", "A1:B5", "D2", "Sales")`.
`excel_export_csv` is pure-Python (no LibreOffice needed) and
exports a single sheet; `excel_export_pdf` and
`excel_export_html` go through LibreOffice for fidelity with
what the user sees in Excel.

### PowerPoint tools

`pptx_create_presentation` lays down a `.pptx` with one
title slide (configurable via `title` / `subtitle`). Add
slides with `pptx_add_slide(layout_index=..., title=...)`;
the default layouts are `0` (Title Slide), `1` (Title and
Content), `5` (Title Only), `6` (Blank). `pptx_delete_slide`
and `pptx_reorder_slides` let the agent reshape the deck
(`pptx_reorder_slides` is a *move*, not a swap).
`pptx_add_text_box` and `pptx_add_shape` are the simple
shape writers — both take x / y / w / h in inches. For
data, `pptx_add_table` writes a rows × cols table at a
given position, and `pptx_add_chart` writes a chart with a
Python dict payload (categories + series). All
`pptx_export_*` tools delegate to LibreOffice.

## Architecture overview

The full design is in `architecture.md`. The 30-second version:

```
+--------------------+        stdio JSON-RPC        +--------------------+
|   MCP agent        |  <----------------------->   |   office-mcp       |
|  (Claude Desktop)  |  initialize / tools/list    |   (Python process) |
|  or custom client  |  tools/call {name, args}    |                    |
+--------------------+                              |  FastMCP("office-  |
                                                   |  mcp") + 47 tools  |
                                                   +---------+----------+
                                                             |
                                              subprocess (PDF / HTML / CSV)
                                                             |
                                                   +---------v----------+
                                                   |  LibreOffice 7+    |
                                                   |  (soffice)         |
                                                   +--------------------+
```

Module layout:

```
office-mcp/
├── server.py                # FastMCP entry; mcp singleton; tool registration
└── office_mcp/
    ├── config.py            # OFFICE_MCP_DEFAULT_FOLDER + find_libreoffice()
    ├── paths.py             # resolve_path(file, folder) -> absolute Path
    ├── errors.py            # OfficeMCPError + 9 error codes (-32001..-32009)
    ├── general_tools.py     # list_documents, get_document_info, search_text, convert_document
    ├── word_tools.py        # 14 word_* tools
    ├── excel_tools.py       # 15 excel_* tools
    ├── pptx_tools.py        # 14 pptx_* tools
    └── exporters.py         # export_to_pdf / export_to_html / export_to_csv
```

Critical idioms (also enforced by the test suite):

* **Singleton via `from server import mcp`.** Every tool function
  is decorated with `@mcp.tool()` from `mcp.server.fastmcp`,
  imported as `from server import mcp`. This works because
  `server.py` registers itself under both `__main__` and `server`
  in `sys.modules` via `sys.modules.setdefault("server",
  sys.modules[__name__])` at module top. Do not remove that line.
* **Side-effect imports in `server.py` use `importlib.import_module`.**
  This avoids `pyflakes` F401 false positives on the tool module
  side-effect imports.
* **No `print()` to stdout.** All logging goes to `sys.stderr`
  (configured at the top of `server.py`).
* **Office files are ZIPs** — open in binary mode
  (`"rb"`/`"wb"`). Text files (HTML, CSV, README) with
  `encoding="utf-8"`.
* **`*_create_*` tools refuse to overwrite.** All other tools
  raise `ERR_FILE_NOT_FOUND` (-32001) if the target does not
  exist.
* **Error model.** Every tool raises `OfficeMCPError(code,
  message, details)`. FastMCP serialises the exception to a
  `CallToolResult` with `isError=True` and a `structuredContent`
  dict carrying the error code. The JSON-RPC error code stays
  clean.

## Configuration

| Env var                     | Default                       | Effect                                              |
|-----------------------------|-------------------------------|-----------------------------------------------------|
| `OFFICE_MCP_DEFAULT_FOLDER` | server CWD                    | Base folder for relative paths in tool calls.       |
| `OFFICE_MCP_SOFFICE`        | auto-detected                 | Override the LibreOffice executable path.           |
| `PYTHONUTF8`                | unset                         | Set to `1` to enable UTF-8 mode in the interpreter.  |
| `PYTHONIOENCODING`          | unset                         | Set to `utf-8` so `sys.stdin` / `sys.stdout` are UTF-8. |

Set these in `claude_desktop_config.json` (see
[Claude Desktop registration](#claude-desktop-registration)) or
in the shell before launching the server.

## Troubleshooting

### "LibreOffice (soffice) is not installed or not on PATH"

`ERR_LIBREOFFICE_MISSING` (-32006) is raised on any export that
needs LibreOffice — every `*_export_pdf`, every
`excel_export_html`, and every `pptx_export_html` call. Word's
`word_export_html` does **not** need LibreOffice (it uses
`mammoth`).

1. **Install LibreOffice.** On Windows, use the official MSI
   (`soffice.exe` lands in
   `C:\Program Files\LibreOffice\program`). On macOS, drag the
   `.dmg` to `/Applications`. On Debian / Ubuntu:
   `sudo apt install libreoffice`.
2. **Check the executable.** `init.sh` prints
   `soffice: LibreOffice ...` when the binary is found. If it
   prints `WARNING: soffice not on PATH`, either re-run
   `init.sh` or set `OFFICE_MCP_SOFFICE=/full/path/to/soffice(.exe)`
   in the agent config.
3. **Watch out for the Windows `.COM` shim.** `shutil.which`
   on Windows can return `soffice.COM` (a 16-bit DOS wrapper)
   when the LibreOffice `program` directory is on `PATH` but
   not in the auto-detect candidate list. `find_libreoffice()`
   in `office_mcp/config.py` explicitly prefers the
   `.exe` candidates and rejects `.COM` files. If you see the
   server hang for the full 180s timeout before raising
   `ERR_EXPORT_FAILED`, you are probably hitting this — set
   `OFFICE_MCP_SOFFICE` to the absolute `soffice.exe` path.
4. **Concurrent calls.** Each `*_export_*` call uses a unique
   `-env:UserInstallation=file:///<tempdir>` so two simultaneous
   exports do not fight over the default profile. You can run
   `word_export_pdf` in parallel from two different agent
   sessions without locking.

### Encoding issues (mojibake, `UnicodeDecodeError`)

* Always launch the server with `PYTHONUTF8=1` and
  `PYTHONIOENCODING=utf-8` in the env. `init.sh` does this for
  the local shell; the Claude Desktop config snippet above sets
  them in the `env` block.
* Office files are **ZIPs** — the tools always open them in
  binary mode, so non-ASCII content is preserved end-to-end.
* If you see mojibake only in tool output (not on disk), the
  most likely cause is the agent or its console not running in
  UTF-8. Set `PYTHONIOENCODING=utf-8` in the server's `env`.
* If you see mojibake on disk, the source file was probably
  written by an older tool that did not declare UTF-8. The
  server cannot retroactively fix it.

### "File is locked" / "Permission denied" on save

* `ERR_FILE_LOCKED` (-32002) means the file is open in Word /
  Excel / PowerPoint (or another process holds an exclusive
  handle). Close the file in the Office app and re-call the
  tool. Office writes lock files (`.~lock.<name>#`) next to the
  document; if the previous run crashed you can delete the
  lock file by hand.
* If you are running the server in a sandboxed agent, make
  sure the agent's filesystem permissions include write
  access to the file and its containing directory.
* Antivirus software occasionally holds a write lock for a few
  seconds after Word closes. If the failure is intermittent,
  wait a second and retry.

### Server starts but the agent sees 0 tools

This means the `sys.modules.setdefault("server",
sys.modules[__name__])` line in `server.py` is missing, or
`server.py` was launched in a way that bypasses the FastMCP
singleton. **Do not edit that line.** Verify it is present and
re-launch. The same fix applies if you ever see the second
`FastMCP` instance warning in the logs.

### Server hangs without producing output

* Confirm the agent is talking JSON-RPC and not raw bytes —
  the server owns stdin/stdout and will not echo any prompt.
* Confirm `PYTHONIOENCODING=utf-8` is set. Without it, the
  interpreter may try to re-encode the JSON-RPC stream and
  fail silently.
* Check the server's `stderr` (the agent usually surfaces
  this). A clean start produces a single INFO line for the
  session negotiation and nothing else.

### Excel "file is corrupt" / openpyxl warnings

* `openpyxl` writes a warning when a workbook contains
  features it does not preserve (some pivot tables, some
  VBA macros). The server still saves the file but the
  warning is in `stderr`. Reopening the file in Excel
  succeeds because Excel ignores the missing optional
  features; the warning is informational only.

## Development commands

All commands assume the project root as the current directory
and the venv on `PATH` (or the explicit `.venv/Scripts/python.exe`
prefix shown). The single source of truth is `services.yaml`.

```bash
# Run the full pytest suite (≈100 tests, sequential, no -n).
.venv/Scripts/python.exe -m pytest -q

# Run tests for a single module.
.venv/Scripts/python.exe -m pytest tests/test_word_core.py -q
.venv/Scripts/python.exe -m pytest tests/test_excel_advanced.py -q

# Run the cross-format integration test (spawns the server
# over stdio and exercises the agent round-trip).
.venv/Scripts/python.exe -m pytest tests/test_integration.py -v

# Smoke check: import the singleton and report the tool count.
.venv/Scripts/python.exe -c "from server import mcp; print(mcp.name, len(mcp._tool_manager._tools))"

# Type check (syntax + import resolution for every .py file).
.venv/Scripts/python.exe -m py_compile server.py office_mcp/*.py

# Lint with pyflakes (suppress the import side-effect noise).
.venv/Scripts/python.exe -m pyflakes office_mcp server.py

# Manually launch the server from a clean shell (talks
# JSON-RPC on stdio; press Ctrl+C to exit).
python server.py

# Manually launch via the MCP Inspector for an interactive UI.
.venv/Scripts/python.exe -m mcp.cli inspector server.py
```

The `services.yaml` file at the project root pins the exact
command strings (Windows PowerShell) used by the per-milestone
scrutiny validator; if you add a new test entry point, add it
there too.

## License

MIT. See `pyproject.toml` for the canonical metadata.
