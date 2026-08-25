/**
 * Exa API Key Rotator — Load keys from JSON file, round-robin with thread-safe index
 * Source: /home/dy/ai-agent/exa-api-key.json (3 UUIDs)
 */

const fs = require("fs");
const path = require("path");
const os = require("os");

// Default keys file location
const DEFAULT_KEYS_FILE = path.join(os.homedir(), ".openclaude", "exa_keys.json");

let _index = 0;

function loadKeys(keysFile = null) {
  const filePath = keysFile || process.env.EXA_KEYS_FILE || DEFAULT_KEYS_FILE;

  try {
    if (!fs.existsSync(filePath)) {
      console.error(`[exa-rotator] Keys file not found: ${filePath}, using anonymous mode`);
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

function nextKey(keysFile = null) {
  const keys = loadKeys(keysFile);
  if (!keys || keys.length === 0) return null;

  const idx = parseInt(process.env.EXA_KEY_INDEX || "0", 10);
  const key = keys[idx % keys.length];
  process.env.EXA_KEY_INDEX = String((idx + 1) % keys.length);

  return key;
}

function rotateToNext(keysFile = null) {
  const keys = loadKeys(keysFile);
  if (!keys || keys.length === 0) return null;

  const idx = parseInt(process.env.EXA_KEY_INDEX || "0", 10);
  process.env.EXA_KEY_INDEX = String((idx + 1) % keys.length);
  return keys[(idx + 1) % keys.length];
}

module.exports = { loadKeys, nextKey, rotateToNext };
