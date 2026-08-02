#!/usr/bin/env node
const { TOOLS, dispatchTool } = require("./tools.js");

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

  if (method === "initialize") {
    sendResult(id, {
      protocolVersion: "2024-11-05",
      capabilities: { tools: {} },
      serverInfo: { name: "web-access-mcp", version: "2.1.0" },
    });
    return;
  }

  if (method === "notifications/initialized") {
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
        sendError(id, -32603, err.message);
      })
      .finally(() => {
        pendingOps--;
        if (stdinEnded && pendingOps === 0) process.stdin.unref();
      });
    return;
  }

  sendResult(id, {});
}

// ── STDIN processing ───────────────────────────────────────────

process.stdin.on("data", (chunk) => {
  buffer += chunk;
  const lines = buffer.split("\n");
  buffer = lines.pop() || "";

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      handleRequest(JSON.parse(trimmed));
    } catch {
      // skip malformed JSON
    }
  }
});

process.stdin.on("end", () => {
  stdinEnded = true;
  if (pendingOps === 0) process.stdin.unref();
});
