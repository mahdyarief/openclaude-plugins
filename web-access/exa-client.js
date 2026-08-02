const EXA_MCP_URL = "https://mcp.exa.ai/mcp";

/**
 * Call Exa MCP endpoint via HTTP POST (no API key required).
 */
async function callExaMcp(toolName, args) {
  const response = await fetch(EXA_MCP_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
    },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/call",
      params: { name: toolName, arguments: args },
    }),
    signal: AbortSignal.timeout(60000),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Exa error ${response.status}: ${err.slice(0, 300)}`);
  }

  const body = await response.text();

  // Try SSE data: lines first, then raw JSON
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
