const { exaSearch, exaAnswer, exaContents, exaSpend, EXA_CATEGORIES } = require("./exa-client.js");
const { fetchDocument, paginate, findInText, UnsupportedContentError, BlockedUrlError } = require("./web-fetcher.js");
const { stripLinks } = require("./html-markdown.js");
const { mergeResults, formatItems, truncate, capPerDomain, stripRepeatedLines } = require("./formatter.js");
const { searchGithub, readGithub } = require("./github-client.js");
const {
  tavilySearch,
  tavilyExtract,
  tavilyMap,
  tavilyCrawl,
  tavilyUsage,
  tavilyAvailable,
  keylessEnabled: tavilyKeyless,
  formatTavilyExtract,
  cleanExtracted,
  tavilyItems,
} = require("./tavily-client.js");
const { loadKeys: loadTavilyKeys, keySource: tavilyKeySource } = require("./tavily-rotator.js");
const { hasKeys: hasExaKeys, loadKeys: loadExaKeys, keySource: exaKeySource } = require("./exa-rotator.js");
const { describeKeys, stateFile, maskKey } = require("./key-health.js");
const budget = require("./budget.js");
const { getDefaultProvider, loadConfig, configPath } = require("./config.js");
const cache = require("./cache.js");

const MAX_QUERIES = 5;
const MAX_URLS = 10;
const DEFAULT_PER_DOMAIN = 3;

// ── Shared schema fragments ──────────────────────────────────

const SNIPPET_PROP = {
  type: "number",
  description:
    "Max characters of text per result (default 1200, 100–10000). Lower it for compact overviews, raise it when snippets need more detail",
  default: 1200,
};
const FRESH_PROP = { type: "boolean", description: "Bypass the result cache and force a new request", default: false };
const FILTER_PROPS = {
  site: {
    type: "string",
    description: "Limit results to these domains (e.g. 'docs.python.org', or comma-separated 'a.com,b.org')",
  },
  excludeSite: {
    type: "array",
    items: { type: "string" },
    description: "Domains to leave out of the results, e.g. ['pinterest.com', 'quora.com']",
  },
  recency: {
    type: "string",
    description: "Only results published within this period (ignored when startDate is set)",
    enum: ["day", "week", "month", "year"],
  },
  startDate: { type: "string", description: "Only results published on/after this date (YYYY-MM-DD)" },
  endDate: { type: "string", description: "Only results published on/before this date (YYYY-MM-DD)" },
};
const PER_DOMAIN_PROP = {
  type: "number",
  description: "Max results from one domain (default 3; 0 = unlimited; not applied when 'site' is set)",
  default: DEFAULT_PER_DOMAIN,
};
const CATEGORY_PROP = {
  type: "string",
  description:
    "Exa content category: 'news', 'publication' (papers/articles), 'company', 'personal site' (blogs), 'financial report', 'people'. Note: with 'company'/'people', site and date filters are ignored by Exa.",
  enum: EXA_CATEGORIES,
};
const LIVECRAWL_PROP = {
  type: "string",
  description: "Exa freshness: 'always' (fetch live), 'fallback' (default), 'never' (cache only)",
  enum: ["always", "fallback", "never"],
};

const CRAWL_COMMON = {
  url: { type: "string", description: "Root URL to start from (http/https)" },
  instructions: {
    type: "string",
    description: "Natural-language focus, e.g. 'only API reference pages' (costs more credits)",
  },
  maxDepth: { type: "number", description: "How many link levels deep to go (1–5, default 1)", default: 1 },
  selectPaths: {
    type: "array",
    items: { type: "string" },
    description: "Regex path filters to include, e.g. ['/docs/.*']",
  },
  excludePaths: {
    type: "array",
    items: { type: "string" },
    description: "Regex path filters to exclude, e.g. ['/blog/.*']",
  },
  allowExternal: { type: "boolean", description: "Follow links to other domains (default false)", default: false },
};

/** MCP tool annotations: every tool here only reads (from the web). */
function readOnly(title) {
  return { title, readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true };
}

// ── Tool definitions ─────────────────────────────────────────

