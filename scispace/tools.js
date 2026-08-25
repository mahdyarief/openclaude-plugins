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
  {
    name: "list_library",
    description:
      "List saved paper records in your SciSpace My Library (via /api/library/records). Returns the records stored in the account linked to the saved session.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "list_collections",
    description:
      "List all collection folders in your SciSpace My Library (via /api/library/collection), with their slugs, record counts, and permissions.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "get_collection",
    description:
      "Get the contents/metadata of a single collection folder by its full_slug (e.g. 'untitled-folder-p3fi09sf').",
    inputSchema: {
      type: "object",
      properties: {
        slug: { type: "string", description: "full_slug of the collection, e.g. 'untitled-folder-p3fi09sf'" },
      },
      required: ["slug"],
    },
  },
  {
    name: "create_collection",
    description:
      "Create a new collection folder in My Library. Returns the API response (may be the created collection object).",
    inputSchema: {
      type: "object",
      properties: {
        name: { type: "string", description: "Name of the new collection folder" },
      },
      required: ["name"],
    },
  },
  {
    name: "bookmark_paper",
    description:
      "Bookmark or un-bookmark a paper on SciSpace by its entity slug (the /papers/<slug> part). Uses the authenticated session.",
    inputSchema: {
      type: "object",
      properties: {
        entitySlug: { type: "string", description: "Paper entity slug, e.g. 'sumber-daya-manusia-generasi-z-di-era-artificial-5lcsnrcvx5ll'" },
        bookmarked: { type: "boolean", description: "true to bookmark, false to remove bookmark (default: true)" },
      },
      required: ["entitySlug"],
    },
  },
  {
    name: "export_citations",
    description:
      "Generate a formatted citation for a DOI in APA, MLA, Chicago, Harvard, or BibTeX, using public Crossref/DataCite APIs (no CAPTCHA, no browser needed).",
    inputSchema: {
      type: "object",
      properties: {
        doi: { type: "string", description: "Digital Object Identifier, e.g. '10.3389/feduc.2025.1504726'" },
        style: { type: "string", enum: ["apa", "mla", "chicago", "harvard", "bibtex"], description: "Citation style (default: apa)" },
      },
      required: ["doi"],
    },
  },
  {
    name: "export_library_csv",
    description:
      "Build a CSV export (title, authors, year, journal, doi, url) from a list of paper records. Accepts records from list_library or search results.",
    inputSchema: {
      type: "object",
      properties: {
        records: {
          type: "array",
          description: "Paper records, each may have title, authors (array), year, journal, doi, url.",
          items: { type: "object" },
        },
      },
      required: ["records"],
    },
  },
  {
    name: "check_credits",
    description:
      "Check your SciSpace account credit balance, usage, and access window (via /api/meters/credits).",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "list_translation_languages",
    description:
      "List the languages SciSpace supports for in-app translation (via /api/translation/languages).",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "get_review_columns",
    description:
      "List the comparison columns SciSpace can extract for literature-review tables: insights, tldr, conclusions, summarized_abstract, results, summarized_introduction, methods_used, literature_survey (via /api/paper-info/columns).",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "get_model_access",
    description:
      "Check which SciSpace model tiers your account can access (Standard V1, Premium V2, Advanced V3) for a given feature: 'literature-review' or 'library'.",
    inputSchema: {
      type: "object",
      properties: {
        kind: { type: "string", enum: ["literature-review", "library"], description: "Feature to check model access for (default: literature-review)" },
      },
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
    case "list_library":
      return JSON.stringify(await client.listLibrary(), null, 2);
    case "list_collections":
      return JSON.stringify(await client.listCollections(), null, 2);
    case "get_collection":
      return JSON.stringify(await client.getCollection(args.slug), null, 2);
    case "create_collection":
      return JSON.stringify(await client.createCollection(args.name), null, 2);
    case "bookmark_paper":
      return JSON.stringify(
        await client.bookmarkPaper(args.entitySlug, { bookmarked: args.bookmarked !== false }),
        null,
        2
      );
    case "export_citations":
      return JSON.stringify(await client.exportCitation(args.doi, { style: args.style || "apa" }), null, 2);
    case "export_library_csv":
      return JSON.stringify(await client.exportLibraryCsv(args.records || []), null, 2);
    case "check_credits":
      return JSON.stringify(await client.checkCredits(), null, 2);
    case "list_translation_languages":
      return JSON.stringify(await client.listTranslationLanguages(), null, 2);
    case "get_review_columns":
      return JSON.stringify(await client.getReviewColumns(), null, 2);
    case "get_model_access":
      return JSON.stringify(await client.getModelAccess(args.kind || "literature-review"), null, 2);
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

module.exports = { TOOLS, dispatchTool };
