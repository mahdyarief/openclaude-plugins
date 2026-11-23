const { keysInRotationOrder, hasKeys } = require("./tavily-rotator");
const { loadConfig } = require("./config");
const { markFailure, markSuccess, shouldRotate } = require("./key-health");
const { formatItems, toList } = require("./formatter");
const budget = require("./budget");

const TAVILY_API = "https://api.tavily.com";
// Endpoints Tavily serves in keyless mode (opt-in: "tavily": { "keyless": true }).
const KEYLESS_ENDPOINTS = new Set(["/search", "/extract"]);

function keylessEnabled() {
  return loadConfig()?.tavily?.keyless === true;
}

/** Can this Tavily endpoint be used right now (keys, or opt-in keyless mode)? */
function tavilyAvailable(endpoint = "/search") {
  return hasKeys() || (keylessEnabled() && KEYLESS_ENDPOINTS.has(endpoint));
}

/** Credits for a call: what Tavily reports (include_usage), else an estimate. */
function creditsUsed(endpoint, payload, data) {
  const reported = Number(data?.usage?.credits);
  if (Number.isFinite(reported)) return reported;
  const adv = payload.search_depth === "advanced" || payload.extract_depth === "advanced" ? 2 : 1;
  const n = (data?.results || []).length;
  if (endpoint === "/search") return adv;
  if (endpoint === "/extract") return Math.ceil(n / 5) * adv;
  const map = Math.ceil(n / 10) * (payload.instructions ? 2 : 1);
  return endpoint === "/crawl" ? map + Math.ceil(n / 5) * adv : map;
}
const DEFAULT_DEADLINE_MS = 45000; // total budget across all keys
const MAX_ATTEMPT_MS = 30000;

class RetryableError extends Error {}

/**
 * POST to a Tavily endpoint, rotating through healthy keys.
 * Without keys, only the opt-in keyless mode ("tavily": { "keyless": true })
 * is available, for /search and /extract.
 * Key/quota errors put the key on cooldown and try the next one; 5xx and
 * network errors try the next key; anything else fails fast.
 */
async function callTavily(endpoint, payload, { deadlineMs } = {}) {
  const keyless = !hasKeys() && keylessEnabled() && KEYLESS_ENDPOINTS.has(endpoint);
  if (!hasKeys() && !keyless) {
    throw new Error(
      "No Tavily API keys configured. Run /plugin configure web-access@mahdyarief " +
        '(or add {"tavily": {"keys": ["tvly-..."]}} to ~/.openclaude/web-access.json, or set TAVILY_API_KEYS).'
    );
  }
  budget.assertBudget("tavily");
  payload = { ...payload, include_usage: true };

  if (keyless) {
    const cfgTimeout = Number(loadConfig()?.tavily?.timeoutMs);
    const t = deadlineMs || (cfgTimeout > 0 ? cfgTimeout : DEFAULT_DEADLINE_MS);
    const data = await attemptOnce(endpoint, payload, null, t);
    budget.record("tavily", creditsUsed(endpoint, payload, data));
    return data;
  }

  const keys = keysInRotationOrder();
  if (keys.length === 0) {
    throw new Error("All Tavily keys are cooling down (rate-limited or out of credits).");
  }

  const cfgTimeout = Number(loadConfig()?.tavily?.timeoutMs);
  const total = deadlineMs || (cfgTimeout > 0 ? cfgTimeout : DEFAULT_DEADLINE_MS);
  const deadline = Date.now() + total;
  let lastError = null;

  for (let i = 0; i < keys.length; i++) {
    const key = keys[i];
    const remaining = deadline - Date.now();
    if (remaining < 1000) {
      lastError = new Error(`Tavily request timed out after ${total}ms (${i} attempt(s))`);
      break;
    }
    try {
      const data = await attemptOnce(endpoint, payload, key, Math.min(remaining, Math.max(MAX_ATTEMPT_MS, total / 2)));
      markSuccess("tavily", key);
      budget.record("tavily", creditsUsed(endpoint, payload, data));
      return data;
    } catch (err) {
      if (!(err instanceof RetryableError)) throw err;
      lastError = err;
      if (i < keys.length - 1) console.error(`[tavily] Key #${i + 1}: ${err.message} — trying next key...`);
    }
  }
  throw lastError || new Error("Tavily request failed");
}

