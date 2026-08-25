// scispace-client.js — headless Playwright wrapper for scispace.com
// Uses a persisted browser storage state (cookies) so login happens once.
const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");

const STORAGE_STATE_FILE = path.join(__dirname, "storage-state.json");
const USER_AGENT =
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

async function launchContext() {
  const browser = await chromium.launch({ headless: true });
  const hasState = fs.existsSync(STORAGE_STATE_FILE);
  const ctx = await browser.newContext({
    userAgent: USER_AGENT,
    viewport: { width: 1366, height: 768 },
    locale: "en-US",
    timezoneId: "Asia/Jakarta",
    storageState: hasState ? STORAGE_STATE_FILE : undefined,
  });
  return { browser, ctx, hasState };
}

function saveState(ctx) {
  return ctx.storageState().then((state) => {
    fs.writeFileSync(STORAGE_STATE_FILE, JSON.stringify(state, null, 2));
  });
}

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

// Open a login page in a headful browser so the user can sign in once.
// After login the cookies are persisted to storage-state.json.
async function login({ headful = true, timeoutMs = 300000 } = {}) {
  const browser = await chromium.launch({ headless: !headful });
  const ctx = await browser.newContext({
    userAgent: USER_AGENT,
    viewport: { width: 1366, height: 900 },
    locale: "en-US",
  });
  const page = await ctx.newPage();
  await page.goto("https://scispace.com/login", {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });

  const deadline = Date.now() + timeoutMs;
  let loggedIn = false;
  while (Date.now() < deadline) {
    await page.waitForTimeout(5000);
    const body = await page.evaluate(
      () => (document.body ? document.body.innerText : "")
    );
    // After login, the "Sign up"/"Login" nav items usually disappear
    if (
      body.toLowerCase().includes("literature review") &&
      !body.toLowerCase().includes("sign up")
    ) {
      loggedIn = true;
      break;
    }
  }

  if (loggedIn) {
    await saveState(ctx);
  }
  await browser.close();
  return {
    loggedIn,
    message: loggedIn
      ? "Login session saved to storage-state.json — premium access ready."
      : "Login not detected within timeout. Try again or log in manually in the opened browser.",
  };
}

// Check current login / premium status without performing a search.
async function status() {
  const { browser, ctx, hasState } = await launchContext();
  try {
    const page = await ctx.newPage();
    await page.goto("https://scispace.com/search", {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    await page.waitForTimeout(4000);
    const body = await page.evaluate(
      () => (document.body ? document.body.innerText : "")
    );
    const lower = body.toLowerCase();
    const loggedIn = hasState && !lower.includes("sign up");
    const premium = loggedIn && lower.includes("upgrade");
    return {
      hasStoredSession: hasState,
      loggedIn,
      premiumFeaturesVisible: premium,
      snippet: body.replace(/\s+/g, " ").slice(0, 300),
    };
  } finally {
    await browser.close();
  }
}

module.exports = { searchPapers, login, status };
