# OpenClaude Plugins

Plugin marketplace for [OpenClaude](https://github.com/Gitlawb/openclaude) — MCP server plugins and a skill for building your own.

## Prerequisites

All plugins run on **Windows** and **Linux/Ubuntu**.

- **Node.js 18+** (tested on v25) — required for all plugins
- **Python 3.6+** — only for `markdown-preview` PNG and `vision-ocr`

### markdown-preview (PDF)

- **pandoc 3.x** (with `--pdf-engine` support)
- **LaTeX engine** (MiKTeX on Windows / TeX Live on Linux)
- Fonts: **Times New Roman, Arial, Courier New** on Windows; **Liberation Serif, Liberation Sans, DejaVu Sans Mono** on Linux (usually preinstalled, or `sudo apt install fonts-liberation fonts-dejavu`)

### markdown-preview (PNG)

- **Python 3.6+** with `pip install DrissionPage`
- A **Chrome or Edge** browser already installed (DrissionPage connects via CDP — no browser download)

### vision-ocr

- **Python 3.6+** with `pip install rapidocr-onnxruntime pymupdf Pillow numpy`

Check: `node --version`, `python --version`, `pandoc --version`.

## Plugins

| Plugin | Tools | Deps | Description |
|---|---|---|---|
| [markdown-preview](./markdown-preview) | `markdown_to_pdf`, `markdown_to_html`, `markdown_to_png` | `@modelcontextprotocol/sdk` + pandoc/LaTeX + Python `DrissionPage` + Chrome/Edge | Markdown → PDF/HTML/PNG via pandoc + LaTeX + DrissionPage |
| [context7](./context7) | `ctx7_resolve_library`, `ctx7_query_docs`, `ctx7_add_key`, `ctx7_remove_key`, `ctx7_list_keys`, `ctx7_set_strategy`, `ctx7_set_limit`, `ctx7_reset_stats`, `ctx7_current_key` | none | Library documentation lookup with API key rotation |
| [web-access](./web-access) | `web_search`, `web_get_contents`, `github_search`, `web_search_exa` | none | Web search, URL fetching, GitHub search |
| [vision-ocr](./vision-ocr) | `vision-ocr` | `@modelcontextprotocol/sdk` + Python `rapidocr-onnxruntime`, `pymupdf`, `Pillow`, `numpy` | Extract text from images/PDFs (RapidOCR, CPU) |
| [codebase-intelligence](./codebase-intelligence) | `codebase_scan`, `codebase_search`, `codebase_context`, `codebase_impact`, `codebase_status` | `@modelcontextprotocol/sdk` | Codebase analysis (local, no LLM dependency) |

## Install

```bash
# 1. Add the marketplace (user scope = all your projects)
openclaude plugin marketplace add https://github.com/<you>/openclaude-plugins

# 2. Install plugins with dependencies
openclaude plugin install markdown-preview@<marketplace-name>
openclaude plugin install context7@<marketplace-name>
openclaude plugin install web-access@<marketplace-name>
openclaude plugin install vision-ocr@<marketplace-name>
openclaude plugin install codebase-intelligence@<marketplace-name>
```

**After installing, run `/reload-plugins` inside OpenClaude.**
MCP tools are exposed as `mcp__plugin_<plugin>_<plugin>__<tool>`.

### System dependencies per OS

#### Windows

```bash
# 1. Node.js: https://nodejs.org (or: winget install OpenJS.NodeJS.LTS)
# 2. Python: https://www.python.org/downloads/ (check "Add to PATH")
#    Or: winget install Python.Python.3.13
# 3. pandoc: https://pandoc.org/installing.html (or: winget install JohnMacFarlane.Pandoc)
# 4. LaTeX (MiKTeX): https://miktex.org/download (needed for markdown_to_pdf)
# 5. Python packages (needed for markdown_to_png + vision-ocr):
python -m pip install DrissionPage rapidocr-onnxruntime pymupdf Pillow numpy
```

MiKTeX will auto-install missing packages on first PDF run (needs an internet connection).

#### Ubuntu / Linux

```bash
# 1. Node.js
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs

# 2. Python + pandoc + LaTeX + fonts
sudo apt update
sudo apt install -y python3 python3-pip pandoc texlive-xetex \
  fonts-liberation fonts-dejavu

# 3. Python packages (needed for markdown_to_png + vision-ocr)
python3 -m pip install DrissionPage rapidocr-onnxruntime pymupdf Pillow numpy
```

Note: on Linux the plugin auto-detects `python3` (the `python` command may not exist).
The PDF preamble uses **Liberation/DejaVu** fonts, which the packages above install.

### If tools fail to load (missing deps)

If a plugin server crashes with `Cannot find module '@modelcontextprotocol/sdk'`, install its npm dependencies manually from inside the plugin directory:

```bash
cd ~/.openclaude/plugins/markdown-preview   # or vision-ocr, codebase-intelligence
npm install
```

Then `/reload-plugins` again.

## Skill: plugin-creator

Build your own plugins with the included skill:

- Path: `skills/plugin-creator/SKILL.md`
- Copy it to `~/.openclaude/skills/plugin-creator/` (or install via this marketplace) to make it available in every session.
- Covers: plugin structure, `.mcp.json` / `plugin.json` templates, MCP server patterns (SDK vs manual JSON-RPC), local registration, critical gotchas (cache sync, stale process kill, NODE_PATH, pandoc verbatim headers, binary version checks), GitHub publishing, common mistakes.

## License

MIT
