const test = require("node:test");
const assert = require("node:assert/strict");
const { setup, fail, exaOk, exaText, tavilyOk } = require("./helpers");

const EXA_ONE = exaText([{ title: "Exa Result", url: "https://exa.example/a" }]);
const TAV_ONE = [{ title: "Tavily Result", url: "https://tav.example/a", content: "tav" }];

function defaultHandler(call) {
  return call.provider === "exa" ? exaOk(EXA_ONE) : tavilyOk(TAV_ONE);
}

let env;
test.afterEach(() => env?.cleanup());

// ── Tavily key rotation ──────────────────────────────────────

test("tavily: round-robin across requests", async () => {
  env = setup({ tavily: { keys: ["tvly-A", "tvly-B", "tvly-C"] } }, defaultHandler);
  for (let i = 0; i < 4; i++) await env.tools.dispatchTool("web_search_tavily", { query: `q${i}` });
  assert.deepEqual(env.calls.map((c) => c.auth), ["tvly-A", "tvly-B", "tvly-C", "tvly-A"]);
});

test("tavily: quota error rotates and puts key on cooldown", async () => {
  env = setup({ tavily: { keys: ["tvly-A", "tvly-B"] } }, (call) =>
    call.auth === "tvly-A" ? fail(432, "plan limit") : tavilyOk(TAV_ONE)
  );
  await env.tools.dispatchTool("web_search_tavily", { query: "q1" });
  await env.tools.dispatchTool("web_search_tavily", { query: "q2" });
  await env.tools.dispatchTool("web_search_tavily", { query: "q3" });
  // A is tried once, then skipped while cooling
  assert.deepEqual(env.calls.map((c) => c.auth), ["tvly-A", "tvly-B", "tvly-B", "tvly-B"]);

  const status = await env.tools.dispatchTool("web_access_status", {});
  assert.match(status, /cooling \(HTTP 432/);
  assert.doesNotMatch(status, /tvly-A\b/, "full keys must not be shown");
});

test("tavily: non-key error (400) fails fast without rotating", async () => {
  env = setup({ tavily: { keys: ["tvly-A", "tvly-B"] } }, () => fail(400, "bad request"));
  await assert.rejects(env.tools.dispatchTool("web_search_tavily", { query: "q" }), /Tavily error 400/);
  assert.equal(env.calls.length, 1);
});

test("tavily: requires a key", async () => {
  env = setup({}, defaultHandler);
  await assert.rejects(env.tools.dispatchTool("web_search_tavily", { query: "q" }), /No Tavily API keys/);
  assert.equal(env.calls.length, 0);
});

test("tavily: env TAVILY_API_KEYS is honored", async () => {
  env = setup({}, defaultHandler);
  process.env.TAVILY_API_KEYS = "tvly-ENV1, tvly-ENV2";
  await env.tools.dispatchTool("web_search_tavily", { query: "q" });
  assert.equal(env.calls[0].auth, "tvly-ENV1");
});

// ── Plugin settings (env from .mcp.json user_config substitution) ──

test("plugin env: keys from EXA_API_KEYS / TAVILY_API_KEYS take precedence", async () => {
  env = setup({ tavily: { keys: ["tvly-FILE"] }, exa: { keys: ["e-file"] } }, defaultHandler);
  process.env.TAVILY_API_KEYS = "tvly-P1,tvly-P2";
  process.env.EXA_API_KEYS = "e-p1, e-p2";
  await env.tools.dispatchTool("web_search_tavily", { query: "q" });
  await env.tools.dispatchTool("web_search", { query: "q", provider: "exa" });
  assert.deepEqual(env.calls.map((c) => c.auth), ["tvly-P1", "e-p1"]);
  const status = await env.tools.dispatchTool("web_access_status", {});
  assert.match(status, /2 key\(s\) from env \/ plugin settings/);
});

test("plugin env: unset options (literal placeholders / empty) are ignored", async () => {
  env = setup({ tavily: { keys: ["tvly-FILE"] } }, defaultHandler);
  process.env.TAVILY_API_KEYS = "${user_config.tavily_api_keys}";
  process.env.EXA_API_KEYS = "";
  process.env.WEB_SEARCH_PROVIDER = "${user_config.search_provider}";
  await env.tools.dispatchTool("web_search_tavily", { query: "q" });
  await env.tools.dispatchTool("web_search", { query: "q2" });
  assert.equal(env.calls[0].auth, "tvly-FILE", "falls back to config file");
  assert.equal(env.calls[1].provider, "exa", "provider falls back to auto");
  assert.equal(env.calls[1].auth, null, "Exa keyless");
});

test("plugin env: invalid provider value falls back to auto", async () => {
  env = setup({}, defaultHandler);
  process.env.WEB_SEARCH_PROVIDER = "google";
  await env.tools.dispatchTool("web_search", { query: "q" });
  assert.equal(env.calls[0].provider, "exa");
});

// ── Exa: keyless support ─────────────────────────────────────

test("exa: works keyless when no keys configured", async () => {
  env = setup({}, defaultHandler);
  const out = await env.tools.dispatchTool("web_search", { query: "q" });
  assert.match(out, /Exa Result/);
  assert.equal(env.calls[0].auth, null);
});

test("exa: round-robin, then keyless fallback when all keys rejected", async () => {
  env = setup({ exa: { keys: ["e-1", "e-2"] } }, (call) => (call.auth ? fail(429, "rate") : exaOk(EXA_ONE)));
  const out = await env.tools.dispatchTool("web_search", { query: "q", provider: "exa" });
  assert.match(out, /Exa Result/);
  assert.deepEqual(env.calls.map((c) => c.auth), ["e-1", "e-2", null]);

  // both keys now cooling → next request goes straight to keyless
  await env.tools.dispatchTool("web_search", { query: "q2", provider: "exa" });
  assert.deepEqual(env.calls.slice(3).map((c) => c.auth), [null]);
});

test("exa: keylessFallback=false surfaces the error", async () => {
  env = setup({ exa: { keys: ["e-1"], keylessFallback: false } }, () => fail(429, "rate"));
  await assert.rejects(env.tools.dispatchTool("web_search", { query: "q", provider: "exa" }), /429/);
  assert.equal(env.calls.length, 1);
});

test("exa REST: keys use api.exa.ai with x-api-key; out of credits (402) rotates", async () => {
  env = setup({ exa: { keys: ["e-1", "e-2"] } }, (call) =>
    call.auth === "e-1" ? fail(402, '{"error":"no credits","tag":"NO_MORE_CREDITS"}') : exaOk(EXA_ONE)
  );
  const out = await env.tools.dispatchTool("web_search", { query: "q", provider: "exa" });
  assert.match(out, /Exa Result/);
  assert.deepEqual(env.calls.map((c) => [c.auth, c.rest]), [["e-1", true], ["e-2", true]]);
});

test("exa keyless MCP: quota message inside a 200 body is surfaced", async () => {
  env = setup({}, () => ({
    ok: true,
    status: 200,
    text: async () =>
      `data: ${JSON.stringify({ result: { isError: true, content: [{ type: "text", text: "Rate limit exceeded" }] } })}`,
  }));
  await assert.rejects(env.tools.dispatchTool("web_search", { query: "q", provider: "exa" }), /Rate limit exceeded/);
  assert.equal(env.calls[0].rest, false);
});

test("exa: non-retryable error does not burn through keys", async () => {
  env = setup({ exa: { keys: ["e-1", "e-2"] } }, () => fail(400, "bad"));
  await assert.rejects(env.tools.dispatchTool("web_search", { query: "q", provider: "exa" }), /Exa error 400/);
  assert.equal(env.calls.length, 1);
});

test("exa: overall deadline caps total wait", async () => {
  env = setup({ exa: { keys: ["e-1", "e-2", "e-3"], timeoutMs: 1500 } }, (call) =>
    new Promise((_, reject) => call.signal.addEventListener("abort", () => reject(call.signal.reason)))
  );
  const t0 = Date.now();
  await assert.rejects(env.tools.dispatchTool("web_search", { query: "q", provider: "exa" }));
  assert.ok(Date.now() - t0 < 3000, `took ${Date.now() - t0}ms`);
});

// ── Provider routing ─────────────────────────────────────────

test("auto: Exa first, Tavily on failure", async () => {
  env = setup({ tavily: { keys: ["tvly-A"] }, exa: { keylessFallback: false, keys: ["e-1"] } }, (call) =>
    call.provider === "exa" ? fail(401, "bad key") : tavilyOk(TAV_ONE)
  );
  const out = await env.tools.dispatchTool("web_search", { query: "q" });
  assert.match(out, /Tavily Result/);
  assert.deepEqual(env.calls.map((c) => c.provider), ["exa", "tavily"]);
});

test("auto + recency/site: Tavily first with native filters", async () => {
  env = setup({ tavily: { keys: ["tvly-A"] } }, defaultHandler);
  await env.tools.dispatchTool("web_search", { query: "q", recency: "week", site: "example.com" });
  assert.equal(env.calls[0].provider, "tavily");
  assert.equal(env.calls[0].body.time_range, "week");
  assert.deepEqual(env.calls[0].body.include_domains, ["example.com"]);
});

test("auto without Tavily key: never calls Tavily", async () => {
  env = setup({}, defaultHandler);
  await env.tools.dispatchTool("web_search", { query: "q", recency: "week" });
  assert.deepEqual(env.calls.map((c) => c.provider), ["exa"]);
});

test("provider=tavily without key: uses Exa with a note", async () => {
  env = setup({}, defaultHandler);
  const out = await env.tools.dispatchTool("web_search", { query: "q", provider: "tavily" });
  assert.match(out, /Exa Result/);
  assert.match(out, /no Tavily API key/);
});

test("provider=both: merges, dedupes by URL, shared hits first", async () => {
  env = setup({ tavily: { keys: ["tvly-A"] } }, (call) =>
    call.provider === "exa"
      ? exaOk(
          exaText([
            { title: "Only Exa", url: "https://exa.example/x" },
            { title: "Shared", url: "https://www.shared.example/page/?utm_source=a" },
          ])
        )
      : tavilyOk(
          [
            { title: "Only Tavily", url: "https://tav.example/y", content: "t" },
            { title: "Shared", url: "https://shared.example/page", content: "longer tavily content" },
          ],
          { answer: "the answer" }
        )
  );
  const out = await env.tools.dispatchTool("web_search", { query: "q", provider: "both" });
  assert.match(out, /^\*\*Answer:\*\* the answer/);
  assert.equal((out.match(/### \[Shared\]/g) || []).length, 1);
  assert.ok(out.indexOf("Shared") < out.indexOf("Only Exa"), "shared result floats to top");
  assert.match(out, /via exa \+ tavily/);
  assert.doesNotMatch(out, /N\/A/);
});

test("provider=both without Tavily key: Exa only, no failure note", async () => {
  env = setup({}, defaultHandler);
  const out = await env.tools.dispatchTool("web_search", { query: "q", provider: "both" });
  assert.match(out, /Tavily skipped \(no API key configured\)/);
  assert.doesNotMatch(out, /Tavily failed/);
});

test("config provider default + hot reload", async () => {
  env = setup({ provider: "tavily", tavily: { keys: ["tvly-A"] } }, defaultHandler);
  await env.tools.dispatchTool("web_search", { query: "q1" });
  assert.equal(env.calls[0].provider, "tavily");
  env.writeConfig({ provider: "exa" });
  await env.tools.dispatchTool("web_search", { query: "q2" });
  assert.equal(env.calls[1].provider, "exa");
});

test("web_search_exa always uses Exa, even if default provider is tavily", async () => {
  env = setup({ provider: "tavily", tavily: { keys: ["tvly-A"] } }, defaultHandler);
  await env.tools.dispatchTool("web_search_exa", { query: "q" });
  assert.deepEqual(env.calls.map((c) => c.provider), ["exa"]);
});

test("web_search: numResults clamped to 1..10 for Exa", async () => {
  env = setup({}, defaultHandler);
  await env.tools.dispatchTool("web_search", { query: "q", numResults: 99 });
  assert.equal(env.calls[0].body.params.arguments.numResults, 10);
});

// ── Cache ────────────────────────────────────────────────────

test("cache: identical search served from memory; fresh bypasses", async () => {
  env = setup({}, defaultHandler);
  await env.tools.dispatchTool("web_search", { query: "same" });
  await env.tools.dispatchTool("web_search", { query: "same " }); // whitespace-insensitive
  assert.equal(env.calls.length, 1);
  await env.tools.dispatchTool("web_search", { query: "same", fresh: true });
  assert.equal(env.calls.length, 2);
});

test("cache: disabled with cacheTtlSeconds=0, errors never cached", async () => {
  env = setup({ cacheTtlSeconds: 0 }, defaultHandler);
  await env.tools.dispatchTool("web_search", { query: "q" });
  await env.tools.dispatchTool("web_search", { query: "q" });
  assert.equal(env.calls.length, 2);
});
