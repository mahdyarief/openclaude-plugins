/**
 * Result cache for tool calls — saves API credits when the model repeats a
 * request within a few minutes.
 *
 * - TTL from "cacheTtlSeconds" in web-access.json (default 600; 0 disables).
 * - Identical requests that are still in flight share one upstream call
 *   (even with the TTL cache disabled), so parallel duplicates cost once.
 * - Optional persistence ("cachePersist": true): entries are saved to
 *   web-access-cache.json next to the config file (or WEB_ACCESS_CACHE_FILE)
 *   and reused across sessions until they expire. Internal entries (keys
 *   starting with "__", e.g. whole documents) stay in memory only.
 */

const fs = require("fs");
const path = require("path");
const { loadConfig, configPath } = require("./config");

const DEFAULT_TTL_S = 600;
const MAX_ENTRIES = 200;
const MAX_PERSIST_VALUE = 256 * 1024; // don't write huge results to disk

const _store = new Map(); // key → { value, expires }
const _inflight = new Map(); // key → Promise
let _hits = 0;
let _misses = 0;
let _shared = 0;
let _loadedFile = null;
let _saveTimer = null;
let _exitHook = false;

function ttlMs() {
  const v = loadConfig()?.cacheTtlSeconds;
  const s = v === undefined ? DEFAULT_TTL_S : Number(v);
  return Number.isFinite(s) && s > 0 ? s * 1000 : 0;
}

function cacheFile() {
  if (loadConfig()?.cachePersist !== true) return null;
  const env = (process.env.WEB_ACCESS_CACHE_FILE || "").trim();
  return env || path.join(path.dirname(configPath()), "web-access-cache.json");
}

function persistable(key, value) {
  return !key.startsWith("__") && typeof value === "string" && value.length <= MAX_PERSIST_VALUE;
}

function loadFromDisk() {
  const file = cacheFile();
  if (!file || _loadedFile === file) return;
  _loadedFile = file;
  try {
    const data = JSON.parse(fs.readFileSync(file, "utf-8"));
    const now = Date.now();
    for (const [k, v] of Object.entries(data?.entries || {})) {
      if (v && v.expires > now && !_store.has(k)) _store.set(k, v);
    }
  } catch {
    // missing or unreadable cache file — start empty
  }
}

function saveToDisk() {
  const file = cacheFile();
  if (!file) return;
  try {
    const now = Date.now();
    let onDisk = {};
    try {
      onDisk = JSON.parse(fs.readFileSync(file, "utf-8"))?.entries || {};
    } catch {}
    const entries = {};
    for (const [k, v] of Object.entries(onDisk)) if (v && v.expires > now) entries[k] = v;
    for (const [k, v] of _store) if (v.expires > now && persistable(k, v.value)) entries[k] = v;
    const keys = Object.keys(entries).sort((a, b) => entries[b].expires - entries[a].expires).slice(0, MAX_ENTRIES);
    const out = {};
    for (const k of keys) out[k] = entries[k];
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const tmp = `${file}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify({ version: 1, entries: out }));
    fs.renameSync(tmp, file);
  } catch (err) {
    console.error(`[cache] Could not save ${file}: ${err.message}`);
  }
}

function scheduleSave() {
  if (!cacheFile()) return;
  if (!_exitHook) {
    _exitHook = true;
    process.on("exit", () => {
      if (_saveTimer) saveToDisk();
    });
  }
  if (_saveTimer) return;
  _saveTimer = setTimeout(() => {
    _saveTimer = null;
    saveToDisk();
  }, 2000);
  _saveTimer.unref?.();
}

/** Stable key: sorted args so {a,b} and {b,a} hit the same entry. */
function makeKey(tool, args) {
  const sorted = Object.keys(args || {})
    .sort()
    .reduce((o, k) => {
      const v = args[k];
      o[k] = typeof v === "string" ? v.trim() : v;
      return o;
    }, {});
  return `${tool}:${JSON.stringify(sorted)}`;
}

/**
 * Return the cached value for (tool,args) or compute it with fn(). Only
 * successful results are cached; concurrent identical calls share one fn().
 */
async function cached(tool, args, fn) {
  const ttl = ttlMs();
  const key = makeKey(tool, args);

  if (ttl) {
    loadFromDisk();
    const hit = _store.get(key);
    if (hit && hit.expires > Date.now()) {
      _hits++;
      _store.delete(key); // refresh LRU position
      _store.set(key, hit);
      return hit.value;
    }
  }

  const pending = _inflight.get(key);
  if (pending) {
    _shared++;
    return pending;
  }
  _misses++;

  const p = Promise.resolve().then(fn);
  _inflight.set(key, p);
  try {
    const value = await p;
    if (ttl) {
      _store.set(key, { value, expires: Date.now() + ttl });
      while (_store.size > MAX_ENTRIES) _store.delete(_store.keys().next().value);
      if (persistable(key, value)) scheduleSave();
    }
    return value;
  } finally {
    _inflight.delete(key);
  }
}

function stats() {
  const now = Date.now();
  let live = 0;
  for (const v of _store.values()) if (v.expires > now) live++;
  return {
    entries: live,
    hits: _hits,
    misses: _misses,
    shared: _shared,
    ttlSeconds: ttlMs() / 1000,
    file: cacheFile(),
  };
}

function clear() {
  _store.clear();
  _inflight.clear();
  _hits = 0;
  _misses = 0;
  _shared = 0;
  _loadedFile = null;
}

module.exports = { cached, stats, clear, makeKey, saveToDisk };
