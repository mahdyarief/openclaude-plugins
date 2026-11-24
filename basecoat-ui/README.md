# Basecoat UI plugin

Basecoat UI with the shadcn/ui look, for plain HTML with no React. This is a rewrite of
[zygiu-zygis/basecoat-ui-mcp](https://github.com/zygiu-zygis/basecoat-ui-mcp) as a
Claude/OpenClaude plugin that contains only skills and commands. There is no MCP server,
no Node entry point, and no background process.

## What is inside

| Path | Contents |
|---|---|
| `skills/basecoat/` | Core protocol, 58 component references, rules, design system, install guide |
| `skills/basecoat-dashboard/` | Page blueprints, block patterns, audit checklist |
| `skills/basecoat-charts/` | ApexCharts and SVG chart blueprints |
| `commands/` | `/basecoat-ui:find <intent>` and `/basecoat-ui:component <name>` |

The agent reads `components/<name>.md` on demand, which is the same lookup the old MCP
server performed, but through the file system instead of a running process.

## Install

Register this folder as a local marketplace, then enable the plugin:

```
/plugin marketplace add D:\Work\Nusantech\dashboard-rs\basecoat-ui-mcp
/plugin install basecoat-ui@basecoat-ui
```

Or add it to `~/.openclaude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "basecoat-ui": {
      "source": { "source": "git", "url": "file:///D:/Work/Nusantech/dashboard-rs/basecoat-ui-mcp" }
    }
  },
  "enabledPlugins": { "basecoat-ui@basecoat-ui": true }
}
```

## Use

- Ask for UI in the Basecoat or shadcn style; the skill triggers on its own.
- `/basecoat-ui:find confirm a destructive action`
- `/basecoat-ui:component alert-dialog`

## Resource footprint

- No process, no port, no network calls.
- Disk: about 380 KB.
- Context: one skill description line until the skill is invoked, then only the files the agent opens.

## CDN quick start

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/basecoat-css@1.3.0/dist/basecoat.cdn.min.css">
<script src="https://cdn.jsdelivr.net/npm/basecoat-css@1.3.0/dist/js/all.min.js" defer></script>
```

The CDN bundle carries only the Tailwind utilities Basecoat uses, so prefer semantic tokens
such as `var(--primary)` over utilities like `bg-primary`.

## Attribution

Component references, rules, and dashboard blueprints are derived from Basecoat UI MCP by
Žygimantas Jasiulionis / Intellmedia, MIT licensed. See `LICENSE` and `THIRD_PARTY_NOTICES.md`.
Basecoat CSS itself is by Steve Marrero and contributors, MIT licensed.
