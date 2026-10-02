---
name: navigating-docs
description: Use when answering questions from a local folder of documents (markdown, PDF, docx) such as Project Knowledge, regulasi, PRD, or spec folders
---

# Navigating Docs

## Overview
Local document folders are searched INDEX-first, not scan-first. Read the 1 KB map before opening any file.

## When to Use
- Question refers to contents of a document folder (`Project Knowledge/<project>`, regulasi, PRD, specs)
- Folder contains markdown plus PDF/docx binaries
- Symptoms: tempted to `Glob **/*`, list hundreds of files, or guess which file holds the answer

When NOT to use: source code questions (use graft/codebase tools instead), single file already known, semantic/conceptual search inside scanned-image PDFs (use vision-ocr on specific pages instead).

## Core Pattern
Wrong: scan folder (`Glob **/*` over 400+ files) → guess a file → read → guess again → verify manually. Burns context, slow, misses PDFs entirely.

Right: INDEX → search → open ≤3 files.
1. `ls <folder>` (one level only) + check `<folder>/INDEX.md`. If INDEX exists, read it and skip to step 3.
2. If no INDEX: run `bash <skill-dir>/scripts/nv-index.sh "<folder>"`, then read the generated INDEX.md.
3. Run `bash <skill-dir>/scripts/nv-search.sh "<folder>" "<keywords>"` to locate matches across md/txt (PDF opt-in, see below).
4. Read only the 1-3 files with hits. Answer with `source: path:line`.

## Quick Reference
| Need | Command |
|---|---|
| Map a project folder | `bash scripts/nv-index.sh "D:/Work/Nusantech/Project Knowledge/<project>"` |
| Keyword search (text, fast <2s) | `bash scripts/nv-search.sh "<folder>" kata1 kata2 kata3` (kata TERPISAH → OR per kata) |
| Include PDFs in search (slow) | append `--pdf` (scans all PDFs ≤20MB; ~40s on 68 files) |
| More hits | append `--max 40` |
| Search one PDF directly | `pdftotext "<file.pdf>" - \| grep -in "kata"` — faster than `--pdf` when INDEX.md already names the file |
| PDF has no text layer (scanned) | vision-ocr tool on that PDF, specific pages |

## Implementation
Scripts live in `scripts/`: `nv-index.sh` (walks folder, extracts H1 titles from md, sizes for pdf/docx, writes INDEX.md), `nv-search.sh` (rg for text by default; `--pdf` adds a pdftotext loop over PDFs ≤20 MB; pandoc loop for docx; lines capped at 300 chars). Requires `rg` in PATH; `pdftotext`/`pandoc` optional (that section skipped if absent). Default is text-only because brute-forcing every PDF on each query costs ~40s versus <2s — prefer naming the 1-2 PDFs from INDEX.md then searching them directly.

## Common Mistakes
| Mistake | Fix |
|---|---|
| `Glob **/*` over whole KB folder | `ls` top level + read INDEX.md |
| Opening .mmd/diagram files for prose answers | Prefer .md with same basename; .mmd is diagram source |
| Assuming PDF is searchable | Check: `pdftotext file.pdf - \| head`; empty = scanned, use vision-ocr |
| Reading entire 70-file regulasi folder | Read `INDEX-REGULASI.md` map first, then 1-2 PDFs |
| Re-embedding whole folder for one question | Incremental: nv-search is stateless, zero background RAM |

## Real-World Impact
nusamedis (447 files, 70 PDFs): baseline agent without skill scanned all files, guessed entry file, 7 tool calls + manual verify. INDEX-first answers same questions with 1 index read + 1 search + ≤3 file reads, <2s, ~1k tokens vs tens of thousands.
