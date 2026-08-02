const https = require("https");

const CONTEXT7_API = "https://context7.com/api/v2";

function getActiveKey(config) {
  const active = config.keys.filter(k => k.status === "active");
  if (active.length === 0) throw new Error("No active Context7 API keys. Add one with ctx7_add_key.");
  if (config.settings.rotationStrategy === "first") return active[0];
  if (config.settings.rotationStrategy === "round-robin") {
    // Simple round-robin: pick the one with fewest requests
    return active.reduce((min, k) => k.requestCount < min.requestCount ? k : min);
  }
  // "least-used" (default)
  return active.reduce((min, k) => k.requestCount < min.requestCount ? k : min);
}

function recordUsage(config, keyId) {
  const key = config.keys.find(k => k.id === keyId);
  if (!key) return;
  key.requestCount++;
  key.lastUsed = new Date().toISOString();
  config.stats.totalRequests++;
  if (config.settings.autoRotate && key.requestCount >= config.settings.maxRequestsPerKey) {
    key.status = "exhausted";
    config.stats.rotationCount++;
  }
  require("./key-manager.js").saveConfigRaw(config);
}

function httpsGet(url, apiKey) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const req = https.request({
      hostname: parsed.hostname,
      path: parsed.pathname + parsed.search,
      method: "GET",
      headers: { "Authorization": `Bearer ${apiKey}` },
      timeout: 30000
    }, (res) => {
      let data = "";
      res.on("data", (chunk) => data += chunk);
      res.on("end", () => {
        if (res.statusCode >= 400) {
          reject(new Error(`Context7 API error ${res.statusCode}: ${data.slice(0, 200)}`));
        } else {
          resolve(data);
        }
      });
    });
    req.on("error", reject);
    req.on("timeout", () => { req.destroy(); reject(new Error("Request timed out")); });
    req.end();
  });
}

async function resolveLibrary(libraryName, query) {
  const { loadConfig } = require("./key-manager.js");
  const config = loadConfig();
  const key = getActiveKey(config);
  const searchQuery = query || libraryName;

  const url = `${CONTEXT7_API}/libs/search?query=${encodeURIComponent(searchQuery)}&library=${encodeURIComponent(libraryName)}`;
  const data = await httpsGet(url, key.apiKey);
  recordUsage(config, key.id);

  try {
    const parsed = JSON.parse(data);
    if (Array.isArray(parsed)) {
      return parsed.map(lib => {
        return `- **${lib.name}** (${lib.id}) — ${lib.description || "No description"}` +
          (lib.version ? ` v${lib.version}` : "") +
          (lib.stars ? ` ⭐${lib.stars}` : "");
      }).join("\n") || "No libraries found.";
    }
    return JSON.stringify(parsed, null, 2);
  } catch {
    return data;
  }
}

async function queryDocs(libraryId, query) {
  const { loadConfig } = require("./key-manager.js");
  const config = loadConfig();
  const key = getActiveKey(config);

  const url = `${CONTEXT7_API}/context?libraryId=${encodeURIComponent(libraryId)}&query=${encodeURIComponent(query)}`;
  const data = await httpsGet(url, key.apiKey);
  recordUsage(config, key.id);

  try {
    const parsed = JSON.parse(data);
    // Format the response nicely
    if (Array.isArray(parsed)) {
      return parsed.map((item, i) => {
        return `### ${i + 1}. ${item.title || "Untitled"}\n${item.content || item.text || JSON.stringify(item)}`;
      }).join("\n\n");
    }
    if (parsed.sections || parsed.content) {
      const sections = parsed.sections || [parsed];
      return sections.map(s => {
        return `### ${s.title || "Section"}\n${s.content || s.text || JSON.stringify(s)}`;
      }).join("\n\n");
    }
    return JSON.stringify(parsed, null, 2);
  } catch {
    return data;
  }
}

module.exports = { resolveLibrary, queryDocs };
