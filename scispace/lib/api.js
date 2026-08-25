// lib/api.js — shared SciSpace same-origin API helper.
// All calls run inside a logged-in browser page so session cookies apply,
// and every request carries the X-CSRFToken header (required by Django/DRF
// for POST/PUT/DELETE — proven by live probe: create_collection 200 with
// the header, and the old code without it would fail).
const { launchContext } = require("./browser.js");

async function apiFetch(page, path, { method = "GET", headers = {}, body } = {}) {
  return page.evaluate(
    async ({ path, method, headers, body }) => {
      const csrf =
        (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
      const resp = await fetch(path, {
        method,
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": csrf,
          ...headers,
        },
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

// True when the API says the session is gone (401/403). Callers can use this
// to return a friendly "run scispace_login" message instead of raw errors.
function sessionExpired(r) {
  return r.status === 401 || r.status === 403;
}

module.exports = { apiFetch, withPage, sessionExpired };