const TOOLS = [
  {
    name: "web_search",
    description:
      "Search the web for current/recent information, news, documentation, or anything beyond your knowledge cutoff. Returns titles, URLs, dates and snippets. Pass several 'queries' to research a topic from different angles in one call (results merged and deduplicated). Uses Exa and/or Tavily depending on 'provider'.",
    annotations: readOnly("Web search"),
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query — be specific for best results" },
        queries: {
          type: "array",
          items: { type: "string" },
          description: `Several queries at once (max ${MAX_QUERIES}), run in parallel and merged — use instead of, or in addition to, 'query'`,
        },
        numResults: { type: "number", description: "Results per query (1–10, default 5)", default: 5 },
        ...FILTER_PROPS,
        category: CATEGORY_PROP,
        provider: {
          type: "string",
          description:
            "'auto' (default: Exa first, Tavily on error), 'exa', 'tavily', or 'both' (Exa + Tavily in parallel, merged with rank fusion and deduplicated — broader coverage for research, uses credits on both). Defaults to the configured provider.",
          enum: ["auto", "exa", "tavily", "both"],
        },
        includeAnswer: {
          type: "boolean",
          description:
            "Also return a short AI-generated answer (Tavily answer and/or Exa /answer — needs a key for that provider). In 'both' mode answers from both are shown for cross-checking.",
          default: false,
        },
        maxCharsPerResult: SNIPPET_PROP,
        maxPerDomain: PER_DOMAIN_PROP,
        livecrawl: LIVECRAWL_PROP,
        fresh: FRESH_PROP,
      },
    },
  },
  {
    name: "web_search_exa",
    description:
      "Search with Exa only (works keyless; with Exa keys uses the REST API with native filters and key rotation).",
    annotations: readOnly("Exa search"),
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query" },
        numResults: { type: "number", description: "Number of results (1–10, default 5)", default: 5 },
        ...FILTER_PROPS,
        category: CATEGORY_PROP,
        type: {
          type: "string",
          description: "Exa search type: 'auto' (default), 'lite' (fastest), 'deep' (more thorough, slower). Needs an Exa key.",
          enum: ["auto", "lite", "deep"],
          default: "auto",
        },
        maxCharsPerResult: SNIPPET_PROP,
        maxPerDomain: PER_DOMAIN_PROP,
        livecrawl: LIVECRAWL_PROP,
        fresh: FRESH_PROP,
      },
      required: ["query"],
    },
  },
  {
    name: "web_search_tavily",
    description:
      "Search with Tavily only. Requires a Tavily API key (tvly-...). Supports news/finance topics, advanced depth, native domain/date filters and an optional AI answer.",
    annotations: readOnly("Tavily search"),
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query" },
        numResults: { type: "number", description: "Number of results (1–20, default 5)", default: 5 },
        ...FILTER_PROPS,
        searchDepth: {
          type: "string",
          description: "'basic' (1 credit) or 'advanced' (2 credits, better relevance)",
          enum: ["basic", "advanced"],
          default: "basic",
        },
        topic: {
          type: "string",
          description: "'general', 'news', or 'finance'",
          enum: ["general", "news", "finance"],
          default: "general",
        },
        includeAnswer: {
          type: "boolean",
          description: "Include a short AI-generated answer above the results",
          default: false,
        },
        maxCharsPerResult: SNIPPET_PROP,
        maxPerDomain: PER_DOMAIN_PROP,
        fresh: FRESH_PROP,
      },
      required: ["query"],
    },
  },
  {
    name: "web_get_contents",
    description:
      "Read web pages as Markdown (links, tables and code blocks kept). PDFs and JS-heavy pages are handled via Tavily Extract or Exa when a key is configured. Use 'find' to get only the parts of a long page that mention something; long pages are paged with 'offset'. Pass 'urls' to read several pages at once. Internal/private network addresses are refused.",
    annotations: readOnly("Read web page"),
    inputSchema: {
      type: "object",
      properties: {
        url: { type: "string", description: "The full URL (http:// or https://)" },
        urls: {
          type: "array",
          items: { type: "string" },
          description: `Several URLs read in parallel (max ${MAX_URLS}); maxChars, offset, find and format apply to each`,
        },
        find: {
          type: "string",
          description:
            "Return only the sections that mention this text (phrase first, then its words), each with its offset — ideal for long pages",
        },
        format: {
          type: "string",
          description: "'markdown' (default, keeps links) or 'text' (links reduced to their text — fewer tokens)",
          enum: ["markdown", "text"],
          default: "markdown",
        },
        maxChars: {
          type: "number",
          description:
            "Max characters returned per page (500–50000, default 8000; with several URLs the default is ~24000 split across them)",
          default: 8000,
        },
        offset: {
          type: "number",
          description: "Character offset to continue a long page from (given at the end of the previous result)",
          default: 0,
        },
        fresh: FRESH_PROP,
      },
    },
  },
  {
    name: "web_extract_tavily",
    description:
      "Extract clean content from up to 20 URLs at once with Tavily Extract (handles PDFs and JS-heavy pages). Requires a Tavily API key.",
    annotations: readOnly("Tavily extract"),
    inputSchema: {
      type: "object",
      properties: {
        urls: { type: "array", items: { type: "string" }, description: "URLs to extract (max 20)" },
        extractDepth: {
          type: "string",
          description: "'basic' or 'advanced' (tables, embedded content; costs more)",
          enum: ["basic", "advanced"],
          default: "basic",
        },
        maxCharsPerPage: { type: "number", description: "Max characters per page (default 8000)", default: 8000 },
        fresh: FRESH_PROP,
      },
      required: ["urls"],
    },
  },
  {
    name: "web_map",
    description:
      "List the pages of a website (URLs only, no content) using Tavily Map — e.g. to discover all pages of a documentation site before reading the relevant ones. Requires a Tavily API key (≈1 credit per 10 pages).",
    annotations: readOnly("Map a website"),
    inputSchema: {
      type: "object",
      properties: {
        ...CRAWL_COMMON,
        limit: { type: "number", description: "Max URLs to return (1–500, default 50)", default: 50 },
        fresh: FRESH_PROP,
      },
      required: ["url"],
    },
  },
  {
    name: "web_crawl",
    description:
      "Crawl a website and return the content of multiple pages in one call using Tavily Crawl — e.g. read a whole docs section. Text repeated on most pages (site banners, doc indexes) is removed. Requires a Tavily API key (≈3 credits per 10 pages basic). Prefer web_map + web_get_contents when you only need a few pages.",
    annotations: readOnly("Crawl a website"),
    inputSchema: {
      type: "object",
      properties: {
        ...CRAWL_COMMON,
        limit: { type: "number", description: "Max pages to crawl (1–50, default 10)", default: 10 },
        extractDepth: {
          type: "string",
          description: "'basic' or 'advanced' (tables, embedded content; costs more)",
          enum: ["basic", "advanced"],
          default: "basic",
        },
        maxCharsPerPage: {
          type: "number",
          description: "Max characters per page in the output (default 3000)",
          default: 3000,
        },
        fresh: FRESH_PROP,
      },
      required: ["url"],
    },
  },
  {
    name: "github_search",
    description:
      "Search GitHub repositories, code, issues, commits, or topics. Returns stars, forks, descriptions and links. Read a result with github_read.",
    annotations: readOnly("GitHub search"),
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "GitHub search query — same syntax as github.com/search (e.g. 'mcp server language:typescript stars:>100')",
        },
        type: {
          type: "string",
          description: "'repositories' (default), 'issues', 'code', 'commits', 'topics'",
          enum: ["repositories", "issues", "code", "commits", "topics"],
          default: "repositories",
        },
        sort: {
          type: "string",
          description: "Repos: 'stars', 'forks', 'updated', 'help-wanted-issues'; issues: 'comments', 'reactions', 'updated'",
        },
        order: { type: "string", description: "'desc' (default) or 'asc'", enum: ["desc", "asc"] },
        perPage: { type: "number", description: "Results per page (max 30)", default: 5 },
      },
      required: ["query"],
    },
  },
  {
    name: "github_read",
    description:
      "Read from a GitHub repository: its README (no path), a file, or a directory listing. Accepts 'owner/repo' or any github.com URL (blob/tree links included). Use 'find' / 'offset' for long files.",
    annotations: readOnly("Read GitHub repository"),
    inputSchema: {
      type: "object",
      properties: {
        repo: {
          type: "string",
          description: "'owner/repo' or a github.com URL (e.g. https://github.com/o/r/blob/main/src/x.ts)",
        },
        path: { type: "string", description: "File or directory path in the repo (omit for the README)" },
        ref: { type: "string", description: "Branch, tag or commit (default: the repo's default branch)" },
        find: { type: "string", description: "Return only the parts of the file that mention this text" },
        maxChars: { type: "number", description: "Max characters to return (500–50000, default 12000)", default: 12000 },
        offset: { type: "number", description: "Character offset to continue a long file from", default: 0 },
      },
      required: ["repo"],
    },
  },
  {
    name: "web_access_status",
    description:
      "Show web-access configuration and health: Exa/Tavily keys (masked) and where they come from, keys on cooldown, Tavily remaining credits, today's spend vs. daily budgets, default provider and cache stats. Use when searches fail or to check quota.",
    annotations: readOnly("web-access status"),
    inputSchema: { type: "object", properties: {} },
  },
];

