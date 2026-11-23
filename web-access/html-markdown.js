/**
 * HTML → Markdown, no dependencies.
 *
 * A small forgiving HTML parser builds a tree (good enough for real-world,
 * sloppy HTML: implicit </p>, </li>, </td> …), then the main content is picked
 * (<article> / <main> / role=main, else <body>), boilerplate is dropped
 * (navigation, ads, cookie banners, hidden elements, edit links, citation
 * markers …) and the rest is rendered as Markdown: headings, paragraphs,
 * links (absolute), bold/italic, inline code, fenced code blocks (with
 * language), nested lists, blockquotes and tables.
 */

const VOID = new Set("area base br col embed hr img input link meta param source track wbr keygen".split(" "));
// Elements whose content is not HTML (or never useful) — skipped entirely.
const SKIP_RAW = new Set(["script", "style", "textarea", "title", "noscript", "template", "svg", "math", "iframe", "object"]);
// Always dropped (with their content).
const DROP_TAGS = new Set([
  "nav", "aside", "button", "select", "dialog", "input", "canvas", "embed", "video", "audio", "picture",
  "map", "menu", "head", "link", "meta",
]);
const BLOCK = new Set([
  "p", "div", "section", "article", "main", "header", "footer", "figure", "figcaption", "address", "details",
  "summary", "center", "body", "html", "fieldset", "legend", "caption", "form", "hgroup", "#root",
]);
const ROLE_NOISE = /^(navigation|banner|contentinfo|complementary|search|dialog|alertdialog|menu|menubar|toolbar|tablist)$/i;
// Class / id tokens that mark boilerplate (matched against whole tokens).
const NOISE_TOKEN = new RegExp(
  "^(?:" +
    [
      "nav", "navbar", "navigation", "menu", "menubar", "masthead", "toc", "hatnote", "noprint", "metadata",
      "references", "reflist", "interlanguage-link", "vector-dropdown", "vector-menu[\\w-]*",
      "vector-page-toolbar", "vector-sticky-header", "mw-portlet[\\w-]*", "headerlink", "copy-?button", "copybtn",
      "catlinks", "printfooter", "comments?", "comment-list", "footer",
      "site-(?:header|footer|nav)", "skip-link", "mw-jump-link", "mw-editsection", "mw-indicators",
      "mw-references-wrap", "locmap", "switcher-container", "sistersitebox", "authority-control", "portalbox",
      "consent", "subscribe", "related(?:-[\\w-]+)?", "mw-kartographer(?:-[\\w-]+)?",
      "(?:ad|ads|advert\\w*|cookie\\w*|social|share\\w*|navbox|sidebar|breadcrumbs?|newsletter|popup|modal|gdpr|paywall)(?:-[\\w-]*)?",
    ].join("|") +
    ")$",
  "i"
);

// ── Parser ───────────────────────────────────────────────────

