const test = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const path = require("node:path");
const { setup, ok } = require("./helpers");

let env;
test.afterEach(() => env?.cleanup());

function htmlResponse(html, contentType = "text/html; charset=utf-8") {
  const buf = Buffer.from(html, "utf-8");
  return {
    ok: true,
    status: 200,
    url: "https://site.example/page",
    headers: new Map([["content-type", contentType]]),
    arrayBuffer: async () => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.length),
    text: async () => html,
  };
}

// Test hosts like site.example do not resolve; skip the SSRF DNS check for them.
const OPEN = { fetch: { allowPrivateNetwork: true } };

const LONG = "Real article paragraph with plenty of meaningful words. ".repeat(20);

// ── HTML extraction ──────────────────────────────────────────

test("htmlToText: prefers <article>, drops nav/footer, keeps structure", () => {
  env = setup();
  const { htmlToText } = require("../web-fetcher.js");
  const text = htmlToText(`
    <html><body>
      <nav>Home | About | Login</nav>
      <article><h2>Heading</h2><p>${LONG}</p><ul><li>one</li><li>two</li></ul></article>
      <footer>Copyright junk</footer>
    </body></html>`);
  assert.match(text, /## Heading/);
  assert.match(text, /- one\n- two/);
  assert.doesNotMatch(text, /Login|Copyright/);
});

test("htmlToText: attribute values containing '>' don't leak", () => {
  env = setup();
  const { htmlToText } = require("../web-fetcher.js");
  const text = htmlToText(`<p data-mw='{"a":"x > y"}' title="1 > 0">Hello &amp; &#x263A; &mdash; world</p>`);
  assert.equal(text, "Hello & ☺ — world");
});

test("get_contents: direct fetch used for static pages (no Tavily credits)", async () => {
  env = setup({ ...OPEN, tavily: { keys: ["tvly-A"] } }, (call) =>
    call.provider === "web" ? htmlResponse(`<title>T</title><article><p>${LONG}</p></article>`) : ok({})
  );
  const out = await env.tools.dispatchTool("web_get_contents", { url: "https://site.example/page" });
  assert.match(out, /# T/);
  assert.deepEqual(env.calls.map((c) => c.provider), ["web"]);
});

test("get_contents: thin/JS-rendered page falls back to Tavily Extract", async () => {
  env = setup({ ...OPEN, tavily: { keys: ["tvly-A"] } }, (call) =>
    call.provider === "web"
      ? htmlResponse(`<body><div id="root">Loading the application, please wait...</div></body>`)
      : ok({ results: [{ url: "https://site.example/page", raw_content: "Rendered content ![img](x.png)" }] })
  );
  const out = await env.tools.dispatchTool("web_get_contents", { url: "https://site.example/page" });
  assert.match(out, /Rendered content/);
  assert.doesNotMatch(out, /!\[img\]/, "image markup stripped");
});

test("get_contents: PDF without Tavily key gives actionable error", async () => {
  env = setup(OPEN, () => htmlResponse("%PDF-1.7", "application/pdf"));
  await assert.rejects(
    env.tools.dispatchTool("web_get_contents", { url: "https://site.example/doc.pdf" }),
    /Configure a Tavily API key/
  );
});

test("get_contents: respects maxChars", async () => {
  env = setup(OPEN, () => htmlResponse(`<article><p>${LONG.repeat(10)}</p></article>`));
  const out = await env.tools.dispatchTool("web_get_contents", { url: "https://site.example/p", maxChars: 600 });
  assert.match(out, /more characters — call again with offset=600/);
  assert.ok(out.length < 800);
});

// ── MCP protocol ─────────────────────────────────────────────

function rpc(lines) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(__dirname, "..", "server.js")], {
      env: { ...process.env, WEB_ACCESS_CONFIG: path.join(__dirname, "does-not-exist.json") },
    });
    let out = "";
    child.stdout.on("data", (d) => (out += d));
    child.on("error", reject);
    child.on("close", () =>
      resolve(out.trim().split("\n").filter(Boolean).map((l) => JSON.parse(l)))
    );
    child.stdin.end(lines.map((l) => (typeof l === "string" ? l : JSON.stringify(l))).join("\n") + "\n");
  });
}

test("server: JSON-RPC compliance", async () => {
  const res = await rpc([
    { jsonrpc: "2.0", id: 1, method: "initialize", params: {} },
    { jsonrpc: "2.0", method: "notifications/initialized" },
    { jsonrpc: "2.0", method: "notifications/cancelled", params: {} },
    { jsonrpc: "2.0", id: 2, method: "ping" },
    { jsonrpc: "2.0", id: 3, method: "tools/list" },
    { jsonrpc: "2.0", id: 4, method: "no/such/method" },
    "this is not json",
  ]);
  // notifications produce no responses
  assert.equal(res.length, 5);
  assert.equal(res[0].result.serverInfo.name, "web-access");
  assert.deepEqual(res[1], { jsonrpc: "2.0", id: 2, result: {} });
  const names = res[2].result.tools.map((t) => t.name);
  for (const n of ["web_search", "web_search_tavily", "web_extract_tavily", "web_get_contents", "web_access_status"]) {
    assert.ok(names.includes(n), n);
  }
  assert.equal(res[3].error.code, -32601);
  assert.equal(res[4].error.code, -32700);
});

test("server: tool errors are returned as isError results", async () => {
  const res = await rpc([{ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: "nope", arguments: {} } }]);
  assert.equal(res[0].result.isError, true);
  assert.match(res[0].result.content[0].text, /Unknown tool/);
});
