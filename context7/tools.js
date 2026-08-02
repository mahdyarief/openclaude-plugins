const { resolveLibrary, queryDocs } = require("./context7-client.js");
const { getConfig, addKey, removeKey, listKeys, setStrategy, setLimit, resetStats, getCurrentKey } = require("./key-manager.js");

const TOOLS = [
  {
    name: "ctx7_resolve_library",
    description: "Resolve a library/framework name to a Context7 library ID. Use this to find documentation IDs for libraries like React, Next.js, Vue, Express, etc. Returns library info including ID, name, and version.",
    inputSchema: {
      type: "object",
      properties: {
        libraryName: { type: "string", description: "Library/framework name (e.g., 'react', 'next.js', 'express')" },
        query: { type: "string", description: "Optional search query for better ranking" }
      },
      required: ["libraryName"]
    }
  },
  {
    name: "ctx7_query_docs",
    description: "Query documentation for a specific library using its Context7 ID. Returns relevant documentation snippets and context for the query. Use ctx7_resolve_library first to get the libraryId.",
    inputSchema: {
      type: "object",
      properties: {
        libraryId: { type: "string", description: "Library ID from ctx7_resolve_library (e.g., '/reactjs/react')" },
        query: { type: "string", description: "Documentation query (e.g., 'useEffect cleanup', 'routing setup')" }
      },
      required: ["libraryId", "query"]
    }
  },
  {
    name: "ctx7_add_key",
    description: "Add a new Context7 API key (ctx7sk-...) to the rotation pool. Keys are auto-rotated when they exceed the request limit.",
    inputSchema: {
      type: "object",
      properties: {
        apiKey: { type: "string", description: "Context7 API key (ctx7sk-...)" },
        label: { type: "string", description: "Optional label (e.g., 'Work', 'Personal', 'Primary')" }
      },
      required: ["apiKey"]
    }
  },
  {
    name: "ctx7_remove_key",
    description: "Remove a Context7 API key from the rotation pool by its ID (e.g., 'keyA', 'keyB').",
    inputSchema: {
      type: "object",
      properties: {
        keyId: { type: "string", description: "Key ID to remove (e.g., 'keyA', 'keyB')" }
      },
      required: ["keyId"]
    }
  },
  {
    name: "ctx7_list_keys",
    description: "List all Context7 API keys with their usage stats, status, and rotation settings.",
    inputSchema: {
      type: "object",
      properties: {}
    }
  },
  {
    name: "ctx7_set_strategy",
    description: "Set the key rotation strategy: 'least-used' (uses key with fewest requests), 'round-robin', or 'first' (always uses first available key).",
    inputSchema: {
      type: "object",
      properties: {
        strategy: {
          type: "string",
          description: "Rotation strategy",
          enum: ["least-used", "round-robin", "first"]
        }
      },
      required: ["strategy"]
    }
  },
  {
    name: "ctx7_set_limit",
    description: "Set the maximum requests per key before it's marked as exhausted and auto-rotation kicks in.",
    inputSchema: {
      type: "object",
      properties: {
        limit: { type: "number", description: "Max requests per key (default: 1000)" }
      },
      required: ["limit"]
    }
  },
  {
    name: "ctx7_reset_stats",
    description: "Reset all usage statistics and reactivate all keys. Useful at the start of a new billing period.",
    inputSchema: {
      type: "object",
      properties: {}
    }
  },
  {
    name: "ctx7_current_key",
    description: "Show which Context7 API key will be used for the next request.",
    inputSchema: {
      type: "object",
      properties: {}
    }
  }
];

async function dispatchTool(toolName, args) {
  switch (toolName) {
    case "ctx7_resolve_library":
      return await handleResolveLibrary(args);
    case "ctx7_query_docs":
      return await handleQueryDocs(args);
    case "ctx7_add_key":
      return await handleAddKey(args);
    case "ctx7_remove_key":
      return await handleRemoveKey(args);
    case "ctx7_list_keys":
      return await handleListKeys();
    case "ctx7_set_strategy":
      return await handleSetStrategy(args);
    case "ctx7_set_limit":
      return await handleSetLimit(args);
    case "ctx7_reset_stats":
      return await handleResetStats();
    case "ctx7_current_key":
      return await handleCurrentKey();
    default:
      throw new Error(`Unknown tool: ${toolName}`);
  }
}

async function handleResolveLibrary(args) {
  const { libraryName, query } = args;
  if (!libraryName || libraryName.trim().length === 0) throw new Error("Library name is required");
  const result = await resolveLibrary(libraryName, query);
  return `## Context7 Library Search: "${libraryName}"\n\n${result}`;
}

async function handleQueryDocs(args) {
  const { libraryId, query } = args;
  if (!libraryId || !query) throw new Error("libraryId and query are required");
  const result = await queryDocs(libraryId, query);
  return `## Context7 Documentation: ${libraryId}\nQuery: "${query}"\n\n${result}`;
}

async function handleAddKey(args) {
  const { apiKey, label } = args;
  if (!apiKey || apiKey.trim().length === 0) throw new Error("API key is required");
  const result = addKey(apiKey, label);
  return result;
}

async function handleRemoveKey(args) {
  const { keyId } = args;
  if (!keyId) throw new Error("Key ID is required");
  return removeKey(keyId);
}

async function handleListKeys() {
  return listKeys();
}

async function handleSetStrategy(args) {
  const { strategy } = args;
  if (!strategy) throw new Error("Strategy is required");
  return setStrategy(strategy);
}

async function handleSetLimit(args) {
  const { limit } = args;
  if (typeof limit !== "number" || limit < 1) throw new Error("Limit must be a positive number");
  return setLimit(limit);
}

async function handleResetStats() {
  return resetStats();
}

async function handleCurrentKey() {
  return getCurrentKey();
}

module.exports = { TOOLS, dispatchTool };
