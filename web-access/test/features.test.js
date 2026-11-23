const test = require("node:test");
const assert = require("node:assert/strict");
const { setup, ok, fail, exaOk, exaText, tavilyOk } = require("./helpers");

let env;
test.afterEach(() => env?.cleanup());

const EXA_ONE = exaText([{ title: "Exa Result", url: "https://exa.example/a" }]);
const TAV = [{ title: "Tav Result", url: "https://tav.example/a", content: "tav", score: 0.9 }];

// ── Exa REST request shape ───────────────────────────────────

test("exa REST: native filters, category, type and highlights budget", async () => {
  env = setup({ exa: { keys: ["e-1"] } }, () => exaOk(EXA_ONE));
  await env.tools.dispatchTool("web_search_exa", {
    query: "q",
    site: "docs.python.org",
    recency: "week",
    category: "news",
    type: "deep",
    maxCharsPerResult: 400,
    livecrawl: "always",
  });
  const b = env.calls[0].body;
  assert.equal(env.calls[0].url, "https://api.exa.ai/search");
  assert.deepEqual(b.includeDomains, ["docs.python.org"]);
  assert.equal(b.category, "news");
  assert.equal(b.type, "deep");
  assert.equal(b.contents.highlights.maxCharacters, 400);
  assert.equal(b.contents.maxAgeHours, 0, "livecrawl=always → maxAgeHours 0");
  const age = Date.now() - Date.parse(b.startPublishedDate);
  assert.ok(age > 6.9 * 86400000 && age < 7.1 * 86400000, "startPublishedDate ≈ 7 days ago");
  assert.equal(b.query, "q", "no site:/after: hints in the query on REST");
});

test("exa: legacy type 'neural' maps to 'auto'", async () => {
  env = setup({ exa: { keys: ["e-1"] } }, () => exaOk(EXA_ONE));
  await env.tools.dispatchTool("web_search_exa", { query: "q", type: "neural" });
  assert.equal(env.calls[0].body.type, "auto");
});

test("exa keyless: filters become query hints on the MCP endpoint", async () => {
  env = setup({}, () => exaOk(EXA_ONE));
  await env.tools.dispatchTool("web_search_exa", { query: "q", site: "x.com", recency: "day" });
  const args = env.calls[0].body.params.arguments;
  assert.match(args.query, /^q site:x\.com after:\d{4}-\d{2}-\d{2}$/);
});

test("auto: with Exa keys, filtered queries stay on Exa (native filters)", async () => {
  env = setup({ exa: { keys: ["e-1"] }, tavily: { keys: ["tvly-A"] } }, (c) =>
    c.provider === "exa" ? exaOk(EXA_ONE) : tavilyOk(TAV)
  );
  await env.tools.dispatchTool("web_search", { query: "q", recency: "week" });
  assert.equal(env.calls[0].provider, "exa");
});

test("tavily search asks for published dates; category news → topic news on fallback", async () => {
  env = setup({ tavily: { keys: ["tvly-A"] } }, (c) => (c.provider === "exa" ? fail(500) : tavilyOk(TAV)));
  await env.tools.dispatchTool("web_search", { query: "q", category: "news" });
  const tav = env.calls.find((c) => c.provider === "tavily");
  assert.equal(tav.body.include_published_date, true);
  assert.equal(tav.body.topic, "news");
});

// ── Answers ──────────────────────────────────────────────────

test("includeAnswer in both mode shows Tavily and Exa answers", async () => {
  env = setup({ exa: { keys: ["e-1"] }, tavily: { keys: ["tvly-A"] } }, (c) => {
    if (c.url.endsWith("/answer")) return ok({ answer: "Exa says 42", citations: [{ title: "s", url: "https://src.example" }] });
    if (c.provider === "exa") return exaOk(EXA_ONE);
    return tavilyOk(TAV, { answer: "Tavily says 42" });
  });
  const out = await env.tools.dispatchTool("web_search", { query: "q", provider: "both", includeAnswer: true });
  assert.match(out, /\*\*Answer \(Tavily\):\*\* Tavily says 42/);
  assert.match(out, /\*\*Answer \(Exa\):\*\* Exa says 42/);
  assert.match(out, /Sources: \[1\]\(https:\/\/src\.example\)/);
});

test("includeAnswer without any key adds a note instead of failing", async () => {
  env = setup({}, () => exaOk(EXA_ONE));
  const out = await env.tools.dispatchTool("web_search", { query: "q", includeAnswer: true });
  assert.match(out, /Exa Result/);
  assert.match(out, /no AI answer available/);
});

// ── Compact output & ranking ─────────────────────────────────

test("maxCharsPerResult trims long snippets at a word boundary", async () => {
  const long = "word ".repeat(1000);
  env = setup({ tavily: { keys: ["tvly-A"] } }, () => tavilyOk([{ title: "T", url: "https://t.example", content: long }]));
  const out = await env.tools.dispatchTool("web_search_tavily", { query: "q", maxCharsPerResult: 200 });
  const snippet = out.split("\n\n").pop();
  assert.ok(snippet.length <= 205, `snippet length ${snippet.length}`);
  assert.match(snippet, /word …$/);
});

