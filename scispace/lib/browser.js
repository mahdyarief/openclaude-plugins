// lib/browser.js — shared Playwright browser context & session persistence
const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");

const STORAGE_STATE_FILE = path.join(__dirname, "..", "storage-state.json");
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

async function saveState(ctx) {
  const state = await ctx.storageState();
  fs.writeFileSync(STORAGE_STATE_FILE, JSON.stringify(state, null, 2));
}

module.exports = { launchContext, saveState, STORAGE_STATE_FILE, USER_AGENT };
