/**
 * Exa API Key Rotator — round-robin over keys.
 *
 * Key sources (first non-empty wins):
 *   1. EXA_API_KEYS / EXA_API_KEY env — set by the Claude Code plugin's
 *      "exa_api_keys" option, or manually (comma separated)
 *   2. Unified config ~/.openclaude/web-access.json → "exa"  (see config.js)
 *   3. Legacy file: EXA_KEYS_FILE env or ~/.openclaude/exa_keys.json
 */

const fs = require("fs");
const path = require("path");
const os = require("os");
const { getProviderKeys, envKeys } = require("./config");
const { isCooling } = require("./key-health");

// Default keys file location
const DEFAULT_KEYS_FILE = path.join(os.homedir(), ".openclaude", "exa_keys.json");

let _index = 0;
let _warned = false;
let _source = "none";

function loadKeys(keysFile = null) {
  if (!keysFile) {
    const fromEnv = [...new Set(envKeys("EXA_API_KEYS", "EXA_API_KEY"))];
    if (fromEnv.length) {
      _source = "env / plugin settings";
      return fromEnv;
    }
    const fromConfig = [...new Set(
      getProviderKeys("exa").filter((k) => typeof k === "string" && k.trim()).map((k) => k.trim())
    )];
    if (fromConfig.length) {
      _source = "config file";
      return fromConfig;
    }
  }

  const filePath = keysFile || process.env.EXA_KEYS_FILE || DEFAULT_KEYS_FILE;
  _source = "legacy key file";

  try {
    if (!fs.existsSync(filePath)) {
      if (!_warned) {
        console.error(`[exa-rotator] No Exa keys configured, using anonymous mode`);
        _warned = true;
      }
      return [];
    }

    const content = fs.readFileSync(filePath, "utf-8");
    const data = JSON.parse(content);

    // Support both formats: ["key1", "key2"] or {keys: [...], ...}
    let keys = [];
    if (Array.isArray(data.keys)) {
      keys = data.keys.filter(k => typeof k === "string" && k.trim());
    } else if (typeof data === "object" && Object.keys(data).length > 0) {
      // Legacy format like make3=e50b..., extract all string values
      keys = Object.values(data)
        .filter(k => typeof k === "string" && /^[a-f0-9-]{36}$/.test(k.trim()))
        .map(k => k.trim());
    }

    if (keys.length === 0) {
      console.error("[exa-rotator] No valid keys found in file");
    }

    return keys;
  } catch (err) {
    console.error(`[exa-rotator] Error loading keys: ${err.message}`);
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
    .filter((k) => !isCooling("exa", k));
}

function hasKeys(keysFile = null) {
  return loadKeys(keysFile).length > 0;
}

/** Where the currently loaded keys came from (for web_access_status). */
function keySource() {
  return loadKeys().length ? _source : "none";
}

module.exports = { loadKeys, keysInRotationOrder, hasKeys, keySource };
