const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} = require("@modelcontextprotocol/sdk/types.js");

const { errorResponse } = require("./shared.js");
const diagnostics = require("./diagnostics.js");
const scanner = require("./scanner.js");
const search = require("./search.js");
const artifacts = require("./artifacts.js");
const impact = require("./impact.js");

const server = new Server(
  { name: "codebase-intelligence", version: "1.1.0" },
  { capabilities: { tools: {} } }
);

// Tool definitions
const TOOLS = [
  {
    name: "codebase_scan",
    description: "Full project scan: detect available tools, discover all files, classify, build summary, persist cache",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Project root path" },
        force: { type: "boolean", description: "Force rescan even if cache is fresh" },
      },
      required: ["path"],
    },
  },
  {
    name: "codebase_status",
    description: "Check cache freshness, tool availability, and installation recommendations",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Project root path" },
      },
      required: ["path"],
    },
  },
  {
    name: "codebase_search",
    description: "Hybrid search: literal via rg + structural via ast-grep (when available). Results merged, deduplicated, ranked by score.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Project root path" },
        query: { type: "string", description: "Search query" },
      },
      required: ["path", "query"],
    },
  },
  {
    name: "codebase_context",
    description: "Search docs/specs/schema/config/ADR artifacts by keyword",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Project root path" },
        query: { type: "string", description: "Artifact keyword search" },
      },
      required: ["path", "query"],
    },
  },
  {
    name: "codebase_impact",
    description: "Blast radius analysis: parse import statements, build dependency graph, find direct + transitive dependents, match related tests",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Project root path" },
        target: { type: "string", description: "Relative path to target file" },
      },
      required: ["path", "target"],
    },
  },
];

// ListTools handler
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS,
}));

// CallTool handler
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "codebase_scan": {
        const result = await scanner.scanProject(args.path, args.force || false);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "codebase_status": {
        const tools = diagnostics.detectAllTools();
        const missingTools = diagnostics.getInstallHints(tools);

        const cache = require("./cache.js");
        const indexModule = require("./index.js");
        const { fs, path: p } = require("./shared.js");

        let cacheFresh = false;
        let lastScanAt = null;
        let mode = diagnostics.getMode(tools);
        let indexFresh = false;
        let indexTokenCount = 0;

        if (fs.existsSync(args.path)) {
          const cached = cache.loadCache(args.path);
          if (cached) {
            const { countByKind } = require("./discovery.js");
            const fileCounts = cached.fileCounts || {};
            cacheFresh = cache.isCacheFresh(cached, fileCounts, args.path);
            lastScanAt = cached.scannedAt || null;

            const idx = indexModule.loadIndex(args.path);
            indexFresh = indexModule.isIndexFresh(idx, cached.fingerprint);
            indexTokenCount = idx ? idx.tokenCount || 0 : 0;
          }
        }

        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              path: args.path,
              tools,
              missingTools: missingTools.map((h) => h.tool),
              installHints: missingTools,
              cacheFresh,
              indexFresh,
              indexTokenCount,
              mode,
              lastScanAt,
            }, null, 2),
          }],
        };
      }

      case "codebase_search": {
        const result = await search.hybridSearch(args.path, args.query);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "codebase_context": {
        const results = await artifacts.searchArtifacts(args.path, args.query);
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ query: args.query, results }, null, 2),
          }],
        };
      }

      case "codebase_impact": {
        const result = await impact.analyzeImpact(args.path, args.target);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      default:
        return {
          content: [{ type: "text", text: JSON.stringify(errorResponse("UNKNOWN_TOOL", `Unknown tool: ${name}`)) }],
        };
    }
  } catch (err) {
    return {
      content: [{
        type: "text",
        text: JSON.stringify(errorResponse("INTERNAL_ERROR", err.message || "Internal server error"), null, 2),
      }],
    };
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error("Fatal server error:", err);
  process.exit(1);
});
