# navigating-docs

INDEX-first local document navigation for OpenClaude — fast, zero-RAM keyword search across markdown, PDF, DOCX, and XLSX without heavy vector databases.

## What it does

Teaches the agent a 3-step pattern for answering questions from document folders (Project Knowledge, regulasi, PRD, specs):

1. **INDEX** — read the 1 KB structural map (`INDEX.md`) instead of scanning hundreds of files
2. **Search** — keyword search across md/txt/pdf/docx with one script call
3. **Open ≤3 files** — read only the files with hits, answer with `source: path:line`

## Bundled skill

The plugin bundles the `navigating-docs` skill plus two bash helper scripts:

| Script | Purpose |
|---|---|
| `skills/navigating-docs/scripts/nv-index.sh "<folder>"` | Walks a folder, extracts H1 titles from `.md`, sizes for pdf/docx/xlsx, writes `<folder>/INDEX.md` |
| `skills/navigating-docs/scripts/nv-search.sh "<folder>" kata1 kata2` | `rg` for text by default (<2 s) + `pandoc` loop for docx. Words are OR-ed; a `"quoted phrase"` is treated as a literal phrase. Append `--pdf` to also scan PDFs ≤20 MB via `pdftotext` (slow: ~40 s on 68 files — prefer `pdftotext "<file.pdf>" - \| grep -in "kata"` on 1-2 files named by INDEX.md). Output `path:line:text` capped at 300 chars/line |

## Prerequisites

- **ripgrep (`rg`)** in PATH — required for text search. Check: `rg --version`
- **poppler-utils (`pdftotext`)** — optional, enables PDF search (that section is skipped if absent)
- **pandoc** — optional, enables DOCX search (that section is skipped if absent)

## Usage

```bash
# 1. Build the map (once per project folder)
bash skills/navigating-docs/scripts/nv-index.sh "D:/Work/Nusantech/Project Knowledge/<project>"

# 2. Search (words are OR-ed per word)
bash skills/navigating-docs/scripts/nv-search.sh "<folder>" nusamedis asal usul

# 3. More hits
bash skills/navigating-docs/scripts/nv-search.sh "<folder>" klaim bpjs --max 40
```

## When NOT to use

- Source code questions → use graft/codebase tools instead
- Semantic/conceptual search inside scanned-image PDFs → use vision-ocr on specific pages
- The answer file is already known → just read it

## Provenance

Built and TDD-tested on a real 447-file / 70-PDF knowledge base (nusamedis): baseline agent without the skill scanned all files (7+ tool calls + manual verify); INDEX-first answers the same questions with 1 index read + 1 search + ≤3 file reads, <2 s, ~1 k tokens vs tens of thousands.
