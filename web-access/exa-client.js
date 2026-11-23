/**
 * Exa client.
 *
 * - With API keys → Exa REST API (https://api.exa.ai): structured JSON, native
 *   domain/date/category filters, compact highlights, and /answer.
 * - Without keys (or when every key is exhausted and keylessFallback is on) →
 *   Exa's hosted MCP endpoint, which works anonymously with rate limits.
 *   (The REST API has no free keyless mode: it answers 402 / x402.)
 *
 * Both paths return the shared item shape { title, url, published, content }.
 */

const { keysInRotationOrder, hasKeys } = require("./exa-rotator");
const { loadConfig } = require("./config");
const { markFailure, markSuccess, shouldRotate } = require("./key-health");
const { parseExaResults, recencyToDate, snippetLimit, buildSearchQuery, toList, isoDate } = require("./formatter");
const budget = require("./budget");

const EXA_API = "https://api.exa.ai";
const EXA_MCP_URL = "https://mcp.exa.ai/mcp";

const DEFAULT_DEADLINE_MS = 45000; // total budget across all attempts
const MAX_ATTEMPT_MS = 30000; // cap for a single attempt

// Exa MCP sometimes reports quota problems inside a 200 response body.
const QUOTA_TEXT = /rate.?limit|too many requests|quota|insufficient credits|exceeded/i;

// Current Exa search categories (exa-spec.yaml). Other strings are accepted by
// Exa as hints, but these are the documented ones.
const EXA_CATEGORIES = ["company", "publication", "news", "personal site", "financial report", "people"];
// Current /search types; "neural"/"keyword" were removed from the spec and are mapped to "auto".
const EXA_TYPES = ["auto", "lite", "deep"];

// Running total of Exa REST spend reported in costDollars (this process only).
const _spend = { total: 0, requests: 0 };
function exaSpend() {
  return { ..._spend };
}

/** Error that is worth retrying with another key (or keyless). */
class RetryableError extends Error {}

function exaSettings() {
  const exa = loadConfig()?.exa || {};
  return {
    keylessFallback: exa.keylessFallback !== false,
    deadlineMs: Number(exa.timeoutMs) > 0 ? Number(exa.timeoutMs) : DEFAULT_DEADLINE_MS,
  };
}

/**
 * Run fn(key, timeoutMs) over the attempt list: healthy keys in rotation
 * order, then (optionally) a keyless attempt (key = null). Key/quota errors
 * bench the key; 5xx and network errors try the next attempt; anything else
 * fails fast. All attempts share one deadline.
 */
async function withRotation(fn, { allowKeyless }) {
  const { keylessFallback, deadlineMs } = exaSettings();
  const configured = hasKeys();
  const keys = keysInRotationOrder();

  let attempts;
  if (!configured) attempts = allowKeyless ? [null] : [];
  else attempts = keylessFallback && allowKeyless ? [...keys, null] : keys;

  if (attempts.length === 0) {
    throw new Error(
      configured
        ? "All Exa keys are cooling down (rate-limited or out of credits) and keyless fallback is unavailable."
        : "This Exa feature requires an API key (add one with /plugin configure web-access@mahdyarief or EXA_API_KEYS)."
    );
  }

  const deadline = Date.now() + deadlineMs;
  let lastError = null;
  for (let i = 0; i < attempts.length; i++) {
    const key = attempts[i];
    const remaining = deadline - Date.now();
    if (remaining < 1000) {
      lastError = new Error(`Exa request timed out after ${deadlineMs}ms (${i} attempt(s))`);
      break;
    }
    if (!key && configured) console.error("[exa] No usable key left, retrying keyless...");
    try {
      const out = await fn(key, Math.min(remaining, MAX_ATTEMPT_MS));
      markSuccess("exa", key);
      return out;
    } catch (err) {
      if (!(err instanceof RetryableError)) throw err;
      lastError = err;
      if (i < attempts.length - 1) console.error(`[exa] ${err.message} — trying next...`);
    }
  }
  throw lastError || new Error("Exa request failed");
}

/** Classify a non-OK HTTP response; benches the key when it is the key's fault. */
async function httpError(response, key) {
  let detail = "";
  try {
    const body = await response.text();
    try {
      const j = JSON.parse(body);
      detail = [j.tag, j.error].filter(Boolean).join(": ") || body;
    } catch {
      detail = body;
    }
  } catch {}
  const msg = `Exa error ${response.status}: ${String(detail).slice(0, 300)}`;
  if (key && shouldRotate(response.status)) {
    markFailure("exa", key, response.status, { retryAfter: response.headers?.get?.("retry-after") });
    return new RetryableError(msg);
  }
  if (response.status >= 500) return new RetryableError(msg);
  return new Error(msg);
}

// ── REST (keyed) ─────────────────────────────────────────────

