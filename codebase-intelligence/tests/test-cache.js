const { describe, it, before, after } = require("node:test");
const assert = require("node:assert");
const { fs, path, getCachePath } = require("../shared.js");

describe("cache", () => {
  let tmpDir;
  before(() => {
    tmpDir = fs.mkdtempSync(path.join(require("os").tmpdir(), "cb-cache-"));
  });
  after(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("should save and load cache", () => {
    const cache = require("../cache.js");
    const envelope = {
      version: 1,
      fingerprint: "test123",
      scannedAt: new Date().toISOString(),
      fileCounts: { code: 5, test: 2 },
      modules: ["src"],
      entrypoints: ["src/index.ts"],
      hotspots: [],
      sourceOfTruthCandidates: [],
      artifactKinds: [],
    };

    const saved = cache.saveCache(tmpDir, envelope);
    assert.strictEqual(saved, true);

    const loaded = cache.loadCache(tmpDir);
    assert.ok(loaded);
    assert.strictEqual(loaded.fingerprint, "test123");
    assert.strictEqual(loaded.version, 1);
  });

  it("should return null when no cache exists", () => {
    const cache = require("../cache.js");
    const result = cache.loadCache(path.join(tmpDir, "nonexistent"));
    assert.strictEqual(result, null);
  });

  it("should invalidate cache", () => {
    const cache = require("../cache.js");

    // Create a cache file first
    const cachePath = getCachePath(tmpDir);
    const dir = path.dirname(cachePath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(cachePath, JSON.stringify({ version: 1 }));

    assert.strictEqual(fs.existsSync(cachePath), true);
    cache.invalidateCache(tmpDir);
    assert.strictEqual(fs.existsSync(cachePath), false);
  });

  it("should compute file count fingerprint", () => {
    const cache = require("../cache.js");
    const fp1 = cache.computeFileCountFingerprint({ code: 5, test: 2 });
    const fp2 = cache.computeFileCountFingerprint({ code: 5, test: 2 });
    const fp3 = cache.computeFileCountFingerprint({ code: 6, test: 2 });
    assert.strictEqual(fp1, fp2);
    assert.notStrictEqual(fp1, fp3);
  });
});
