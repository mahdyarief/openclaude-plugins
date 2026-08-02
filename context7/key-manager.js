const fs = require("fs");
const path = require("path");

const CONFIG_PATH = path.join(
  process.env.HOME || process.env.USERPROFILE || "~",
  ".openclaude", "context7-keys.json"
);

let cachedConfig = null;

function defaultConfig() {
  return {
    keys: [],
    settings: { rotationStrategy: "least-used", maxRequestsPerKey: 1000, autoRotate: true },
    stats: { totalRequests: 0, rotationCount: 0, currentPeriodStart: new Date().toISOString(), lastReset: new Date().toISOString() }
  };
}

function loadConfig() {
  if (cachedConfig) return cachedConfig;
  try {
    const dir = path.dirname(CONFIG_PATH);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const raw = fs.readFileSync(CONFIG_PATH, "utf8");
    cachedConfig = JSON.parse(raw);
  } catch {
    cachedConfig = defaultConfig();
    saveConfigRaw(cachedConfig);
  }
  checkMonthlyReset(cachedConfig);
  return cachedConfig;
}

function saveConfigRaw(config) {
  try {
    const dir = path.dirname(CONFIG_PATH);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2));
    cachedConfig = config;
  } catch (e) {
    throw new Error(`Failed to save config: ${e.message}`);
  }
}

function invalidateCache() {
  cachedConfig = null;
}

function checkMonthlyReset(config) {
  const now = new Date();
  const periodStart = new Date(config.stats.currentPeriodStart);
  if (now.getFullYear() !== periodStart.getFullYear() || now.getMonth() !== periodStart.getMonth()) {
    config.keys.forEach(k => { k.requestCount = 0; k.status = "active"; });
    config.stats.totalRequests = 0;
    config.stats.rotationCount = 0;
    config.stats.lastReset = now.toISOString();
    config.stats.currentPeriodStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
    saveConfigRaw(config);
    return true;
  }
  return false;
}

function addKey(apiKey, label) {
  const config = loadConfig();

  // Generate alphabetical IDs: A, B, C, ... Z, AA, AB, ...
  const usedLetters = new Set(config.keys.map(k => {
    const m = k.id.match(/^key([A-Z]+)$/);
    return m ? m[1] : "";
  }));

  let letters = "";
  for (let i = 0; i < 26; i++) {
    letters = String.fromCharCode(65 + i);
    if (!usedLetters.has(letters)) break;
  }
  if (usedLetters.has(letters)) {
    for (let i = 0; i < 26; i++) {
      letters = "A" + String.fromCharCode(65 + i);
      if (!usedLetters.has(letters)) break;
    }
  }

  const id = `key${letters}`;
  const lbl = label || `Key ${letters}`;
  config.keys.push({
    id, apiKey, label: lbl,
    addedAt: new Date().toISOString(), requestCount: 0, lastUsed: null, status: "active"
  });
  saveConfigRaw(config);
  return `✓ Added key: **${id}** (${lbl})`;
}

function removeKey(keyId) {
  const config = loadConfig();
  const idx = config.keys.findIndex(k => k.id === keyId);
  if (idx === -1) throw new Error(`Key not found: ${keyId}`);
  const removed = config.keys[idx];
  config.keys.splice(idx, 1);
  saveConfigRaw(config);
  return `✓ Removed key: **${keyId}** (${removed.label})`;
}

function listKeys() {
  const config = loadConfig();
  if (config.keys.length === 0) {
    return "No API keys configured. Add one with **ctx7_add_key**.";
  }

  let output = `## Context7 Key Manager\n\n`;
  output += `**Settings:** Strategy=\`${config.settings.rotationStrategy}\`, Max=\`${config.settings.maxRequestsPerKey}\`/key\n`;
  output += `**Stats:** ${config.stats.totalRequests} total requests, ${config.stats.rotationCount} rotations\n`;
  output += `**Period:** ${config.stats.currentPeriodStart.slice(0, 10)}\n\n`;
  output += `| ID | Label | Status | Requests | Last Used |\n`;
  output += `|---|---|---|---|---|\n`;

  for (const key of config.keys) {
    const statusEmoji = key.status === "active" ? "🟢" : "🔴";
    const lastUsed = key.lastUsed ? key.lastUsed.slice(0, 10) : "Never";
    output += `| ${key.id} | ${key.label} | ${statusEmoji} ${key.status} | ${key.requestCount}/${config.settings.maxRequestsPerKey} | ${lastUsed} |\n`;
  }

  return output;
}

function setStrategy(strategy) {
  if (!["least-used", "round-robin", "first"].includes(strategy)) {
    throw new Error("Invalid strategy. Use: least-used, round-robin, or first");
  }
  const config = loadConfig();
  config.settings.rotationStrategy = strategy;
  saveConfigRaw(config);
  return `✓ Rotation strategy set to: **${strategy}**`;
}

function setLimit(limit) {
  const config = loadConfig();
  config.settings.maxRequestsPerKey = limit;
  saveConfigRaw(config);
  return `✓ Max requests per key set to: **${limit}**`;
}

function resetStats() {
  const config = loadConfig();
  config.keys.forEach(k => { k.requestCount = 0; k.lastUsed = null; k.status = "active"; });
  config.stats.totalRequests = 0;
  config.stats.rotationCount = 0;
  config.stats.lastReset = new Date().toISOString();
  saveConfigRaw(config);
  return "✓ All stats reset, all keys reactivated";
}

function getCurrentKey() {
  const config = loadConfig();
  const active = config.keys.filter(k => k.status === "active");
  if (active.length === 0) return "No active keys available. Add one with **ctx7_add_key**.";

  let key;
  if (config.settings.rotationStrategy === "first") {
    key = active[0];
  } else {
    key = active.reduce((min, k) => k.requestCount < min.requestCount ? k : min);
  }

  return `**Active key:** ${key.id} (${key.label})\n` +
    `**Requests:** ${key.requestCount}/${config.settings.maxRequestsPerKey}\n` +
    `**Strategy:** ${config.settings.rotationStrategy}`;
}

module.exports = {
  loadConfig, saveConfigRaw, invalidateCache,
  addKey, removeKey, listKeys, setStrategy, setLimit, resetStats, getCurrentKey
};