async function restPost(endpoint, body, key, timeoutMs) {
  budget.assertBudget("exa");
  let response;
  try {
    response = await fetch(`${EXA_API}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-api-key": key },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (err) {
    throw new RetryableError(`Exa network error: ${err.message}`);
  }
  if (!response.ok) throw await httpError(response, key);
  const data = await response.json();
  const cost = Number(data?.costDollars?.total);
  if (Number.isFinite(cost)) {
    _spend.total += cost;
    _spend.requests += 1;
    budget.record("exa", cost);
  }
  return data;
}

function restSearchBody(opts) {
  const body = {
    query: opts.query,
    type: EXA_TYPES.includes(opts.type) ? opts.type : "auto",
    numResults: opts.numResults,
    contents: { highlights: { maxCharacters: opts.snippetChars } },
  };
  if (opts.category) body.category = opts.category;
  const include = toList(opts.site);
  const exclude = toList(opts.excludeSite);
  if (include.length) body.includeDomains = include;
  if (exclude.length) body.excludeDomains = exclude;
  const since = opts.startDate ? isoDate(opts.startDate) : recencyToDate(opts.recency);
  if (since) body.startPublishedDate = since;
  if (opts.endDate) body.endPublishedDate = isoDate(opts.endDate, true);
  // livecrawl (deprecated by Exa) → maxAgeHours
  if (opts.livecrawl === "always") body.contents.maxAgeHours = 0;
  else if (opts.livecrawl === "never") body.contents.maxAgeHours = -1;
  return body;
}

function restItems(data) {
  return (data?.results || []).map((r) => ({
    title: r.title || r.url,
    url: r.url,
    published: r.publishedDate || "",
    content:
      (Array.isArray(r.highlights) && r.highlights.length ? r.highlights.join(" … ") : "") ||
      r.summary ||
      r.text ||
      "",
  }));
}

// ── MCP (keyless) ────────────────────────────────────────────

async function mcpCall(toolName, args, key, timeoutMs) {
  const headers = { "Content-Type": "application/json", Accept: "application/json, text/event-stream" };
  if (key) headers.Authorization = `Bearer ${key}`;
  let response;
  try {
    response = await fetch(EXA_MCP_URL, {
      method: "POST",
      headers,
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: toolName, arguments: args } }),
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (err) {
    throw new RetryableError(`Exa network error: ${err.message}`);
  }
  if (!response.ok) throw await httpError(response, key);

  const body = await response.text();
  const parsed = tryParseSse(body) || tryParseJson(body);
  if (!parsed) throw new Error("Exa MCP returned empty response");

  const errMsg = parsed.error
    ? `Exa error${parsed.error.code ? " " + parsed.error.code : ""}: ${parsed.error.message || "Unknown"}`
    : parsed.result?.isError
      ? parsed.result.content?.find((c) => c.type === "text")?.text?.trim() || "Exa MCP returned an error"
      : null;
  if (errMsg) {
    if (QUOTA_TEXT.test(errMsg)) {
      if (key) markFailure("exa", key, 429);
      throw new RetryableError(errMsg);
    }
    throw new Error(errMsg);
  }

  const text = parsed.result?.content?.find(
    (c) => c.type === "text" && typeof c.text === "string" && c.text.trim().length > 0
  )?.text;
  if (!text) throw new Error("Exa MCP returned empty content");
  return text;
}

/** Kept for compatibility: raw Exa MCP tool call (keyed or keyless). */
async function callExaMcp(toolName, args) {
  return withRotation((key, t) => mcpCall(toolName, args, key, t), { allowKeyless: true });
}

// ── Public API ───────────────────────────────────────────────

/**
 * Search Exa. Returns { items, via: "rest" | "mcp" }.
 * opts: query, numResults, site, recency, category, type, livecrawl, maxCharsPerResult
 */
async function exaSearch(opts) {
  const o = {
    ...opts,
    numResults: Math.min(Math.max(Number(opts.numResults) || 5, 1), 10),
    snippetChars: snippetLimit(opts.maxCharsPerResult),
  };
  return withRotation(
    async (key, t) => {
      if (key) return { items: restItems(await restPost("/search", restSearchBody(o), key, t)), via: "rest" };
      // keyless MCP: filters can only be passed as query hints
      const text = await mcpCall(
        "web_search_exa",
        { query: buildSearchQuery(o.query, o), numResults: o.numResults },
        null,
        t
      );
      return { items: parseExaResults(text), via: "mcp" };
    },
    { allowKeyless: true }
  );
}

/** Exa /answer (requires a key). Returns { answer, citations: items }. */
async function exaAnswer(query) {
  return withRotation(
    async (key, t) => {
      const data = await restPost("/answer", { query }, key, t);
      const answer = typeof data?.answer === "string" ? data.answer : JSON.stringify(data?.answer ?? "");
      return {
        answer,
        citations: (data?.citations || []).map((c) => ({ title: c.title, url: c.url, published: c.publishedDate || "" })),
      };
    },
    { allowKeyless: false }
  );
}

/**
 * Exa /contents for one URL (requires a key): clean page text, including PDFs
 * and JS-rendered pages. Returns { title, text }.
 */
async function exaContents(url) {
  return withRotation(
    async (key, t) => {
      const data = await restPost("/contents", { urls: [url], text: true }, key, t);
      const r = data?.results?.[0];
      if (!r?.text || !r.text.trim()) {
        const st = (data?.statuses || []).find((s) => s.id === url) || data?.statuses?.[0];
        const why = st?.error?.tag || st?.error?.httpStatusCode || st?.status || "no content";
        throw new Error(`Exa could not read the page (${why})`);
      }
      return { title: r.title || "", text: r.text.trim() };
    },
    { allowKeyless: false }
  );
}

function tryParseSse(body) {
  for (const line of body.split("\n").filter((l) => l.startsWith("data:"))) {
    const payload = line.slice(5).trim();
    if (!payload) continue;
    try {
      const c = JSON.parse(payload);
      if (c?.result || c?.error) return c;
    } catch {}
  }
  return null;
}

function tryParseJson(body) {
  try {
    const c = JSON.parse(body);
    if (c?.result || c?.error) return c;
  } catch {}
  return null;
}

module.exports = { exaSearch, exaAnswer, exaContents, exaSpend, callExaMcp, EXA_CATEGORIES, EXA_TYPES };
