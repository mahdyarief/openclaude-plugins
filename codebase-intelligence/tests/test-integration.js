const { describe, it, before, after } = require("node:test");
const assert = require("node:assert");
const { fs, path } = require("../shared.js");

describe("impact", () => {
  let tmpDir;
  before(() => {
    tmpDir = fs.mkdtempSync(path.join(require("os").tmpdir(), "cb-imp-"));
    fs.mkdirSync(path.join(tmpDir, "src"));
    fs.writeFileSync(
      path.join(tmpDir, "src", "index.ts"),
      "import { helper } from './helper';\nimport { config } from './config';\n"
    );
    fs.writeFileSync(
      path.join(tmpDir, "src", "helper.ts"),
      "import { config } from './config';\n"
    );
    fs.writeFileSync(
      path.join(tmpDir, "src", "config.ts"),
      "export const config = { debug: true };\n"
    );
    fs.writeFileSync(
      path.join(tmpDir, "src", "helper.test.ts"),
      "import { helper } from './helper';\n"
    );
  });
  after(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("should build dependency map", () => {
    const { buildDependencyMap } = require("../impact.js");
    const { walkRecursive } = require("../discovery.js");
    const files = walkRecursive(tmpDir, tmpDir);

    const depMap = buildDependencyMap(files, tmpDir);
    const configKey = Object.keys(depMap).find((k) => k.endsWith("config.ts"));
    assert.ok(configKey, "config.ts should be in depMap");
  });

  it("should find reverse dependencies", () => {
    const { buildDependencyMap, reverseDependencyMap } = require("../impact.js");
    const { walkRecursive } = require("../discovery.js");
    const files = walkRecursive(tmpDir, tmpDir);
    const depMap = buildDependencyMap(files, tmpDir);
    const reverse = reverseDependencyMap(depMap);

    const configKey = Object.keys(depMap).find((k) => k.endsWith("config.ts"));
    assert.ok(configKey);
    assert.ok(
      reverse[configKey].length > 0,
      "config.ts should have dependents"
    );
  });
});

describe("scanner", () => {
  let tmpDir;
  before(() => {
    tmpDir = fs.mkdtempSync(path.join(require("os").tmpdir(), "cb-scan-"));
    fs.writeFileSync(path.join(tmpDir, "index.ts"), "console.log('hello');");
    fs.writeFileSync(path.join(tmpDir, "utils.ts"), "export const foo = 1;");
    fs.mkdirSync(path.join(tmpDir, "docs"));
    fs.writeFileSync(path.join(tmpDir, "docs", "readme.md"), "# Hello");
  });
  after(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("should scan a project", async () => {
    const scanner = require("../scanner.js");
    const result = await scanner.scanProject(tmpDir);
    assert.strictEqual(result.status, "scanned");
    assert.ok(result.fileCounts);
    assert.ok(result.fileCounts.code >= 2);
    assert.ok(Array.isArray(result.modules));
    assert.ok(Array.isArray(result.entrypoints));
  });

  it("should return error for nonexistent path", async () => {
    const scanner = require("../scanner.js");
    const result = await scanner.scanProject(path.join(tmpDir, "nonexistent"));
    assert.strictEqual(result.error, true);
    assert.strictEqual(result.code, "ENOENT");
  });
});
