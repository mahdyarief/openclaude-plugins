const GITHUB_API = "https://api.github.com";

/**
 * Search GitHub repositories, code, issues, or commits via the public GitHub API.
 * No authentication required (60 req/hr unauthenticated).
 */
async function searchGithub(query, options = {}) {
  const { type = "repositories", sort, order, perPage = 5 } = options;

  const params = new URLSearchParams({ q: query, per_page: String(Math.min(perPage, 30)) });
  if (sort) params.set("sort", sort);
  if (order) params.set("order", order);

  const endpoint = `${GITHUB_API}/search/${type}`;
  const url = `${endpoint}?${params}`;

  const response = await fetch(url, {
    headers: {
      Accept: "application/vnd.github.v3+json",
      "User-Agent": "exa-search-mcp/2.0",
    },
    signal: AbortSignal.timeout(15000),
  });

  if (response.status === 403) {
    const reset = response.headers.get("X-RateLimit-Reset");
    const wait = reset ? Math.ceil(Number(reset) - Date.now() / 1000) : "unknown";
    throw new Error(`GitHub API rate limited. Resets in ${wait}s. Try unauthenticated search via web_search with site:github.com`);
  }
  if (!response.ok) {
    const err = await response.text();
    throw new Error(`GitHub error ${response.status}: ${err.slice(0, 300)}`);
  }

  const data = await response.json();

  switch (type) {
    case "repositories":
      return formatRepos(data);
    case "issues":
      return formatIssues(data);
    case "code":
      return formatCode(data);
    case "commits":
      return formatCommits(data);
    case "topics":
      return formatTopics(data);
    default:
      return `Unsupported search type: ${type}`;
  }
}

function formatRepos(data) {
  if (!data.items || data.items.length === 0) return "No repositories found.";
  return data.items
    .map((r, i) => {
      const stars = r.stargazers_count ?? 0;
      const forks = r.forks_count ?? 0;
      const desc = r.description ? `\n  ${r.description}` : "";
      const lang = r.language ? ` [${r.language}]` : "";
      const topics = r.topics?.length ? `\n  Topics: ${r.topics.slice(0, 5).join(", ")}` : "";
      return `${i + 1}. [${r.full_name}](${r.html_url}) — ⭐${stars} 🍴${forks}${lang}${desc}${topics}`;
    })
    .join("\n");
}

function formatIssues(data) {
  if (!data.items || data.items.length === 0) return "No issues found.";
  return data.items
    .map((i, idx) => {
      const state = i.state === "open" ? "🟢" : "🔴";
      const labels = i.labels?.length ? ` [${i.labels.map((l) => l.name).join(", ")}]` : "";
      return `${idx + 1}. ${state} [${i.repository_url.split("/").slice(-2).join("/")}#${i.number}](${i.html_url}) — ${i.title}${labels}`;
    })
    .join("\n");
}

function formatCode(data) {
  if (!data.items || data.items.length === 0) return "No code results found.";
  return data.items
    .map((f, idx) => {
      const repo = f.repository?.full_name || "unknown";
      return `${idx + 1}. [${f.path}](${f.html_url}) — ${repo}`;
    })
    .join("\n");
}

function formatCommits(data) {
  if (!data.items || data.items.length === 0) return "No commits found.";
  return data.items
    .map((c, idx) => {
      const repo = c.repository?.full_name || "unknown";
      const sha = c.sha?.slice(0, 7) || "???";
      const msg = c.commit?.message?.split("\n")[0] || "no message";
      const author = c.commit?.author?.name || "unknown";
      return `${idx + 1}. [${repo}@${sha}](${c.html_url}) — ${msg} (${author})`;
    })
    .join("\n");
}

function formatTopics(data) {
  if (!data.items || data.items.length === 0) return "No topics found.";
  return data.items
    .map((t, idx) => {
      const desc = t.description ? ` — ${t.description}` : "";
      return `${idx + 1}. [${t.name}](${t.html_url})${desc}`;
    })
    .join("\n");
}

module.exports = { searchGithub };
