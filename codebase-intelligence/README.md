# codebase-intelligence

MCP server plugin for OpenClaude — scan, search, and analyze impact of any project directory.

## Features

- **Hybrid search** — literal search via ripgrep (`rg`) + structural search via ast-grep (`sg`) when available
- **Project scanning** — discover all files, classify by kind (code, config, docs, schema, etc.), build summary
- **Blast radius analysis** — parse import statements, build dependency graph, find direct + transitive dependents
- **Artifact detection** — search docs, specs, schemas, configs, and ADR files by keyword
- **Persistent cache** — scan results cached with fingerprint invalidation
- **Persistent search index** — once `codebase_scan` runs, identifiers are tokenized into a reusable index (`.openclaude/codebase-cache/search-index.json`). Subsequent `codebase_search` calls for identifiers hit the index directly — no ripgrep spawn. Auto-invalidates when the cache fingerprint changes

## Prerequisites

- **Node.js** >= 18
- **ripgrep** (recommended) — for literal search

  ```bash
  # Windows (scoop)
  scoop install ripgrep

  # Windows (winget)
  winget install BurntSushi.ripgrep.MSVC

  # macOS
  brew install ripgrep

  # Linux
  apt install ripgrep    # or pacman -S ripgrep, yum install ripgrep
  ```

- **ast-grep** (optional) — for structural / AST-based search

  ```bash
  # Windows (scoop)
  scoop install ast-grep

  # Windows (npm)
  npm install -g @ast-grep/cli

  # macOS
  brew install ast-grep

  # Linux
  curl -fsSL https://ast-grep.github.io/install.sh | bash
  # or via npm
  npm install -g @ast-grep/cli
  ```

## Installation

### 1. Install plugin files

Clone or copy the `codebase-intelligence` directory into your OpenClaude plugins folder:

```
~/.openclaude/plugins/codebase-intelligence/
```

### 2. Install dependencies

```bash
cd ~/.openclaude/plugins/codebase-intelligence
npm install
```

### 3. Register in OpenClaude

Add to your OpenClaude settings (`.openclaude/settings.json` or via `/settings`):

```json
{
  "mcpServers": {
    "codebase-intelligence": {
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/server.js"]
    }
  }
}
```

Or use the `.mcp.json` file already included in the plugin directory.

### 4. Verify installation

Restart OpenClaude and check that the tools are available:

```
codebase_search, codebase_scan, codebase_status, codebase_context, codebase_impact
```

Run a quick search:

```
codebase_search(cwd: "/path/to/project", query: "TODO")
```

## Available Tools

| Tool | Description |
|------|-------------|
| `codebase_scan` | Full project scan: detect tools, discover files, classify, build summary, persist cache |
| `codebase_status` | Check cache freshness, tool availability, and install recommendations |
| `codebase_search` | Hybrid search across the project (identifier hits via persistent index + literal via rg + structural via ast-grep) |
| `codebase_context` | Search docs/specs/schema/config/ADR artifacts by keyword |
| `codebase_impact` | Blast radius analysis — dependency graph + related tests |

## Windows Notes

### ripgrep spawn hang

On Windows (mingw/bash environments), Node.js `child_process.spawn` with the `cwd`
option can cause ripgrep to hang indefinitely when searching the current directory.
**Fixed in this plugin** by passing the target directory as an explicit path argument
to ripgrep instead of using the `cwd` spawn option.

### ripgrep exit code 2

On Windows, ripgrep may exit with code 2 when it encounters the reserved `nul` device
(`rg: nul: Incorrect function (os error 1)`). This is **not an error** — ripgrep still
returns valid search results on stdout. This plugin accepts exit code 2 when stdout
has content.

## Development

```bash
# Run all tests
npm test

# Run specific test file
node --test tests/test-search.js

# Test search directly
node -e "
const { hybridSearch } = require('./search.js');
hybridSearch('/path/to/project', 'QUERY').then(r => console.log(r));
"
```

### Project structure

