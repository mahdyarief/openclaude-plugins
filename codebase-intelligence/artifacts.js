const { ARTIFACT_PATTERNS } = require("./shared.js");
const diagnostics = require("./diagnostics.js");
const { spawn } = require("child_process");

function classifyArtifact(filePath) {
  for (const ap of ARTIFACT_PATTERNS) {
    if (ap.pattern.test(filePath)) return ap.kind;
  }
  return null;
}

function searchWithRg(cwd, query) {
  return new Promise((resolve, reject) => {
    const proc = spawn("rg", [
      "--line-number", "--ignore-case", "--max-count", "5",
      "-g", "docs/**", "-g", "*.md", "-g", "*.yml", "-g", "*.yaml",
      "-g", "*.json", "-g", "*.sql", "-g", "Dockerfile",
      "-g", "*.schema.*",
      query,
    ], { cwd, timeout: 15000 });
    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (d) => { stdout += d.toString(); });
    proc.stderr.on("data", (d) => { stderr += d.toString(); });
    proc.on("error", (err) => reject(err));
    proc.on("close", (code) => {
      if (code === 0 || (code === 1 && stdout.length > 0)) {
        resolve(parseRgOutput(stdout, cwd));
      } else if (code === 1) {
        resolve([]);
      } else {
        reject(new Error(`rg exited with code ${code}: ${stderr.slice(0, 200)}`));
      }
    });
  });
}

function parseRgOutput(output, cwd) {
  const results = [];
  const lines = output.split("\n").filter(Boolean);
  for (const line of lines) {
    const match = line.match(/^([^:]+):(\d+):(.+)/);
    if (!match) continue;
    const filePath = match[1].replace(/\\/g, "/");
    const lineNum = parseInt(match[2], 10);
    const preview = match[3].trim().slice(0, 200);
    const kind = classifyArtifact(filePath);

    results.push({
      path: filePath,
      kind: kind || "unknown",
      line: lineNum,
      preview,
      reason: kind ? `Matched ${kind} artifact pattern` : "Matched search in project file",
    });
  }
  return results;
}

async function searchArtifacts(cwd, query) {
  if (!query || typeof query !== "string") {
    return [];
  }

  const tools = diagnostics.detectAllTools();

  if (tools.rg) {
    try {
      return await searchWithRg(cwd, query);
    } catch {
      // fallback
    }
  }

  // Fallback: scan known artifact patterns manually
  const { fs, path } = require("./shared.js");
  const { discoverFiles } = require("./discovery.js");
  let files;
  try {
    files = await discoverFiles(cwd);
  } catch {
    return [];
  }

  const results = [];
  const artifactFiles = files.filter((f) => classifyArtifact(f) !== null);
  const q = query.toLowerCase();

  for (const f of artifactFiles) {
    try {
      const fullPath = path.resolve(cwd, f);
      const content = fs.readFileSync(fullPath, "utf8");
      const lines = content.split("\n");
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].toLowerCase().includes(q)) {
          results.push({
            path: f.replace(/\\/g, "/"),
            kind: classifyArtifact(f) || "unknown",
            line: i + 1,
            preview: lines[i].trim().slice(0, 200),
            reason: `Keyword match in ${classifyArtifact(f)} artifact`,
          });
          if (results.length >= 20) break;
        }
      }
    } catch {
      // skip unreadable files
    }
    if (results.length >= 20) break;
  }

  return results;
}

module.exports = { classifyArtifact, searchArtifacts };
