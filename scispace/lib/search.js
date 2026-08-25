// lib/search.js — SciSpace paper search via headless browser
const { launchContext } = require("./browser.js");

// Search scispace.com for papers. Returns structured results.
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

    // SciSpace runs an AI search: it creates a literature-review session and
    // renders results progressively. Poll until paper cards appear (~7-15s).
    let papers = [];
    for (let i = 0; i < 10; i++) {
      await page.waitForTimeout(5000);
      papers = await page.evaluate(() => {
        const out = [];
        const anchors = Array.from(
          document.querySelectorAll('a[href*="/papers/"]')
        );
        const seen = new Set();
        for (const a of anchors) {
          const href = a.href;
          if (seen.has(href)) continue;
          seen.add(href);
          const title = (a.innerText || "")
            .trim()
            .replace(/^\d+\.\s*/, "")
            .slice(0, 300);
          if (!title || href.includes("/browse")) continue;
          // Find the closest card container for authors/journal context
          let container = a.closest("div") || a;
          for (let j = 0; j < 4 && container.parentElement; j++) {
            container = container.parentElement;
            if (container.innerText && container.innerText.length > title.length + 20) break;
          }
          out.push({
            title,
            url: href,
            context: (container.innerText || "").replace(/\s+/g, " ").trim().slice(0, 500),
          });
        }
        return out.slice(0, 30);
      });
      if (papers.length > 0) break;
    }

    const url = page.url();
    if (!hasState && papers.length === 0) {
      return {
        note: "Not logged in — results limited. Run the login tool first to unlock premium features.",
        query,
        mode,
        finalUrl: url,
        bodySnippet: (
          await page.evaluate(() => (document.body ? document.body.innerText : ""))
        )
          .replace(/\s+/g, " ")
          .slice(0, 400),
        papers,
      };
    }

    return {
      query,
      mode,
      finalUrl: url,
      totalFound: papers.length,
      papers: papers.slice(0, limit),
    };
  } finally {
    await browser.close();
  }
}

module.exports = { searchPapers };
