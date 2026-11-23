const { execFileSync } = require("child_process");

const GITHUB_API = "https://api.github.com";

const GH_CANDIDATES =
  process.platform === "win32"
    ? ["gh", "C:\\Program Files\\GitHub CLI\\gh.exe", "C:\\Program Files (x86)\\GitHub CLI\\gh.exe"]
    : ["gh", "/opt/homebrew/bin/gh", "/usr/local/bin/gh", "/usr/bin/gh"];

let _cachedToken;
function readGhToken() {
  for (const bin of GH_CANDIDATES) {
    try {
      const token = execFileSync(bin, ["auth", "token"], {
        encoding: "utf-8",
        timeout: 5000,
        stdio: ["ignore", "pipe", "ignore"],
      }).trim();
      if (token) return token;
    } catch {
      // try next candidate
    }
  }
  return null;
}

function resolveGithubToken() {
  if (_cachedToken !== undefined) return _cachedToken;
  const fromEnv = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
  if (fromEnv) return (_cachedToken = fromEnv.trim());
  return (_cachedToken = readGhToken());
}

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

  const headers = {
    Accept: "application/vnd.github.v3+json",
    "User-Agent": "web-access-mcp",
  };
  const token = resolveGithubToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(url, {
    headers,
    signal: AbortSignal.timeout(15000),
  });

  if (response.status === 401) {
    throw new Error(
      "GitHub API requires authentication for this search type (code search always does). " +
        "Set GITHUB_TOKEN/GH_TOKEN env var, or run `gh auth login` so the token can be picked up. " +
        "Alternatively use web_search with site:github.com."
    );
  }
  if (response.status === 403) {
    const reset = response.headers.get("X-RateLimit-Reset");
    const wait = reset ? Math.ceil(Number(reset) - Date.now() / 1000) : "unknown";
    throw new Error(
      `GitHub API rate limited. Resets in ${wait}s. ` +
        (token ? "Check your token's rate limit." : "Set GITHUB_TOKEN/GH_TOKEN or run `gh auth login` for a higher limit.")
    );
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

// ── Read a repo's README / file / directory ──────────────────

function ghHeaders(accept = "application/vnd.github+json") {
  const headers = { Accept: accept, "User-Agent": "web-access-mcp", "X-GitHub-Api-Version": "2022-11-28" };
  const token = resolveGithubToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

/**
 * "owner/repo", "github.com/owner/repo", or a full URL such as
 * https://github.com/owner/repo/blob/main/src/index.js → { owner, repo, ref, path }.
 * Explicit path/ref arguments win over what the URL contains.
 */
function parseRepoRef(input, { path = "", ref = "" } = {}) {
  const raw = String(input || "").trim();
  if (!raw) throw new Error("repo is required (e.g. 'owner/repo' or a github.com URL)");
  let rest = raw.replace(/^https?:\/\//i, "").replace(/^(www\.)?github\.com\//i, "");
  rest = rest.replace(/\.git$/, "").replace(/[?#].*$/, "");
  const parts = rest.split("/").filter(Boolean);
  if (parts.length < 2) throw new Error(`Not a repository: "${raw}" (expected 'owner/repo')`);
  const [owner, repo, kind, urlRef, ...urlPath] = parts;
  const fromUrl = kind === "blob" || kind === "tree" || kind === "raw";
  return {
    owner,
    repo,
    ref: String(ref || (fromUrl ? urlRef : "") || "").trim(),
    path: String(path || (fromUrl ? urlPath.join("/") : "") || "")
      .trim()
      .replace(/^\/+|\/+$/g, ""),
  };
}

async function ghGet(url, accept) {
  const response = await fetch(url, { headers: ghHeaders(accept), signal: AbortSignal.timeout(20000) });
  if (response.status === 404) return { notFound: true };
  if (response.status === 401) throw new Error("GitHub rejected the token (401). Check GITHUB_TOKEN / gh auth.");
  if (response.status === 403 || response.status === 429) {
    const reset = response.headers.get("X-RateLimit-Reset");
    const wait = reset ? Math.ceil(Number(reset) - Date.now() / 1000) : "unknown";
    throw new Error(
      `GitHub API rate limited. Resets in ${wait}s. Set GITHUB_TOKEN/GH_TOKEN or run \`gh auth login\` for a higher limit.`
    );
  }
  if (!response.ok) throw new Error(`GitHub error ${response.status}: ${(await response.text()).slice(0, 300)}`);
  return { response };
}

/**
 * Read from a GitHub repository. Returns { title, text } where text is the
 * README (no path), a file's content, or a directory listing.
 */
async function readGithub(input, opts = {}) {
  const { owner, repo, ref, path } = parseRepoRef(input, opts);
  const base = `${GITHUB_API}/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`;
  const q = ref ? `?ref=${encodeURIComponent(ref)}` : "";
  const where = `${owner}/${repo}${ref ? `@${ref}` : ""}`;
  const notFound = (what) =>
    new Error(`Not found: ${what} in ${where}. (Private repositories need GITHUB_TOKEN or \`gh auth login\`.)`);

  if (!path) {
    const r = await ghGet(`${base}/readme${q}`, "application/vnd.github.raw+json");
    if (r.notFound) throw notFound("README");
    return { title: `${where} — README`, text: (await r.response.text()).trim() };
  }

  const encPath = path.split("/").map(encodeURIComponent).join("/");
  const r = await ghGet(`${base}/contents/${encPath}${q}`);
  if (r.notFound) throw notFound(path);
  const data = await r.response.json();

  if (Array.isArray(data)) {
    const rows = data
      .sort((a, b) => (a.type === b.type ? a.name.localeCompare(b.name) : a.type === "dir" ? -1 : 1))
      .map((e) => `- ${e.type === "dir" ? "📁 " : ""}${e.path}${e.type === "dir" ? "/" : ` (${e.size} bytes)`}`);
    return { title: `${where} — ${path}/`, text: `${rows.length} entries\n\n${rows.join("\n")}` };
  }
  if (data.type !== "file") {
    return { title: `${where} — ${path}`, text: `${path} is a ${data.type}${data.target ? ` → ${data.target}` : ""}.` };
  }

  let text;
  if (data.content && data.encoding === "base64") {
    text = Buffer.from(data.content, "base64").toString("utf-8");
  } else if (data.download_url) {
    // files over 1 MB come without inline content
    const raw = await fetch(data.download_url, { headers: { "User-Agent": "web-access-mcp" }, signal: AbortSignal.timeout(30000) });
    if (!raw.ok) throw new Error(`GitHub raw download failed: HTTP ${raw.status}`);
    text = await raw.text();
  } else {
    text = "";
  }
  if (text.includes("\u0000")) {
    return { title: `${where} — ${path}`, text: `Binary file (${data.size} bytes) — not shown. Download: ${data.download_url}` };
  }
  return { title: `${where} — ${path}`, text };
}

module.exports = { searchGithub, readGithub, parseRepoRef };
