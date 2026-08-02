const { describe, it } = require("node:test");
const assert = require("node:assert");

describe("shared", () => {
  it("should classify code files", () => {
    const { isCodeFile, isTestFile, isDocFile, isConfigFile } = require("../shared.js");
    assert.strictEqual(isCodeFile("src/index.ts"), true);
    assert.strictEqual(isCodeFile("main.js"), true);
    assert.strictEqual(isCodeFile("readme.md"), false);
    assert.strictEqual(isTestFile("src/foo.test.ts"), true);
    assert.strictEqual(isTestFile("src/__tests__/foo.ts"), true);
    assert.strictEqual(isTestFile("src/foo.ts"), false);
    assert.strictEqual(isDocFile("docs/guide.md"), true);
    assert.strictEqual(isDocFile("README.md"), true);
    assert.strictEqual(isConfigFile("config.json"), true);
    assert.strictEqual(isConfigFile(".env"), true);
  });

  it("should classify files by kind", () => {
    const { classifyFile } = require("../shared.js");
    assert.strictEqual(classifyFile("src/foo.ts"), "code");
    assert.strictEqual(classifyFile("src/foo.test.ts"), "test");
    assert.strictEqual(classifyFile("docs/guide.md"), "doc");
    assert.strictEqual(classifyFile("config.json"), "config");
    assert.strictEqual(classifyFile("assets/logo.png"), "other");
  });

  it("should classify artifacts", () => {
    const { classifyArtifact } = require("../shared.js");
    assert.strictEqual(classifyArtifact("docs/guide.md"), "doc");
    assert.strictEqual(classifyArtifact("specs/api.md"), "spec");
    assert.strictEqual(classifyArtifact("db/schema.sql"), "sql");
    assert.strictEqual(classifyArtifact("Dockerfile"), "docker");
  });
});
