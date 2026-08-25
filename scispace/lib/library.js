// lib/library.js — My Library management via SciSpace internal API.
// All calls run inside a logged-in browser page so session cookies apply.
const { launchContext } = require("./browser.js");

// Run a same-origin fetch from inside the page context (carries session cookies).
async function apiFetch(page, path, { method = "GET", headers = {}, body } = {}) {
  return page.evaluate(
    async ({ path, method, headers, body }) => {
      const resp = await fetch(path, {
        method,
        headers: { Accept: "application/json", ...headers },
        body: body ? JSON.stringify(body) : undefined,
      });
      const ct = resp.headers.get("content-type") || "";
      const text = await resp.text();
      let parsed;
      try {
        parsed = ct.includes("json") ? JSON.parse(text) : text;
      } catch {
        parsed = text;
      }
      return { status: resp.status, body: parsed };
    },
    { path, method, headers, body }
  );
}

async function withPage(fn) {
  const { browser, ctx } = await launchContext();
  try {
    const page = await ctx.newPage();
    await page.goto("https://scispace.com/search", {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    await page.waitForTimeout(3000);
    return await fn(page);
  } finally {
    await browser.close();
  }
}

// List saved paper records in My Library.
async function listLibrary() {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/library/records");
    return { status: r.status, total: r.body.total ?? null, records: r.body.data ?? [] };
  });
}

// List all collections (folders) in My Library.
async function listCollections() {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/library/collection");
    return { status: r.status, total: r.body.total ?? null, collections: r.body.data ?? [] };
  });
}

// Get the contents of a specific collection by its full_slug.
async function getCollection(fullSlug) {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/library/collection/" + encodeURIComponent(fullSlug));
    return { status: r.status, collection: r.body };
  });
}

// Create a new collection folder. Returns the created collection if the API accepts it.
async function createCollection(name) {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/library/collection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: { name },
    });
    return { status: r.status, result: r.body };
  });
}

// Toggle a bookmark for a paper entity (by its /papers/ slug).
async function bookmarkPaper(entitySlug, { bookmarked = true } = {}) {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/bookmark/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: { entity_slug: entitySlug, entity_type: "PAPER", is_bookmarked: bookmarked },
    });
    return { status: r.status, result: r.body };
  });
}

module.exports = { listLibrary, listCollections, getCollection, createCollection, bookmarkPaper };
