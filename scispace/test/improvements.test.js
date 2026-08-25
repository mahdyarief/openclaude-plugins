// test/improvements.test.js — Tests for caching layer, singleton browser, and rate limit hardening

const { getCache, clearCache, generateCacheKey } = require("../lib/cache.js");
const { getJsonWithRetry } = require("../lib/extract.js");

let passed = 0;
let failed = 0;

function assertEqual(actual, expected, testName) {
  if (JSON.stringify(actual) === JSON.stringify(expected)) {
    console.log(`✓ ${testName}`);
    passed++;
  } else {
    console.log(`✗ ${testName}`);
    console.log(`  Expected: ${JSON.stringify(expected)}`);
    console.log(`  Actual: ${JSON.stringify(actual)}`);
    failed++;
  }
}

function runTest(testName, testFn) {
  try {
    testFn();
    console.log(`✓ ${testName}`);
    passed++;
  } catch (e) {
    console.log(`✗ ${testName}: ${e.message}`);
    failed++;
  }
}

async function asyncRunTest(testName, testFn) {
  try {
    await testFn();
    console.log(`✓ ${testName}`);
    passed++;
  } catch (e) {
    console.log(`✗ ${testName}: ${e.message}`);
    failed++;
  }
}

async function runTests() {
  console.log("=== Testing Caching Layer ===\n");

  // Test LRU cache basic operations
  const cache = getCache();
  clearCache();

  cache.set("key1", "value1", 5000);
  runTest("Cache set/get works", () => {
    if (cache.get("key1") !== "value1") throw new Error("Value mismatch");
  });

  runTest("Cache has key", () => {
    if (!cache.has("key1")) throw new Error("Key not found");
  });

  runTest("Cache doesn't have non-existent key", () => {
    if (cache.has("nonexistent")) throw new Error("Key should not exist");
  });

  // Test cache size limit (LRU eviction)
  for (let i = 0; i < 105; i++) {
    cache.set(`key${i}`, `value${i}`, 5000);
  }
  runTest("LRU max entries enforced", () => {
    if (cache.size() > 100) throw new Error("Cache size exceeds limit");
  });

  // Test TTL expiry
  cache.set("tempkey", "tempvalue", 1);
  await new Promise(resolve => setTimeout(resolve, 5));
  runTest("Cache TTL expires correctly", () => {
    if (cache.get("tempkey") !== null) throw new Error("Should have expired");
  });

  // Test cache key generation
  const key1 = generateCacheKey({ query: "test", limit: 10 });
  const key2 = generateCacheKey({ query: "test", limit: 10 });
  const key3 = generateCacheKey({ query: "different", limit: 10 });
  runTest("Same params produce same cache key", () => {
    if (key1 !== key2) throw new Error("Keys should match");
  });

  runTest("Different params produce different cache keys", () => {
    if (key1 === key3) throw new Error("Keys should differ");
  });

  console.log("\n=== Testing Singleton Browser Structure ===\n");

  // Test withPageReuse exists
  const { withPageReuse, ensureInitialized } = require("../lib/browser.js");
  runTest("withPageReuse function exists", () => {
    if (typeof withPageReuse !== "function") throw new Error("Not a function");
  });

  runTest("ensureInitialized function exists", () => {
    if (typeof ensureInitialized !== "function") throw new Error("Not a function");
  });

  console.log("\n=== Testing Rate Limit Hardening ===\n");

  // Check if delayWithJitter exists (might be internal helper)
  const extractModule = require("../lib/extract.js");
  runTest("getJsonWithRetry exported", () => {
    if (typeof extractModule.getJsonWithRetry !== "function") {
      throw new Error("Not exported");
    }
  });

  // Test getJsonWithRetry signature includes default parameters
  const funcStr = extractModule.getJsonWithRetry.toString();
  runTest("getJsonWithRetry has correct signature", () => {
    if (!funcStr.includes("baseDelayMs") || !funcStr.includes("maxRetries")) {
      throw new Error("Missing parameters in function signature");
    }
  });

  console.log("\n=== Summary ===");
  console.log(`Passed: ${passed}`);
  console.log(`Failed: ${failed}`);

  process.exit(failed > 0 ? 1 : 0);
}

runTests().catch(e => {
  console.error("Test runner error:", e);
  process.exit(1);
});