// ── Search ───────────────────────────────────────────────────

function clampNum(v, def, min, max) {
  const n = Number(v);
  return Math.min(Math.max(Number.isFinite(n) && n > 0 ? Math.floor(n) : def, min), max);
}

/** query + queries → unique, non-empty list (max MAX_QUERIES). */
function collectQueries(args) {
  const list = [args.query, ...(Array.isArray(args.queries) ? args.queries : [])]
    .map((q) => (typeof q === "string" ? q.trim() : ""))
    .filter(Boolean);
  return [...new Set(list)].slice(0, MAX_QUERIES);
}

function requireQuery(args) {
  if (!args.query || !String(args.query).trim()) throw new Error("Search query is required");
}

function hasFilters(args) {
  return !!(
    args.site ||
    args.recency ||
    args.startDate ||
    args.endDate ||
    (Array.isArray(args.excludeSite) ? args.excludeSite.length : args.excludeSite)
  );
}

/** Map an Exa category to the closest Tavily topic (for fallbacks / both mode). */
function tavilyTopicFor(args) {
  if (args.topic) return args.topic;
  if (args.category === "news") return "news";
  if (args.category === "financial report") return "finance";
  return undefined;
}

async function runExa(args) {
  const { items, via } = await exaSearch(args);
  return { source: "exa", items, via };
}

