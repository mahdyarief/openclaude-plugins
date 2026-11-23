const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { setup, fail, tavilyOk } = require("./helpers");

let env;
test.afterEach(() => env?.cleanup());

const OPEN = { fetch: { allowPrivateNetwork: true } };
const LONG = "Meaningful sentence about the topic at hand. ".repeat(40);

function page(html, { status = 200, headers = {}, url = "https://site.example/" } = {}) {
  const buf = Buffer.from(html, "utf-8");
  const h = new Map(Object.entries({ "content-type": "text/html; charset=utf-8", ...headers }));
  return {
    ok: status >= 200 && status < 300,
    status,
    url,
    headers: h,
    arrayBuffer: async () => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.length),
    text: async () => html,
  };
}

// ── SSRF guard ───────────────────────────────────────────────

test("url-guard: classifies private and public IPs", () => {
  env = setup();
  const { isPrivateIp } = require("../url-guard.js");
  for (const ip of ["127.0.0.1", "10.1.2.3", "172.20.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1", "0.0.0.0", "::1", "fd00::1", "fe80::1", "::ffff:127.0.0.1"]) {
    assert.equal(isPrivateIp(ip), true, ip);
  }
  for (const ip of ["8.8.8.8", "93.184.216.34", "1.1.1.1", "2606:4700:4700::1111"]) {
    assert.equal(isPrivateIp(ip), false, ip);
  }
});

test("get_contents: refuses cloud metadata / localhost and never forwards them to Tavily", async () => {
  env = setup({ tavily: { keys: ["tvly-A"] } }, () => page(LONG));
  for (const url of ["http://169.254.169.254/latest/meta-data/", "http://localhost:3000/", "http://127.0.0.1/", "http://printer.local/"]) {
    await assert.rejects(env.tools.dispatchTool("web_get_contents", { url }), /internal address/, url);
  }
  assert.equal(env.calls.length, 0, "no request was made at all");
});

test("get_contents: redirect from a public host to a private one is blocked", async () => {
  env = setup({}, (call) =>
    call.url.startsWith("http://93.184.216.34")
      ? page("", { status: 302, headers: { location: "http://127.0.0.1:8080/admin" } })
      : page(LONG)
  );
  await assert.rejects(env.tools.dispatchTool("web_get_contents", { url: "http://93.184.216.34/go" }), /internal address 127\.0\.0\.1/);
  assert.equal(env.calls.length, 1);
});

test("get_contents: allowPrivateNetwork opts in", async () => {
  env = setup(OPEN, () => page(`<article><p>${LONG}</p></article>`));
  const out = await env.tools.dispatchTool("web_get_contents", { url: "http://127.0.0.1:8080/docs" });
  assert.match(out, /Meaningful sentence/);
});

// ── Download size limit ──────────────────────────────────────

test("get_contents: stops reading after fetch.maxBytes", async () => {
  env = setup({ fetch: { allowPrivateNetwork: true, maxBytes: 2048 } }, () => {
    const big = `<article><p>${"x".repeat(1024 * 1024)}</p></article>`;
    let sent = 0;
    const body = new ReadableStream({
      pull(controller) {
        if (sent >= big.length) return controller.close();
        controller.enqueue(new TextEncoder().encode(big.slice(sent, sent + 1024)));
        sent += 1024;
      },
    });
    return { ok: true, status: 200, headers: new Map([["content-type", "text/html"]]), body };
  });
  const out = await env.tools.dispatchTool("web_get_contents", { url: "https://site.example/big" });
  assert.match(out, /download stopped at/);
  assert.ok(out.length < 4000);
});

// ── Offset paging ────────────────────────────────────────────

test("get_contents: offset pages through a long document without refetching", async () => {
  const text = Array.from({ length: 300 }, (_, i) => `Line number ${i} of the long document.`).join(" ");
  env = setup(OPEN, () => page(`<article><p>${text}</p></article>`));
  const first = await env.tools.dispatchTool("web_get_contents", { url: "https://site.example/long", maxChars: 1000 });
  const next = Number(first.match(/offset=(\d+)/)[1]);
  assert.equal(next, 1000);
  const second = await env.tools.dispatchTool("web_get_contents", { url: "https://site.example/long", maxChars: 1000, offset: next });
  assert.match(second, /\[… characters 1000–2000 of \d+\]/);
  assert.notEqual(first.slice(-200), second.slice(-200));
  assert.equal(env.calls.length, 1, "document fetched once, then served from cache");
});

// ── Persistent cooldowns ─────────────────────────────────────

test("cooldowns persist to a state file (no raw keys) and survive a restart", async () => {
  env = setup({ tavily: { keys: ["tvly-SECRETKEY1", "tvly-B"] } }, (call) =>
    call.auth === "tvly-SECRETKEY1" ? fail(432, "limit") : tavilyOk([{ title: "t", url: "https://a.b", content: "c" }])
  );
  await env.tools.dispatchTool("web_search_tavily", { query: "q1" });

  const { stateFile } = require("../key-health.js");
  const file = stateFile();
  const saved = fs.readFileSync(file, "utf-8");
  assert.match(saved, /"status": 432/);
  assert.doesNotMatch(saved, /SECRETKEY1/, "state file must not contain keys");

  // simulate a new server process: drop module cache, keep the same state file
  for (const id of Object.keys(require.cache)) if (/key-health|rotator|client|tools/.test(id)) delete require.cache[id];
  const tools = require("../tools.js");
  env.calls.length = 0;
  await tools.dispatchTool("web_search_tavily", { query: "q2", fresh: true });
  await tools.dispatchTool("web_search_tavily", { query: "q3", fresh: true });
  assert.deepEqual(env.calls.map((c) => c.auth), ["tvly-B", "tvly-B"], "cooling key skipped after restart");
});

test("WEB_ACCESS_STATE_FILE=off keeps cooldowns in memory only", async () => {
  env = setup({ tavily: { keys: ["tvly-A", "tvly-B"] } }, (call) =>
    call.auth === "tvly-A" ? fail(429) : tavilyOk([])
  );
  process.env.WEB_ACCESS_STATE_FILE = "off";
  await env.tools.dispatchTool("web_search_tavily", { query: "q" });
  const { stateFile } = require("../key-health.js");
  assert.equal(stateFile(), null);
  assert.equal(fs.existsSync(env.cfgFile.replace("web-access.json", "web-access-state.json")), false);
});
