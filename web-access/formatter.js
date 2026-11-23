/**
 * Result model shared by all providers, merging and formatting.
 *
 * Every provider is normalized to items of the form
 *   { title, url, published, content, score? }
 * so formatting, compact output and multi-provider merging work the same way.
 */

const DEFAULT_SNIPPET_CHARS = 1200;
const RRF_K = 60; // standard Reciprocal Rank Fusion constant

/** Clamp the per-result snippet length requested by the caller. */
function snippetLimit(v) {
  const n = Number(v);
  if (!Number.isFinite(n) || n <= 0) return DEFAULT_SNIPPET_CHARS;
  return Math.min(Math.max(Math.floor(n), 100), 10000);
}

/** Cut text at a word boundary close to max, marking the cut with "…". */
function truncate(text, max) {
  const t = (text || "").trim();
  if (t.length <= max) return t;
  const cut = t.slice(0, max);
  const space = cut.lastIndexOf(" ");
  return `${(space > max * 0.7 ? cut.slice(0, space) : cut).trimEnd()} …`;
}

function cleanDate(v) {
  const d = (v || "").trim();
  if (/^(n\/?a|null|undefined|unknown|none)?$/i.test(d)) return "";
  // ISO timestamps → date only; RFC dates ("Fri, 30 Jan 2026 00:00:00 GMT") → YYYY-MM-DD
  const iso = d.match(/^(\d{4}-\d{2}-\d{2})(?:T|$)/);
  if (iso) return iso[1];
  const t = Date.parse(d);
  if (!Number.isNaN(t) && /\b\d{4}\b/.test(d)) return new Date(t).toISOString().slice(0, 10);
  return d;
}

/**
 * Parse Exa MCP's text output into items. (The REST client returns JSON and
 * does not need this.)
 */
function parseExaResults(raw) {
  if (!raw || !raw.trim()) return [];
  return raw
    .split(/\n---+\n/)
    .map((block) => {
      const title = block.match(/Title:\s*(.+)/)?.[1]?.trim();
      if (!title) return null;
      const highlights = block.match(/Highlights:\s*([\s\S]*?)(?=\n\w+:|$)/)?.[1]?.trim();
      return {
        title,
        url: block.match(/URL:\s*(.+)/)?.[1]?.trim() || "",
        published: cleanDate(block.match(/Published:\s*(.+)/)?.[1]),
        content: highlights || extractedContent(block),
      };
    })
    .filter(Boolean);
}

function extractedContent(block) {
  return block
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && !/^(Title|URL|Published|Author|Highlights):/i.test(l))
    .join("\n")
    .trim();
}

function normalizeUrl(url) {
  try {
    const u = new URL(url);
    u.hash = "";
    for (const k of [...u.searchParams.keys()]) {
      if (/^(utm_|ref$|fbclid$|gclid$)/i.test(k)) u.searchParams.delete(k);
    }
    const host = u.hostname.replace(/^www\./, "");
    return `${host}${u.pathname.replace(/\/+$/, "")}${u.search}`.toLowerCase();
  } catch {
    return (url || "").trim().toLowerCase();
  }
}

/**
 * Merge ranked lists from several providers with Reciprocal Rank Fusion:
 * score(url) = Σ 1 / (K + rank), K = 60. Agreement between providers is a
 * strong relevance signal: with K = 60 a result found by both ranks above any
 * single-provider result (top-10 lists). Single-provider results are then
 * interleaved fairly by rank (e#1, t#1, e#2, t#2, …).
 * Duplicates are detected by normalized URL; the longer snippet is kept.
 *
 * lists: [{ source: "exa", items: [...] }, { source: "tavily", items: [...] }]
 * opts.tag: field that records which lists contained a result ("sources" for
 * providers, "queries" when merging several queries). Provider sources of
 * already-merged items are kept and unioned.
 */
function mergeResults(lists, limit, { tag = "sources" } = {}) {
  const byUrl = new Map();
  let order = 0;
  for (const { source, items } of lists) {
    items.forEach((item, rank) => {
      const key = normalizeUrl(item.url) || `${source}:${rank}`;
      let entry = byUrl.get(key);
      if (!entry) {
        entry = { ...item, [tag]: [], rrf: 0, firstSeen: order++ };
        if (tag !== "sources" && item.sources) entry.sources = [...item.sources];
        byUrl.set(key, entry);
      } else {
        if (!entry.published && item.published) entry.published = item.published;
        if ((item.content || "").length > (entry.content || "").length) entry.content = item.content;
        if (tag !== "sources" && item.sources) entry.sources = [...new Set([...(entry.sources || []), ...item.sources])];
      }
      if (!entry[tag].includes(source)) entry[tag].push(source);
      entry.rrf += 1 / (RRF_K + rank + 1);
    });
  }
  return [...byUrl.values()]
    .sort((a, b) => b.rrf - a.rrf || a.firstSeen - b.firstSeen)
    .slice(0, limit);
}

/**
 * Render items as Markdown.
 * @param {object} opts
 *   maxCharsPerResult — snippet length per result (compact output)
 *   showSources — append "via exa + tavily" (merged results)
 */
