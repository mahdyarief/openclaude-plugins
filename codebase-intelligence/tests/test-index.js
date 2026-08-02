const { describe, it, before, after } = require("node:test");
const assert = require("node:assert");
const { fs, path } = require("../shared.js");
const indexModule = require("../index.js");

describe("persistent index", () => {
  let tmpDir;
  before(() => {
    tmpDir = fs.mkdtempSync(path.join(require("os").tmpdir(), "cb-index-"));
  });
  after(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("should build index from code files and skip stopwords", () => {
    fs.writeFileSync(path.join(tmpDir, "a.ts"), "const x = 1;\nfunction buildSummary() { return x; }\n");
    fs.writeFileSync(path.join(tmpDir, "b.py"), "def parse_config():\n    return buildSummary()\n");

    const idx = indexModule.buildIndex(["a.ts", "b.py"], tmpDir, "fp1");
    assert.ok(idx);
    assert.strictEqual(idx.fingerprint, "fp1");
    assert.strictEqual(idx.tokenCount, 2);

    // Stopwords excluded: const/function/return not indexed
    assert.ok(!idx.entries["const"]);
    assert.ok(!idx.entries["function"]);
    // Identifiers indexed
    assert.ok(idx.entries["buildSummary"]);
    assert.ok(idx.entries["parse_config"]);
  });

  it("should save and load index", () => {
    const idx = indexModule.buildIndex(["a.ts"], tmpDir, "fp2");
    const saved = indexModule.saveIndex(tmpDir, idx);
    assert.strictEqual(saved, true);

    const loaded = indexModule.loadIndex(tmpDir);
    assert.ok(loaded);
    assert.strictEqual(loaded.fingerprint, "fp2");
    assert.strictEqual(loaded.version, 1);
    assert.ok(loaded.entries["buildSummary"]);
  });

  it("should return null when no index exists", () => {
    assert.strictEqual(indexModule.loadIndex(path.join(tmpDir, "nonexistent")), null);
  });

  it("should search exact identifier", () => {
    const idx = indexModule.buildIndex(["a.ts"], tmpDir, "fp3");
    const hits = indexModule.searchIndex(idx, "buildSummary");
    assert.ok(hits);
    assert.ok(hits.length >= 1);
    assert.strictEqual(hits[0].path, "a.ts");
    assert.match(hits[0].reason, /persistent index/);
  });

  it("should search with prefix fallback", () => {
    const idx = indexModule.buildIndex(["a.ts"], tmpDir, "fp4");
    const hits = indexModule.searchIndex(idx, "buildSum");
    assert.ok(hits);
    assert.ok(hits.length >= 1);
  });

  it("should return null for multi-word query (falls back to rg)", () => {
    const idx = indexModule.buildIndex(["a.ts"], tmpDir, "fp5");
    assert.strictEqual(indexModule.searchIndex(idx, "build summary"), null);
  });

  it("should return null for unknown identifier", () => {
    const idx = indexModule.buildIndex(["a.ts"], tmpDir, "fp6");
    assert.strictEqual(indexModule.searchIndex(idx, "doesNotExistAnywhere"), null);
  });

  it("isIndexFresh compares fingerprint", () => {
    const idx = indexModule.buildIndex(["a.ts"], tmpDir, "fp7");
    assert.strictEqual(indexModule.isIndexFresh(idx, "fp7"), true);
    assert.strictEqual(indexModule.isIndexFresh(idx, "different"), false);
    assert.strictEqual(indexModule.isIndexFresh(null, "fp7"), false);
  });
});
