// lib/browser.js — Shared Playwright browser context & session persistence (singleton pattern)
const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");

const STORAGE_STATE_FILE = path.join(__dirname, "..", "storage-state.json");
const USER_AGENT =
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

let browserInstance = null;
let contextInstance = null;
let initialized = false;
let cleanupHandlerAdded = false;

async function ensureInitialized() {
  if (initialized) {
    return { browser: browserInstance, ctx: contextInstance };
  }

  try {
    browserInstance = await chromium.launch({ headless: true });
    const hasState = fs.existsSync(STORAGE_STATE_FILE);
    contextInstance = await browserInstance.newContext({
      userAgent: USER_AGENT,
      viewport: { width: 1366, height: 768 },
      locale: "en-US",
      timezoneId: "Asia/Jakarta",
      storageState: hasState ? STORAGE_STATE_FILE : undefined,
    });

    // Add graceful shutdown handler
    if (!cleanupHandlerAdded) {
      cleanupHandlerAdded = true;
      process.on("SIGINT", handleSigInt);
      process.on("SIGTERM", handleSigInt);
      process.on("beforeExit", handleBeforeExit);
    }

    initialized = true;
    return { browser: browserInstance, ctx: contextInstance };
  } catch (error) {
    console.error("[browser] Failed to initialize:", error.message);
    throw error;
  }
}

async function saveState(ctx) {
  const state = await ctx.storageState();
  fs.writeFileSync(STORAGE_STATE_FILE, JSON.stringify(state, null, 2));
}

async function getBrowserInstance() {
  const { browser, ctx } = await ensureInitialized();
  return { browser, ctx };
}

async function withPageReuse(fn) {
  const { ctx } = await ensureInitialized();
  let page;

  try {
    // Try to reuse existing page if available
    const pages = ctx.pages();
    if (pages.length > 0) {
      page = pages[0];
      // Navigate to a fresh URL or reload
      await page.goto("about:blank", { waitUntil: "domcontentloaded" });
    } else {
      page = await ctx.newPage();
    }

    return await fn(page);
  } finally {
    // Don't close the page, just leave it for reuse
    if (page && !page.isClosed()) {
      // Keep page alive but navigate to blank state
      try {
        await page.goto("about:blank", { waitUntil: "domcontentloaded" }).catch(() => {});
      } catch (e) {
        // Ignore navigation errors on cleanup
      }
    }
  }
}

function handleSigInt() {
  console.log("[browser] Received SIGINT, cleaning up...");
  performCleanup();
  process.exit(0);
}

function handleSigTERM() {
  console.log("[browser] Received SIGTERM, cleaning up...");
  performCleanup();
  process.exit(0);
}

async function handleBeforeExit() {
  if (initialized) {
    console.log("[browser] BeforeExit event, cleaning up...");
    await performCleanup();
  }
}

async function performCleanup() {
  if (browserInstance) {
    try {
      await browserInstance.close();
    } catch (e) {
      console.error("[browser] Cleanup error:", e.message);
    }
    browserInstance = null;
    contextInstance = null;
    initialized = false;
  }
}

module.exports = {
  ensureInitialized,
  getBrowserInstance,
  withPageReuse,
  saveState,
  STORAGE_STATE_FILE,
  USER_AGENT,
  performCleanup,
};
