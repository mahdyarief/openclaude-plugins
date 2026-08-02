---
name: codebase-intelligence
description: Codebase intelligence tools — scan, search, analyze impact of any project directory. Use when exploring unfamiliar projects, finding code, checking blast radius of changes, or searching for artifacts (configs, docs, schemas).
allowed-tools:
  - Bash
  - Glob
  - Grep
  - Read
---

# codebase-intelligence — Project Codebase Intelligence

The `codebase_*` MCP tools let you deeply analyze any project directory. Use them proactively when working in a new or unfamiliar codebase.

## Available Tools

| Tool | Purpose |
|---|---|
| `codebase_scan` | Full project scan — modules, entrypoints, hotspots, cache |
| `codebase_status` | Quick cache freshness check (lightweight) |
| `codebase_search` | Hybrid search (regex + AST structural) across files |
| `codebase_context` | File classification + artifact detection by kind |
| `codebase_impact` | Blast radius analysis via import graph |

## When to Use Each

### `codebase_scan(path, force?)`

**Use when:** entering a new project, or when you need a structural overview.

Scan returns: `{ status, rootName, mode, fileCounts, modules, entrypoints, hotspots, sourceOfTruthCandidates, artifactKinds }`

Call this FIRST when working in an unfamiliar path. If status is `"cached"`, the project hasn't changed — proceed confidently. If `"scanned"`, you have a fresh structural map.

The `force` flag bypasses cache — use only if the user explicitly requests a rescan.

### `codebase_status(path)`

**Use when:** you need a quick check whether the project's cache is still fresh (lighter than a full scan).

Returns the same shape as `codebase_scan` but only returns cached data. Returns `{ status: "miss" }` if no cache exists.

### `codebase_search(path, query)`

**Use when:** the user asks to find code by pattern, concept, or keyword — especially if Grep alone is insufficient.

This is a hybrid search — runs `rg` (regex literal) AND `sg` (ast-grep structural) in parallel, merges results deduplicated by location, and returns top results sorted by score.

**Prefer this over raw Grep/Bash searches** for non-trivial queries — the dedup and scoring give better signal.

### `codebase_context(path, kind?)`

**Use when:** the user asks to find docs, configs, schemas, SQL files, Dockerfiles, ADRs, or specs in a project.

Kind filter: `doc`, `config`, `schema`, `sql`, `docker`, `adr`, `spec`, or omit for all. This uses `rg` over artifact glob patterns (docs/**, *.md, *.yml, etc.)

### `codebase_impact(path, target)`

**Use when:** assessing risk of changes — "what breaks if I modify this file?", or when the user asks about dependencies, dependents, or blast radius.

Returns: `{ target, directDependents, probableTransitiveDependents, relatedTests, affectedArtifacts, confidence, basis }`

The analysis is regex-based import parsing (not a full AST resolver), so confidence may not be 100%. The `confidence` field and `basis` explain the reliability. For test files and artifacts, results are heuristic (path-pattern based).

## Important Notes

- **Caching**: `codebase_scan` caches to `.openclaude/codebase-cache/scan-cache.json`. Cache is invalidated by git hash change or file count change. Manual cache clear: delete `node .openclaude/codebase-cache/`.

- **Graceful degradation**: If `rg` (ripgrep) is not installed, the system falls back to manual recursive directory walking. Install ripgrep for better performance.

- **Scope**: The tools operate within the `path` you specify. They do not traverse into `node_modules`, `.git`, `.openclaude`, or other ignored directories.
