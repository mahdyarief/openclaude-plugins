/**
 * Test helpers: isolated config per test, fresh module state, mocked fetch.
 * No real network calls and no real API keys are used.
 */
const fs = require("fs");
const os = require("os");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const ENV_KEYS = [
  "WEB_ACCESS_CONFIG",
  "EXA_KEYS_FILE",
  "TAVILY_KEYS_FILE",
  "TAVILY_API_KEY",
  "TAVILY_API_KEYS",
  "EXA_API_KEY",
  "EXA_API_KEYS",
  "WEB_SEARCH_PROVIDER",
  "WEB_ACCESS_STATE_FILE",
  "WEB_ACCESS_CACHE_FILE",
];

const realFetch = global.fetch;
// Direct page fetches go through (mocked) global fetch instead of the pinned
// node:http transport; the pinned transport has its own tests against a local server.
process.env.WEB_ACCESS_DIRECT_TRANSPORT = "fetch";

/**
 * Load the project with a given config and a fetch handler.
 * handler(url, init, calls) → Response-like object or throws.
 */
function setup(config = {}, handler = () => ok({})) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "web-access-test-"));
  const cfgFile = path.join(dir, "web-access.json");
  fs.writeFileSync(cfgFile, JSON.stringify(config));

  for (const k of ENV_KEYS) delete process.env[k];
  process.env.WEB_ACCESS_CONFIG = cfgFile;
  // point legacy key files somewhere empty so the developer's real keys never load
  process.env.EXA_KEYS_FILE = path.join(dir, "none.json");
  process.env.TAVILY_KEYS_FILE = path.join(dir, "none.json");

  for (const id of Object.keys(require.cache)) {
    if (id.startsWith(ROOT) && !id.includes(`${path.sep}test${path.sep}`)) delete require.cache[id];
  }

  const calls = [];
  global.fetch = async (url, init = {}) => {
    const call = {
      url: String(url),
      provider: String(url).includes("exa.ai") ? "exa" : String(url).includes("tavily") ? "tavily" : "web",
      auth: init.headers?.Authorization?.replace(/^Bearer /, "") || init.headers?.["x-api-key"] || null,
      rest: String(url).includes("api.exa.ai"),
      headers: init.headers || {},
      body: init.body ? JSON.parse(init.body) : null,
      signal: init.signal,
    };
    calls.push(call);
    // A real in-flight fetch keeps the event loop alive (open socket). Mirror
    // that, otherwise a never-resolving mock + AbortSignal.timeout (unref'd
    // timer) lets Node exit before the abort fires.
    const keepAlive = setInterval(() => {}, 1000);
    try {
      return await handler(call, calls);
    } finally {
      clearInterval(keepAlive);
    }
  };

  const origError = console.error;
  console.error = () => {};

  return {
    calls,
    cfgFile,
    tools: require(path.join(ROOT, "tools.js")),
    writeConfig(c) {
      fs.writeFileSync(cfgFile, JSON.stringify(c));
      // make sure mtime changes even on coarse filesystems
      const t = new Date(Date.now() + 2000);
      fs.utimesSync(cfgFile, t, t);
    },
    cleanup() {
      console.error = origError;
      global.fetch = realFetch;
      fs.rmSync(dir, { recursive: true, force: true });
    },
  };
}

function ok(json) {
  return { ok: true, status: 200, json: async () => json, text: async () => JSON.stringify(json) };
}

function fail(status, text = "error", headers = {}) {
  return {
    ok: false,
    status,
    statusText: text,
    headers: new Map(Object.entries(headers)),
    json: async () => ({}),
    text: async () => text,
  };
}

/**
 * Exa response that works for both transports: .text() is the MCP SSE body,
 * .json() is the REST /search body built from the same items.
 */
function exaOk(text) {
  const payload = JSON.stringify({ result: { content: [{ type: "text", text }] } });
  const results = text.split(/\n---+\n/).map((b) => ({
    title: b.match(/Title: (.+)/)?.[1],
    url: b.match(/URL: (.+)/)?.[1],
    publishedDate: (b.match(/Published: (.+)/)?.[1] || "").replace("N/A", "") || null,
    highlights: [b.match(/Highlights: (.+)/)?.[1] || "snippet"],
  }));
  return {
    ok: true,
    status: 200,
    headers: new Map(),
    text: async () => `event: message\ndata: ${payload}\n\n`,
    json: async () => ({ requestId: "r", results, costDollars: { total: 0.005 } }),
  };
}

function exaText(items) {
  return items
    .map((i) => `Title: ${i.title}\nURL: ${i.url}\nPublished: ${i.published || "N/A"}\nHighlights: ${i.text || "snippet"}`)
    .join("\n---\n");
}

function tavilyOk(results, extra = {}) {
  return ok({ results, ...extra });
}

module.exports = { setup, ok, fail, exaOk, exaText, tavilyOk };
