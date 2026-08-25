// lib/search.js — SciSpace paper search via headless browser (with caching & page reuse)
const { withPageReuse } = require("./browser.js");
const { getCache, generateCacheKey, DEFAULT_TTL_SEARCH } = require("./cache.js");

// Search scispace.com for papers. Returns structured results.
// Uses LRU cache to avoid repeated browser launches.
async function searchPapers(query, { mode = "standard", limit = 10 } = {}) {
  // Generate cache key from input parameters
  const cacheKey = generateCacheKey({ query, mode, limit });
  const cache = getCache();

  // Check cache first
  const cachedResult = cache.get(cacheKey);
  if (cachedResult) {
    return cachedResult;
  }

  // Perform actual search
  const result = await _performSearch(query, { mode, limit });

  // Store in cache with TTL
  cache.set(cacheKey, result, DEFAULT_TTL_SEARCH);

  return result;
}

async function _performSearch(query, { mode, limit }) {
  const page = await withPageReuse(async (page) => {
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
        loggedIn: true,
      };
    }

    // Type char-by-char to trigger React state updates, then submit with Enter.
    await input.first().click();
    await input.first().pressSequentially(query, { delay: 20 });
    await page.waitForTimeout(800);
    await page.keyboard.press("Enter");

    // Adaptive poll: 2s interval, up to 15 attempts (30s max), early exit on
    // results or when the page explicitly reports no matches.
    for (let i = 0; i < 15; i++) {
      await page.waitForTimeout(2000);
      const state = await page.evaluate(() => {
        const out = [];
        const anchors = Array.from(document.querySelectorAll('a[href*="/papers/"]'));
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
        const noResults = /no (papers|results|matches?)/i.test(bodyText) && !/showing .* results/i.test(bodyText);
        return { papers: out, noResults };
      });

      if (state.papers.length || state.noResults) break;
    }

    return page;
  });

  // Extract papers from the page evaluation
  const finalState = await withPageReuse(async (p) => {
    return p.evaluate(() => {
      const out = [];
      const anchors = Array.from(document.querySelectorAll('a[href*="/papers/"]'));
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
      const noResults = /no (papers|results|matches?)/i.test(bodyText) && !/showing .* results/i.test(bodyText);
      return { papers: out, noResults, hasBody: !!document.body };
    });
  });

  let papers = finalState.papers;

  // De-duplicate by URL, drop UI/nav links like /papers/browse
  const unique = [];
  const seenUrls = new Set();
  for (const p of papers) {
    const slug = (p.url.split("/papers/")[1] || "").split(/[/?#]/)[0];
    if (!slug || slug === "browse" || seenUrls.has(p.url)) continue;
    seenUrls.add(p.url);
    unique.push(p);
  }

  const result = {
    query,
    mode,
    loggedIn: true,
    count: unique.length,
    papers: unique.slice(0, limit),
  };

  return result;
}

module.exports = { searchPapers, getCache, clearCache: require("./cache.js").clearCache };
