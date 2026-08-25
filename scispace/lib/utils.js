// lib/utils.js — account credits & translation utilities via SciSpace internal API.
const { launchContext } = require("./browser.js");

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

// Current credit balance / usage window from /api/meters/credits.
async function checkCredits() {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/meters/credits");
    return { status: r.status, credits: r.body };
  });
}

// Languages supported for SciSpace's in-app translation.
async function listTranslationLanguages() {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/translation/languages");
    return { status: r.status, languages: (r.body && r.body.languages) || [] };
  });
}

// Which literature-review / library model tiers the account can access.
async function getModelAccess(kind = "literature-review") {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/hooks/models/" + encodeURIComponent(kind));
    return { status: r.status, models: (r.body && r.body.data) || [] };
  });
}

module.exports = { checkCredits, listTranslationLanguages, getModelAccess };
