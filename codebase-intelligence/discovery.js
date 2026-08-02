const { execSync, spawn } = require("child_process");
const { fs, path, DEFAULT_IGNORE, MAX_FILES } = require("./shared.js");
const diagnostics = require("./diagnostics.js");

function walkRecursive(dir, relativeTo) {
  const files = [];
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (DEFAULT_IGNORE.has(entry.name)) continue;
      if (entry.name.startsWith(".")) continue;

      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        const subFiles = walkRecursive(fullPath, relativeTo);
        files.push(...subFiles);
      } else if (entry.isFile()) {
        files.push(path.relative(relativeTo, fullPath));
      }

      if (files.length > MAX_FILES) {
        throw new Error("TOO_LARGE");
      }
    }
  } catch (err) {
    if (err.message === "TOO_LARGE") throw err;
    // Permission denied or similar — skip directory
  }
  return files;
}

function discoverFilesWithRg(cwd) {
  return new Promise((resolve, reject) => {
    const args = ["--files", "--no-ignore-vcs"];
    for (const ig of DEFAULT_IGNORE) {
      args.push("--glob", `!${ig}`);
    }
    args.push("--glob", "!.*");

    const proc = spawn("rg", args, { cwd, timeout: 30000 });
    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (d) => { stdout += d.toString(); });
    proc.stderr.on("data", (d) => { stderr += d.toString(); });
    proc.on("error", (err) => reject(err));
    proc.on("close", (code) => {
      if (code === 0 || (code === 1 && stdout.length > 0)) {
        const files = stdout.split("\n").filter(Boolean).map((f) => f.replace(/\\/g, "/"));
        if (files.length > MAX_FILES) {
          reject(new Error("TOO_LARGE"));
        } else {
          resolve(files);
        }
      } else if (code === 1) {
        // rg exit code 1 means no matches
        resolve([]);
      } else {
        reject(new Error(`rg --files exited with code ${code}: ${stderr.slice(0, 200)}`));
      }
    });
  });
}

async function discoverFiles(cwd) {
  const tools = diagnostics.detectAllTools();

  if (tools.rg) {
    try {
      return await discoverFilesWithRg(cwd);
    } catch (err) {
      if (err.message === "TOO_LARGE") throw err;
      // Fall back to recursive walk
    }
  }

  try {
    return walkRecursive(cwd, cwd);
  } catch (err) {
    if (err.message === "TOO_LARGE") throw err;
    return [];
  }
}

function countByKind(files) {
  const { classifyFile } = require("./shared.js");
  const counts = { code: 0, test: 0, doc: 0, config: 0, other: 0 };
  for (const f of files) {
    const kind = classifyFile(f);
    counts[kind]++;
  }
  return counts;
}

module.exports = { discoverFiles, countByKind, walkRecursive };
