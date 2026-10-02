---
name: slidev
description: Use when creating or editing Slidev developer slide decks, working with slides.md files, or operating the Slidev MCP server and CLI
---

# Slidev

## Overview

Slidev is a Markdown-first slide maker for developers. One `slides.md` becomes an interactive Vue/Vite/UnoCSS deck. Agents drive it via Slidev's built-in MCP server, not raw text edits.

## When to Use

- User asks for a Slidev deck, `slides.md`, or markdown-based developer slides
- Editing, inserting, removing, or reordering slides in a Slidev project
- Exporting to PDF/PPTX/PNG or building a static site
- Keywords: Slidev, `slides.md`, `slidev-get-slide`, `/__mcp`, `slidev export`, `v-click`, magic-move, Monaco, KaTeX, Mermaid

When NOT to use: native `.pptx` binary work without Slidev — use `pptx` skill instead. For zero-dependency single-file HTML decks (no Node/Vite, visual style discovery, PPTX-to-web conversion) — use `frontend-slides` skill instead; see Router below.

## Router: Slidev vs frontend-slides vs pptx

| Need | Skill |
|---|---|
| Markdown `slides.md`, live code (Shiki/Monaco/magic-move), KaTeX/Mermaid, Vue components, `slidev export/build`, MCP-driven edits | This skill (`slidev`) |
| Single self-contained `.html` (no build), style-preview picking, anti-AI-slop presets, PPTX→web conversion via `extract-pptx.py` | `frontend-slides` (supporting files: `STYLE_PRESETS.md`, `html-template.md`, `animation-patterns.md`, `viewport-base.css`, `bold-template-pack/`, `scripts/`) |
| Native `.pptx` binary create/edit/analyze | `pptx` |

Bridge: build the narrative in Slidev, then `slidev export` to PDF/PPTX and hand the file to `frontend-slides` (Mode B: PPT Conversion) or `pptx` for restyling. Or go the other way: prototype the visual direction with `frontend-slides` style previews, then implement it as a Slidev theme/layout.

## MCP Connection (Do This First)

Never reimplement it — Slidev already ships an MCP server.

**Option A — dev server running (preferred, enables `goto-slide` live verify):**

```bash
slidev slides.md --open   # default :3030, endpoint /__mcp
claude mcp add --transport http slidev http://localhost:3030/__mcp
```

Cursor / VS Code (`mcp.json`): `{ "mcpServers": { "slidev": { "type": "http", "url": "http://localhost:3030/__mcp" } } }`

**Option B — no dev server (stdio, edits files directly):**

```json
{ "mcpServers": { "slidev": { "command": "npx", "args": ["slidev", "mcp", "slides.md"] } } }
```

Requires Node.js >= 22.12.0 and `@slidev/cli`. Disable per-deck with `mcp: false` in headmatter.

## MCP Workflow

Slides are addressed by rendered 1-based number.

| Step | Tool | Purpose |
|---|---|---|
| 1 | `slidev-get-info` | Deck overview: title, slide count, files, dev URL |
| 2 | `slidev-list-slides` | Number, title, layout, source file per slide |
| 3 | `slidev-get-slide` | Full source: frontmatter + content + note |
| 4 | `slidev-update-slide` | Edit content, note, and/or frontmatter |
| 5 | `slidev-insert-slide` / `slidev-remove-slide` / `slidev-move-slide` | Insert after N, remove, reorder |
| 6 | `slidev-goto-slide` | Dev-server only: navigate browsers to verify visually |

Edits write back to markdown and hot-reload instantly.

## Quick Reference: Syntax

Separator is `---` with blank lines around it. First YAML block is headmatter (whole deck); rest are per-slide frontmatter. Only the trailing HTML comment is the presenter note.

````md
---
theme: seriph
title: Welcome to Slidev
---
# Slide 1
---
layout: center
class: text-white
---
# Slide 2
Centered layout
<!-- presenter note: trailing comment only -->
````

Headmatter keys: `theme`, `title`, `transition`, `addons`, `fonts`, `mcp`, `drawings`. Per-slide keys: `layout`, `background`, `class`, `transition`, `clicks`, `src`, `hide`.

## Quick Reference: Layouts, Animation, Rich Content

- Layouts: `cover`, `center`, `default`, `image`, `image-left`/`image-right`, `two-cols`, `quote`, `section`, `statement`, `fact`, `intro`, `full`, `none`. Set via `layout:`.
- Clicks: `<v-click>`, `<v-clicks>`, `<v-after>`; `clicks:` frontmatter for max clicks.
- Motion: `motion:` / `v-motion`; page transition via `transition:` (`slide-left`, `fade`).
- Code: fenced blocks (Shiki); `{1,3-5}` highlight, `lines:true`, `monaco` / `monaco-run`, `magic-move`, `<<< @/file#snippet` import.
- Math: `$...$` / `$$...$$` (KaTeX). Diagrams: `mermaid` / `plantuml` blocks. Styling: UnoCSS utilities, `<style scoped>`, Vue components inline.