function formatItems(items, { maxCharsPerResult, showSources = false, showQueries = false } = {}) {
  if (!items || !items.length) return "No results found.";
  const max = snippetLimit(maxCharsPerResult);
  return items
    .map((r) => {
      let out = `### [${r.title || r.url}](${r.url || ""})`;
      const meta = [
        cleanDate(r.published),
        showSources && r.sources ? `via ${r.sources.join(" + ")}` : "",
        showQueries && r.queries ? `query ${r.queries.join(", ")}` : "",
      ].filter(Boolean);
      if (meta.length) out += `\n_${meta.join(" · ")}_`;
      if (r.content) out += `\n\n${truncate(r.content, max)}`;
      return out;
    })
    .join("\n\n---\n\n");
}

/** Exa MCP text → Markdown (keyless path). */
function formatSearchResults(raw, opts = {}) {
  if (!raw || raw.trim().length === 0) return "No results found.";
  const items = parseExaResults(raw);
  return items.length ? formatItems(items, opts) : truncate(raw, snippetLimit(opts.maxCharsPerResult) * 5);
}

/** Query-text hints for backends without native filters (Exa MCP keyless). */
function buildSearchQuery(query, options) {
  let enriched = query;
  const sites = toList(options.site);
  if (sites.length) enriched = `${enriched} ${sites.map((d) => `site:${d}`).join(" OR ")}`;
  for (const d of toList(options.excludeSite)) enriched = `${enriched} -site:${d}`;
  const since = options.startDate ? isoDate(options.startDate) : recencyToDate(options.recency);
  if (since) enriched = `${enriched} after:${since.slice(0, 10)}`;
  if (options.endDate) enriched = `${enriched} before:${isoDate(options.endDate).slice(0, 10)}`;
  return enriched;
}

/** "a.com, b.com" | ["a.com"] | undefined → ["a.com", "b.com"] (bare domains). */
function toList(v) {
  const arr = Array.isArray(v) ? v : typeof v === "string" ? v.split(",") : [];
  return arr
    .map((d) => String(d).trim().replace(/^https?:\/\//i, "").replace(/\/.*$/, ""))
    .filter(Boolean);
}

/** "2025-01-31" → ISO timestamp (start of day, or end of day with endOfDay). */
function isoDate(v, endOfDay = false) {
  const d = String(v || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d) || Number.isNaN(Date.parse(d))) {
    throw new Error(`Invalid date "${d}" — use YYYY-MM-DD`);
  }
  return `${d}T${endOfDay ? "23:59:59.999" : "00:00:00.000"}Z`;
}

function domainOf(url) {
  try {
    return new URL(url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return "";
  }
}

/** Keep at most n results per domain (n <= 0 → unlimited). Order is preserved. */
function capPerDomain(items, n) {
  if (!(n > 0)) return items;
  const seen = new Map();
  return items.filter((it) => {
    const d = domainOf(it.url);
    if (!d) return true;
    const c = (seen.get(d) || 0) + 1;
    seen.set(d, c);
    return c <= n;
  });
}

function normLine(l) {
  return l
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1") // links/images → text
    .replace(/<[^>\s]*>/g, (m) => m.slice(1, -1)) // <autolinks>
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "");
}

/**
 * Remove lines that repeat across most pages of a crawl (site banners, doc
 * indexes, cookie notices, footers). A line is dropped when it appears on at
 * least 60% of the pages (and on at least 2). Returns { texts, removed }.
 */
function stripRepeatedLines(texts) {
  if (texts.length < 2) return { texts, removed: 0 };
  const count = new Map();
  for (const t of texts) {
    for (const k of new Set(t.split("\n").map(normLine).filter((k) => k.length >= 4))) {
      count.set(k, (count.get(k) || 0) + 1);
    }
  }
  const threshold = Math.max(2, Math.ceil(texts.length * 0.6));
  const common = new Set([...count].filter(([, c]) => c >= threshold).map(([k]) => k));
  let removed = 0;
  const out = texts.map((t) =>
    t
      .split("\n")
      .filter((l) => {
        if (common.has(normLine(l))) {
          removed++;
          return false;
        }
        return true;
      })
      .filter((l, i, arr) => !/^\s*>\s*$/.test(l) || (arr[i - 1] && !/^\s*>?\s*$/.test(arr[i - 1])))
      .join("\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim()
  );
  return { texts: out, removed };
}

const RECENCY_DAYS = { day: 1, week: 7, month: 30, year: 365 };

/** "week" → ISO timestamp 7 days ago (or null). */
function recencyToDate(recency) {
  const days = RECENCY_DAYS[recency];
  return days ? new Date(Date.now() - days * 86400000).toISOString() : null;
}

module.exports = {
  toList,
  isoDate,
  domainOf,
  capPerDomain,
  stripRepeatedLines,
  formatSearchResults,
  buildSearchQuery,
  parseExaResults,
  mergeResults,
  formatItems,
  normalizeUrl,
  truncate,
  snippetLimit,
  cleanDate,
  recencyToDate,
};
