const { path, isCodeFile, isTestFile, classifyFile } = require("./shared.js");

function buildSummary(files, cwd) {
  const modules = extractModules(files);
  const entrypoints = findEntrypoints(files, cwd);
  const hotspots = findHotspots(files);
  const sourceOfTruthCandidates = findSourceOfTruthCandidates(files);
  const artifactKinds = findArtifactKinds(files);

  return { modules, entrypoints, hotspots, sourceOfTruthCandidates, artifactKinds };
}

function extractModules(files) {
  const dirs = new Set();
  const codeFiles = files.filter((f) => isCodeFile(f) || isTestFile(f));

  for (const f of codeFiles) {
    const dir = path.dirname(f);
    if (dir === ".") continue;
    // Only consider top-3 level directories as modules
    const parts = dir.split(/[/\\]/);
    if (parts.length <= 3) {
      dirs.add(dir.replace(/\\/g, "/"));
    }
  }

  // Sort by depth (shallowest first), then alphabetically
  return [...dirs].sort((a, b) => {
    const aDepth = a.split("/").length;
    const bDepth = b.split("/").length;
    if (aDepth !== bDepth) return aDepth - bDepth;
    return a.localeCompare(b);
  });
}

function findEntrypoints(files, cwd) {
  const entrypointNames = [
    "index.ts", "index.tsx", "index.js", "index.jsx",
    "main.ts", "main.tsx", "main.js", "main.jsx",
    "app.ts", "app.tsx", "app.js", "app.jsx",
    "cli.ts", "cli.js", "bin.ts", "bin.js",
  ];

  const candidates = [];
  for (const f of files) {
    const base = path.basename(f);
    if (entrypointNames.includes(base)) {
      candidates.push(f.replace(/\\/g, "/"));
    }
  }

  // Check for package.json entry
  const { fs } = require("./shared.js");
  const pkgPath = path.join(cwd, "package.json");
  try {
    if (fs.existsSync(pkgPath)) {
      const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
      if (pkg.main) candidates.push(pkg.main.replace(/\\/g, "/"));
      if (pkg.bin) {
        if (typeof pkg.bin === "string") candidates.push(pkg.bin.replace(/\\/g, "/"));
        else Object.values(pkg.bin).forEach((b) => candidates.push(b.replace(/\\/g, "/")));
      }
    }
  } catch {
    // ignore
  }

  // Deduplicate and return
  return [...new Set(candidates)];
}

function findHotspots(files) {
  // Hotspots: files with high change frequency or complexity indicators
  // Simplified: large files and files in "utils", "helpers", "shared" dirs
  const hotspots = [];
  const codeFiles = files.filter((f) => isCodeFile(f));

  for (const f of codeFiles) {
    const normalized = f.replace(/\\/g, "/");
    const dirs = path.dirname(normalized).split("/");
    const isUtility = dirs.some((d) =>
      /^(utils?|helpers?|shared|common|lib)$/i.test(d)
    );
    const isCore = /^(core|kernel|engine|runtime)$/i.test(path.basename(path.dirname(normalized)));

    if (isUtility || isCore) {
      hotspots.push(normalized);
    }
  }

  return hotspots.slice(0, 30);
}

function findSourceOfTruthCandidates(files) {
  const candidates = [];
  const srcDirFiles = files.filter((f) => {
    const normalized = f.replace(/\\/g, "/");
    return /^src\//.test(normalized) && isCodeFile(f);
  });

  for (const f of srcDirFiles) {
    const base = path.basename(f, path.extname(f));
    const plural = ["types", "interfaces", "models", "schemas", "constants", "enums", "config"];
    if (plural.includes(base.toLowerCase()) || plural.includes(base.toLowerCase() + "s")) {
      candidates.push(f.replace(/\\/g, "/"));
    }
  }

  return candidates;
}

function findArtifactKinds(files) {
  const { classifyArtifact } = require("./shared.js");
  const kinds = new Set();
  for (const f of files) {
    const kind = classifyArtifact(f);
    if (kind) kinds.add(kind);
  }
  return [...kinds].sort();
}

module.exports = { buildSummary };
