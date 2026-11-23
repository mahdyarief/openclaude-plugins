/**
 * Tavily API Key Rotator — load keys from a JSON file (or env), round-robin.
 *
 * Key sources (first non-empty wins):
 *   1. TAVILY_API_KEYS env  — comma separated; set by the Claude Code plugin's
 *      "tavily_api_keys" option, or manually
 *   2. TAVILY_API_KEY env   — single key
 *   3. Unified config ~/.openclaude/web-access.json → "tavily"  (see config.js)
 *   4. Legacy file: TAVILY_KEYS_FILE env or ~/.openclaude/tavily_keys.json
 *
 * Supported JSON formats:
 *   ["tvly-aaa", "tvly-bbb"]
 *   { "keys": ["tvly-aaa", "tvly-bbb"] }
 *   { "acc1": "tvly-aaa", "acc2": "tvly-bbb" }   (legacy / named)
 */

const fs = require("fs");
const path = require("path");
const os = require("os");
const { getProviderKeys, envKeys } = require("./config");
const { isCooling } = require("./key-health");

const DEFAULT_KEYS_FILE = path.join(os.homedir(), ".openclaude", "tavily_keys.json");
const KEY_PATTERN = /^tvly-[A-Za-z0-9_-]+$/;

let _index = 0;
let _warned = false;
let _source = "none";

function cleanKeys(list) {
  const seen = new Set();
  return list
    .filter((k) => typeof k === "string")
    .map((k) => k.trim())
    .filter((k) => k && KEY_PATTERN.test(k) && !seen.has(k) && seen.add(k));
}

function loadKeys(keysFile = null) {
  if (!keysFile) {
    const fromEnv = cleanKeys(envKeys("TAVILY_API_KEYS", "TAVILY_API_KEY"));
    if (fromEnv.length) {
      _source = "env / plugin settings";
      return fromEnv;
    }
    const fromConfig = cleanKeys(getProviderKeys("tavily"));
    if (fromConfig.length) {
      _source = "config file";
      return fromConfig;
    }
  }

  const filePath = keysFile || process.env.TAVILY_KEYS_FILE || DEFAULT_KEYS_FILE;
  _source = "legacy key file";
  try {
    if (!fs.existsSync(filePath)) {
      if (!_warned) {
        console.error(`[tavily-rotator] No Tavily keys configured (Tavily disabled)`);
        _warned = true;
      }
      return [];
    }

    const data = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    let keys = [];
    if (Array.isArray(data)) keys = cleanKeys(data);
    else if (data && Array.isArray(data.keys)) keys = cleanKeys(data.keys);
    else if (data && typeof data === "object") keys = cleanKeys(Object.values(data));

    if (keys.length === 0) console.error("[tavily-rotator] No valid keys (tvly-...) found in file");
    return keys;
  } catch (err) {
    console.error(`[tavily-rotator] Error loading keys: ${err.message}`);
    return [];
  }
}

/**
 * Returns usable keys ordered from the current round-robin position and
 * advances the position, so each request starts on a different key.
 */
function keysInRotationOrder(keysFile = null) {
  const keys = loadKeys(keysFile);
  if (keys.length === 0) return [];
  const start = _index % keys.length;
  _index = (start + 1) % keys.length;
  // Skip keys on cooldown (exhausted / rate-limited / invalid) — see key-health.js
  return keys
    .slice(start)
    .concat(keys.slice(0, start))
    .filter((k) => !isCooling("tavily", k));
}

function hasKeys(keysFile = null) {
  return loadKeys(keysFile).length > 0;
}

function keySource() {
  return loadKeys().length ? _source : "none";
}

module.exports = { loadKeys, keysInRotationOrder, hasKeys, keySource };
