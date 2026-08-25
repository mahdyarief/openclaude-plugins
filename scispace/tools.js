// tools.js — MCP tool definitions and dispatcher for the SciSpace plugin
const client = require("./scispace-client.js");

const TOOLS = [
  {
    name: "search_papers",
    description:
      "Search papers on SciSpace (scispace.com) using a natural-language query. Returns structured results: title, URL, DOI, and surrounding context for each paper found. When enrich=true (default), each result also gets accessible URLs (open-access PDF or DOI resolver) resolved from public scholarly APIs — useful because SciSpace paper detail pages are CAPTCHA-protected. Uses the persisted login session (premium account) if available.",
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
        enrich: {
          type: "boolean",
          description: "Resolve accessible URLs (open-access PDF / DOI resolver) for each result via Crossref+OpenAlex (default: true). Set false for faster bare search.",
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
  {
    name: "deep_extract_paper",
    description:
      "Deep-extract a single paper by DOI from public scholarly APIs: Crossref (metadata, abstract, references), OpenAlex (citation count, concepts, open-access status + PDF), Semantic Scholar (TLDR, citations, OA PDF), and Unpaywall (best OA location). Returns accessibleUrls (PDF first, then DOI resolver) that work without CAPTCHA.",
    inputSchema: {
      type: "object",
      properties: {
        doi: {
          type: "string",
          description: "Digital Object Identifier of the paper, e.g. '10.30587/jpm.v5i01.10253'",
        },
      },
      required: ["doi"],
    },
  },
  {
    name: "enrich_papers",
    description:
      "Given a list of papers from search_papers (title + url + context), extract each DOI and resolve accessible URLs (open-access PDF via Crossref/OpenAlex, plus DOI resolver fallback) so every paper has a URL that actually opens. Optionally deep-extracts the first few papers for abstract/journal/citation data.",
    inputSchema: {
      type: "object",
      properties: {
        papers: {
          type: "array",
          description: "Array of paper objects as returned by search_papers: each with title, url, context.",
          items: {
            type: "object",
            properties: {
              title: { type: "string" },
              url: { type: "string" },
              context: { type: "string" },
            },
          },
        },
        maxDepth: {
          type: "number",
          description: "How many papers to fully deep-extract (abstract + analytics) in the same call. Default 3. Remaining papers still get DOI + accessible URLs.",
        },
      },
      required: ["papers"],
    },
  },
];

async function dispatchTool(name, args) {
  switch (name) {
    case "search_papers": {
      const result = await client.searchPapers(args.query, {
        mode: args.mode || "standard",
        limit: args.limit || 10,
      });
      // Resolve accessible URLs for each result by default (unless enrich:false).
      if (args.enrich !== false && result.papers && result.papers.length) {
        result.papers = await client.enrichPapers(result.papers, { maxDepth: 3 });
      }
      return JSON.stringify(result, null, 2);
    }
    case "scispace_login":
      return JSON.stringify(
        await client.login({ timeoutMs: args.timeoutMs || 300000 }),
        null,
        2
      );
    case "scispace_status":
      return JSON.stringify(await client.status(), null, 2);
    case "deep_extract_paper":
      return JSON.stringify(await client.deepExtractPaper(args.doi), null, 2);
    case "enrich_papers":
      return JSON.stringify(
        await client.enrichPapers(args.papers || [], { maxDepth: args.maxDepth || 3 }),
        null,
        2
      );
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

module.exports = { TOOLS, dispatchTool };
