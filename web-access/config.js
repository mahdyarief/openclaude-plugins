/**
 * Unified config for web-access — one file for Exa + Tavily keys and settings.
 *
 * Location (first match):
 *   1. WEB_ACCESS_CONFIG env (path)
 *   2. ~/.openclaude/web-access.json
 *
 * Format:
 * {
 *   "provider": "auto",                 // auto | exa | tavily | both
 *   "exa":    { "keys": ["uuid-1", "uuid-2"] },
 *   "tavily": { "keys": ["tvly-aaa", "tvly-bbb"] }
 * }
 *
 * "exa"/"tavily" may also be a plain array of keys.
 * The file is re-read automatically when it changes (no restart needed).
 */

const fs = require("fs");
const path = require("path");
const os = require("os");

const DEFAULT_CONFIG_FILE = path.join(os.homedir(), ".openclaude", "web-access.json");

let _cache = { file: null, mtimeMs: -1, data: {} };

function configPath() {
  return process.env.WEB_ACCESS_CONFIG || DEFAULT_CONFIG_FILE;
}

function loadConfig() {
  const file = configPath();
  try {
    const stat = fs.statSync(file);
    if (_cache.file === file && _cache.mtimeMs === stat.mtimeMs) return _cache.data;
    const data = JSON.parse(fs.readFileSync(file, "utf-8")) || {};
    _cache = { file, mtimeMs: stat.mtimeMs, data };
    return data;
  } catch (err) {
    if (err.code !== "ENOENT") console.error(`[config] Error reading ${file}: ${err.message}`);
    _cache = { file, mtimeMs: -1, data: {} };
    return {};
  }
}

/** Raw key list for a provider from the unified config ([] if none). */
function getProviderKeys(provider) {
  const section = loadConfig()[provider];
  if (Array.isArray(section)) return section;
  if (section && Array.isArray(section.keys)) return section.keys;
  return [];
}

const PROVIDERS = ["auto", "exa", "tavily", "both"];

/**
 * Read an env var, ignoring empty values and unsubstituted placeholders such
 * as "${user_config.tavily_api_keys}" (left behind when a plugin option is unset).
 */
function envValue(name) {
  const v = (process.env[name] || "").trim();
  if (!v || /\$\{[^}]*\}/.test(v)) return "";
  return v;
}

/** Comma/space/newline separated key list from env vars (first non-empty wins). */
function envKeys(...names) {
  for (const n of names) {
    const v = envValue(n);
    if (v) return v.split(/[\s,;]+/).filter(Boolean);
  }
  return [];
}

function getDefaultProvider() {
  for (const v of [envValue("WEB_SEARCH_PROVIDER"), loadConfig().provider]) {
    const p = String(v || "").trim().toLowerCase();
    if (PROVIDERS.includes(p)) return p;
  }
  return "auto";
}

module.exports = {
  loadConfig,
  getProviderKeys,
  getDefaultProvider,
  configPath,
  envValue,
  envKeys,
  PROVIDERS,
};
