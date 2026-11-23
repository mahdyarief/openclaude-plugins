#!/usr/bin/env node
const { TOOLS, dispatchTool } = require("./tools.js");
const { loadKeys: loadExaKeys } = require("./exa-rotator.js");
const { loadKeys: loadTavilyKeys } = require("./tavily-rotator.js");
const { getDefaultProvider } = require("./config.js");

{
  const exaN = loadExaKeys().length;
  const tavN = loadTavilyKeys().length;
  console.error(
    `[web-access] Exa: ${exaN ? `${exaN} key(s)` : "keyless (anonymous)"} | ` +
      `Tavily: ${tavN ? `${tavN} key(s)` : "disabled (no API key)"} | ` +
      `default provider: ${getDefaultProvider()}`
  );
}

process.stdin.setEncoding("utf-8");
let buffer = "";
let pendingOps = 0;
let stdinEnded = false;

// ── MCP message helpers ────────────────────────────────────────

function sendMessage(msg) {
  const line = JSON.stringify(msg);
  process.stdout.write(line + "\n");
}

function sendError(id, code, message) {
  sendMessage({ jsonrpc: "2.0", id, error: { code, message } });
}

function sendResult(id, result) {
  sendMessage({ jsonrpc: "2.0", id, result });
}

// ── Request handler ────────────────────────────────────────────

function handleRequest(request) {
  const { id, method, params } = request;
  // JSON-RPC: a message without an id is a notification and must never get a response
  const isNotification = id === undefined || id === null;

  if (method === "initialize") {
    sendResult(id, {
      protocolVersion: params?.protocolVersion || "2024-11-05",
      capabilities: { tools: {} },
      serverInfo: { name: "web-access", version: require("./package.json").version },
    });
    return;
  }

  if (isNotification) return; // notifications/initialized, notifications/cancelled, ...

  if (method === "ping") {
    sendResult(id, {});
    return;
  }

  if (method === "tools/list") {
    sendResult(id, { tools: TOOLS });
    return;
  }

  if (method === "tools/call") {
    const toolName = params?.name;
    const args = params?.arguments || {};

    pendingOps++;
    dispatchTool(toolName, args)
      .then((text) => {
        sendResult(id, { content: [{ type: "text", text }] });
      })
      .catch((err) => {
        // Tool failures are reported as tool results so the model can read them
        sendResult(id, { content: [{ type: "text", text: `Error: ${err.message}` }], isError: true });
      })
      .finally(() => {
        pendingOps--;
        maybeExit();
      });
    return;
  }

  // Optional MCP list methods: answer with empty lists instead of an error
  if (method === "resources/list") return sendResult(id, { resources: [] });
  if (method === "prompts/list") return sendResult(id, { prompts: [] });

  sendError(id, -32601, `Method not found: ${method}`);
}

function maybeExit() {
  if (stdinEnded && pendingOps === 0 && typeof process.stdin.unref === "function") {
    process.stdin.unref();
  }
}

// ── STDIN processing ───────────────────────────────────────────

process.stdin.on("data", (chunk) => {
  buffer += chunk;
  const lines = buffer.split("\n");
  buffer = lines.pop() || "";

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    let msg;
    try {
      msg = JSON.parse(trimmed);
    } catch {
      sendError(null, -32700, "Parse error");
      continue;
    }
    try {
      handleRequest(msg);
    } catch (err) {
      if (msg?.id !== undefined && msg?.id !== null) sendError(msg.id, -32603, err.message);
    }
  }
});

process.stdin.on("end", () => {
  stdinEnded = true;
  maybeExit();
});
