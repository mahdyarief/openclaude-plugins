const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const zlib = require("node:zlib");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { setup, ok, fail, exaOk, exaText, tavilyOk } = require("./helpers");

let env;
test.afterEach(() => env?.cleanup());

const OPEN = { fetch: { allowPrivateNetwork: true } };
const LONG = "Real article paragraph with plenty of meaningful words. ".repeat(20);

function htmlResponse(html, contentType = "text/html; charset=utf-8") {
  const buf = Buffer.from(html, "utf-8");
  return {
    ok: true,
    status: 200,
    headers: new Map([["content-type", contentType]]),
    arrayBuffer: async () => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.length),
    text: async () => html,
  };
}

// ── HTML → Markdown ──────────────────────────────────────────

test("markdown: links, emphasis, code, nested lists, tables, code blocks", () => {
  env = setup();
  const { htmlToMarkdown } = require("../html-markdown.js");
  const md = htmlToMarkdown(
    `<article><h1>T</h1><p>See <a href="/docs/x">the docs</a>, <b>bold</b>, <i>it</i> and <code>npm i</code>.</p>
     <ul><li>one<li>two<ul><li>nested</li></ul></ul>
     <ol start="3"><li>c<li>d</ol>
     <pre class="highlight"><code class="language-python">def f():
    return 1</code><button class="copy-button">Copy</button></pre>
     <table><tr><th>Name<th>Value<tr><td>a|b<td>1</table><p>${LONG}</p></article>`,
    { baseUrl: "https://ex.com/a/b" }
  );
  assert.match(md, /^# T/);
  assert.match(md, /See \[the docs\]\(https:\/\/ex\.com\/docs\/x\), \*\*bold\*\*, _it_ and `npm i`\./);
  assert.match(md, /- one\n- two\n {2}- nested/);
  assert.match(md, /3\. c\n4\. d/);
  assert.match(md, /```python\ndef f\(\):\n {4}return 1\n```/);
  assert.doesNotMatch(md, /Copy/);
  assert.match(md, /\| Name \| Value \|\n\| --- \| --- \|\n\| a\\\|b \| 1 \|/);
});

test("markdown: boilerplate removed, real content kept", () => {
  env = setup();
  const { htmlToMarkdown } = require("../html-markdown.js");
  const md = htmlToMarkdown(`<body>
    <div class="cookie-banner">Accept cookies</div>
    <div aria-hidden="true">hidden widget</div>
    <p style="display:none">invisible</p>
    <form id="aspnetForm"><main>
      <h2>Intro<a class="headerlink" href="#intro">¶</a></h2>
      <p>Fact.<sup class="reference"><a href="#cite-1">[1]</a></sup> Spec by <a class="reference external" href="https://rfc.example/1">RFC 1</a>.</p>
      <div class="mw-editsection">[edit]</div>
      <p>${LONG}</p>
    </main></form>
    <div class="share-buttons">Share on X</div>
  </body>`);
  assert.match(md, /## Intro\n/);
  assert.doesNotMatch(md, /¶|\[1\]|\[edit\]|Accept cookies|hidden widget|invisible|Share on X/);
  assert.match(md, /Spec by \[RFC 1\]\(https:\/\/rfc\.example\/1\)/, "Sphinx a.reference links are content");
});

// ── find / format / several URLs ─────────────────────────────

test("findInText: phrase hits with offset + heading; word fallback; no match", () => {
  env = setup();
  const { findInText } = require("../web-fetcher.js");
  const text = `# Doc\n\nIntro text.\n\n## Transport\n\nThe MRT line opened in 2019.\n\n## Food\n\nNasi goreng is popular.`;
  const out = findInText(text, "mrt line");
  assert.match(out, /Found 1 section\(s\) matching "mrt line"/);
  assert.match(out, /\[offset \d+ · under "Transport"\]\n\nThe MRT line opened in 2019\./);
  const off = Number(out.match(/offset (\d+)/)[1]);
  assert.ok(text.slice(off).startsWith("The MRT line"));
  assert.match(findInText(text, "goreng recipe"), /by words/);
  assert.match(findInText(text, "zzzz"), /No matches for "zzzz"/);
});

test("web_get_contents: find, text format and several URLs (one failing)", async () => {
  env = setup(OPEN, (call) => {
    if (call.url.includes("/bad")) return fail(404, "Not Found");
    return htmlResponse(`<title>P</title><article><p>${LONG}</p><h2>Pricing</h2><p>Costs <a href="/buy">10 USD</a>.</p></article>`);
  });
  const found = await env.tools.dispatchTool("web_get_contents", { url: "https://site.example/a", find: "10 USD" });
  assert.match(found, /under "Pricing"/);
  assert.match(found, /Costs \[10 USD\]\(https:\/\/site\.example\/buy\)\./);

  const text = await env.tools.dispatchTool("web_get_contents", { url: "https://site.example/a", format: "text" });
  assert.match(text, /Costs 10 USD\./);

  const multi = await env.tools.dispatchTool("web_get_contents", {
    urls: ["https://site.example/a", "https://site.example/bad"],
  });
  assert.match(multi, /## Content from: https:\/\/site\.example\/a/);
  assert.match(multi, /## Failed: https:\/\/site\.example\/bad\n\nDirect fetch: HTTP 404/);
  assert.equal(env.calls.filter((c) => c.url === "https://site.example/a").length, 1, "document cached once");

  await assert.rejects(
    env.tools.dispatchTool("web_get_contents", { urls: Array.from({ length: 11 }, (_, i) => `https://s.example/${i}`) }),
    /At most 10 URLs/
  );
});

test("web_get_contents: Exa /contents reads a PDF when only an Exa key exists", async () => {
  env = setup({ ...OPEN, exa: { keys: ["e-1"] } }, (call) =>
    call.url === "https://api.exa.ai/contents"
      ? ok({ results: [{ url: "https://site.example/doc.pdf", title: "Doc", text: "PDF body text" }] })
      : htmlResponse("%PDF-1.7", "application/pdf")
  );
  const out = await env.tools.dispatchTool("web_get_contents", { url: "https://site.example/doc.pdf" });
  assert.match(out, /# Doc/);
  assert.match(out, /via Exa/);
  assert.match(out, /PDF body text/);
  assert.deepEqual(env.calls.at(-1).body, { urls: ["https://site.example/doc.pdf"], text: true });
});

// ── Search: several queries, domain cap, filters ─────────────

test("web_search: several queries run in parallel, merged and labelled", async () => {
  env = setup({}, (call) => {
    const q = call.body.params.arguments.query;
    return exaOk(
      exaText(
        q === "alpha"
          ? [{ title: "Shared", url: "https://shared.example/x" }, { title: "A only", url: "https://a.example/1" }]
          : [{ title: "B only", url: "https://b.example/1" }, { title: "Shared", url: "https://shared.example/x" }]
      )
    );
  });
  const out = await env.tools.dispatchTool("web_search", { queries: ["alpha", "beta"] });
  assert.match(out, /_2 queries: 1\. “alpha” · 2\. “beta”_/);
  assert.equal((out.match(/\[Shared\]/g) || []).length, 1, "deduplicated");
  assert.match(out, /### \[Shared\]\(https:\/\/shared\.example\/x\)\n_query 1, 2_/);
  assert.equal(env.calls.length, 2);
});

test("maxPerDomain caps results from one domain (not with site)", async () => {
  const many = Array.from({ length: 5 }, (_, i) => ({ title: `R${i}`, url: `https://same.example/${i}`, content: "c" }));
  env = setup({ tavily: { keys: ["tvly-A"] } }, () => tavilyOk(many));
  const out = await env.tools.dispatchTool("web_search_tavily", { query: "q" });
  assert.equal((out.match(/^### /gm) || []).length, 3);
  assert.match(out, /2 more result\(s\) from already-listed domains hidden/);
  const withSite = await env.tools.dispatchTool("web_search_tavily", { query: "q", site: "same.example" });
  assert.equal((withSite.match(/^### /gm) || []).length, 5);
  const unlimited = await env.tools.dispatchTool("web_search_tavily", { query: "q2", maxPerDomain: 0 });
  assert.equal((unlimited.match(/^### /gm) || []).length, 5);
});

test("filters: excludeSite and date range reach Exa REST and Tavily natively", async () => {
  env = setup({ exa: { keys: ["e-1"] }, tavily: { keys: ["tvly-A"] } }, (c) =>
    c.provider === "exa" ? exaOk(exaText([{ title: "E", url: "https://e.example" }])) : tavilyOk([])
  );
  const f = { excludeSite: ["pinterest.com"], startDate: "2025-01-01", endDate: "2025-03-31", recency: "week" };
  await env.tools.dispatchTool("web_search_exa", { query: "q", ...f });
  const exa = env.calls[0].body;
  assert.deepEqual(exa.excludeDomains, ["pinterest.com"]);
  assert.equal(exa.startPublishedDate, "2025-01-01T00:00:00.000Z", "startDate wins over recency");
  assert.equal(exa.endPublishedDate, "2025-03-31T23:59:59.999Z");

  await env.tools.dispatchTool("web_search_tavily", { query: "q", ...f, site: "a.com, b.com" });
  const tav = env.calls[1].body;
  assert.deepEqual(tav.include_domains, ["a.com", "b.com"]);
  assert.deepEqual(tav.exclude_domains, ["pinterest.com"]);
  assert.equal(tav.start_date, "2025-01-01");
  assert.equal(tav.end_date, "2025-03-31");
  assert.equal(tav.time_range, undefined);
  assert.equal(tav.include_usage, true);

  await assert.rejects(env.tools.dispatchTool("web_search_exa", { query: "q", startDate: "01/02/2025" }), /YYYY-MM-DD/);
});

// ── Cache: in-flight sharing and persistence ─────────────────

test("identical concurrent calls share one upstream request (even with cache off)", async () => {
  let release;
  const gate = new Promise((r) => (release = r));
  env = setup({ cacheTtlSeconds: 0 }, async () => {
    await gate;
    return exaOk(exaText([{ title: "X", url: "https://x.example" }]));
  });
  const a = env.tools.dispatchTool("web_search", { query: "same" });
  const b = env.tools.dispatchTool("web_search", { query: "same" });
  release();
  const [ra, rb] = await Promise.all([a, b]);
  assert.equal(ra, rb);
  assert.equal(env.calls.length, 1);
});

test("cachePersist: results survive a restart via web-access-cache.json", async () => {
  env = setup({ cachePersist: true }, () => exaOk(exaText([{ title: "Persisted", url: "https://p.example" }])));
  const first = await env.tools.dispatchTool("web_search", { query: "keep me" });
  require("../cache.js").saveToDisk();
  const file = path.join(path.dirname(env.cfgFile), "web-access-cache.json");
  assert.ok(fs.existsSync(file));

  // simulate a new server process: fresh modules, same config dir
  for (const id of Object.keys(require.cache)) if (!id.includes(`${path.sep}test${path.sep}`)) delete require.cache[id];
  const tools = require("../tools.js");
  const again = await tools.dispatchTool("web_search", { query: "keep me" });
  assert.equal(again, first);
  assert.equal(env.calls.length, 1, "second call served from disk");
});

// ── Budgets and usage ────────────────────────────────────────

test("Tavily daily credit budget: reported credits are counted, then refused (auto falls back to Exa)", async () => {
  env = setup({ tavily: { keys: ["tvly-A"], dailyCreditBudget: 2 } }, (c) => {
    if (c.provider === "tavily") return tavilyOk([{ title: "T", url: "https://t.example", content: "t" }], { usage: { credits: 1 } });
    return exaOk(exaText([{ title: "Exa fallback", url: "https://e.example" }]));
  });
  await env.tools.dispatchTool("web_search_tavily", { query: "one" });
  await env.tools.dispatchTool("web_search_tavily", { query: "two" });
  await assert.rejects(env.tools.dispatchTool("web_search_tavily", { query: "three" }), /Daily Tavily budget reached \(2 \/ 2/);
  const out = await env.tools.dispatchTool("web_search", { query: "four", provider: "tavily" });
  assert.match(out, /Exa fallback/);
  const status = await env.tools.dispatchTool("web_access_status", {});
  assert.match(status, /today \(UTC\): 2 credits over 2 request\(s\) · budget 2 credits/);
  const state = JSON.parse(fs.readFileSync(path.join(path.dirname(env.cfgFile), "web-access-state.json"), "utf8"));
  assert.equal(state.spend.tavily, 2);
});

test("Exa daily USD budget uses costDollars", async () => {
  env = setup({ exa: { keys: ["e-1"], dailyBudgetUsd: 0.01 } }, () => exaOk(exaText([{ title: "E", url: "https://e.example" }])));
  await env.tools.dispatchTool("web_search_exa", { query: "a" }); // 0.005
  await env.tools.dispatchTool("web_search_exa", { query: "b" }); // 0.010
  await assert.rejects(env.tools.dispatchTool("web_search_exa", { query: "c" }), /Daily Exa budget reached/);
});

test("Tavily keyless mode is opt-in and only for search/extract", async () => {
  env = setup({ tavily: { keyless: true } }, () => tavilyOk([{ title: "K", url: "https://k.example", content: "k" }]));
  const out = await env.tools.dispatchTool("web_search_tavily", { query: "q" });
  assert.match(out, /\[K\]/);
  assert.equal(env.calls[0].headers["X-Tavily-Access-Mode"], "keyless");
  assert.equal(env.calls[0].headers.Authorization, undefined);
  await assert.rejects(env.tools.dispatchTool("web_map", { url: "https://x.example" }), /No Tavily API keys/);
});

// ── Crawl, GitHub, MCP metadata ──────────────────────────────

test("web_crawl drops lines repeated across pages", async () => {
  const banner = "> ## Documentation Index\n> Fetch the complete documentation index at: [/llms.txt](https://d.example/llms.txt)";
  env = setup({ tavily: { keys: ["tvly-A"] } }, () =>
    ok({
      results: [
        { url: "https://d.example/a", raw_content: `${banner}\n\nPage A body` },
        { url: "https://d.example/b", raw_content: `${banner.replace("[/llms.txt](https://d.example/llms.txt)", "</llms.txt>")}\n\nPage B body` },
      ],
    })
  );
  const out = await env.tools.dispatchTool("web_crawl", { url: "https://d.example" });
  assert.doesNotMatch(out, /Documentation Index/);
  assert.match(out, /### https:\/\/d\.example\/a\n\nPage A body/);
  assert.match(out, /line\(s\) repeated across pages removed/);
});

test("github_read: README, directory listing, file with find", async () => {
  process.env.GITHUB_TOKEN = "test-token";
  try {
    env = setup({}, (c) => {
      if (c.url.endsWith("/repos/o/r/readme")) return { ok: true, status: 200, headers: new Map(), text: async () => "# R\n\nHello" };
      if (c.url.endsWith("/contents/src"))
        return ok([
          { name: "b.js", path: "src/b.js", type: "file", size: 10 },
          { name: "lib", path: "src/lib", type: "dir", size: 0 },
        ]);
      if (c.url.includes("/contents/src/b.js?ref=dev")) {
        const content = Buffer.from("line one\n\nfunction target() {}\n").toString("base64");
        return ok({ type: "file", encoding: "base64", content, size: 30 });
      }
      return fail(404);
    });
    assert.match(await env.tools.dispatchTool("github_read", { repo: "o/r" }), /## o\/r — README\n\n# R\n\nHello/);
    assert.match(await env.tools.dispatchTool("github_read", { repo: "o/r", path: "src" }), /- 📁 src\/lib\/\n- src\/b\.js \(10 bytes\)/);
    const f = await env.tools.dispatchTool("github_read", {
      repo: "https://github.com/o/r/blob/dev/src/b.js",
      find: "target",
    });
    assert.match(f, /o\/r@dev — src\/b\.js/);
    assert.match(f, /function target\(\) \{\}/);
    await assert.rejects(env.tools.dispatchTool("github_read", { repo: "o/missing" }), /Not found: README/);
    assert.equal(env.calls[0].headers.Authorization, "Bearer test-token");
  } finally {
    delete process.env.GITHUB_TOKEN;
  }
});

test("every tool is annotated read-only", () => {
  env = setup();
  for (const t of env.tools.TOOLS) {
    assert.equal(t.annotations?.readOnlyHint, true, t.name);
    assert.equal(t.annotations?.destructiveHint, false, t.name);
    assert.ok(t.annotations?.title, t.name);
  }
});

// ── Pinned transport (real sockets, local server) ────────────

test("pinned transport: refuses private IPs at connect time, decodes gzip, follows redirects", async () => {
  const server = http.createServer((req, res) => {
    if (req.url === "/redirect") {
      res.writeHead(302, { Location: "/page" });
      return res.end();
    }
    const html = `<html><head><title>Local</title></head><body><article><h1>Hi</h1><p>${LONG}</p></article></body></html>`;
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Content-Encoding": "gzip" });
    res.end(zlib.gzipSync(html));
  });
  // No host → dual-stack (:: + IPv4), so "localhost" works whether it resolves
  // to ::1 (Node 18 without happy-eyeballs) or 127.0.0.1.
  await new Promise((r) => server.listen(0, r));
  const port = server.address().port;
  const prev = process.env.WEB_ACCESS_DIRECT_TRANSPORT;
  try {
    env = setup(OPEN);
    const { pinnedFetch, fetchDocument } = require("../web-fetcher.js");
    const { BlockedUrlError } = require("../url-guard.js");

    // DNS-rebinding style: the URL check was skipped, the socket lookup still refuses
    await assert.rejects(
      pinnedFetch(`http://localhost:${port}/page`, { headers: {}, allowPrivate: false }),
      (err) => err instanceof BlockedUrlError || /private IP/.test(err.message)
    );

    delete process.env.WEB_ACCESS_DIRECT_TRANSPORT; // use the real pinned transport
    const doc = await fetchDocument(`http://localhost:${port}/redirect`);
    assert.equal(doc.title, "Local");
    assert.match(doc.text, /^# Hi/);
    assert.equal(doc.finalUrl, `http://localhost:${port}/page`);
  } finally {
    process.env.WEB_ACCESS_DIRECT_TRANSPORT = prev;
    server.close();
  }
});
