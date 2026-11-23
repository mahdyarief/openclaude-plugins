/**
 * Fetch a URL and return its readable content as Markdown — no dependencies.
 *
 * - SSRF-safe: every redirect hop is checked, and the socket connects only to
 *   an address that passed the check (pinned DNS lookup, see url-guard.js).
 * - Size-capped streaming download (fetch.maxBytes, default 25 MB).
 * - Decodes gzip / deflate / brotli and the page's charset.
 * - HTML → Markdown (html-markdown.js): main content only, links, tables,
 *   code blocks, lists. Plain text / JSON / Markdown are returned as-is.
 * - Throws UnsupportedContentError for PDFs and other binary types so the
 *   caller can fall back to Tavily Extract / Exa contents.
 */

const http = require("http");
const https = require("https");
const zlib = require("zlib");
const { assertPublicUrl, pinnedLookup, BlockedUrlError } = require("./url-guard");
const { htmlToMarkdown, htmlTitle } = require("./html-markdown");

const DEFAULT_MAX_CHARS = 8000;
const DEFAULT_MAX_BYTES = 25 * 1024 * 1024; // stop downloading after 25 MB
const MAX_REDIRECTS = 5;

class UnsupportedContentError extends Error {}

const BROWSER_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
  "Accept-Language": "en-US,en;q=0.7,id;q=0.5",
};

function fetchSettings() {
  const f = require("./config").loadConfig()?.fetch || {};
  return {
    allowPrivate: f.allowPrivateNetwork === true,
    maxBytes: Number(f.maxBytes) > 0 ? Number(f.maxBytes) : DEFAULT_MAX_BYTES,
  };
}

/**
 * Minimal reader over a Node stream with the subset of the web-stream API we
 * use (getReader().read()/cancel(), body.cancel()). Avoids Readable.toWeb,
 * which throws "Controller is already closed" on cancel in Node 18.
 */
function nodeBody(stream, res) {
  const it = stream[Symbol.asyncIterator]();
  const destroy = async () => {
    stream.destroy();
    if (res !== stream) res.destroy();
  };
  const reader = {
    async read() {
      const r = await it.next();
      return r.done ? { done: true, value: undefined } : { done: false, value: r.value };
    },
    cancel: destroy,
  };
  return { getReader: () => reader, cancel: destroy };
}

/**
 * GET over node:http(s) with the pinned lookup. Returns a minimal
 * fetch-like response: { ok, status, statusText, headers, body }.
 */
function pinnedFetch(url, { signal, headers, allowPrivate }) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const mod = u.protocol === "https:" ? https : http;
    const req = mod.request(
      u,
      {
        method: "GET",
        headers: { ...headers, "Accept-Encoding": "gzip, deflate, br" },
        lookup: pinnedLookup(allowPrivate),
        signal,
      },
      (res) => {
        let stream = res;
        const enc = String(res.headers["content-encoding"] || "").toLowerCase();
        if (enc === "gzip" || enc === "x-gzip") stream = res.pipe(zlib.createGunzip());
        else if (enc === "deflate") stream = res.pipe(zlib.createInflate());
        else if (enc === "br") stream = res.pipe(zlib.createBrotliDecompress());
        if (stream !== res) res.on("error", (e) => stream.destroy(e));

        const h = new Headers();
        for (const [k, v] of Object.entries(res.headers)) {
          if (v !== undefined) h.set(k, Array.isArray(v) ? v.join(", ") : String(v));
        }
        resolve({
          ok: res.statusCode >= 200 && res.statusCode < 300,
          status: res.statusCode,
          statusText: res.statusMessage || "",
          headers: h,
          body: nodeBody(stream, res),
        });
      }
    );
    req.on("error", reject);
    req.end();
  });
}

/** Direct-fetch transport. Tests set WEB_ACCESS_DIRECT_TRANSPORT=fetch to use (mocked) global fetch. */
function transport() {
  return process.env.WEB_ACCESS_DIRECT_TRANSPORT === "fetch" ? globalThis.fetch : pinnedFetch;
}

