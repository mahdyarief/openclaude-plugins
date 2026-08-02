---
name: plugin-creator
description: Use when building a new plugin for OpenClaude or Claude Code — MCP server plugins, marketplace packaging, or debugging plugins that don't reload (edits not taking effect after /reload-plugins, stale server processes, missing tools after restart)
---

# Plugin Creator

## Overview

A plugin is a directory with MCP server code + 2 config files, published via a marketplace. Users install with `openclaude plugin install <name>@<marketplace>`.

## When to Use

- Building a new MCP-based plugin
- Converting a local MCP server (`local-mcp/`) into a publishable plugin
- Debugging a plugin whose changes don't take effect after `/reload-plugins`
- Preparing a plugin folder for GitHub publishing

## Plugin Structure

```
plugins/<name>/
├── .claude-plugin/plugin.json   # metadata (REQUIRED)
├── .mcp.json                     # MCP server config (REQUIRED)
├── server.js                     # MCP server entry
├── lib/                          # optional: logic modules
├── package.json                  # deps (if any)
└── node_modules/                 # installed deps
```

## Key Files

### .claude-plugin/plugin.json

```json
{
  "name": "my-plugin",
  "description": "What it does + tools it exposes",
  "version": "1.0.0",
  "keywords": ["mcp", "..."],
  "author": { "name": "You" }
}
```

### .mcp.json

```json
{
  "my-plugin": {
    "command": "node",
    "args": ["${CLAUDE_PLUGIN_ROOT}/server.js"],
    "env": { "KEY": "value" }
  }
}
```

`${CLAUDE_PLUGIN_ROOT}` resolves to the plugin directory — always use it, never absolute paths.

Top-level key MUST be the plugin name. Do NOT wrap in `"mcpServers": {...}` — OpenClaude's plugin loader reads the plugin name as the top-level key, so a `mcpServers` wrapper will not register the server.

### server.js — two working patterns

**MCP SDK** (`@modelcontextprotocol/sdk`): Server + StdioServerTransport + CallToolRequestSchema/ListToolsRequestSchema. Use when you have npm deps anyway.

**Manual JSON-RPC** (no deps): read stdin lines, respond to `initialize` / `tools/list` / `tools/call` with JSON lines on stdout. Simpler for dependency-free servers (all built-in node).

## Registration (local plugin)

1. Add entry to `plugins/.claude-plugin/marketplace.json`:
   `{ "name": "<name>", "source": "./<name>", "description": "...", "category": "development" }`
2. Add `"<name>@local-plugins": true` to `enabledPlugins` in `~/.openclaude/settings.json`
3. Sync to cache (see Gotcha #1)
4. User runs `/reload-plugins`

## Critical Gotchas

### 1. CLI loads from the CACHE, not your source folder

`plugins/cache/local-plugins/<name>/<version>/` is what actually runs. Editing `plugins/<name>/` does nothing until you sync:

```bash
cp -r plugins/<name>/. plugins/cache/local-plugins/<name>/<version>/
```

This is the #1 cause of "I fixed it but it still fails".

### 2. /reload-plugins does NOT kill running server processes

Old server processes keep serving stale code. After a fix + reload, if it still fails: find and kill the old process.

```bash
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*<name>*" }
taskkill //PID <pid> //F
```

Then `/reload-plugins` again to respawn from the fixed files.

### 3. Tool names become long

`mcp__plugin_<name>_<name>__<tool>` — by design. Users call tools with this full name.

### 4. Subprocess scripts can't find plugin node_modules

If server.js spawns `node someScriptInTempDir.js` that `require("puppeteer")` — resolution is relative to the script location, not the plugin. Fix: pass `env: { ...process.env, NODE_PATH: <plugin>/node_modules }` to the child process.

### 5. --include-in-header is VERBATIM (pandoc)

Content is inserted raw, NOT processed as a pandoc template. `$if(...)$`, `${""}` become literal `$` → LaTeX errors. Keep header files pure LaTeX/CSS.

### 6. Verify the actual binary version

`execFile("pandoc")` on Windows resolves differently from bash `pandoc` (npm shims). Check with `node -e "require('child_process').execFile('pandoc',['--version'],(e,s)=>console.log(s))"` — pandoc 3.x removed `--latex-engine` (use `--pdf-engine`).

## Publishing to GitHub

1. Repo root = marketplace root: put plugin subdirectories + a root-level `.claude-plugin/marketplace.json` with `"source": "./<name>"` relative entries
2. Add README.md with install:
   ```
   openclaude plugin marketplace add https://github.com/<you>/<repo>
   openclaude plugin install <name>@<repo>
   ```
3. Push. Users install from anywhere.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Edited source, reloaded, still old behavior | Sync to cache first (Gotcha #1) |
| Killed nothing, reloaded twice, still failing | Kill stale server process (Gotcha #2) |
| Used pandoc template syntax in header | Keep verbatim (Gotcha #5) |
| Assumed bash `pandoc` == what server runs | Check via node execFile (Gotcha #6) |
| Wrote absolute paths in .mcp.json | Use ${CLAUDE_PLUGIN_ROOT} |
