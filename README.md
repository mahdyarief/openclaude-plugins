# OpenClaude Plugins

Plugin marketplace for [OpenClaude](https://github.com/Gitlawb/openclaude) — MCP server plugins, a hooks-only plugin, and a skill for building your own.

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
| [productivity-hooks](./productivity-hooks) | none (hooks only) | none | PostToolUse productivity hooks — output-distiller (collapse noisy command output) + adhd-mode (focus tracking) |
| [office-mcp](./office-mcp) | 47 tools: read/write/edit/format/export docx, xlsx, pptx | Python `mcp[cli]`, `python-docx`, `openpyxl`, `python-pptx`, `mammoth`, `xlsxwriter` | Word/Excel/PowerPoint document management via LibreOffice |
| [scispace](./scispace) | `search_papers`, `scispace_login`, `scispace_status` | `playwright` (npm) | SciSpace literature search via headless Playwright using a logged-in premium session |

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
openclaude plugin install productivity-hooks@<marketplace-name>
openclaude plugin install office-mcp@<marketplace-name>
openclaude plugin install scispace@<marketplace-name>
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

## Office Skills (docx / xlsx / pptx / office-pdf)

Office document manipulation skills from [tfriedel/claude-office-skills](https://github.com/tfriedel/claude-office-skills) — copy these folders to `~/.openclaude/skills/` (or use the copy-mapping below):

| Skill | Purpose |
|---|---|
| [docx](./skills/docx) | Create/edit .docx documents — tracked changes, comments, formatting preservation, text extraction |
| [xlsx](./skills/xlsx) | Create/edit .xlsx spreadsheets — formulas, formatting, data analysis, visualization |
| [pptx](./skills/pptx) | Create/edit .pptx presentations — slides, layouts, themes |
| [office-pdf](./skills/office-pdf) | PDF manipulation — extract text/tables, merge/split, fill forms (renamed from `pdf` to avoid conflict with the `pdf` generation skill) |

> Note: the `pdf` skill from the upstream repo is shipped here as `office-pdf` because a `pdf` skill (PDF generation) already exists in the default skill set — renaming avoids the name conflict.
- Covers: plugin structure, `.mcp.json` / `plugin.json` templates, MCP server patterns (SDK vs manual JSON-RPC), local registration, critical gotchas (cache sync, stale process kill, NODE_PATH, pandoc verbatim headers, binary version checks), GitHub publishing, common mistakes.

## Anti-AI-Slop Frontend / UI-UX Skills

Curated set of open-source skills that stop AI coding tools from generating generic "AI slop" frontends (Inter everywhere, purple→blue gradients, cream backgrounds, grey low-contrast text, pill badges above heroes, three icon cards in a row, em-dash copy, fade-up-on-scroll). Install into the OpenClaude skills directory (`C:\Users\Lenovo\.openclaude\skills\` on Windows / `~/.openclaude/skills/` elsewhere). Format is identical to Claude Code: each skill is a folder with `SKILL.md` (+ optional `references/`, `TELLS.md`, etc.). Skills auto-load; no plugin registration needed.

### Quick install (all 8 sources)

```bash
# 1. Clone each repo into a temp dir
mkdir -p /tmp/skill-install && cd /tmp/skill-install
git clone --depth 1 https://github.com/Leonxlnx/taste-skill.git
git clone --depth 1 https://github.com/Nutlope/hallmark.git
git clone --depth 1 https://github.com/claudiusararu/unslop-ui-skill.git
git clone --depth 1 https://github.com/LucasSantana-Dev/repaint.git
git clone --depth 1 https://github.com/funboy322/avoid-ai-design.git
git clone --depth 1 https://github.com/gral-digital/frontend-skill.git
git clone --depth 1 https://github.com/Laith0003/ux-skill.git
git clone --depth 1 https://github.com/AslanMazhidov/design-review-skill.git
```

### What to copy where

| Source repo | Copy this | → into `skills/<name>/` |
|---|---|---|
| `Leonxlnx/taste-skill` | `skills/<subskill>/` for each of the 13 sub-skills | rename folder to the `name:` field in `SKILL.md` frontmatter (e.g. `taste-skill` → `design-taste-frontend`) |
| `Nutlope/hallmark` | `skills/hallmark/` (SKILL.md + references/) | `hallmark/` |
| `claudiusararu/unslop-ui-skill` | `.claude/skills/no-ai-slop/` **+ root `TELLS.md`** (referenced by SKILL.md) | `no-ai-slop/` |
| `LucasSantana-Dev/repaint` | `SKILL.md` + `references/` + `evals/` + `docs/` | `repaint/` |
| `funboy322/avoid-ai-design` | `SKILL.md` + `references/` + `docs/` | `avoid-ai-design/` |
| `AslanMazhidov/design-review-skill` | `SKILL.md` | `design-review/` |
| `gral-digital/frontend-skill` | `commands/` (18 playbooks) + `reference/` (8 files) + a thin wrapper `SKILL.md` (see below) | `frontend-design/` |
| `Laith0003/ux-skill` | `commands/` (25 playbooks) + `agents/` (5 sub-agents) + a thin wrapper `SKILL.md` | `ux-skill/` |

**Wrapper SKILL.md for `frontend-design` and `ux-skill`** — these repos ship Claude Code *slash-command* files, not `SKILL.md` skills. Create a minimal orchestrator so OpenClaude detects them:

```markdown
---
name: frontend-design
description: Frontend design engineering system — 18 specialized design command playbooks plus an 8-file reference library. Read the commands/ folder for the full playbooks.
---
# Frontend Design
Orchestrator for the 18 command playbooks in `commands/` (typography, layout, color, motion, responsive, UX writing, audit, ...) and 8 reference files in `reference/`.
```

```markdown
---
name: ux-skill
description: Design intelligence engine — deterministic anti-AI-slop linter, 25 ux-* command playbooks, 5 sub-agents. Read the commands/ folder for the playbook to apply.
---
# ux-skill
25 command playbooks in `commands/` + 5 sub-agent definitions in `agents/`. Python engine: `pip install uxskill`.
```

### Taste Skill sub-skills (13) and their folder names

The `npx skills add` install name equals the `name:` frontmatter, not the folder name:

`taste-skill`→`design-taste-frontend` · `taste-skill-v1`→`design-taste-frontend-v1` · `gpt-tasteskill`→`gpt-taste` · `image-to-code-skill`→`image-to-code` · `redesign-skill`→`redesign-existing-projects` · `soft-skill`→`high-end-visual-design` · `minimalist-skill`→`minimalist-ui` · `brutalist-skill`→`industrial-brutalist-ui` · `output-skill`→`full-output-enforcement` · `stitch-skill`→`stitch-design-taste` · `imagegen-frontend-web` · `imagegen-frontend-mobile` · `brandkit`

### ux-skill Python engine (optional)

```bash
pip install uxskill
```

The PyPI package is an older build (2.0.0a1) whose module is named `engine` (not `uxskill`). The CLI (`uxskill` / `ux`) is **not** on PATH — invoke via full path:
`"C:/Users/Lenovo/AppData/Roaming/Python/Python313/Scripts/uxskill.exe"` (adjust for your Python version).

### design-review dependency: Playwright MCP

`design-review` needs `@playwright/mcp` for real-browser screenshots (desktop/tablet/mobile) and visual audits:

```bash
claude mcp add playwright -- npx -y @playwright/mcp@latest
```

### Synergy map (no conflicts — all names unique)

| Phase | Skills |
|---|---|
| **Build** (new UI) | `design-taste-frontend`, `hallmark`, `repaint`, `ux-skill`, `frontend-design` |
| **Redesign / audit** | `redesign-existing-projects`, `avoid-ai-design`, `no-ai-slop`, `scrutinio` (in frontend-design) |
| **Visual review** | `design-review` (Playwright screenshots) |
| **Style directions** | `minimalist-ui`, `industrial-brutalist-ui`, `high-end-visual-design`, `gpt-taste` |
| **Image/asset generation** | `imagegen-frontend-web`, `imagegen-frontend-mobile`, `brandkit`, `image-to-code` |

All names are unique and none collide with the bundled superpowers skills (`design-critique`, `brainstorming`, etc.).

### Update user-level CLAUDE.md (make sessions aware of these skills)

Installing the skills alone is not enough — the model must know they exist and when to use them. Add a section to the **user-level global CLAUDE.md** (`C:\Users\Lenovo\.openclaude\CLAUDE.md` on Windows, `~/.openclaude/CLAUDE.md` elsewhere) so every session loads this knowledge automatically.

1. Open the global CLAUDE.md file:
   ```bash
   notepad "C:\Users\Lenovo\.openclaude\CLAUDE.md"   # Windows
   # or
   $EDITOR ~/.openclaude/CLAUDE.md                   # Linux/macOS
   ```
2. Append the following section (adjust paths if your Python version differs):

```markdown
## 🎨 Anti-AI-Slop Frontend / UI-UX Skills (WAJIB dipakai)

Sebelum mengerjakan frontend/UI-UX, cek skill anti-slop yang tersedia. JANGAN generate UI generik (Inter, purple-blue gradient, cream bg, pill badge, 3 icon cards, em-dash copy, fade-up-on-scroll).

| Fase | Skill yang dipakai |
|---|---|
| Build UI baru | `design-taste-frontend`, `hallmark`, `repaint`, `ux-skill`, `frontend-design` |
| Redesign / audit | `redesign-existing-projects`, `avoid-ai-design`, `no-ai-slop`, `scrutinio` (frontend-design) |
| Review visual | `design-review` (butuh Playwright MCP — `claude mcp add playwright -- npx -y @playwright/mcp@latest`) |
| Style direction | `minimalist-ui`, `industrial-brutalist-ui`, `high-end-visual-design`, `gpt-taste` |
| Image/asset gen | `imagegen-frontend-web`, `imagegen-frontend-mobile`, `brandkit`, `image-to-code` |

**ux-skill CLI** (engine Python `uxskill` v2.0.0a1, module `engine`) — TIDAK di PATH, panggil via:
`"C:/Users/Lenovo/AppData/Roaming/Python/Python313/Scripts/uxskill.exe"` (contoh: `.../uxskill.exe lint .`)

**Alur kerja:** saat build → invoke skill build (design-taste-frontend/hallmark/repaint) → setelah selesai jalankan audit (avoid-ai-design / no-ai-slop) → tawarkan review visual (design-review) jika relevan.
```

3. Simpan. Skill & instruksi ini otomatis terbaca di setiap session baru (restart session jika sedang berjalan).

**Catatan:** Jangan meng-copy instruksi ini ke CLAUDE.md project — cukup di user level, agar berlaku global di semua project.

## License

MIT
