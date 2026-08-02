const { spawn } = require("child_process");
const diagnostics = require("./diagnostics.js");
const indexModule = require("./index.js");
const cache = require("./cache.js");

function searchWithRg(cwd, query) {
  return new Promise((resolve, reject) => {
    // Windows: spawn+ cwd option causes rg to hang. Pass dir as explicit path arg.
    const proc = spawn("rg", [
      "--line-number", "--ignore-case", "--fixed-strings",
      "--max-count", "10",
      "--no-ignore-vcs",
      "-g", "!node_modules", "-g", "!.git",
      query,
      cwd,
    ], { timeout: 15000 });
    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (d) => { stdout += d.toString(); });
    proc.stderr.on("data", (d) => { stderr += d.toString(); });
    proc.on("error", (err) => reject(err));
    proc.on("close", (code) => {
      // code 2 = rg hit errors (e.g. Windows "nul" device) but may have results
      if (code === 0 || stdout.length > 0) {
        resolve(parseRgSearchOutput(stdout, cwd));
      } else {
        resolve([]);
      }
    });
  });
}

function parseRgSearchOutput(output, cwd) {
  const results = [];
  const lines = output.split("\n").filter(Boolean);
  for (const line of lines) {
    // Handle both Unix paths and Windows paths with drive letters (D:/path/file:19:content)
    const match = line.match(/^(?:([a-zA-Z]):)?(.+?):(\d+):(.+)/);
    if (!match) continue;
    const drive = match[1] || "";
    const pathOnly = match[2];
    results.push({
      path: (drive ? drive + ":" : "") + pathOnly.replace(/\\/g, "/"),
      line: parseInt(match[3], 10),
      preview: match[3].trim().slice(0, 200),
      reason: "Literal match via ripgrep",
      confidence: "high",
      score: 1.0,
    });
  }
  return results;
}

function searchWithSg(cwd, query) {
  return new Promise((resolve, reject) => {
    const proc = spawn("sg", [
      "search", "--json", "--pattern", query,
    ], { cwd, timeout: 15000 });
    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (d) => { stdout += d.toString(); });
    proc.stderr.on("data", (d) => { stderr += d.toString(); });
    proc.on("error", (err) => reject(err));
    proc.on("close", (code) => {
      if (code === 0) {
        resolve(parseSgOutput(stdout, query));
      } else if (code === 1) {
        resolve([]);
      } else {
        reject(new Error(`sg exited with code ${code}: ${stderr.slice(0, 200)}`));
      }
    });
  });
}

function parseSgOutput(output, query) {
  try {
    const parsed = JSON.parse(output);
    if (!Array.isArray(parsed)) return [];

    return parsed.map((hit) => ({
      path: (hit.file?.path || hit.file || "").replace(/\\/g, "/"),
      line: hit.line_number || hit.line || 0,
      preview: (hit.text || hit.content || "").trim().slice(0, 200),
      reason: "Structural match via ast-grep",
      confidence: "high",
      score: 1.5,
    }));
  } catch {
    return [];
  }
}

function mergeResults(rgResults, sgResults) {
  const seen = new Set();
  const merged = [];

  // Interleave: sg results first (higher score), then rg
  const all = [...sgResults, ...rgResults];
  for (const r of all) {
    const key = `${r.path}:${r.line}:${r.preview.slice(0, 80)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(r);
  }

  // Sort by score descending, then by path
  merged.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return a.path.localeCompare(b.path);
  });

  return merged.slice(0, 20);
}

/**
 * Fast path: query the persistent index (built by codebase_scan).
 * Returns a result object when the index is fresh and has hits, else null.
 */
function searchFromIndex(cwd, query) {
  try {
    const idx = indexModule.loadIndex(cwd);
    if (!idx) return null;

    const cached = cache.loadCache(cwd);
    if (!cached || !indexModule.isIndexFresh(idx, cached.fingerprint)) return null;

    const hits = indexModule.searchIndex(idx, query);
    if (!hits) return null;

    return {
      mode: "indexed",
      query,
      results: hits,
      suggestions: ["Persistent index hit — no rg spawned. Use codebase_scan --force to rebuild after code changes."],
    };
  } catch {
    return null;
  }
}

async function hybridSearch(cwd, query) {
  const fromIndex = searchFromIndex(cwd, query);
  if (fromIndex) return fromIndex;

  const tools = diagnostics.detectAllTools();

  const promises = [];
  if (tools.rg) {
    promises.push(searchWithRg(cwd, query).catch(() => []));
  }
  if (tools.astGrep) {
    promises.push(searchWithSg(cwd, query).catch(() => []));
  }

  if (promises.length === 0) {
    return { mode: "degraded", query, results: [], suggestions: ["Install ripgrep for faster search results"] };
  }

  const results = await Promise.all(promises);
  const merged = mergeResults(results[0] || [], results[1] || []);

  const mode = tools.rg ? (tools.astGrep ? "hybrid" : "literal") : "degraded";
  const suggestions = [];
  if (!tools.astGrep && tools.rg) {
    suggestions.push("Install ast-grep for structural code search: scoop install ast-grep");
  }

  return { mode, query, results: merged, suggestions };
}

module.exports = { hybridSearch, searchWithRg, searchWithSg, mergeResults };