async function runTavily(args, { withAnswer = false } = {}) {
  const data = await tavilySearch({
    query: args.query,
    maxResults: args.numResults || 5,
    site: args.site,
    excludeSite: args.excludeSite,
    recency: args.recency,
    startDate: args.startDate,
    endDate: args.endDate,
    searchDepth: args.searchDepth,
    topic: tavilyTopicFor(args),
    includeAnswer: withAnswer,
  });
  return { source: "tavily", items: tavilyItems(data), answer: data?.answer || "" };
}

/** Exa /answer, only when asked and an Exa key exists; never fails the search. */
function maybeExaAnswer(args) {
  if (!args.includeAnswer || !hasExaKeys()) return Promise.resolve(null);
  return exaAnswer(args.query).catch((err) => {
    console.error(`[web_search] Exa answer failed: ${err.message}`);
    return null;
  });
}

function renderAnswers(answers) {
  const real = answers.filter((a) => a && a.text);
  if (!real.length) return "";
  return real
    .map((a) => {
      const bits = [real.length > 1 ? a.source : "", a.query ? `“${a.query}”` : ""].filter(Boolean);
      let out = `**Answer${bits.length ? ` (${bits.join(", ")})` : ""}:** ${a.text.trim()}`;
      if (a.citations?.length) {
        out += `\n\nSources: ${a.citations
          .slice(0, 5)
          .map((c, i) => `[${i + 1}](${c.url})`)
          .join(" ")}`;
      }
      return out;
    })
    .join("\n\n");
}

function perDomainLimit(args) {
  if (args.site) return 0;
  return args.maxPerDomain === undefined || args.maxPerDomain === null ? DEFAULT_PER_DOMAIN : Number(args.maxPerDomain);
}

function renderSearch({ answers = [], items, showSources = false, showQueries = false, notes = [], header = "", args }) {
  const parts = [];
  if (header) parts.push(header);
  const ans = renderAnswers(answers);
  if (ans) parts.push(ans);
  const capped = capPerDomain(items, perDomainLimit(args));
  parts.push(formatItems(capped, { maxCharsPerResult: args.maxCharsPerResult, showSources, showQueries }));
  const allNotes = [...notes];
  if (capped.length < items.length) {
    allNotes.push(`${items.length - capped.length} more result(s) from already-listed domains hidden (maxPerDomain)`);
  }
  if (allNotes.length) parts.push(`_Note: ${allNotes.join("; ")}_`);
  return parts.join("\n\n---\n\n");
}

