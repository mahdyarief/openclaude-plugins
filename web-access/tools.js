const { callExaMcp } = require("./exa-client.js");
const { fetchWebContent } = require("./web-fetcher.js");
const { formatSearchResults, buildSearchQuery } = require("./formatter.js");
const { searchGithub } = require("./github-client.js");

/**
 * Tool handlers and their definitions.
 */

const TOOLS = [
  {
    name: "web_search",
    description:
      "Search the web for current/recent information, news, real-time data, or anything beyond your knowledge cutoff. Returns formatted results with titles, URLs, publication dates, and content snippets. Use this when you need up-to-date information, recent events, or facts you're not confident about.",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "Search query — be specific for best results",
        },
        numResults: {
          type: "number",
          description: "Number of results to return (max 10)",
          default: 5,
        },
        site: {
          type: "string",
          description:
            "Limit results to a specific domain (e.g. 'example.com')",
        },
        recency: {
          type: "string",
          description:
            "Only return results from a specific time period: 'day', 'week', 'month', 'year'",
          enum: ["day", "week", "month", "year"],
        },
        livecrawl: {
          type: "string",
          description:
            "Live crawl mode: 'always' fetches fresh, 'fallback' only if needed, 'never' uses cache",
          default: "fallback",
        },
      },
      required: ["query"],
    },
  },
  {
    name: "web_get_contents",
    description:
      "Fetch and extract readable text content from a URL. Use this when you need to read the full article, documentation, or detailed content behind a link — beyond what search snippets provide.",
    inputSchema: {
      type: "object",
      properties: {
        url: {
          type: "string",
          description: "The full URL to fetch content from (http:// or https://)",
        },
      },
      required: ["url"],
    },
  },
  {
    name: "web_search_exa",
    description:
      "Alias for web_search. Search the web using Exa AI. Returns raw results with titles, URLs, and snippets.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query" },
        numResults: {
          type: "number",
          description: "Number of results (default 5)",
          default: 5,
        },
        livecrawl: {
          type: "string",
          description:
            "Live crawl mode: 'always', 'fallback', or 'never'",
          default: "fallback",
        },
        type: {
          type: "string",
          description: "Search type: 'auto', 'keyword', or 'neural'",
          default: "auto",
        },
      },
      required: ["query"],
    },
  },
  {
    name: "github_search",
    description:
      "Search GitHub repositories, code, issues, commits, or topics. Returns formatted results with stars, forks, descriptions, and links. Use this to find open-source projects, explore code, look up issues, or discover trending repos.",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "GitHub search query — same syntax as github.com/search (e.g. 'openclaude mcp server', 'react state management stars:>10000')",
        },
        type: {
          type: "string",
          description: "Type of search: 'repositories' (default), 'issues', 'code', 'commits', 'topics'",
          enum: ["repositories", "issues", "code", "commits", "topics"],
          default: "repositories",
        },
        sort: {
          type: "string",
          description: "Sort field: 'stars', 'forks', 'updated', 'help-wanted-issues' (repos); 'comments', 'reactions', 'updated' (issues)",
        },
        order: {
          type: "string",
          description: "Sort order: 'desc' (default) or 'asc'",
          enum: ["desc", "asc"],
        },
        perPage: {
          type: "number",
          description: "Results per page (max 30)",
          default: 5,
        },
      },
      required: ["query"],
    },
  },
];

async function handleWebSearch(args) {
  const query = buildSearchQuery(args.query, args);
  const raw = await callExaMcp("web_search_exa", {
    query,
    numResults: args.numResults || 5,
    livecrawl: args.livecrawl || "fallback",
    type: args.type || "auto",
  });
  return formatSearchResults(raw);
}

async function handleGetContents(args) {
  const url = args.url;
  if (!url || (!url.startsWith("http://") && !url.startsWith("https://"))) {
    throw new Error("Valid URL is required (http:// or https://)");
  }
  const content = await fetchWebContent(url);
  return `## Content from: ${url}\n\n${content}`;
}

async function handleGithubSearch(args) {
  const { query, type = "repositories", sort, order, perPage = 5 } = args;
  if (!query || query.trim().length === 0) {
    throw new Error("Search query is required");
  }
  const result = await searchGithub(query, { type, sort, order, perPage });
  const header = `## GitHub ${type} search: "${query}"\n\n`;
  return header + result;
}

async function dispatchTool(toolName, args) {
  if (toolName === "web_search" || toolName === "web_search_exa") {
    return await handleWebSearch(args);
  } else if (toolName === "web_get_contents") {
    return await handleGetContents(args);
  } else if (toolName === "github_search") {
    return await handleGithubSearch(args);
  }
  throw new Error(`Unknown tool: ${toolName}`);
}

module.exports = { TOOLS, dispatchTool };
