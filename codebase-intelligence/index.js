const { fs, path, isCodeFile, getIndexPath } = require("./shared.js");

const INDEX_VERSION = 1;
const MAX_ENTRIES_PER_TOKEN = 30; // cap results per identifier to bound file size
const MAX_TOKENS_PER_LINE = 200;

// Common language keywords / noise tokens to skip from the index.
// Keeps the index focused on user-defined identifiers, not boilerplate.
const STOPWORDS = new Set([
  // JS/TS
  "const", "let", "var", "function", "return", "if", "else", "for", "while", "do",
  "switch", "case", "break", "continue", "new", "delete", "typeof", "instanceof",
  "in", "of", "this", "super", "class", "extends", "import", "export", "from",
  "default", "async", "await", "try", "catch", "finally", "throw", "yield",
  "static", "get", "set", "true", "false", "null", "undefined", "void", "interface",
  "type", "enum", "implements", "private", "protected", "public", "readonly",
  "abstract", "declare", "as", "is", "keyof", "infer", "namespace", "module",
  "require", "exports", "process", "console", "window", "document", "global",
  "Promise", "Array", "Object", "String", "Number", "Boolean", "JSON", "Math",
  "Date", "Error", "Set", "Map", "Buffer",
  // Python
  "def", "pass", "lambda", "with", "raise", "except", "elif", "not", "and", "or",
  "None", "True", "False", "self", "cls", "print", "import", "return", "yield",
  "global", "nonlocal", "assert", "del",
  // Go
  "package", "func", "chan", "range", "select", "struct", "map", "interface",
  "defer", "go", "fallthrough", "goto", "nil",
  // Java
  "int", "long", "double", "float", "boolean", "char", "byte", "short", "native",
  "synchronized", "volatile", "transient", "strictfp", "throws", "instanceof",
  // Rust
  "fn", "mut", "impl", "trait", "mod", "use", "crate", "where", "match", "move",
  "ref", "box", "dyn", "unsafe", "extern", "loop", "loop",
  // misc noise
  "todo", "fixme", "xxx", "i", "ii", "iii", "n", "num", "str", "txt", "val",
]);

const IDENTIFIER_RE = /[A-Za-z_$][A-Za-z0-9_$]*/g;

/**
 * Build an inverted identifier index from discovered files.
 * @param {string[]} files - relative paths (as returned by discovery.discoverFiles)
 * @param {string} cwd - project root, used to resolve file contents
 * @param {string} fingerprint - cache fingerprint (git hash or file-count hash)
 */
function buildIndex(files, cwd, fingerprint) {
  const entries = new Map(); // token -> [{path, line, preview}]

  for (const relFile of files) {
    if (!isCodeFile(relFile)) continue;

    const absFile = path.join(cwd, relFile);
    let content;
    try {
      content = fs.readFileSync(absFile, "utf8");
    } catch {
      continue; // unreadable file — skip
    }

    const lines = content.split("\n");
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      let count = 0;
      IDENTIFIER_RE.lastIndex = 0;
      let m;
      while ((m = IDENTIFIER_RE.exec(line)) !== null) {
        const token = m[0];
        if (token.length >= 2 && !STOPWORDS.has(token)) {
          let arr = entries.get(token);
          if (!arr) {
            arr = [];
            entries.set(token, arr);
          }
          if (arr.length < MAX_ENTRIES_PER_TOKEN) {
            arr.push({ path: relFile.replace(/\\/g, "/"), line: i + 1, preview: line.trim().slice(0, 200) });
          }
        }
        if (++count >= MAX_TOKENS_PER_LINE) break;
      }
    }
  }

  // Convert Map to plain object for JSON serialization
  const indexObj = {};
  for (const [token, arr] of entries) {
    indexObj[token] = arr;
  }

  return {
    version: INDEX_VERSION,
    fingerprint,
    builtAt: new Date().toISOString(),
    tokenCount: entries.size,
    entries: indexObj,
  };
}

function getIndexPathFor(cwd) {
  return getIndexPath(cwd);
}

function loadIndex(cwd) {
  const indexPath = getIndexPath(cwd);
  try {
    if (!fs.existsSync(indexPath)) return null;
    const raw = fs.readFileSync(indexPath, "utf8");
    const index = JSON.parse(raw);
    if (index.version !== INDEX_VERSION) return null;
    return index;
  } catch {
    return null;
  }
}

function saveIndex(cwd, index) {
  const indexPath = getIndexPath(cwd);
  try {
    const dir = path.dirname(indexPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(indexPath, JSON.stringify(index));
    return true;
  } catch {
    return false;
  }
}

/**
 * Query the index. Returns null when the index has no usable hits for the query
 * (e.g. multi-word query, no identifier match) so the caller falls back to rg.
 */
function searchIndex(index, query) {
  if (!index || !index.entries) return null;
  const q = query.trim();
  if (!q || q.length < 2) return null;
  // Only single-identifier queries hit the index — multi-word goes to rg.
  if (/\s/.test(q)) return null;

  let hits = index.entries[q] || [];

  // Prefix fallback for partial identifiers (e.g. "buildSum" -> buildSummary)
  if (hits.length === 0 && q.length >= 3) {
    hits = [];
    for (const [token, arr] of Object.entries(index.entries)) {
      if (token.startsWith(q)) {
        hits.push(...arr);
        if (hits.length >= MAX_ENTRIES_PER_TOKEN) break;
      }
    }
  }

  if (hits.length === 0) return null;

  return hits.map((h) => ({
    ...h,
    reason: "Identifier match via persistent index",
    confidence: "high",
    score: 2.0,
  }));
}

function isIndexFresh(index, fingerprint) {
  return !!index && index.fingerprint === fingerprint && index.version === INDEX_VERSION;
}

module.exports = {
  INDEX_VERSION,
  MAX_ENTRIES_PER_TOKEN,
  buildIndex,
  loadIndex,
  saveIndex,
  searchIndex,
  isIndexFresh,
  getIndexPathFor,
};
