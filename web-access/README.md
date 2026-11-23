# web-access

<img src=".claude-plugin/icon.png" alt="" width="96" align="right">

[Bahasa Indonesia](README.id.md) · [Changelog](CHANGELOG.md) · MIT licensed · [![test](https://github.com/mahdyarief/web-access/actions/workflows/test.yml/badge.svg)](https://github.com/mahdyarief/web-access/actions/workflows/test.yml)

A zero-dependency local [MCP](https://modelcontextprotocol.io) server, packaged as a Claude Code plugin, that gives AI coding agents web access through **[Exa](https://exa.ai) and [Tavily](https://tavily.com)**:

- **Web search**: one provider, automatic fallback, or both merged with rank fusion. Supports several queries per call, domain include/exclude, date ranges and categories, AI answers, compact snippets and a per-domain cap.
- **API key rotation** for both providers, with persistent cooldowns for exhausted, rate-limited or invalid keys, plus optional **daily budgets**
- **Reading the web as Markdown**: links, tables and code blocks are kept. You can `find` the relevant part of a long page, read several URLs at once, and fall back to Tavily Extract or Exa for PDFs and JS-rendered pages. Tavily Map/Crawl cover whole sites.
- **Safe by default**: internal and private network addresses are refused, including against DNS rebinding. Downloads are size-capped and no telemetry is sent.
- **GitHub**: search repositories, code, issues, commits and topics, and read a repo's README, files or folders

It works out of the box, because Exa is used **keyless** when no key is configured. Keys unlock more:

| | No keys | + Exa key(s) | + Tavily key(s) |
|---|---|---|---|
| Web search | ✅ Exa (anonymous) | ✅ Exa REST: native filters, `category`, `type` | ✅ Tavily search: news/finance topics |
| Fallback between providers | — | — | ✅ |
| `provider: "both"` (merged) | Exa only | Exa only | ✅ Exa + Tavily |
| AI answer (`includeAnswer`) | — | ✅ Exa `/answer` | ✅ Tavily answer |
| `web_get_contents` | ✅ HTML → Markdown | ✅ plus PDFs and JS pages (Exa contents) | ✅ plus PDFs and JS pages (Tavily Extract) |
| `web_extract_tavily`, `web_map`, `web_crawl` | — | — | ✅ |
| `github_search`, `github_read` | ✅ | ✅ | ✅ |

## Contents

- [Requirements](#requirements)
- [Install](#install)
- [Quick start](#quick-start)
- [Tools reference](#tools-reference)
- [How it works](#how-it-works)
- [Configuration](#configuration)
- [Key rotation and cooldowns](#key-rotation-and-cooldowns)
- [Credits and cost](#credits-and-cost)
- [Privacy and security](#privacy-and-security)
- [Troubleshooting](#troubleshooting)
- [Updating and uninstalling](#updating-and-uninstalling)
- [Project structure](#project-structure)
- [Development and releasing](#development-and-releasing)

## Requirements

- **Node.js 18.17 or newer** on your `PATH`. Check with `node -v`. No `npm install` is needed, because there are no dependencies.
- **Claude Code** for plugin install, or any MCP client that supports stdio servers.
- Optional: [Tavily API key(s)](https://app.tavily.com) (free tier: 1,000 credits/month), [Exa API key(s)](https://dashboard.exa.ai), and the [GitHub CLI](https://cli.github.com) (`gh auth login`) for GitHub code search.

Works on Windows, macOS and Linux. CI covers Node 18, 20 and 22 on Linux and Windows.

## Install

### Claude Code plugin (recommended)

```
/plugin marketplace add mahdyarief/web-access
/plugin install web-access@mahdyarief
```

On Claude Code 2.1.275 or later, a single command does both:

```
/plugin install web-access --marketplace mahdyarief/web-access
```

During install, Claude Code asks for the plugin options. **All of them are optional**:

| Option | Key | Meaning |
|---|---|---|
| **Tavily API keys** | `tavily_api_keys` | `tvly-...` keys, comma separated, rotated automatically. |
| **Exa API keys** | `exa_api_keys` | Comma separated. Leave empty to use Exa keyless. |
| **Default search provider** | `search_provider` | `auto` (default), `exa`, `tavily` or `both`. |

The key fields are marked *sensitive*. Claude Code stores them in your OS credential store, not in `settings.json`, and they never pass through the chat. To change them later, run `/plugin configure web-access@mahdyarief` and then restart Claude Code (or reconnect `web-access` in `/mcp`).

From a shell (for scripts or CI):

```bash
claude plugin marketplace add mahdyarief/web-access
claude plugin install web-access@mahdyarief
echo '{"tavily_api_keys":"tvly-aaa,tvly-bbb","search_provider":"auto"}' \
  | claude plugin configure web-access@mahdyarief --values-stdin
```

The plugin bundles:

| Component | Name | Purpose |
|---|---|---|
| MCP server | `web-access` | The tools below, exposed as `mcp__plugin_web-access_web-access__<tool>`. |
| Skill | `web-research` | Teaches Claude which tool and mode to use for each kind of question. |
| Skill | `/web-access:research <question>` | Step-by-step, source-backed research: sub-questions, multi-query search, reading the best sources, cross-checking, and an answer with citations. |
| Skill | `/web-access:setup` | Guided key setup, a status check and diagnosis. |

### Any other MCP client

The server is client-agnostic. Its config and state live in plain files, not in any client-specific folder. Clone the repo and point your client at `server.js`:

```bash
git clone https://github.com/mahdyarief/web-access.git
```

```json
{
  "mcpServers": {
    "web-access": {
      "command": "node",
      "args": ["/absolute/path/to/web-access/server.js"],
      "env": {
        "TAVILY_API_KEYS": "tvly-aaa,tvly-bbb",
        "EXA_API_KEYS": ""
      }
    }
  }
}
```

You can leave `env` out and use the [config file](#configuration) instead.

## Quick start

After installing, just ask Claude:

- *"What changed in the latest Node.js release?"* → `web_search` with `recency`
- *"Read https://example.com/docs/api and summarize the auth section"* → `web_get_contents` with `find: "auth"`
- *"Compare these three pricing pages"* → `web_get_contents` with `urls: [...]`
- *"Which pages does docs.tavily.com have about the API?"* → `web_map`
- *"Read all the API reference pages of this docs site"* → `web_crawl` with `selectPaths`
- *"Find popular MCP server repos written in TypeScript and show me the best one's README"* → `github_search`, then `github_read`
- *"Research Bun vs Deno, give me a short answer and cite sources"* → `web_search` with `queries: [...]`, `provider: "both"` and `includeAnswer: true`
- `/web-access:research Is Bun production-ready in 2026?` → the full research workflow, with citations

To check the setup, run `/web-access:setup` or ask *"run web_access_status"*:

```
## web-access status

**Config file:** `~/.openclaude/web-access.json`
**Default provider:** auto

**Exa:** 2 key(s) from env / plugin settings · REST API · keyless fallback on
  - `3f2a91c0…7d1e` — ready
  - `b81e44aa…02cf` — cooling (HTTP 402, 1380 min left)
  - spend this session: $0.0350 over 7 request(s)
  - today (UTC): $0.0350 over 7 request(s) · budget $1

**Tavily:** 1 key(s) from env / plugin settings
  - `tvly-aaaa…zzzz` — ready · credits 150 / 1000 used
  - account plan: Researcher · plan 150 / 1000 used
  - today (UTC): 12 credits over 9 request(s) · budget 100 credits

**State file (cooldowns, daily spend):** `~/.openclaude/web-access-state.json`
**Cache:** 5 entries, TTL 600s, 3 hit(s) / 5 miss(es), 1 duplicate in-flight call(s) shared
```

Example `web_search` result with `provider: "both"` and `includeAnswer: true`:

```markdown
**Answer (Tavily):** The Model Context Protocol (MCP) is an open standard …

**Answer (Exa):** MCP is an open-source protocol … Sources: [1](https://…) [2](https://…)

---

### [What is the Model Context Protocol (MCP)?](https://modelcontextprotocol.io/docs/getting-started/intro)
_2025-11-25 · via exa + tavily_

MCP (Model Context Protocol) is an open-source standard for connecting AI applications to external …
```

## Tools reference

Every tool returns Markdown text. If a tool fails, the result is marked `isError` and the error message says what to fix. All search, extract, map and crawl tools accept `fresh: true` to bypass the cache.

### `web_search`

Searches the web with the configured provider strategy.

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `query` | string | `query` or `queries` | Be specific: include product names, versions or error text. |
| `queries` | string[] | | Up to 5 queries run in parallel and merged with rank fusion. Each result is labelled with the queries that found it (`query 1, 3`). Use it to research a topic from several angles in one call. |
| `numResults` | number | `5` | 1–10 per query. In `both` mode, up to 2× after deduplication. |
| `site` | string | | Limits results to these domains, e.g. `docs.python.org` or `a.com,b.org`. |
| `excludeSite` | string[] | | Domains to leave out, e.g. `["pinterest.com"]`. |
| `recency` | `day` \| `week` \| `month` \| `year` | | Only results published in that period. |
| `startDate` / `endDate` | `YYYY-MM-DD` | | Explicit date range. `startDate` overrides `recency`. |
| `category` | `news` \| `publication` \| `company` \| `personal site` \| `financial report` \| `people` | | Exa category. Mapped to a Tavily topic on fallback (`news` → news, `financial report` → finance). With `company`/`people`, Exa ignores the site and date filters. |
| `provider` | `auto` \| `exa` \| `tavily` \| `both` | config, else `auto` | See [provider modes](#provider-modes). |
| `includeAnswer` | boolean | `false` | Adds an AI answer: the Tavily answer and/or Exa `/answer` (each needs a key). `both` shows both answers for cross-checking. With several queries, each answer is labelled with its query. |
| `maxCharsPerResult` | number | `1200` | Snippet length per result (100–10000). |
| `maxPerDomain` | number | `3` | At most this many results from one domain, so one site can't fill the list. `0` = unlimited. Not applied when `site` is set. |
| `livecrawl` | `always` \| `fallback` \| `never` | `fallback` | Exa freshness (`always` = fetch live, which also skips the cache). |
| `fresh` | boolean | `false` | Skips the result cache. |

### `web_search_exa`

Exa only. Without a key it uses Exa's anonymous MCP endpoint. With keys it uses the REST API with native filters and key rotation.

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `query` | string | **required** | |
| `numResults` | number | `5` | 1–10 |
| `site`, `excludeSite`, `recency`, `startDate`, `endDate`, `category`, `maxPerDomain` | | | As in `web_search`. Filters are native with a key, and added to the query text as hints (`site:`, `-site:`, `after:`, `before:`) when keyless. |
| `type` | `auto` \| `lite` \| `deep` | `auto` | `lite` is fastest, `deep` is the most thorough (needs a key). The legacy values `neural`/`keyword` are treated as `auto`. |
| `maxCharsPerResult` | number | `1200` | Sent to Exa as the highlights budget, so snippets are compact at the source. |
| `livecrawl` | `always` \| `fallback` \| `never` | `fallback` | Mapped to Exa `maxAgeHours` (`0` / default / `-1`). |
| `fresh` | boolean | `false` | |

### `web_search_tavily`

Tavily only. **Requires a Tavily key.**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `query` | string | **required** | |
| `numResults` | number | `5` | 1–20 |
| `site`, `excludeSite`, `recency`, `startDate`, `endDate`, `maxPerDomain` | | | Sent as Tavily `include_domains`, `exclude_domains`, `time_range` and `start_date`/`end_date`. |
| `topic` | `general` \| `news` \| `finance` | `general` | |
| `searchDepth` | `basic` \| `advanced` | `basic` | `advanced` gives better relevance and costs 2 credits. |
| `includeAnswer` | boolean | `false` | Adds a short AI answer. |
| `maxCharsPerResult` | number | `1200` | |
| `fresh` | boolean | `false` | |

### `web_get_contents`

Returns the content of web pages as **Markdown**: headings, links, tables, lists and fenced code blocks with their language. Works without any key. See [reading pages](#reading-pages).

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `url` | string | `url` or `urls` | `http://` or `https://`. Internal addresses are refused. |
| `urls` | string[] | | Up to 10 URLs read in parallel. A failed URL is listed under `## Failed:` without failing the rest. |
| `find` | string | | Returns only the sections that mention this text (exact phrase first, then its words). Each hit shows its `offset` and the heading it sits under. Ideal for long pages. |
| `format` | `markdown` \| `text` | `markdown` | `text` reduces links to their text, which saves tokens. |
| `maxChars` | number | `8000` | Characters returned per page (500–50000). With several URLs the default is ~24000 split across them. |
| `offset` | number | `0` | Continues a long page. Each truncated result ends with `call again with offset=N`. |
| `fresh` | boolean | `false` | Re-downloads the page. Otherwise the document is cached, so paging and `find` do not re-fetch it. |

### `web_extract_tavily`

Extracts several URLs in one call with Tavily Extract. **Requires a Tavily key.**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `urls` | string[] | **required** | Up to 20 `http(s)` URLs. A single string is also accepted. |
| `extractDepth` | `basic` \| `advanced` | `basic` | `advanced` handles tables and embedded content, and costs more. |
| `maxCharsPerPage` | number | `8000` | |
| `fresh` | boolean | `false` | |

URLs that fail are listed under `## Failed:` along with the reason.

### `web_map`

Lists the URLs of a website (no content) with Tavily Map. Use it to find the right pages of a docs site before reading them. **Requires a Tavily key.**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `url` | string | **required** | Root URL to start from. |
| `limit` | number | `50` | 1–500 URLs. |
| `maxDepth` | number | `1` | 1–5 link levels. |
| `selectPaths` / `excludePaths` | string[] | | Regex path filters, e.g. `["/docs/.*"]`. |
| `instructions` | string | | Natural-language focus. Costs 2× credits. |
| `allowExternal` | boolean | `false` | Follow links to other domains. |
| `fresh` | boolean | `false` | |

### `web_crawl`

Crawls a website and returns several pages' content in one call with Tavily Crawl. **Requires a Tavily key.** Takes the same parameters as `web_map`, plus:

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `limit` | number | `10` | 1–50 pages. |
| `extractDepth` | `basic` \| `advanced` | `basic` | |
| `maxCharsPerPage` | number | `3000` | Per-page text in the output. Read any page in full with `web_get_contents`. |

Lines repeated on most crawled pages, such as site banners, doc indexes and footers, are removed so `maxCharsPerPage` is spent on real content.

### `github_search`

Searches GitHub through the REST API.

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `query` | string | **required** | Same syntax as github.com/search, e.g. `mcp server language:typescript stars:>100`. |
| `type` | `repositories` \| `issues` \| `code` \| `commits` \| `topics` | `repositories` | **Code search requires auth.** |
| `sort` | string | | Repos: `stars`, `forks`, `updated`, `help-wanted-issues`. Issues: `comments`, `reactions`, `updated`. |
| `order` | `desc` \| `asc` | `desc` | |
| `perPage` | number | `5` | 1–30 |

Authentication is optional and improves rate limits. The token is taken from `GITHUB_TOKEN`, then `GH_TOKEN`, then `gh auth token`.

### `github_read`

Reads from a GitHub repository: its README, a file, or a directory listing.

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `repo` | string | **required** | `owner/repo` or any github.com URL, including `blob`/`tree` links such as `https://github.com/o/r/blob/main/src/x.ts`. |
| `path` | string | | File or folder in the repo. Leave it out to read the README. |
| `ref` | string | default branch | Branch, tag or commit. |
| `find` | string | | Returns only the parts of the file that mention this text. |
| `maxChars` / `offset` | number | `12000` / `0` | Paging for long files. |

Private repositories need `GITHUB_TOKEN` or `gh auth login`. Binary files are not shown. Files over 1 MB are downloaded raw.

### `web_access_status`

No parameters. Shows:
- the config file and the default provider
- key counts and where they came from, with masked keys and their cooldown state
- **remaining Tavily credits** per key and for the account (from Tavily's `/usage` endpoint, cached for 10 minutes)
- **Exa spend this session** (summed from Exa's `costDollars`)
- **today's spend** per provider and the [daily budget](#daily-budgets), if one is set
- the state file and cache stats

Full keys are never shown.

## How it works

### Provider modes

| Mode | Behaviour | Best for |
|---|---|---|
| `auto` | Exa first, Tavily on error. **Exception:** when Exa has no key and the query uses site or date filters, Tavily goes first, because keyless Exa can only receive those filters as query hints. | Everyday use |
| `exa` | Exa only. | Saving Tavily credits |
| `tavily` | Tavily, with Exa on error. Without a Tavily key it uses Exa directly and adds a note. | News, recent events |
| `both` | Exa and Tavily run in parallel. Results are merged with **Reciprocal Rank Fusion** and deduplicated by normalized URL (ignoring `www.`, trailing `/` and `utm_*`). | Research, thin results, cross-checking |

How the `both` ranking works: each result scores Σ 1/(60 + rank) over the providers that returned it. Hits found by **both** providers therefore rank first and are tagged `via exa + tavily`. Single-provider hits follow, interleaved fairly by rank. If one provider fails, you still get the other's results plus a note.

With **several `queries`**, each query runs with the same strategy in parallel, and the result lists are fused the same way: results found by several queries rank higher. After merging, `maxPerDomain` (default 3) keeps one site from filling the list, and a note says how many results it hid.

### Exa: REST vs keyless

- **With Exa keys**, requests go to the REST API at `api.exa.ai`. You get native `includeDomains`, `startPublishedDate` and `category` filters, a `type` choice, highlight-based compact snippets, `/answer`, and exact per-request cost.
- **Without keys**, requests go to Exa's hosted MCP endpoint, which works anonymously with rate limits. The REST API has no free keyless mode.
- **When every key is rejected or cooling down**, one keyless attempt is made, unless `exa.keylessFallback` is `false`.

### Reading pages

`web_get_contents` tries the cheapest method that works:

1. **Direct fetch**, which is free.
   - It refuses internal and private addresses. The check runs on every redirect hop, and again on the IP the socket actually connects to.
   - It stops downloading after 25 MB.
   - It decodes gzip/deflate/brotli and the page's declared charset.
   - It converts HTML to **Markdown** with a built-in parser:
     - Main content: `<article>` / `<main>` when they hold enough text.
     - Dropped: navigation, cookie and consent banners, ads, share buttons, hidden elements, edit links, citation markers and permalink anchors.
     - Kept: headings, absolute links, bold/italic, inline code, fenced code blocks with their language, nested lists, blockquotes and tables.
2. **Tavily Extract**, used only with a Tavily key, when the direct fetch fails (blocked, timeout, HTTP error), when the URL is a **PDF** or other document, or when the page yields under ~300 characters (usually JS-rendered).
3. **Exa contents**, used with an Exa key in the same cases, when Tavily is not configured or could not read the page.

Internal URLs are never sent to a provider. The full document is cached, so paging with `offset` or searching with `find` costs one download.

### Caching

- **What is kept**: successful results, in memory for `cacheTtlSeconds` (600 by default). They are keyed by tool plus arguments, ignoring argument order and surrounding whitespace. Errors are never cached.
- **Bypassing it**: `fresh: true` or `livecrawl: "always"`.
- **Size**: up to 200 entries; the oldest are evicted first.
- **Parallel duplicates**: identical requests that are still running share one upstream call, even with the cache disabled, so they cost once.
- **Across restarts**: set `"cachePersist": true` to also save results to `web-access-cache.json` next to the config file (or `WEB_ACCESS_CACHE_FILE`) and reuse them in later sessions until they expire. Whole documents and results over 256 KB stay in memory only.

## Configuration

### Where keys come from

Keys are loaded from the **first source that has any**, separately for each provider:

1. **Environment / plugin settings**: `TAVILY_API_KEYS` (or `TAVILY_API_KEY`) and `EXA_API_KEYS` (or `EXA_API_KEY`). Separate multiple keys with commas. The Claude Code plugin fills these from its options.
2. **Config file**: `~/.openclaude/web-access.json`, described below.
3. **Legacy files**: `~/.openclaude/exa_keys.json` and `~/.openclaude/tavily_keys.json` (paths can be changed with `EXA_KEYS_FILE` / `TAVILY_KEYS_FILE`).

`web_access_status` shows which source is in use.

### Config file

The default path is `~/.openclaude/web-access.json`. Override it with `WEB_ACCESS_CONFIG=/path/to/file.json`. Copy [`web-access.example.json`](web-access.example.json) to get started:

```json
{
  "provider": "auto",
  "cacheTtlSeconds": 600,
  "cachePersist": false,
  "exa": {
    "keylessFallback": true,
    "timeoutMs": 45000,
    "dailyBudgetUsd": 1,
    "keys": ["your-exa-key-1", "your-exa-key-2"]
  },
  "tavily": {
    "timeoutMs": 45000,
    "dailyCreditBudget": 100,
    "keyless": false,
    "keys": ["tvly-your-key-1", "tvly-your-key-2"]
  },
  "fetch": {
    "allowPrivateNetwork": false,
    "maxBytes": 26214400
  }
}
```

| Setting | Default | Meaning |
|---|---|---|
| `provider` | `auto` | Default mode for `web_search`. `WEB_SEARCH_PROVIDER` or the plugin option overrides it. Invalid values fall back to `auto`. |
| `cacheTtlSeconds` | `600` | Cache lifetime. `0` disables the cache. |
| `cachePersist` | `false` | Saves results to `web-access-cache.json` next to the config file and reuses them across sessions. |
| `exa.keys` | `[]` | Exa API keys. With none, Exa runs keyless. |
| `exa.keylessFallback` | `true` | Makes one keyless attempt when every key is rejected or cooling down. Set it to `false` to fail instead. |
| `exa.timeoutMs` | `45000` | Total time budget for one Exa request across all attempts. |
| `exa.dailyBudgetUsd` | none | [Daily budget](#daily-budgets) for keyed Exa calls, in dollars. |
| `tavily.keys` | `[]` | Tavily API keys (`tvly-...`). Tavily is disabled without at least one key, unless `tavily.keyless` is on. |
| `tavily.timeoutMs` | `45000` | Time budget for one Tavily search (extract: 90 s, map/crawl: 160 s). |
| `tavily.dailyCreditBudget` | none | [Daily budget](#daily-budgets) in Tavily credits. |
| `tavily.keyless` | `false` | Opt-in: use Tavily's keyless mode for search and extract when no key is configured. It is rate-limited per IP with a small daily cap; map and crawl still need a key. |
| `fetch.allowPrivateNetwork` | `false` | Allows `web_get_contents` to read localhost and private-network URLs, for example local dev docs. |
| `fetch.maxBytes` | `26214400` | Download cap for direct fetches (25 MB). |

`"exa"` and `"tavily"` can also be plain arrays of keys. The file is **re-read automatically when it changes**, so you don't need to restart.

### State file

Key cooldowns and today's spend are saved to **`web-access-state.json` next to the config file** (default `~/.openclaude/web-access-state.json`), so they survive restarts and are shared between concurrent sessions. The file contains only short SHA-256 fingerprints of keys, **never the keys themselves**. It is a plain file, not tied to any MCP client. Use `WEB_ACCESS_STATE_FILE=/path/to/file.json` to move it, or `WEB_ACCESS_STATE_FILE=off` to keep everything in memory only.

### Daily budgets

These settings cap what an agent can spend per UTC day:

```json
{ "tavily": { "dailyCreditBudget": 100 }, "exa": { "dailyBudgetUsd": 1 } }
```

- **How spend is counted**: from what the APIs report, so it is exact. Tavily returns `usage.credits` on every call, and Exa returns `costDollars`. It is stored in the state file, so all sessions share it.
- **When the budget is reached**: calls to that provider are refused until 00:00 UTC. `web_search` then falls back to the other provider.
- **Checking it**: `web_access_status` shows today's spend next to the budget.
- **Default**: no budget, which means no limit.

### Environment variables

| Variable | Purpose |
|---|---|
| `TAVILY_API_KEYS` / `TAVILY_API_KEY` | Tavily keys (comma separated). |
| `EXA_API_KEYS` / `EXA_API_KEY` | Exa keys (comma separated). |
| `WEB_SEARCH_PROVIDER` | Default provider (`auto`, `exa`, `tavily`, `both`). |
| `WEB_ACCESS_CONFIG` | Path to the config file. |
| `WEB_ACCESS_STATE_FILE` | Path to the state file (cooldowns, daily spend), or `off`. |
| `WEB_ACCESS_CACHE_FILE` | Path to the persistent cache file (when `cachePersist` is on). |
| `EXA_KEYS_FILE` / `TAVILY_KEYS_FILE` | Paths to the legacy key files. |
| `GITHUB_TOKEN` / `GH_TOKEN` | GitHub token for `github_search` and `github_read`. |

Empty values and unfilled placeholders such as `${user_config.tavily_api_keys}` are ignored.

### Legacy key file formats

These are still supported for existing setups:

```jsonc
["key-1", "key-2"]                      // plain array
{ "keys": ["key-1", "key-2"] }          // object with keys
{ "account1": "key-1", "acc2": "key-2" } // named values (Exa: UUID keys only)
```

## Key rotation and cooldowns

- **Round-robin**: each request starts on the next key, so usage spreads evenly across keys.
- **Retry on key problems**: when a key is rejected, the same request moves on to the next key, and the rejected key is put on cooldown:

  | Status | Meaning | Cooldown |
  |---|---|---|
  | 429 | Rate limited | 1 minute, or longer if the response's `Retry-After` asks (max 1 h) |
  | 402 / 432 / 433 | Out of credits, or over the budget, plan or pay-as-you-go limit | 24 hours |
  | 401 | Invalid key | 6 hours |

- **403 does not bench a key.** Tavily uses 403 for "URL not supported" and Exa uses it for prohibited content or disabled features. Neither is the key's fault, so the request fails instead of burning through keys.
- **Other failures**: network errors and 5xx responses also move on to the next attempt, without a cooldown. Other errors (for example a 400 bad request) fail fast.
- **Deadline**: all attempts share one time budget (`timeoutMs`), so a request never hangs for minutes.
- **Persistence**: cooldowns are written to the [state file](#state-file).

## Credits and cost

| Action | Exa | Tavily |
|---|---|---|
| `web_search` in `auto` / `exa` | 1 search (free when keyless) | only used as a fallback |
| `web_search` in `both` | 1 search | 1 search |
| `includeAnswer` | +1 `/answer` call (with a key) | answer included in the search |
| `web_search_tavily` | none | `basic` 1 credit, `advanced` 2 credits |
| `web_get_contents` | only as a fallback without Tavily: Exa `/contents` | only used as a fallback: 1 credit per 5 pages |
| `web_search` with `queries` | one search per query | one search per query (if used) |
| `web_extract_tavily` | none | 1 credit per 5 URLs (basic), 2 per 5 (advanced); failed URLs are free |
| `web_map` | none | 1 credit per 10 pages (2 with `instructions`) |
| `web_crawl` | none | map plus extract, e.g. 10 pages basic ≈ 3 credits |
| Cached repeat | none | none |

Credit numbers come from Tavily's credits documentation at the time of writing, and Exa bills per request in dollars. Both can change, so check [Tavily's credits page](https://docs.tavily.com/documentation/api-credits) and [Exa's billing page](https://exa.ai/docs/admin/billing). `web_access_status` shows your actual Tavily usage and Exa spend. To put a hard cap on both, use the [daily budgets](#daily-budgets).

## Privacy and security

- **What leaves your machine**:
  - search queries go to Exa (`api.exa.ai` or `mcp.exa.ai`) and/or Tavily (`api.tavily.com`)
  - URLs you read are fetched **directly from your machine**, or sent to Tavily Extract / Exa contents when a fallback is used
  - GitHub queries go to `api.github.com`
- **No telemetry**: nothing is sent anywhere else. The files written are the [state file](#state-file), which holds key fingerprints (not keys) and today's spend, and, only if you turn on `cachePersist`, the result cache.
- **Keys**: plugin keys are stored by Claude Code in your OS credential store. Keys are never logged, and `web_access_status` only shows masked keys.
- **SSRF protection**: fetched pages are untrusted and can try to steer the model into requesting internal services. By default, `web_get_contents` refuses:
  - `localhost`
  - private and link-local ranges, including the cloud metadata address `169.254.169.254`
  - `.local` / `.internal` hosts
  - hostnames that resolve to any of these, checked again on every redirect

  The address is also checked when the socket connects (a pinned DNS lookup), so a DNS-rebinding answer cannot slip in between the check and the connection. Internal URLs are never forwarded to Tavily or Exa.
- **Resource limits**: direct downloads stop at 25 MB (`fetch.maxBytes`).
- **Config file**: `~/.openclaude/web-access.json` is plain text. Keep it private and never commit it. This repo's `.gitignore` excludes it, the state file and the legacy key files.
- **Leaked key**: if a key ever ends up in a chat, log or commit, rotate it in the provider's dashboard.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `web-access` is missing from `/mcp`, or shows as failed | Node.js isn't on `PATH` or is older than 18.17. Run `node -v`, install a newer Node, and restart Claude Code. |
| `No Tavily API keys configured` | Tavily is optional. Use `web_search` (Exa works keyless), or add keys with `/plugin configure web-access@mahdyarief`. |
| You set keys but `web_access_status` still shows none | Restart Claude Code after `/plugin configure`, because plugin options are passed when the server starts. Also check that Tavily keys start with `tvly-`. |
| `All Tavily keys are cooling down` | Every key hit a rate or credit limit. Check `web_access_status` for the time left and the remaining credits, switch provider meanwhile, or add a key. To clear cooldowns early, delete the state file. |
| `Exa error 429` with keyless Exa | You hit the anonymous rate limit. Add an Exa key, or configure Tavily so `auto` can fall back. |
| `Exa error 403` with keyless Exa | Keyless Exa requires a direct IPv4 connection. It is refused over IPv6 or proxies. Add an Exa key. |
| `refusing to fetch internal address …` | This is the SSRF protection. To read local or intranet docs, set `"fetch": {"allowPrivateNetwork": true}`. |
| `request timed out` | Slow network or provider. Retry, or raise `timeoutMs`. |
| `PDF documents are not supported by the direct fetcher` | Add a Tavily or Exa key. PDFs are then extracted automatically. |
| A page returns almost no text | The page is probably JS-rendered. With a Tavily or Exa key this is retried automatically. Otherwise, find another source. |
| `Daily Tavily budget reached` / `Daily Exa budget reached` | Your [daily budget](#daily-budgets) is used up. It resets at 00:00 UTC. Raise the budget, or let `web_search` use the other provider meanwhile. |
| `daily_cap_reached` with `tavily.keyless` | Tavily's keyless mode has a small per-IP daily cap. Add a Tavily key. |
| Some results are missing from one site | `maxPerDomain` (default 3) hides extra results from the same domain, and the result says how many. Pass `maxPerDomain: 0` or use `site`. |
| `Tavily error 403` on map/crawl | Tavily does not support that URL. Use `web_get_contents` on individual pages. |
| `GitHub API requires authentication` | Code search always needs auth. Run `gh auth login`, or set `GITHUB_TOKEN`. |
| Results look stale | Pass `fresh: true`, or set `cacheTtlSeconds` to `0`. |

Server logs go to stderr, so they appear in your MCP client's server log. They include the startup summary, key rotations and fallbacks.

## Updating and uninstalling

```
/plugin marketplace update mahdyarief
/plugin update web-access@mahdyarief
```

Restart Claude Code after updating. To remove the plugin:

```
/plugin uninstall web-access@mahdyarief
/plugin marketplace remove mahdyarief
```

Your config, state and cache files (`~/.openclaude/web-access*.json`) are left untouched. Delete them yourself if you no longer need them.

## Project structure

```
.claude-plugin/
  plugin.json         plugin manifest + userConfig (keys, provider)
  marketplace.json    "mahdyarief" marketplace listing this plugin
  icon.png
.github/workflows/    CI: tests on Node 18/20/22 × Linux/Windows, manifest checks
.mcp.json             MCP server definition (passes plugin options as env)
skills/
  web-research/       when to use which tool
  research/           /web-access:research (multi-step research with citations)
  setup/              /web-access:setup
server.js             stdio JSON-RPC / MCP entry point
tools.js              tool schemas + annotations, routing, multi-query, answers, status
config.js             config file + env helpers (hot reload)
exa-client.js         Exa REST (keyed) + MCP (keyless) client, /answer, /contents, spend
exa-rotator.js        Exa key loading + round-robin
tavily-client.js      Tavily search/extract/map/crawl/usage, keyless mode, credits
tavily-rotator.js     Tavily key loading + round-robin
key-health.js         per-key cooldowns, state file, masking
budget.js             daily spend tracking + budgets
cache.js              TTL cache, in-flight sharing, optional disk persistence
formatter.js          result model, filters, rank fusion, domain cap, crawl dedupe
web-fetcher.js        direct fetch: pinned transport, redirects, size cap, find, paging
html-markdown.js      HTML parser + Markdown renderer (main content, boilerplate removal)
url-guard.js          SSRF protection (URL check + connect-time pinned lookup)
github-client.js      GitHub search + read (README, files, folders)
test/                 node:test suite (mocked APIs + a local HTTP server)
```

## Development and releasing

```bash
git clone https://github.com/mahdyarief/web-access.git
cd web-access
npm test                          # fully mocked: no network, no keys
claude plugin validate .          # validate the plugin manifest
claude plugin validate .claude-plugin/marketplace.json
```

To try local changes in Claude Code, add the folder as a marketplace: `/plugin marketplace add ./path/to/web-access`.

**Releasing a new version:**

1. Bump `version` in **both** `.claude-plugin/plugin.json` and `package.json`. Claude Code uses the plugin version to detect updates, and CI checks that the two match.
2. Add an entry to [`CHANGELOG.md`](CHANGELOG.md).
3. Run `npm test` and `claude plugin validate .`.
4. Commit, push, and optionally tag with `claude plugin tag .`.

Issues and pull requests are welcome at [github.com/mahdyarief/web-access](https://github.com/mahdyarief/web-access/issues).

## License

[MIT](LICENSE) © mahdyarief
