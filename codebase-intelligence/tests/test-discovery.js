const { describe, it, before, after } = require("node:test");
const assert = require("node:assert");
const { fs, path } = require("../shared.js");

describe("discovery", () => {
  let tmpDir;
  before(() => {
    tmpDir = fs.mkdtempSync(path.join(require("os").tmpdir(), "cb-disc-"));
  });
  after(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("should discover files recursively", () => {
    fs.writeFileSync(path.join(tmpDir, "a.ts"), "");
    fs.writeFileSync(path.join(tmpDir, "b.js"), "");
    fs.mkdirSync(path.join(tmpDir, "sub"));
    fs.writeFileSync(path.join(tmpDir, "sub", "c.ts"), "");

    const { walkRecursive } = require("../discovery.js");
    const files = walkRecursive(tmpDir, tmpDir);
    assert.ok(files.length >= 3);
    assert.ok(files.includes("a.ts"));
    assert.ok(files.includes("b.js"));
    assert.ok(
      files.includes("sub/c.ts") || files.includes("sub\\c.ts"),
      "should find sub/c.ts"
    );
  });

  it("should count files by kind", () => {
    const { countByKind } = require("../discovery.js");
    const files = ["src/foo.ts", "src/bar.test.ts", "docs/readme.md", "config.json"];
    const counts = countByKind(files);
    assert.strictEqual(counts.code, 1);
    assert.strictEqual(counts.test, 1);
    assert.strictEqual(counts.doc, 1);
    assert.strictEqual(counts.config, 1);
  });
});
