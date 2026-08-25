// lib/auth.js — session login, status, and validation.
const { chromium } = require("playwright");
const { saveState, STORAGE_STATE_FILE } = require("./browser.js");
const { apiFetch, withPage } = require("./api.js");

// Open a visible browser window for the user to log in, then persist the session.
async function login({ timeoutMs = 300000 } = {}) {
  const browser = await chromium.launch({ headless: false });
  const ctx = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    viewport: { width: 1366, height: 768 },
    locale: "en-US",
    timezoneId: "Asia/Jakarta",
  });
  try {
    const page = await ctx.newPage();
    await page.goto("https://scispace.com", { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(5000);
    // Let the user log in manually
    await page.waitForTimeout(timeoutMs);
    await saveState(ctx);
    return { success: true, message: "Session saved to " + STORAGE_STATE_FILE };
  } finally {
    await browser.close();
  }
}

// Check whether a login session is stored and validate it against the server.
// Uses the confirmed /api/auth/validate endpoint (returns 200 with user info).
async function status() {
  const fs = require("fs");
  const hasState = fs.existsSync(STORAGE_STATE_FILE);
  if (!hasState) return { loggedIn: false, error: "No stored session — run scispace_login first." };

  return withPage(async (page) => {
    const v = await apiFetch(page, "/api/auth/validate");
    if (v.status === 200 && v.body && v.body.user) {
      const user = v.body.user;
      return {
        loggedIn: true,
        email: user.email,
        fullName: user.full_name,
        userId: user.user_id,
      };
    }
    return { loggedIn: false, status: v.status, error: "Session invalid — run scispace_login again." };
  });
}

module.exports = { login, status };