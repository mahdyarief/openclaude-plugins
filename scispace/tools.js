// tools.js — MCP tool definitions and dispatcher for the SciSpace plugin
const client = require("./scispace-client.js");

const TOOLS = [
  {
    name: "search_papers",
    description:
      "Search papers on SciSpace (scispace.com) using a natural-language query. Returns structured results: title, URL, and surrounding context for each paper found. Uses the persisted login session (premium account) if available.",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "Natural-language research query, e.g. 'how does climate change impact biodiversity'",
        },
        mode: {
          type: "string",
          enum: ["standard", "high-quality", "deep-review"],
          description: "Literature review mode (default: standard)",
        },
        limit: {
          type: "number",
          description: "Maximum number of papers to return (default: 10)",
        },
      },
      required: ["query"],
    },
  },
  {
    name: "scispace_login",
    description:
      "Open a visible browser window so the user can sign in to SciSpace once. The session cookies are then saved and reused by all other tools. Run this once after installing the plugin.",
    inputSchema: {
      type: "object",
      properties: {
        timeoutMs: {
          type: "number",
          description: "How long to wait for login in milliseconds (default: 300000)",
        },
      },
    },
  },
  {
    name: "scispace_status",
    description:
      "Check whether a SciSpace login session is stored and whether premium features appear to be active. No search is performed.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
];

async function dispatchTool(name, args) {
  switch (name) {
    case "search_papers":
      return JSON.stringify(
        await client.searchPapers(args.query, {
          mode: args.mode || "standard",
          limit: args.limit || 10,
        }),
        null,
        2
      );
    case "scispace_login":
      return JSON.stringify(
        await client.login({ timeoutMs: args.timeoutMs || 300000 }),
        null,
        2
      );
    case "scispace_status":
      return JSON.stringify(await client.status(), null, 2);
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

module.exports = { TOOLS, dispatchTool };
