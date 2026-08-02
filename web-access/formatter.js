/**
 * Format search results and build search queries.
 */

function formatSearchResults(raw) {
  if (!raw || raw.trim().length === 0) {
    return "No results found.";
  }

  const blocks = raw.split(/\n---+\n/);
  const formatted = blocks
    .map((block) => {
      const titleMatch = block.match(/Title:\s*(.+)/);
      const urlMatch = block.match(/URL:\s*(.+)/);
      const publishedMatch = block.match(/Published:\s*(.+)/);
      const highlightsMatch = block.match(/Highlights:\s*([\s\S]*?)(?=\n\w+:|$)/);

      if (!titleMatch) return block.trim();

      const title = titleMatch[1].trim();
      const url = urlMatch ? urlMatch[1].trim() : "";
      const published = publishedMatch ? publishedMatch[1].trim() : "";
      const highlights = highlightsMatch
        ? highlightsMatch[1].trim()
        : extractedContent(raw, block);

      let out = `### [${title}](${url || ""})`;
      if (published) out += `\n_${published}_`;
      if (highlights) out += `\n\n${highlights}`;
      return out;
    })
    .join("\n\n---\n\n");

  return formatted;
}

function extractedContent(raw, block) {
  const lines = block.split("\n").filter((l) => l.trim());
  const contentLines = lines.filter(
    (l) =>
      !/^(Title|URL|Published|Author|Highlights):/i.test(l.trim()) &&
      l.trim().length > 0
  );
  return contentLines.join("\n").trim().slice(0, 2000);
}

function buildSearchQuery(query, options) {
  let enriched = query;

  if (options.site) {
    enriched = `${enriched} site:${options.site}`;
  }

  if (options.recency) {
    const now = new Date();
    let since;
    switch (options.recency) {
      case "day":
        since = new Date(now.getTime() - 86400000);
        break;
      case "week":
        since = new Date(now.getTime() - 7 * 86400000);
        break;
      case "month":
        since = new Date(now.getTime() - 30 * 86400000);
        break;
      case "year":
        since = new Date(now.getTime() - 365 * 86400000);
        break;
    }
    if (since) {
      enriched = `${enriched} after:${since.toISOString().split("T")[0]}`;
    }
  }

  return enriched;
}

module.exports = { formatSearchResults, buildSearchQuery };