/** Fetch with manual redirect handling so every hop passes the SSRF guard. */
async function guardedFetch(url, { allowPrivate, signal }) {
  const send = transport();
  let current = url;
  for (let hop = 0; hop <= MAX_REDIRECTS; hop++) {
    await assertPublicUrl(current, { allowPrivate });
    const response = await send(current, { signal, headers: BROWSER_HEADERS, redirect: "manual", allowPrivate });
    const location = response.headers.get("location");
    if (response.status >= 300 && response.status < 400 && location) {
      await response.body?.cancel?.().catch(() => {});
      current = new URL(location, current).toString();
      continue;
    }
    return { response, finalUrl: current };
  }
  throw new Error(`Too many redirects (>${MAX_REDIRECTS})`);
}

/** Read at most maxBytes of the body; never buffers an unbounded response. */
async function readLimited(response, maxBytes) {
  if (!response.body || typeof response.body.getReader !== "function") {
    const buf = new Uint8Array(await response.arrayBuffer());
    return { buf: buf.slice(0, maxBytes), cut: buf.length > maxBytes };
  }
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  let cut = false;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (size + value.length > maxBytes) {
      chunks.push(value.slice(0, maxBytes - size));
      size = maxBytes;
      cut = true;
      await reader.cancel().catch(() => {});
      break;
    }
    chunks.push(value);
    size += value.length;
  }
  const buf = new Uint8Array(size);
  let pos = 0;
  for (const c of chunks) {
    buf.set(c, pos);
    pos += c.length;
  }
  return { buf, cut };
}

/**
 * Fetch a URL and return its full readable document as Markdown:
 * { title, text, finalUrl, bytesCut }.
 * Paging / searching for the model is done by the caller (paginate, findInText).
 */
async function fetchDocument(url) {
  const { allowPrivate, maxBytes } = fetchSettings();
  const { response, finalUrl } = await guardedFetch(url, {
    allowPrivate,
    signal: AbortSignal.timeout(20000),
  });

  if (!response.ok) {
    await response.body?.cancel?.().catch(() => {});
    throw new Error(`HTTP ${response.status}: ${response.statusText || ""}`.trim());
  }

  const contentType = (response.headers.get("content-type") || "").toLowerCase();
  if (/application\/pdf/.test(contentType) || /\.pdf$/i.test(new URL(finalUrl).pathname)) {
    await response.body?.cancel?.().catch(() => {});
    throw new UnsupportedContentError("PDF documents are not supported by the direct fetcher");
  }
  if (contentType && !/text\/|html|xml|json|javascript|markdown/.test(contentType)) {
    await response.body?.cancel?.().catch(() => {});
    throw new UnsupportedContentError(`Unsupported content type: ${contentType}`);
  }

  const { buf, cut } = await readLimited(response, maxBytes);
  const raw = decode(buf, contentType);

  let title = "";
  let text;
  if (/html|xml/.test(contentType) || /^\s*</.test(raw)) {
    title = htmlTitle(raw);
    text = htmlToMarkdown(raw, { baseUrl: finalUrl });
  } else {
    text = raw.trim();
  }

  if (text.length < 50) {
    throw new Error("Page content is empty or couldn't be extracted (possibly JS-rendered)");
  }
  return { title, text, finalUrl, bytesCut: cut ? maxBytes : 0 };
}

/** Return one window of a long text plus a hint for reading the next part. */
function paginate(text, { offset = 0, maxChars = DEFAULT_MAX_CHARS } = {}) {
  const total = text.length;
  const start = Math.min(Math.max(0, Math.floor(offset) || 0), total);
  const end = Math.min(start + maxChars, total);
  let out = text.slice(start, end);
  if (start > 0) out = `[… characters ${start}–${end} of ${total}]\n\n${out}`;
  if (end < total) {
    out += `\n\n[… ${total - end} more characters — call again with offset=${end} to continue]`;
  }
  return out;
}

/**
 * Find the parts of a long document that mention `query`.
 * Exact phrase first; if nothing matches, any of its words (≥3 chars),
 * ranked by how many distinct words a section contains. Each hit shows its
 * offset (to continue reading there) and the heading it sits under.
 */
