const { describe, it } = require("node:test");
const assert = require("node:assert");

describe("diagnostics", () => {
  it("should detect available tools", () => {
    const diag = require("../diagnostics.js");
    const tools = diag.detectAllTools();
    assert.ok(typeof tools.rg === "boolean");
    assert.ok(typeof tools.astGrep === "boolean");
  });

  it("should return install hints for missing tools", () => {
    const diag = require("../diagnostics.js");
    const hints = diag.getInstallHints({ rg: false, astGrep: false, mgrep: false });
    assert.ok(hints.length > 0);
    assert.ok(hints.some((h) => h.tool === "ripgrep"));
  });

  it("should determine mode based on tool availability", () => {
    const diag = require("../diagnostics.js");
    assert.strictEqual(diag.getMode({ rg: true }), "full");
    assert.strictEqual(diag.getMode({ rg: false }), "degraded");
  });
});

describe("search (unit)", () => {
  it("should merge and deduplicate results", () => {
    const search = require("../search.js");
    const rgResults = [
      { path: "a.ts", line: 1, preview: "hello world", reason: "rg", confidence: "high", score: 1.0 },
      { path: "b.ts", line: 5, preview: "test", reason: "rg", confidence: "high", score: 1.0 },
    ];
    const sgResults = [
      { path: "a.ts", line: 1, preview: "hello world", reason: "sg", confidence: "high", score: 1.5 },
    ];

    const merged = search.mergeResults(rgResults, sgResults);
    assert.strictEqual(merged.length, 2);
    assert.strictEqual(merged[0].reason, "sg");
  });
});