const TOKEN =
  /<!--[\s\S]*?(?:-->|$)|<![^>]*>|<\?[^>]*>|<\/([a-zA-Z][\w:-]*)\s*>|<([a-zA-Z][\w:-]*)((?:[^>"']|"[^"]*"|'[^']*')*)>/g;
const ATTR = /([^\s"'>\/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g;

function parseAttrs(s) {
  const attrs = {};
  if (!s) return attrs;
  let m;
  ATTR.lastIndex = 0;
  while ((m = ATTR.exec(s))) {
    const name = m[1].toLowerCase();
    if (!(name in attrs)) attrs[name] = decodeEntities(m[2] ?? m[3] ?? m[4] ?? "");
  }
  return attrs;
}

const CLOSES_P = new Set([
  "p", "div", "ul", "ol", "dl", "table", "pre", "blockquote", "section", "article", "header", "footer", "nav",
  "aside", "form", "hr", "figure", "main", "h1", "h2", "h3", "h4", "h5", "h6", "address", "details", "fieldset",
]);

function parseHtml(html) {
  const root = { tag: "#root", attrs: {}, children: [], parent: null };
  let cur = root;
  const lower = html.toLowerCase();

  const openUntil = (tags, stopAt) => {
    // nearest open element in `tags`, not crossing an element in `stopAt`
    for (let n = cur; n && n !== root; n = n.parent) {
      if (tags.has(n.tag)) return n;
      if (stopAt.has(n.tag)) return null;
    }
    return null;
  };
  const closeNode = (n) => {
    if (n) cur = n.parent || root;
  };

  let last = 0;
  let m;
  TOKEN.lastIndex = 0;
  while ((m = TOKEN.exec(html))) {
    if (m.index > last) cur.children.push(html.slice(last, m.index));
    last = TOKEN.lastIndex;

    if (m[1]) {
      const tag = m[1].toLowerCase();
      for (let n = cur; n && n !== root; n = n.parent) {
        if (n.tag === tag) {
          cur = n.parent;
          break;
        }
      }
      continue;
    }
    if (!m[2]) continue; // comment / doctype / processing instruction

    const tag = m[2].toLowerCase();
    if (SKIP_RAW.has(tag)) {
      const end = lower.indexOf(`</${tag}`, last);
      const gt = end === -1 ? -1 : html.indexOf(">", end);
      last = TOKEN.lastIndex = gt === -1 ? html.length : gt + 1;
      continue;
    }

    // implicit end tags
    if (CLOSES_P.has(tag) && cur.tag === "p") closeNode(cur);
    if (tag === "li") closeNode(openUntil(new Set(["li"]), new Set(["ul", "ol", "menu"])));
    if (tag === "dt" || tag === "dd") closeNode(openUntil(new Set(["dt", "dd"]), new Set(["dl"])));
    if (tag === "tr") closeNode(openUntil(new Set(["tr"]), new Set(["table"])));
    if (tag === "td" || tag === "th") closeNode(openUntil(new Set(["td", "th"]), new Set(["tr", "table"])));
    if (tag === "tbody" || tag === "thead" || tag === "tfoot") {
      closeNode(openUntil(new Set(["tbody", "thead", "tfoot"]), new Set(["table"])));
    }
    if (tag === "option") closeNode(openUntil(new Set(["option"]), new Set(["select"])));

    const attrStr = m[3] || "";
    const node = { tag, attrs: parseAttrs(attrStr), children: [], parent: cur };
    cur.children.push(node);
    if (!VOID.has(tag) && !/\/\s*$/.test(attrStr)) cur = node;
  }
  if (last < html.length) cur.children.push(html.slice(last));
  return root;
}

// ── Tree helpers ─────────────────────────────────────────────

function textContent(node) {
  if (typeof node === "string") return decodeEntities(node);
  if (node.tag === "br") return "\n";
  return node.children.map(textContent).join("");
}

function findAll(node, pred, out = []) {
  for (const c of node.children) {
    if (typeof c === "string") continue;
    if (pred(c)) out.push(c);
    else findAll(c, pred, out);
  }
  return out;
}

function hasDescendant(node, pred) {
  return findAll(node, pred).length > 0;
}

const _len = new WeakMap();
function textLen(node) {
  if (typeof node === "string") return node.replace(/\s+/g, " ").trim().length;
  if (_len.has(node)) return _len.get(node);
  const n = node.children.reduce((s, c) => s + textLen(c), 0);
  _len.set(node, n);
  return n;
}

// Class-based noise is only applied to containers; inline elements such as
// <a class="reference"> (Sphinx) carry real content.
const INLINE = new Set(["a", "span", "code", "em", "strong", "b", "i", "small", "abbr", "cite", "time", "mark", "label"]);

function isNoise(node) {
  const { tag, attrs } = node;
  if (tag === "sup" && /\breference\b/.test(attrs.class || "")) return true; // Wikipedia [1] markers
  if (DROP_TAGS.has(tag)) return true;
  if ("hidden" in attrs) return true;
  if (attrs["aria-hidden"] === "true") return true;
  if (attrs.style && /display\s*:\s*none|visibility\s*:\s*hidden/i.test(attrs.style)) return true;
  if (attrs.role && ROLE_NOISE.test(attrs.role.trim())) return true;
  const tokens = `${attrs.class || ""} ${attrs.id || ""}`.split(/\s+/).filter(Boolean);
  if (!INLINE.has(tag) && tokens.some((t) => NOISE_TOKEN.test(t))) {
    // never drop a container that clearly holds the page's main content
    return !(textLen(node) > 3000 && hasDescendant(node, (n) => /^(p|h1|h2)$/.test(n.tag)));
  }
  if (tag === "header") return !hasDescendant(node, (n) => n.tag === "h1");
  if (tag === "footer") return true;
  if (tag === "form") return textLen(node) < 1000; // ASP.NET pages wrap the whole page in a <form>
  return false;
}

/** Main content: <article> / <main> / role=main when they hold enough text, else <body>. */
function pickMain(root) {
  const preds = [
    (n) => n.tag === "article",
    (n) => n.tag === "main",
    (n) => (n.attrs.role || "").toLowerCase() === "main",
  ];
  for (const p of preds) {
    const nodes = findAll(root, p);
    if (nodes.reduce((s, n) => s + textLen(n), 0) > 500) return nodes;
  }
  const body = findAll(root, (n) => n.tag === "body")[0];
  return [body || root];
}

// ── Renderer ─────────────────────────────────────────────────

const IND = "\u0001"; // indentation marker (survives line trimming)
const PH = "\u0002"; // code block placeholder delimiter

function inline(s) {
  return s.replace(/\s+/g, " ").trim();
}

function wrap(inner, mark) {
  const t = inline(inner);
  if (!t || inner.includes("\n\n")) return inner;
  const lead = /^\s/.test(inner) ? " " : "";
  const trail = /\s$/.test(inner) ? " " : "";
  return `${lead}${mark}${t}${mark}${trail}`;
}

function resolveUrl(href, base) {
  if (!href) return null;
  const h = href.trim();
  if (!h || h.startsWith("#") || /^(javascript|data|vbscript):/i.test(h)) return null;
  try {
    return base ? new URL(h, base).toString() : new URL(h).toString();
  } catch {
    return null;
  }
}

function renderChildren(node, ctx) {
  let out = "";
  for (const c of node.children) {
    out += typeof c === "string" ? decodeEntities(c).replace(/\s+/g, " ") : renderNode(c, ctx);
  }
  return out;
}

function renderNode(node, ctx) {
  if (isNoise(node)) return "";
  const tag = node.tag;

  if (/^h[1-6]$/.test(tag)) {
    const t = inline(renderChildren(node, ctx));
    return t ? `\n\n${"#".repeat(Number(tag[1]))} ${t}\n\n` : "";
  }
  if (BLOCK.has(tag)) return `\n\n${renderChildren(node, ctx)}\n\n`;

  switch (tag) {
    case "br":
      return "\n";
    case "hr":
      return "\n\n---\n\n";
    case "img":
      return "";
    case "a": {
      const inner = renderChildren(node, ctx);
      const t = inline(inner);
      if (!t || /^[#¶§🔗]$/u.test(t)) return ""; // heading permalink anchors
      const url = ctx.links ? resolveUrl(node.attrs.href, ctx.base) : null;
      if (!url || inner.includes("\n\n")) return inner;
      const lead = /^\s/.test(inner) ? " " : "";
      const trail = /\s$/.test(inner) ? " " : "";
      return `${lead}[${t.replace(/([[\]])/g, "\\$1")}](${url.replace(/[()]/g, encodeURIComponent)})${trail}`;
    }
    case "strong":
    case "b":
      return wrap(renderChildren(node, ctx), "**");
    case "em":
    case "i":
      return wrap(renderChildren(node, ctx), "_");
    case "del":
    case "s":
    case "strike":
      return wrap(renderChildren(node, ctx), "~~");
    case "code":
    case "kbd":
    case "samp":
    case "tt": {
      const t = textContent(node).replace(/\s+/g, " ").trim();
      if (!t) return "";
      const fence = t.includes("`") ? "``" : "`";
      return `${fence}${t}${fence}`;
    }
    case "pre":
      return renderPre(node, ctx);
    case "ul":
    case "ol":
      return renderList(node, ctx);
    case "li":
      return `\n- ${inline(renderChildren(node, ctx))}\n`;
    case "blockquote": {
      const body = tidy(renderChildren(node, ctx));
      if (!body) return "";
      return `\n\n${body.split("\n").map((l) => (l ? `> ${l}` : ">")).join("\n")}\n\n`;
    }
    case "table":
      return renderTable(node, ctx);
    case "dl":
      return `\n\n${renderChildren(node, ctx)}\n\n`;
    case "dt": {
      const t = inline(renderChildren(node, ctx));
      return t ? `\n\n**${t}**\n` : "";
    }
    case "dd":
      return `\n${renderChildren(node, ctx)}\n`;
    default:
      return renderChildren(node, ctx);
  }
}

function renderPre(node, ctx) {
  const codeChild = node.children.find((c) => typeof c !== "string" && c.tag === "code");
  const cls = `${node.attrs.class || ""} ${codeChild?.attrs.class || ""} ${node.attrs["data-lang"] || ""}`;
  const lang = (cls.match(/(?:language|lang|highlight-source)-([\w+#.-]+)/i)?.[1] || node.attrs["data-lang"] || "")
    .toLowerCase()
    .replace(/[^\w+#.-]/g, "");
  // Only the <code> parts when present: skips copy buttons, language labels, toggles.
  const codes = findAll(node, (n) => n.tag === "code");
  const code = (codes.length ? codes.map((c) => textContent(c).replace(/\s+$/, "")).join("\n\n") : textContent(node))
    .replace(/\r\n?/g, "\n")
    .replace(/^\n+|\s+$/g, "");
  if (!code.trim()) return "";
  const fence = code.includes("```") ? "~~~~" : "```";
  ctx.blocks.push(`${fence}${lang}\n${code}\n${fence}`);
  return `\n\n${PH}${ctx.blocks.length - 1}${PH}\n\n`;
}

function renderList(node, ctx) {
  const ordered = node.tag === "ol";
  let n = Number(node.attrs.start) || 1;
  const items = [];
  for (const c of node.children) {
    if (typeof c === "string") {
      if (c.trim()) items.push({ body: decodeEntities(c).trim() });
      continue;
    }
    if (isNoise(c)) continue;
    const body = tidy(c.tag === "li" ? renderChildren(c, ctx) : renderNode(c, ctx));
    if (body) items.push({ body, li: c.tag === "li" });
  }
  if (!items.length) return "";
  const lines = [];
  for (const it of items) {
    const marker = ordered ? `${n++}. ` : "- ";
    const pad = IND.repeat(marker.length);
    it.body
      .split("\n")
      .filter((l, i, arr) => l || (i > 0 && i < arr.length - 1 && arr[i + 1]))
      .forEach((l, i) => lines.push(i === 0 ? `${marker}${l}` : l ? `${pad}${l}` : ""));
  }
  return `\n\n${lines.join("\n").replace(/\n{2,}/g, "\n")}\n\n`;
}

function tableRows(node) {
  const rows = [];
  for (const c of node.children) {
    if (typeof c === "string") continue;
    if (c.tag === "tr") rows.push(c);
    else if (c.tag === "thead" || c.tag === "tbody" || c.tag === "tfoot") rows.push(...tableRows(c));
  }
  return rows;
}

function renderTable(node, ctx) {
  const rows = tableRows(node)
    .filter((r) => !isNoise(r))
    .map((r) => r.children.filter((c) => typeof c !== "string" && (c.tag === "td" || c.tag === "th") && !isNoise(c)));
  const caption = node.children.find((c) => typeof c !== "string" && c.tag === "caption");
  const cols = Math.max(0, ...rows.map((r) => r.length));

  // Layout tables (one column, nested tables, or huge cells) → render as blocks.
  const layout =
    cols <= 1 ||
    hasDescendant(node, (n) => n.tag === "table") ||
    rows.some((r) => r.some((c) => textLen(c) > 600));
  if (layout) {
    return `\n\n${rows.map((r) => r.map((c) => `\n\n${renderChildren(c, ctx)}\n\n`).join("")).join("")}\n\n`;
  }

  const cellText = (c) =>
    inline(renderChildren(c, ctx).replace(new RegExp(`${PH}(\\d+)${PH}`, "g"), (_, i) => ctx.blocks[i].replace(/\n/g, " ")))
      .replace(/\|/g, "\\|");
  const matrix = rows.map((r) => r.map(cellText)).filter((r) => r.some(Boolean));
  if (!matrix.length) return "";
  const width = Math.max(...matrix.map((r) => r.length));
  const line = (r) => `| ${Array.from({ length: width }, (_, i) => r[i] || "").join(" | ")} |`;
  const out = [line(matrix[0]), `|${" --- |".repeat(width)}`, ...matrix.slice(1).map(line)];
  const cap = caption ? `${inline(renderChildren(caption, ctx))}\n\n` : "";
  return `\n\n${cap}${out.join("\n")}\n\n`;
}

/** Trim every line, collapse blank lines, restore list indentation. */
function tidy(s) {
  return s
    .split("\n")
    .map((l) => l.trim())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/ +([,.;:!?)])/g, "$1")
    .trim();
}

/**
 * @param {string} html
 * @param {object} [opts]
 *   baseUrl — resolve relative links against this URL
 *   links   — keep links as [text](url) (default true)
 * @returns {string} Markdown
 */
function htmlToMarkdown(html, { baseUrl, links = true } = {}) {
  const root = parseHtml(html || "");
  const ctx = { base: baseUrl, links, blocks: [] };
  const md = pickMain(root)
    .map((n) => renderNode(n, ctx))
    .join("\n\n");
  return tidy(md)
    .replace(new RegExp(IND, "g"), " ")
    .replace(new RegExp(`${PH}(\\d+)${PH}`, "g"), (_, i) => ctx.blocks[Number(i)]);
}

/** Title from <title> (or the first <h1>). */
function htmlTitle(html) {
  const t = (html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1] || "").trim();
  return inline(decodeEntities(t.replace(/<[^>]*>/g, "")));
}

/** Markdown → plain-ish text: links become their text. */
function stripLinks(md) {
  return md.replace(/\[((?:\\.|[^\]\\])*)\]\((?:[^()\s]|\([^()]*\))*\)/g, (_, t) => t.replace(/\\([[\]])/g, "$1"));
}

const NAMED_ENTITIES = {
  amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", ndash: "–", mdash: "—", hellip: "…",
  lsquo: "‘", rsquo: "’", ldquo: "“", rdquo: "”", copy: "©", reg: "®", trade: "™", laquo: "«", raquo: "»",
  middot: "·", bull: "•", times: "×", divide: "÷", deg: "°", euro: "€", pound: "£", yen: "¥", cent: "¢",
  sect: "§", para: "¶", rarr: "→", larr: "←", uarr: "↑", darr: "↓", harr: "↔", minus: "−", plusmn: "±",
  thinsp: " ", ensp: " ", emsp: " ", zwj: "", zwnj: "", shy: "",
};

function decodeEntities(s) {
  return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z][a-z0-9]*);/gi, (m, e) => {
    if (e[0] === "#") {
      const code = e[1].toLowerCase() === "x" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      try {
        return String.fromCodePoint(code);
      } catch {
        return m;
      }
    }
    return NAMED_ENTITIES[e.toLowerCase()] ?? m;
  });
}

module.exports = { htmlToMarkdown, htmlTitle, stripLinks, parseHtml, decodeEntities };