function findInText(text, query, { maxChars = DEFAULT_MAX_CHARS, maxHits = 12 } = {}) {
  const q = String(query || "").trim();
  if (!q) return paginate(text, { maxChars });

  // split into blocks with offsets, remembering the latest heading
  const blocks = [];
  const re = /\n{2,}/g;
  let start = 0;
  let heading = "";
  let m;
  const push = (end) => {
    const body = text.slice(start, end);
    if (body.trim()) {
      const h = body.match(/^#{1,6} .+/)?.[0];
      blocks.push({ start, body, heading: h ? "" : heading });
      if (h) heading = h;
    }
  };
  while ((m = re.exec(text))) {
    push(m.index);
    start = re.lastIndex;
  }
  push(text.length);

  const lower = (s) => s.toLowerCase();
  const phrase = lower(q);
  let hits = blocks.filter((b) => lower(b.body).includes(phrase)).map((b) => ({ ...b, score: 1 }));
  let mode = "phrase";
  let words = [];
  if (!hits.length) {
    words = [...new Set(phrase.split(/[^\p{L}\p{N}]+/u).filter((w) => w.length >= 3))];
    if (words.length) {
      hits = blocks
        .map((b) => ({ ...b, score: words.filter((w) => lower(b.body).includes(w)).length }))
        .filter((b) => b.score > 0)
        .sort((a, b) => b.score - a.score || a.start - b.start);
      mode = "words";
    }
  }
  if (!hits.length) {
    return `No matches for "${q}" in this page (${text.length} characters). Try other words, or read it with offset.`;
  }

  const total = hits.length;
  const shown = hits.slice(0, maxHits).sort((a, b) => a.start - b.start);
  const perHit = Math.max(300, Math.floor(maxChars / shown.length));
  const parts = [];
  let used = 0;
  for (const h of shown) {
    let body = h.body.trim();
    if (body.length > perHit) {
      const lb = lower(body);
      const at = Math.max(0, Math.min(...(mode === "phrase" ? [phrase] : words).map((w) => lb.indexOf(w)).filter((i) => i >= 0)));
      const from = Math.max(0, at - Math.floor(perHit / 3));
      body = `${from > 0 ? "… " : ""}${body.slice(from, from + perHit).trim()} …`;
    }
    const where = h.heading ? ` · under "${h.heading.replace(/^#+\s*/, "")}"` : "";
    const piece = `[offset ${h.start}${where}]\n\n${body}`;
    if (used + piece.length > maxChars && parts.length) break;
    parts.push(piece);
    used += piece.length;
  }
  const head =
    `Found ${total} section(s) matching "${q}"${mode === "words" ? " (by words)" : ""}; ` +
    `showing ${parts.length}. Read around a match with offset=<number>.`;
  return `${head}\n\n${parts.join("\n\n---\n\n")}`;
}

/** Backwards-compatible helper: first window of the document. */
async function fetchWebContent(url, { maxChars = DEFAULT_MAX_CHARS, offset = 0 } = {}) {
  const doc = await fetchDocument(url);
  const body = paginate(doc.text, { offset, maxChars });
  return doc.title && !offset ? `# ${doc.title}\n\n${body}` : body;
}

function decode(buf, contentType) {
  let charset = contentType.match(/charset=["']?([\w-]+)/)?.[1];
  if (!charset) {
    const head = new TextDecoder("latin1").decode(buf.slice(0, 4096));
    charset =
      head.match(/<meta[^>]+charset=["']?([\w-]+)/i)?.[1] ||
      head.match(/<meta[^>]+content=["'][^"']*charset=([\w-]+)/i)?.[1];
  }
  try {
    return new TextDecoder(charset || "utf-8").decode(buf);
  } catch {
    return new TextDecoder("utf-8").decode(buf);
  }
}

/** Kept for compatibility: HTML → readable Markdown. */
function htmlToText(html, opts) {
  return htmlToMarkdown(html, opts);
}

module.exports = {
  fetchWebContent,
  fetchDocument,
  paginate,
  findInText,
  htmlToText,
  pinnedFetch,
  UnsupportedContentError,
  BlockedUrlError,
};