test("rank fusion: shared hits first, then single-provider hits interleaved by rank", () => {
  env = setup();
  const { mergeResults } = require("../formatter.js");
  const mk = (n, p) => Array.from({ length: n }, (_, i) => ({ title: `${p}${i}`, url: `https://${p}.example/${i}` }));
  const exa = mk(10, "e");
  const tav = mk(10, "t");
  exa[9] = { title: "shared", url: "https://shared.example/x" };
  tav[9] = { title: "shared", url: "https://shared.example/x" };
  const merged = mergeResults([{ source: "exa", items: exa }, { source: "tavily", items: tav }], 20);
  assert.equal(merged[0].title, "shared", "agreement between providers wins");
  assert.deepEqual(merged[0].sources, ["exa", "tavily"]);
  assert.deepEqual(
    merged.slice(1, 5).map((m) => m.title),
    ["e0", "t0", "e1", "t1"],
    "then fair interleaving by rank"
  );
  assert.equal(merged.length, 19, "shared URL deduplicated");
});

// ── Cooldown semantics ───────────────────────────────────────

test("403 does not bench a key (it is about the URL/content, not the key)", async () => {
  env = setup({ tavily: { keys: ["tvly-A", "tvly-B"] } }, () => fail(403, "URL is not supported"));
  await assert.rejects(env.tools.dispatchTool("web_map", { url: "https://x.example" }), /403/);
  assert.equal(env.calls.length, 1, "no rotation on 403");
  const status = await env.tools.dispatchTool("web_access_status", {});
  assert.doesNotMatch(status, /cooling/);
});

test("429 Retry-After lengthens the cooldown", async () => {
  env = setup({ tavily: { keys: ["tvly-A", "tvly-B"] } }, (c) =>
    c.url.endsWith("/usage") ? ok({}) : c.auth === "tvly-A" ? fail(429, "slow down", { "retry-after": "600" }) : tavilyOk(TAV)
  );
  await env.tools.dispatchTool("web_search_tavily", { query: "q" });
  const status = await env.tools.dispatchTool("web_access_status", {});
  assert.match(status, /cooling \(HTTP 429, (9|10) min left\)/);
});

// ── Map & crawl ──────────────────────────────────────────────

test("web_map lists URLs and sends path filters", async () => {
  env = setup({ tavily: { keys: ["tvly-A"] } }, () =>
    ok({ base_url: "https://docs.example", results: ["https://docs.example/a", "https://docs.example/b"] })
  );
  const out = await env.tools.dispatchTool("web_map", { url: "https://docs.example", selectPaths: ["/a.*"], maxDepth: 9 });
  assert.match(out, /- https:\/\/docs\.example\/a\n- https:\/\/docs\.example\/b/);
  assert.equal(env.calls[0].url, "https://api.tavily.com/map");
  assert.deepEqual(env.calls[0].body.select_paths, ["/a.*"]);
  assert.equal(env.calls[0].body.max_depth, 5, "clamped to 5");
  assert.equal(env.calls[0].body.allow_external, false);
});

test("web_crawl returns per-page content trimmed to maxCharsPerPage", async () => {
  env = setup({ tavily: { keys: ["tvly-A"] } }, () =>
    ok({
      base_url: "https://docs.example",
      results: [
        { url: "https://docs.example/a", raw_content: "Page A " + "text ".repeat(500) },
        { url: "https://docs.example/b", raw_content: "Page B ![img](x.png) body" },
      ],
    })
  );
  const out = await env.tools.dispatchTool("web_crawl", { url: "https://docs.example", maxCharsPerPage: 300 });
  assert.match(out, /### https:\/\/docs\.example\/a\n\nPage A/);
  assert.match(out, /Page B {1,2}body/);
  assert.doesNotMatch(out, /!\[img\]/);
  assert.equal(env.calls[0].body.limit, 10);
});

test("map/crawl require a Tavily key", async () => {
  env = setup({}, () => ok({}));
  await assert.rejects(env.tools.dispatchTool("web_crawl", { url: "https://x.example" }), /No Tavily API keys/);
  assert.equal(env.calls.length, 0);
});

// ── Status: Tavily usage & Exa spend ─────────────────────────

test("status shows Tavily credits per key and Exa spend; usage is cached", async () => {
  env = setup({ exa: { keys: ["e-1"] }, tavily: { keys: ["tvly-A"] } }, (c) => {
    if (c.url.endsWith("/usage")) {
      return ok({
        key: { usage: 150, limit: 1000 },
        account: { current_plan: "Researcher", plan_usage: 500, plan_limit: 1000, paygo_usage: 0, paygo_limit: 0 },
      });
    }
    return exaOk(EXA_ONE);
  });
  await env.tools.dispatchTool("web_search_exa", { query: "q" });
  const s1 = await env.tools.dispatchTool("web_access_status", {});
  await env.tools.dispatchTool("web_access_status", {});
  assert.match(s1, /credits 150 \/ 1000 used/);
  assert.match(s1, /account plan: Researcher · plan 500 \/ 1000 used/);
  assert.match(s1, /spend this session: \$0\.0050 over 1 request/);
  assert.equal(env.calls.filter((c) => c.url.endsWith("/usage")).length, 1, "usage fetched once (10-min cache)");
});