async function attemptOnce(endpoint, payload, key, timeoutMs) {
  let response;
  try {
    response = await fetch(`${TAVILY_API}${endpoint}`, {
      method: "POST",
      headers: key
        ? { "Content-Type": "application/json", Authorization: `Bearer ${key}` }
        : { "Content-Type": "application/json", "X-Tavily-Access-Mode": "keyless" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (err) {
    throw new RetryableError(`Tavily network error: ${err.message}`);
  }

  if (!response.ok) {
    const msg = `Tavily error ${response.status}: ${(await response.text()).slice(0, 300)}`;
    if (key && shouldRotate(response.status)) {
      markFailure("tavily", key, response.status, { retryAfter: response.headers?.get?.("retry-after") });
      throw new RetryableError(msg);
    }
    if (!key && (response.status === 429 || response.status === 402 || response.status === 432)) {
      throw new Error(`${msg} — Tavily keyless mode is rate-limited per IP; add a Tavily key for reliable access.`);
    }
    if (response.status >= 500) throw new RetryableError(msg);
    throw new Error(msg);
  }
  return await response.json();
}

/**
 * Tavily web search.
 * @param {object} opts
 *   query, maxResults, site, recency (day|week|month|year),
 *   searchDepth (basic|advanced), topic (general|news|finance),
 *   includeAnswer (bool), includeRawContent (bool)
 */
async function tavilySearch(opts) {
  const payload = {
    query: opts.query,
    max_results: Math.min(Math.max(Number(opts.maxResults) || 5, 1), 20),
    search_depth: opts.searchDepth || "basic",
    topic: opts.topic || "general",
    include_answer: opts.includeAnswer ?? false,
    include_raw_content: opts.includeRawContent ?? false,
    include_published_date: true,
  };
  const include = toList(opts.site);
  const exclude = toList(opts.excludeSite);
  if (include.length) payload.include_domains = include;
  if (exclude.length) payload.exclude_domains = exclude;
  if (opts.startDate || opts.endDate) {
    if (opts.startDate) payload.start_date = String(opts.startDate).trim();
    if (opts.endDate) payload.end_date = String(opts.endDate).trim();
  } else if (opts.recency) {
    payload.time_range = opts.recency;
  }

  return callTavily("/search", payload);
}

/**
 * Tavily map — list the URLs of a site (no content). Requires a key.
 * 1 credit per 10 pages (2 with instructions).
 */
async function tavilyMap(opts) {
  const payload = { url: opts.url, max_depth: opts.maxDepth || 1, limit: opts.limit || 50 };
  if (opts.instructions) payload.instructions = opts.instructions;
  if (opts.selectPaths?.length) payload.select_paths = opts.selectPaths;
  if (opts.excludePaths?.length) payload.exclude_paths = opts.excludePaths;
  payload.allow_external = opts.allowExternal === true;
  return callTavily("/map", payload, { deadlineMs: 160000 });
}

/**
 * Tavily crawl — map + extract pages of a site in one call. Requires a key.
 * Cost ≈ map cost + extract cost (e.g. 10 pages basic ≈ 3 credits).
 */
async function tavilyCrawl(opts) {
  const payload = {
    url: opts.url,
    max_depth: opts.maxDepth || 1,
    limit: opts.limit || 10,
    extract_depth: opts.extractDepth || "basic",
    format: "markdown",
    allow_external: opts.allowExternal === true,
  };
  if (opts.instructions) payload.instructions = opts.instructions;
  if (opts.selectPaths?.length) payload.select_paths = opts.selectPaths;
  if (opts.excludePaths?.length) payload.exclude_paths = opts.excludePaths;
  return callTavily("/crawl", payload, { deadlineMs: 160000 });
}

/**
 * Tavily credit usage for one key: GET /usage (rate limit: 10 req / 10 min).
 * Not rotated — it reports on the specific key passed in.
 */
async function tavilyUsage(key) {
  const response = await fetch(`${TAVILY_API}/usage`, {
    headers: { Authorization: `Bearer ${key}` },
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error(`Tavily usage error ${response.status}`);
  return response.json();
}

/**
 * Tavily extract — fetch clean content from one or more URLs.
 */
async function tavilyExtract(urls, { extractDepth = "basic" } = {}) {
  return callTavily(
    "/extract",
    { urls: Array.isArray(urls) ? urls : [urls], extract_depth: extractDepth },
    { deadlineMs: 90000 }
  );
}

// ── Formatting ─────────────────────────────────────────────────

/** Tavily search response → shared result items. */
function tavilyItems(data) {
  return (data?.results || []).map((r) => ({
    title: r.title,
    url: r.url,
    published: r.published_date || "",
    content: r.raw_content || r.content || "",
    score: typeof r.score === "number" ? r.score : undefined,
  }));
}

function formatTavilySearch(data, opts = {}) {
  const parts = [];
  if (data?.answer) parts.push(`**Answer:** ${data.answer.trim()}`);
  const items = tavilyItems(data);
  if (items.length === 0 && parts.length === 0) return "No results found.";
  if (items.length) parts.push(formatItems(items, opts));
  return parts.join("\n\n---\n\n");
}

/** Strip image markup and navigation-only lines (in-page anchors, skip links). */
function cleanExtracted(md) {
  return (md || "")
    .replace(/\[(\s*!\[[^\]]*\]\([^)]*\)\s*)+\]\([^)]*\)/g, "") // linked images
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "") // images
    .split("\n")
    .filter((line) => {
      const t = line.trim();
      if (!t) return true;
      // drop lines that are nothing but links to in-page anchors / site search
      const rest = t
        .replace(/^[*+\-\s]+/, "")
        .replace(/\[[^\]]*\]\((#|\/wiki\/Special:)[^)]*\)/g, "")
        .trim();
      return rest.length > 0;
    })
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function formatTavilyExtract(data, { maxChars = 8000 } = {}) {
  const parts = [];
  for (const r of data?.results || []) {
    const text = cleanExtracted(r.raw_content);
    const more = text.length > maxChars ? `\n\n[… truncated at ${maxChars} characters]` : "";
    parts.push(`## Content from: ${r.url}\n\n${text.slice(0, maxChars)}${more}`);
  }
  for (const f of data?.failed_results || []) {
    parts.push(`## Failed: ${f.url}\n\n${f.error || "unknown error"}`);
  }
  return parts.length ? parts.join("\n\n---\n\n") : "No content extracted.";
}

module.exports = {
  callTavily,
  tavilySearch,
  tavilyExtract,
  formatTavilySearch,
  formatTavilyExtract,
  cleanExtracted,
  tavilyItems,
  tavilyMap,
  tavilyCrawl,
  tavilyUsage,
  tavilyAvailable,
  keylessEnabled,
};