/** Exa + Tavily in parallel for one query → { answers, items, notes, showSources }. */
async function searchBoth(args) {
  const limit = clampNum(args.numResults, 5, 1, 10);
  const tavilyEnabled = tavilyAvailable("/search");
  const [exa, tavily, exaAns] = await Promise.allSettled([
    runExa(args),
    tavilyEnabled ? runTavily(args, { withAnswer: !!args.includeAnswer }) : Promise.resolve(null),
    maybeExaAnswer(args),
  ]);

  const lists = [];
  const notes = [];
  if (!tavilyEnabled) notes.push("Tavily skipped (no API key configured) — Exa results only");
  if (exa.status === "fulfilled") lists.push(exa.value);
  else notes.push(`Exa failed: ${exa.reason?.message}`);
  if (tavily.status === "fulfilled" && tavily.value) lists.push(tavily.value);
  else if (tavilyEnabled) notes.push(`Tavily failed: ${tavily.reason?.message}`);

  if (lists.length === 0) throw new Error(`All providers failed — ${notes.join("; ")}`);

  const answers = [
    tavily.status === "fulfilled" && tavily.value?.answer ? { source: "Tavily", text: tavily.value.answer } : null,
    exaAns.status === "fulfilled" && exaAns.value
      ? { source: "Exa", text: exaAns.value.answer, citations: exaAns.value.citations }
      : null,
  ].filter(Boolean);
  return { answers, items: mergeResults(lists, limit * 2), notes, showSources: true };
}

/** Run primary, fall back to secondary on error. */
async function withFallback(primary, secondary, label) {
  try {
    return await primary();
  } catch (err) {
    console.error(`[web_search] ${label} failed (${err.message}), falling back`);
    return await secondary();
  }
}

/** One query with the configured provider strategy → { answers, items, notes, showSources }. */
async function searchOnce(args) {
  const provider = String(args.provider || getDefaultProvider()).toLowerCase();
  if (provider === "both") return await searchBoth(args);

  const tavilyOn = tavilyAvailable("/search");
  const exa = () => runExa(args);
  const tavily = () => runTavily(args, { withAnswer: !!args.includeAnswer });
  const notes = [];

  let order; // [primary, secondary|null]
  if (provider === "exa" || !tavilyOn) {
    order = [exa, null];
    if (provider === "tavily") notes.push("Tavily requested but no Tavily API key is configured — used Exa instead");
  } else if (provider === "tavily") {
    order = [tavily, exa];
  } else if (hasFilters(args) && !hasExaKeys() && !args.category) {
    // auto: keyless Exa can only take filters as query hints, Tavily has
    // native ones — so prefer Tavily for filtered queries.
    order = [tavily, exa];
  } else {
    order = [exa, tavily];
  }

  // Exa answer runs in parallel with the search when the result comes from Exa.
  const exaAnsP = order[0] === exa ? maybeExaAnswer(args) : Promise.resolve(null);
  const result = order[1]
    ? await withFallback(order[0], order[1], order[0] === exa ? "Exa" : "Tavily")
    : await order[0]();

  const answers = [];
  if (result.source === "tavily" && result.answer) answers.push({ source: "Tavily", text: result.answer });
  const ea = await exaAnsP;
  if (ea) answers.push({ source: "Exa", text: ea.answer, citations: ea.citations });
  if (args.includeAnswer && !answers.length) {
    notes.push("no AI answer available (needs a Tavily or Exa API key)");
  }
  return { answers, items: result.items, notes, showSources: false };
}

async function handleWebSearch(args) {
  const queries = collectQueries(args);
  if (!queries.length) throw new Error("Search query is required ('query' or 'queries')");

  if (queries.length === 1) {
    const r = await searchOnce({ ...args, query: queries[0] });
    return renderSearch({ ...r, args });
  }

  // Several queries: run in parallel, merge with rank fusion across queries.
  const settled = await Promise.allSettled(queries.map((q) => searchOnce({ ...args, query: q })));
  const lists = [];
  const answers = [];
  const notes = [];
  let showSources = false;
  settled.forEach((s, i) => {
    const q = queries[i];
    if (s.status === "fulfilled") {
      lists.push({ source: String(i + 1), items: s.value.items });
      answers.push(...s.value.answers.map((a) => ({ ...a, query: q })));
      notes.push(...s.value.notes.map((n) => `query ${i + 1}: ${n}`));
      showSources = showSources || s.value.showSources;
    } else {
      notes.push(`query ${i + 1} failed: ${s.reason?.message}`);
    }
  });
  if (!lists.length) throw new Error(`All queries failed — ${notes.join("; ")}`);

  const per = clampNum(args.numResults, 5, 1, 10);
  const items = mergeResults(lists, Math.min(per * queries.length, 25), { tag: "queries" });
  const header = `_${queries.length} queries: ${queries.map((q, i) => `${i + 1}. “${q}”`).join(" · ")}_`;
  return renderSearch({ answers, items, notes, showSources, showQueries: true, header, args });
}

