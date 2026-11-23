/**
 * Key health tracker shared by the Exa and Tavily rotators.
 *
 * A key that gets rejected is put on cooldown so later requests skip it instead
 * of wasting a round-trip on a key that is known to be exhausted.
 *
 * Cooldowns are persisted to a small JSON state file so they survive server
 * restarts (MCP clients usually start a fresh server per session) and are
 * shared between concurrent sessions. The file never contains keys — only a
 * short SHA-256 fingerprint of each key.
 *
 * State file location (client-agnostic, works with any MCP client):
 *   1. WEB_ACCESS_STATE_FILE env
 *   2. next to the config file: <config dir>/web-access-state.json
 *      (default ~/.openclaude/web-access-state.json)
 * Set WEB_ACCESS_STATE_FILE=off (or "none") to keep cooldowns in memory only.
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { configPath } = require("./config");

const MINUTE = 60 * 1000;
const HOUR = 60 * MINUTE;

// HTTP status → how long to skip the key. Only statuses that are about the
// KEY belong here. 403 is deliberately absent: Tavily uses it for "URL not
// supported" and Exa for prohibited content / disabled features — rotating
// keys would not help and would wrongly bench a healthy key.
const COOLDOWNS = {
  429: 1 * MINUTE, // rate limited — short pause (or Retry-After, if longer)
  402: 24 * HOUR, // out of credits / budget exceeded (Exa)
  432: 24 * HOUR, // Tavily: key or plan credit limit exceeded
  433: 24 * HOUR, // Tavily: pay-as-you-go limit exceeded
  401: 6 * HOUR, // invalid key — retried later in case it was a transient auth issue
};
const MAX_RETRY_AFTER = 1 * HOUR;

let _state = new Map(); // fingerprint → { until, status, at, provider }
let _loadedFrom = null;
let _loadedMtime = -1;

function stateFile() {
  const env = (process.env.WEB_ACCESS_STATE_FILE || "").trim();
  if (/^(off|none|false|0)$/i.test(env)) return null;
  if (env) return env;
  return path.join(path.dirname(configPath()), "web-access-state.json");
}

function fingerprint(provider, key) {
  return `${provider}:${crypto.createHash("sha256").update(`${provider}:${key}`).digest("hex").slice(0, 16)}`;
}

/** (Re)load the state file when it changed on disk (another session may have written it). */
function sync() {
  const file = stateFile();
  if (!file) return;
  let mtime = -1;
  try {
    mtime = fs.statSync(file).mtimeMs;
  } catch {
    if (_loadedFrom !== file) {
      _state = new Map();
      _loadedFrom = file;
      _loadedMtime = -1;
    }
    return;
  }
  if (_loadedFrom === file && _loadedMtime === mtime) return;
  try {
    const data = JSON.parse(fs.readFileSync(file, "utf-8"));
    const now = Date.now();
    _state = new Map(
      Object.entries(data?.cooldowns || {}).filter(([, v]) => v && Number(v.until) > now)
    );
  } catch {
    _state = new Map();
  }
  _loadedFrom = file;
  _loadedMtime = mtime;
}

/** Read the whole state file (other sections such as "spend" included). */
function readStateFile() {
  const file = stateFile();
  if (!file) return null;
  try {
    return JSON.parse(fs.readFileSync(file, "utf-8")) || {};
  } catch {
    return {};
  }
}

/** Atomically rewrite the state file with mutate(data); keeps other sections. */
function updateStateFile(mutate) {
  const file = stateFile();
  if (!file) return false;
  try {
    const data = readStateFile() || {};
    mutate(data);
    data.version = 1;
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const tmp = `${file}.${process.pid}.${Date.now()}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
    fs.renameSync(tmp, file);
    return true;
  } catch (err) {
    console.error(`[web-access] Could not save state to ${file}: ${err.message}`);
    return false;
  }
}

function persist() {
  const file = stateFile();
  if (!file) return;
  const now = Date.now();
  const cooldowns = {};
  for (const [k, v] of _state) if (v.until > now) cooldowns[k] = v;
  if (updateStateFile((data) => (data.cooldowns = cooldowns))) {
    try {
      _loadedFrom = file;
      _loadedMtime = fs.statSync(file).mtimeMs;
    } catch {}
  }
}

function shouldRotate(status) {
  return Object.prototype.hasOwnProperty.call(COOLDOWNS, status);
}

/**
 * Put a key on cooldown. For 429, a Retry-After header (seconds or HTTP date)
 * extends the default pause, capped at 1 hour.
 */
function markFailure(provider, key, status, { retryAfter } = {}) {
  if (!key || !shouldRotate(status)) return;
  sync();
  const now = Date.now();
  let ms = COOLDOWNS[status];
  if (status === 429 && retryAfter) {
    const secs = Number(retryAfter);
    const ra = Number.isFinite(secs) ? secs * 1000 : Date.parse(retryAfter) - now;
    if (ra > ms) ms = Math.min(ra, MAX_RETRY_AFTER);
  }
  _state.set(fingerprint(provider, key), { until: now + ms, status, at: now, provider });
  persist();
}

function markSuccess(provider, key) {
  if (!key) return;
  sync();
  if (_state.delete(fingerprint(provider, key))) persist();
}

function cooldownOf(provider, key) {
  sync();
  const id = fingerprint(provider, key);
  const s = _state.get(id);
  if (!s) return null;
  if (s.until <= Date.now()) {
    _state.delete(id);
    return null;
  }
  return s;
}

function isCooling(provider, key) {
  return cooldownOf(provider, key) !== null;
}

function maskKey(key) {
  if (!key) return "(keyless)";
  return key.length <= 12 ? `${key.slice(0, 3)}…` : `${key.slice(0, 8)}…${key.slice(-4)}`;
}

/** Status rows for the web_access_status tool. Never exposes full keys. */
function describeKeys(provider, keys) {
  return keys.map((k) => {
    const s = cooldownOf(provider, k);
    if (!s) return { key: maskKey(k), state: "ready" };
    const mins = Math.ceil((s.until - Date.now()) / MINUTE);
    return { key: maskKey(k), state: `cooling (HTTP ${s.status}, ${mins} min left)` };
  });
}

function reset() {
  _state = new Map();
  persist();
}

module.exports = {
  COOLDOWNS,
  shouldRotate,
  markFailure,
  markSuccess,
  isCooling,
  describeKeys,
  maskKey,
  reset,
  stateFile,
  readStateFile,
  updateStateFile,
};