## Quick Reference: CLI

```bash
slidev slides.md     # dev server
slidev export        # PDF/PPTX/PNG
slidev build         # static SPA
slidev format        # prettier-format slides
slidev mcp slides.md # standalone stdio MCP server
```

New project: `pnpm create slidev` (content starts in `slides.md`).

## Outputs: No Build Required

No — you rarely need `slidev build`. Modes:

- Dev/present directly: `slidev slides.md --open` — present from dev server, no build.
- Share without build: `slidev export` → PDF / PPTX / PNG (Playwright) — send the file, done.
- Only when you need a URL: `slidev build` → static SPA in `dist/` (needs a static host; set `--base` for sub-path).
- Single-file HTML alternative: Slidev has no true single-file HTML export; for one `.html` with no Node/hosting, use the `frontend-slides` skill instead.

## Export Reference (`slidev export`, Playwright-based)

Prerequisite: `playwright-chromium` installed in the project (`pnpm add -D playwright-chromium`). Alternative without CLI: browser exporter UI at `http://localhost:<port>/export` (Chromium-based browsers only) — PDF directly, or slides-as-images → PPTX/zip.

```bash
slidev export                         # PDF → ./slides-export.pdf
slidev export --output deck.pdf       # custom filename (or headmatter exportFilename:)
slidev export --format pptx           # image-per-slide PPTX (text NOT selectable, notes carried over)
slidev export --format pptx-editable  # native-shape PPTX (text selectable/editable; SVG/canvas/iframe/video/KaTeX/gradients/filters stay pictures; per-slide fallback to image export with reason printed)
slidev export --format png            # one PNG per slide
slidev export --format md             # markdown composed of compiled PNGs
slidev export --with-clicks           # one page per click-step (default: clicks collapsed to one page)
slidev export --range 1,6-8,10        # subset of slides
slidev export --dark                  # dark variant of theme
slidev export --timeout 60000 --wait 10000  # big/complex decks; --wait-until networkidle|load|domcontentloaded|none
```

Caveats: interactivity is lost on export (host the built SPA to keep it). PPTX names fonts without embedding them — recipients need the fonts installed. `pptx-editable` text may rewrap vs browser; `::before/::after` decorations and code line-numbers (CSS counters) are dropped. `--per-slide` unsupported with `pptx-editable`.

## Quality: Design, Density, Verification

Slidev default (`theme: default`) looks generic. For non-slop output, lock these before writing slides:

- Theme + tokens: pick one official theme (`seriph`, `apple-basic`, `bricks`, `dracula`, `light`, `dark`) or set `themeConfig:` + `fonts:` in headmatter; define 2-3 CSS vars in `<style>` (bg, ink, accent) and reuse via UnoCSS — never mix per-slide palettes.
- Typography: one display + one body font via `fonts:` headmatter; cover ≤ 8 words, body ≤ 6 bullets; code slides use `two-cols` (code left, explanation right), not walls of text.
- Anti-slop: no purple-gradient-on-white, no Inter/Roboto-as-display, no everything-centered decks; vary layouts (`cover → two-cols → fact → quote → section`), add one signature element (number badge, accent bar, background image).
- Density: ask speaker-led (1 idea/slide, large type, more slides) vs reading-first (self-contained, tables/cards OK); overflow → split slide, never shrink to cram. Borrow density rules from `frontend-slides` skill.
- Style inspiration: adapt palettes from `../frontend-slides/STYLE_PRESETS.md` (Bold Signal, Dark Botanical, Swiss Modern, etc.) into Slidev `themeConfig`/UnoCSS — don't copy HTML, translate tokens.
- Verify loop: after MCP edits, `slidev-goto-slide` per changed slide → screenshot at 1280×720 → fix overflow/contrast → `slidev export` (PDF/PNG) for final QA. For high-stakes decks, run repo skills `design-review` (browser audit) and `no-ai-slop` / `frontend-design` (de-slop pass).
- Accessibility: min ~24px body on stage, 4.5:1 contrast, `prefers-reduced-motion`-safe transitions (`fade` over flashy), alt text on `image` layouts.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Hand-editing while dev MCP is live | Use `get-info → list → get → update/insert/move → goto` |
| `---` without blank lines | Separator needs blank line before/after |
| First block treated as per-slide | First block is headmatter (whole deck) |
| Mid-slide comment expected as note | Only trailing comment is the note |
| `goto-slide` without dev server | Start `slidev slides.md` first, or use stdio mode |
| Rebuilding Slidev as a plugin | Don't — connect to built-in MCP |

## Sources

- https://sli.dev/guide/work-with-ai — https://sli.dev/features/mcp — https://sli.dev/guide/syntax — https://sli.dev/llms.txt
