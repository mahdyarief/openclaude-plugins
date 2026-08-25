// lib/search.js — SciSpace paper search via headless browser.
const { launchContext } = require("./browser.js");

// Search scispace.com for papers. Returns structured results.
// Polling is adaptive: every 2s we check for paper cards or an explicit
// "no results" state, so we return as soon as the page settles instead of
// always waiting the full window.
async function searchPapers(query, { mode = "standard", limit = 10 } = {}) {
  const { browser, ctx, hasState } = await launchContext();
  try {
    const page = await ctx.newPage();

    await page.goto("https://scispace.com/search", {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    await page.waitForTimeout(4000);

    const input = page.locator('textarea[name="search-input"]');
    const count = await input.count();
    if (count === 0) {
      return {
        error: "Search input not found — SciSpace may have changed its UI or blocked the session.",
        loggedIn: hasState,
      };
    }

    // Type char-by-char to trigger React state updates, then submit with Enter.
    // (fill() + click on the submit button does NOT fire the search.)
    await input.first().click();
    await input.first().pressSequentially(query, { delay: 20 });
    await page.waitForTimeout(800);
    await page.keyboard.press("Enter");

    // Adaptive poll: 2s interval, up to 15 attempts (30s max), early exit on
    // results or when the page explicitly reports no matches.
    let papers = [];
    for (let i = 0; i < 15; i++) {
      await page.waitForTimeout(2000);
      const state = await page.evaluate(() => {
        const out = [];
        const anchors = Array.from(
          document.querySelectorAll('a[href*="/papers/"]')
        );
        const seen = new Set();
        for (const a of anchors) {
          const href = a.href;
          if (seen.has(href)) continue;
          seen.add(href);
          const title = (a.innerText || "").trim();
          const container = a.closest("div") || a;
          const context = (container.innerText || "").trim().slice(0, 400);
          out.push({ title: title || null, url: href, context });
        }
        const bodyText = document.body ? document.body.innerText : "";
        const noResults =
          /no (papers|results|matches?)/i.test(bodyText) &&
          !/showing .* results/i.test(bodyText);
        return { papers: out, noResults };
      });
      papers = state.papers;
      if (papers.length || state.noResults) break;
    }

    // De-duplicate by URL, drop UI/nav links like /papers/browse.
    const unique = [];
    const seenUrls = new Set();
    for (const p of papers) {
      const slug = (p.url.split("/papers/")[1] || "").split(/[/?#]/)[0];
      if (!slug || slug === "browse" || seenUrls.has(p.url)) continue;
      seenUrls.add(p.url);
      unique.push(p);
    }

    return {
      query,
      mode,
      loggedIn: hasState,
      count: unique.length,
      papers: unique.slice(0, limit),
    };
  } finally {
    await browser.close();
  }
}

module.exports = { searchPapers };