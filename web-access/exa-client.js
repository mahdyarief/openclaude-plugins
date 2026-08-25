const { loadKeys, nextKey } = require("./exa-rotator");
const EXA_MCP_URL = "https://mcp.exa.ai/mcp";

let _attemptsRemaining = 0;
let _currentKeyIndex = 0;

async function callExaMcp(toolName, args) {
  const keys = loadKeys();

  // If we have keys, retry up to number of keys times on 429/401
  const maxAttempts = keys.length > 1 ? keys.length : 1;
  let lastError = null;

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const headers = {
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
      };

      // Add Authorization header if we have keys
      if (keys.length > 0) {
        const key = keys[attempt % keys.length];
        headers["Authorization"] = `Bearer ${key}`;
      }

      const response = await fetch(EXA_MCP_URL, {
        method: "POST",
        headers: headers,
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: 1,
          method: "tools/call",
          params: { name: toolName, arguments: args },
        }),
        signal: AbortSignal.timeout(60000),
      });

      if (!response.ok) {
        const errText = await response.text();

        // Handle rate limit (429) or invalid auth (401) - rotate key
        if ((response.status === 429 || response.status === 401) && keys.length > 1 && attempt < maxAttempts - 1) {
          console.error(`[exa] Rate limited (${response.status}), rotating key...`);
          lastError = new Error(`Exa error ${response.status}: ${errText.slice(0, 300)}`);
          continue;
        }

        throw new Error(`Exa error ${response.status}: ${errText.slice(0, 300)}`);
      }

      const body = await response.text();
      let parsed = tryParseSse(body) || tryParseJson(body);

      if (!parsed) throw new Error("Exa MCP returned empty response");

      if (parsed.error) {
        throw new Error(
          `Exa error${parsed.error.code ? " " + parsed.error.code : ""}: ${parsed.error.message || "Unknown"}`
        );
      }
      if (parsed.result?.isError) {
        const msg = parsed.result.content?.find((i) => i.type === "text")?.text?.trim();
        throw new Error(msg || "Exa MCP returned an error");
      }

      const text = parsed.result?.content?.find(
        (i) => i.type === "text" && typeof i.text === "string" && i.text.trim().length > 0
      )?.text;
      if (!text) throw new Error("Exa MCP returned empty content");

      return text;

    } catch (err) {
      lastError = err;
    }
  }

  throw lastError || new Error("Exa MCP request failed after all retries");
}

function tryParseSse(body) {
  const dataLines = body.split("\n").filter((l) => l.startsWith("data:"));
  for (const line of dataLines) {
    const payload = line.slice(5).trim();
    if (!payload) continue;
    try {
      const c = JSON.parse(payload);
      if (c?.result || c?.error) return c;
    } catch {}
  }
  return null;
}

function tryParseJson(body) {
  try {
    const c = JSON.parse(body);
    if (c?.result || c?.error) return c;
  } catch {}
  return null;
}

module.exports = { callExaMcp };
