// lib/auth.js — login & session status
const { chromium } = require("playwright");
const { launchContext, saveState, USER_AGENT } = require("./browser.js");

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

module.exports = { login, status };
