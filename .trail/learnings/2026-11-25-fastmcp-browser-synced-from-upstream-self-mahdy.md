---
title: "fastmcp-browser synced from upstream, self-building"
author: Mahdy
date: 2026-11-25
branch: main
id: l-d4a14dfb
scope: repo
status: active
src: agent
touches:
  - fastmcp-browser/.mcp.json
---

fastmcp-browser/ is a copy of upstream rayss868/fastmcp-browser, not our own code. Update it only with scripts/sync-fastmcp-browser.mjs (or the weekly sync workflow), never by hand-editing upstream files: the script wipes fastmcp-browser/ and keeps only .claude-plugin/, .mcp.json and launch.mjs (plus local server/dist and node_modules). Why launch.mjs exists: upstream .gitignore excludes server/dist, so before this change a marketplace install had no built server and only worked on machines where someone built it by hand inside the plugin cache. launch.mjs builds on first run and rebuilds when plugin.json version changes (stamp in server/dist/.plugin-version); it must log to stderr only because stdout is the MCP stdio channel. spawnSync uses one command string with shell:true because npm is npm.cmd on Windows and an args array with shell:true is deprecated (DEP0190). The extension has no token field (it reads fastmcpToken from its manifest, else the public default fastmcp-local-dev) and the bridge has no Origin check, so the default token is a known weakness we have not fixed here.
