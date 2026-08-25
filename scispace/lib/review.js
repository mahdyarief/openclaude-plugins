// lib/review.js — literature-review session helpers.
// The search UI creates a review session; this module exposes the column schema
// SciSpace uses to compare papers (methods, results, conclusions, etc.) and a
// helper that assembles the per-column extraction request for a set of paper slugs.
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

// Available comparison columns (what SciSpace can extract per paper):
// insights, tldr, conclusions, summarized_abstract, results,
// summarized_introduction, methods_used, literature_survey.
async function getReviewColumns() {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/paper-info/columns");
    const generic = (r.body && r.body.generic && r.body.generic.data) || [];
    return {
      status: r.status,
      columns: generic.map((c) => ({
        key: c.key,
        displayName: c.display_name,
        isSelected: c.is_selected,
        isFixed: c.is_fixed,
      })),
    };
  });
}

module.exports = { getReviewColumns };
