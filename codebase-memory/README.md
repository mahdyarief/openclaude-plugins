# codebase-memory

OpenClaude plugin that bundles [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) v0.10.2 — a high-performance code intelligence MCP server written in C. It indexes codebases into a persistent knowledge graph (158 languages, sub-ms structural queries, 99% fewer tokens) and ships as a single static binary with zero dependencies.

## What it provides

15 MCP tools for structural code discovery and codebase intelligence:

| Tool | Purpose |
|---|---|
| `index_repository` | Index a repository into the knowledge graph (full / moderate / fast / cross-repo-intelligence modes) |
| `search_graph` | Find symbols and definitions via the knowledge graph |
| `trace_path` | Trace callers and callees of a symbol |
| `get_code_snippet` | Fetch exact source for a symbol or line range |
| `query_graph` | Cypher-style multi-hop graph queries |
| `get_architecture` | High-level architecture orientation for a repo |
| `index_status` | Index health, freshness, and per-run logfile |
| `list_projects` | List indexed projects |
| `search_code` | Literal / non-code text search |
| `check_index_coverage` | Verify coverage for cited paths and scopes |
| ... and more | dead code detection, dependencies, and graph utilities |

## Install

```bash
openclaude plugin marketplace add <this-repo>
openclaude plugin install codebase-memory@local-plugins
```

Or enable locally by adding `"codebase-memory@local-plugins": true` to `enabledPlugins` in `~/.openclaude/settings.json`, then `/reload-plugins`.

## Setup

The 282 MB Windows binary is too large for GitHub's 100 MB per-file limit, so it is NOT committed to this repo. Fetch it once with the install script (downloads from the upstream release, verifies SHA-256 against `checksums.txt`, then extracts to `bin/`):

```powershell
powershell -ExecutionPolicy Bypass -File codebase-memory/install-binary.ps1
```

The script is idempotent — it skips the download if `bin/codebase-memory-mcp.exe` already exists.

## How it works

`.mcp.json` launches `bin/codebase-memory-mcp.exe` directly over stdio — no Node runtime, no npm deps, no compilation.

## Configuration

Optional environment variables (set in `.mcp.json` → `env` if needed):

- `CBM_CACHE_DIR` — cache/index location (default `~/.cache/codebase-memory-mcp`)
- `CBM_ALLOWED_ROOT` — restrict which root directories the server may index
- `CBM_LOG_LEVEL` — logging verbosity (debug/info/warn/error)

Per-project ignore rules: add a `.cbmignore` file in the repository root. See [docs/cbmignore.md](https://github.com/DeusData/codebase-memory-mcp/blob/main/docs/cbmignore.md).

## First use

1. `list_projects` — see what is already indexed
2. `index_repository` with `repo_path` — index a repo (mode `fast` for speed, `full` for semantic edges)
3. `search_graph` / `trace_path` / `get_code_snippet` — structural discovery
4. Watched projects auto-refresh in the background after external changes

## Updating the binary

1. Delete `bin/codebase-memory-mcp.exe` and re-run `install-binary.ps1` to fetch the latest release
2. Bump `version` in `.claude-plugin/plugin.json` and `package.json` per the plugin-creator workflow

## License

MIT (upstream binary). Bundled `LICENSE` and `THIRD_PARTY_NOTICES.md` in `bin/`.