async function handleExaSearch(args) {
  requireQuery(args);
  const r = await runExa(args);
  return renderSearch({ items: r.items, args });
}

async function handleTavilySearch(args) {
  requireQuery(args);
  const r = await runTavily(args, { withAnswer: !!args.includeAnswer });
  return renderSearch({ answers: r.answer ? [{ source: "Tavily", text: r.answer }] : [], items: r.items, args });
}

// ── Extract / map / crawl ────────────────────────────────────

function cleanUrls(urls, max) {
  if (typeof urls === "string") urls = [urls];
  if (!Array.isArray(urls) || urls.length === 0) throw new Error("At least one URL is required");
  const valid = [...new Set(urls.map((u) => String(u).trim()).filter((u) => /^https?:\/\//i.test(u)))].slice(0, max);
  if (valid.length === 0) throw new Error("Valid URL(s) required (http:// or https://)");
  return valid;
}

async function handleTavilyExtract(args) {
  const urls = cleanUrls(args.urls ?? args.url, 20);
  const data = await tavilyExtract(urls, { extractDepth: args.extractDepth || "basic" });
  return formatTavilyExtract(data, { maxChars: clampNum(args.maxCharsPerPage, 8000, 500, 50000) });
}

function crawlOpts(args, defaultLimit, maxLimit) {
  const [url] = cleanUrls(args.url, 1);
  return {
    url,
    instructions: args.instructions,
    maxDepth: clampNum(args.maxDepth, 1, 1, 5),
    limit: clampNum(args.limit, defaultLimit, 1, maxLimit),
    selectPaths: args.selectPaths,
    excludePaths: args.excludePaths,
    allowExternal: args.allowExternal === true,
    extractDepth: args.extractDepth,
  };
}

async function handleMap(args) {
  const data = await tavilyMap(crawlOpts(args, 50, 500));
  const urls = data?.results || [];
  if (!urls.length) return `No pages found for ${args.url}.`;
  return [
    `## Site map: ${data.base_url || args.url}`,
    `_${urls.length} URL(s)_`,
    urls.map((u) => `- ${u}`).join("\n"),
  ].join("\n\n");
}

async function handleCrawl(args) {
  const data = await tavilyCrawl(crawlOpts(args, 10, 50));
  const pages = data?.results || [];
  if (!pages.length) return `No pages crawled for ${args.url}.`;
  const per = clampNum(args.maxCharsPerPage, 3000, 200, 20000);
  const { texts, removed } = stripRepeatedLines(pages.map((p) => cleanExtracted(p.raw_content)));
  const note = removed ? `; ${removed} line(s) repeated across pages removed` : "";
  const header = `## Crawl: ${data.base_url || args.url}\n\n_${pages.length} page(s)${note}; read any page in full with web_get_contents_`;
  const body = pages
    .map((p, i) => `### ${p.url}\n\n${truncate(texts[i], per) || "_(no content)_"}`)
    .join("\n\n---\n\n");
  return `${header}\n\n${body}`;
}

// ── Page contents ────────────────────────────────────────────

// Below this many characters a direct fetch is probably a JS-rendered shell
const MIN_USEFUL_CHARS = 300;

/**
 * Load the full readable content of a URL as Markdown: { title, text, via }.
 * 1. Direct fetch (free; usually cleanest for static HTML).
 * 2. Tavily Extract (with a key): fetch failures/blocks, PDFs & other
 *    documents, thin JS-rendered pages.
 * 3. Exa /contents (with an Exa key): same cases when Tavily is unavailable
 *    or failed.
 * Internal addresses are refused and never forwarded to a provider.
 */
async function loadDocument(url) {
  let direct = null;
  let directErr = null;
  try {
    direct = await fetchDocument(url);
  } catch (err) {
    if (err instanceof BlockedUrlError) throw err;
    directErr = err;
  }

  if (direct && direct.text.length >= MIN_USEFUL_CHARS) return { ...direct, via: "direct" };

  const why = directErr ? `failed (${directErr.message})` : "returned very little text";
  const errors = directErr ? [`Direct fetch: ${directErr.message}`] : [];

  if (tavilyAvailable("/extract")) {
    console.error(`[web_get_contents] Direct fetch ${why}, trying Tavily Extract`);
    try {
      const data = await tavilyExtract([url]);
      const text = cleanExtracted(data?.results?.[0]?.raw_content);
      if (text) return { title: "", text, via: "tavily" };
      errors.push(`Tavily Extract: ${data?.failed_results?.[0]?.error || "no content"}`);
    } catch (err) {
      errors.push(`Tavily Extract: ${err.message}`);
    }
  }

  if (hasExaKeys()) {
    console.error(`[web_get_contents] Trying Exa contents for ${url}`);
    try {
      const r = await exaContents(url);
      return { title: r.title, text: r.text, via: "exa" };
    } catch (err) {
      errors.push(`Exa: ${err.message}`);
    }
  }

  if (direct) return { ...direct, via: "direct" };
  if (directErr instanceof UnsupportedContentError && errors.length === 1) {
    throw new Error(`${directErr.message}. Configure a Tavily API key (or an Exa key) to read PDFs and other documents.`);
  }
  throw new Error(errors.join("; "));
}

async function readOne(url, args, maxChars) {
  // The whole document is cached once, so paging (offset) or searching (find)
  // a long page does not download it again.
  const doc = args.fresh
    ? await loadDocument(url)
    : await cache.cached("__document", { url: url.trim() }, () => loadDocument(url));

  const text = args.format === "text" ? stripLinks(doc.text) : doc.text;
  const offset = Math.max(0, Math.floor(Number(args.offset) || 0));
  const head = [`## Content from: ${url}`];
  if (doc.title && offset === 0 && !args.find) head.push(`# ${doc.title}`);
  const meta = [];
  if (doc.via && doc.via !== "direct") meta.push(`via ${doc.via === "tavily" ? "Tavily Extract" : "Exa"}`);
  if (doc.bytesCut) meta.push(`download stopped at ${Math.round(doc.bytesCut / 1048576)} MB`);
  if (meta.length) head.push(`_(${meta.join(" · ")})_`);
  const body = args.find ? findInText(text, args.find, { maxChars }) : paginate(text, { offset, maxChars });
  return `${head.join("\n\n")}\n\n${body}`;
}

async function handleGetContents(args) {
  const extra = Array.isArray(args.urls) ? args.urls : typeof args.urls === "string" ? [args.urls] : [];
  const urls = [...new Set([args.url, ...extra].map((u) => (typeof u === "string" ? u.trim() : "")).filter(Boolean))];
  if (!urls.length) throw new Error("Valid URL is required (http:// or https://)");
  const bad = urls.find((u) => !/^https?:\/\//i.test(u));
  if (bad) throw new Error(`Valid URL is required (http:// or https://): ${bad}`);
  if (urls.length > MAX_URLS) throw new Error(`At most ${MAX_URLS} URLs per call (got ${urls.length})`);

  if (urls.length === 1) return await readOne(urls[0], args, clampNum(args.maxChars, 8000, 500, 50000));

  const per = clampNum(args.maxChars, Math.max(2000, Math.floor(24000 / urls.length)), 500, 50000);
  const settled = await Promise.allSettled(urls.map((u) => readOne(u, args, per)));
  if (settled.every((s) => s.status === "rejected")) {
    throw new Error(settled.map((s, i) => `${urls[i]}: ${s.reason?.message}`).join("; "));
  }
  return settled
    .map((s, i) => (s.status === "fulfilled" ? s.value : `## Failed: ${urls[i]}\n\n${s.reason?.message}`))
    .join("\n\n---\n\n");
}

// ── GitHub ───────────────────────────────────────────────────

async function handleGithubSearch(args) {
  const { query, type = "repositories", sort, order, perPage = 5 } = args;
  if (!query || query.trim().length === 0) throw new Error("Search query is required");
  const result = await searchGithub(query, { type, sort, order, perPage });
  return `## GitHub ${type} search: "${query}"\n\n${result}`;
}

async function handleGithubRead(args) {
  const r = await readGithub(args.repo, { path: args.path, ref: args.ref });
  const maxChars = clampNum(args.maxChars, 12000, 500, 50000);
  const offset = Math.max(0, Math.floor(Number(args.offset) || 0));
  const body = args.find ? findInText(r.text, args.find, { maxChars }) : paginate(r.text, { offset, maxChars });
  return `## ${r.title}\n\n${body}`;
}

// ── Status ───────────────────────────────────────────────────

const USAGE_TTL_MS = 10 * 60 * 1000; // Tavily /usage allows 10 requests per 10 minutes
const _usageCache = new Map(); // key → { at, data | error }

async function tavilyUsageCached(key) {
  const hit = _usageCache.get(key);
  if (hit && Date.now() - hit.at < USAGE_TTL_MS) return hit;
  let entry;
  try {
    entry = { at: Date.now(), data: await tavilyUsage(key) };
  } catch (err) {
    entry = { at: Date.now(), error: err.message };
  }
  _usageCache.set(key, entry);
  return entry;
}

function fmtCredits(used, limit) {
  return limit === null || limit === undefined ? `${used ?? "?"} used (no limit)` : `${used ?? "?"} / ${limit} used`;
}

async function handleStatus() {
  const exaKeys = loadExaKeys();
  const tavilyKeys = loadTavilyKeys();
  const cfg = loadConfig();
  const c = cache.stats();
  const spend = exaSpend();

  const lines = [
    "## web-access status",
    "",
    `**Config file:** \`${configPath()}\``,
    `**Default provider:** ${getDefaultProvider()}`,
    "",
    `**Exa:** ${
      exaKeys.length ? `${exaKeys.length} key(s) from ${exaKeySource()} · REST API` : "keyless (anonymous MCP endpoint)"
    }` + (exaKeys.length ? ` · keyless fallback ${cfg?.exa?.keylessFallback === false ? "off" : "on"}` : ""),
  ];
  for (const r of describeKeys("exa", exaKeys)) lines.push(`  - \`${r.key}\` — ${r.state}`);
  if (spend.requests) lines.push(`  - spend this session: $${spend.total.toFixed(4)} over ${spend.requests} request(s)`);
  if (exaKeys.length) lines.push(`  - ${budget.describe("exa")}`);

  lines.push(
    "",
    `**Tavily:** ${
      tavilyKeys.length
        ? `${tavilyKeys.length} key(s) from ${tavilyKeySource()}`
        : tavilyKeyless()
          ? "keyless mode (search/extract only, rate-limited per IP)"
          : "disabled — requires an API key (tvly-...); add one with /web-access:setup"
    }`
  );
  if (tavilyKeys.length) {
    const rows = describeKeys("tavily", tavilyKeys);
    const usages = await Promise.all(tavilyKeys.map((k) => tavilyUsageCached(k)));
    let account = null;
    rows.forEach((r, i) => {
      const u = usages[i];
      const credits = u.data?.key ? ` · credits ${fmtCredits(u.data.key.usage, u.data.key.limit)}` : "";
      const err = u.error ? ` · usage unavailable (${u.error})` : "";
      lines.push(`  - \`${r.key}\` — ${r.state}${credits}${err}`);
      if (!account && u.data?.account) account = u.data.account;
    });
    if (account) {
      lines.push(
        `  - account plan: ${account.current_plan ?? "?"} · plan ${fmtCredits(account.plan_usage, account.plan_limit)}` +
          (account.paygo_limit ? ` · pay-as-you-go ${fmtCredits(account.paygo_usage, account.paygo_limit)}` : "")
      );
    }
  }
  if (tavilyKeys.length || tavilyKeyless()) lines.push(`  - ${budget.describe("tavily")}`);

  lines.push(
    "",
    `**State file (cooldowns, daily spend):** ${stateFile() ? `\`${stateFile()}\`` : "memory only"}`,
    `**Cache:** ${
      c.ttlSeconds
        ? `${c.entries} entries, TTL ${c.ttlSeconds}s, ${c.hits} hit(s) / ${c.misses} miss(es)` +
          (c.shared ? `, ${c.shared} duplicate in-flight call(s) shared` : "") +
          (c.file ? ` · persisted to \`${c.file}\`` : "")
        : "disabled"
    }`
  );
  return lines.join("\n");
}

// ── Dispatch ─────────────────────────────────────────────────

const CACHEABLE = {
  web_search: handleWebSearch,
  web_search_exa: handleExaSearch,
  web_search_tavily: handleTavilySearch,
  web_extract_tavily: handleTavilyExtract,
  web_map: handleMap,
  web_crawl: handleCrawl,
  github_read: handleGithubRead,
};

async function dispatchTool(toolName, args = {}) {
  const handler = CACHEABLE[toolName];
  if (handler) {
    const { fresh, ...keyArgs } = args;
    if (fresh || args.livecrawl === "always") return await handler(args);
    return await cache.cached(toolName, keyArgs, () => handler(args));
  }
  if (toolName === "web_get_contents") return await handleGetContents(args); // caches documents internally
  if (toolName === "web_access_status") return await handleStatus();
  if (toolName === "github_search") return await handleGithubSearch(args);
  throw new Error(`Unknown tool: ${toolName}`);
}

module.exports = { TOOLS, dispatchTool, maskKey };