```
codebase-intelligence/
├── server.js          # MCP server — stdio transport, tool routing
├── search.js          # Hybrid search (rg + sg) with merge/dedup
├── scanner.js         # Full project scan + cache pipeline
├── impact.js          # Import graph + blast radius analysis
├── artifacts.js       # Keyword search in docs/specs/config
├── diagnostics.js     # Tool detection (rg, sg, mgrep)
├── discovery.js       # File tree walk + classification
├── cache.js           # Persistent cache with fingerprint
├── index.js           # Persistent search index (identifier tokenizer + query)
├── shared.js          # Shared utilities (path helpers, error codes)
└── tests/             # Test suite
    ├── test-search.js
    ├── test-cache.js
    ├── test-discovery.js
    ├── test-integration.js
    ├── test-index.js
    └── test-shared.js
```

## Mode Detection

The plugin operates in one of three modes depending on available tools:

| Mode | Tools | Capability |
|------|-------|------------|
| `hybrid` | rg + ast-grep | Full literal + structural search |
| `literal` | rg only | Regex-based search |
| `degraded` | neither | Fallback — no search, suggestions shown |

## Cache & Persistent Index

The plugin caches scan results and builds a reusable search index inside the project
(`.openclaude/codebase-cache/`) — no external state.

| Aspect | Detail |
|--------|--------|
| **Scan cache** | `.openclaude/codebase-cache/scan-cache.json` — summary + fingerprint |
| **Search index** | `.openclaude/codebase-cache/search-index.json` — identifier → file:line map |
| **Fingerprint** | Git HEAD hash (fallback: file-count hash) |
| **Invalidation** | Cache + index auto-invalidate when the fingerprint changes |
| **Search behavior** | `codebase_search` with a single identifier hits the index (no rg spawn); multi-word / unknown queries fall back to rg + ast-grep |
| **Rebuild** | `codebase_scan(path, force: true)` rebuilds both cache and index |
| **Clear** | Delete the `.openclaude/codebase-cache/` directory in the project |

## Working with codebase-memory-mcp

This plugin can run **alongside** [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)
(DeusData's high-performance code intelligence server) — they complement each other:

| Capability | codebase-intelligence (this plugin) | codebase-memory-mcp |
|---|---|---|
| **Language** | Node.js — zero binary, runs anywhere Node does | Single static C binary (35–37 MB) |
| **Search** | Identifier hits via persistent index + ripgrep literal + ast-grep structural | Tree-sitter AST knowledge graph, 158 languages |
| **Semantic queries** | No AST — regex tokenizer | Hybrid LSP type resolution, call chains, cross-service links |
| **Best for** | Lightweight, zero-dependency, quick searches | Large repos, deep structural queries, dead code, Cypher |
| **Setup** | `npm install` + ripgrep | Download binary (or `npx codebase-memory-mcp --skip-config`) |
| **Tokens** | Aggregated results, moderate savings | ~120× fewer tokens on structural queries |

Use this plugin for fast day-to-day identifier search and status checks, and add
codebase-memory-mcp when a project grows large enough to need AST-level structural
analysis. Both register as MCP servers and coexist in the same agent session.

**Tip:** to evaluate codebase-memory-mcp without touching your agent config, run
`npx codebase-memory-mcp --skip-config` — it starts the server without writing
settings, hooks, or durable instructions.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `codebase_search` returns 0 results | Wrong `cwd` path or rg not installed | Verify path exists and `rg --version` works |
| MCP server not connecting | Plugin not registered in settings | Check `.openclaude/settings.json` or `.mcp.json` config |
| Mode is `degraded` | Neither rg nor ast-grep found | Install ripgrep (see Prerequisites) |
| `sg` command not found | npm global path not in `PATH` | Restart terminal or add npm global bin to PATH |
| Search hangs on Windows | Old plugin version without Windows fix | Update to latest version (passes cwd as arg, not spawn option) |
| Unexpected results | ast-grep `sg` is deprecated | Use `ast-grep` command instead (alias may not work on all systems) |

## Uninstall

```bash
# 1. Remove from OpenClaude settings
# Remove the "codebase-intelligence" entry from mcpServers in settings.json

# 2. Remove plugin files
rm -rf ~/.openclaude/plugins/codebase-intelligence

# 3. (Optional) Clear cache
rm -rf ~/.openclaude/cache/codebase-intelligence/

# 4. (Optional) Uninstall ast-grep
npm uninstall -g @ast-grep/cli
```
