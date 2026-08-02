const { fs, path, isTestFile, ARTIFACT_PATTERNS } = require("./shared.js");
const diagnostics = require("./diagnostics.js");
const { spawn } = require("child_process");

const IMPORT_PATTERNS = [
  // ES6 import
  /import\s+(?:\{[^}]*\}\s*|\w+\s*(?:,\s*\{[^}]*\}\s*)?)from\s+['"]([^'"]+)['"]/g,
  // Dynamic import
  /import\(['"]([^'"]+)['"]\)/g,
  // require
  /(?:const|let|var)\s+(?:\{[^}]*\}\s*|\w+\s*(?:,\s*\{[^}]*\}\s*)?)=\s*require\(['"]([^'"]+)['"]\)/g,
  // Plain require
  /require\(['"]([^'"]+)['"]\)/g,
];

const TS_CONFIG_ALIAS = {}; // populated lazily

function resolveTsConfigPaths(cwd) {
  if (Object.keys(TS_CONFIG_ALIAS).length > 0) return TS_CONFIG_ALIAS;

  const tsconfigPath = path.join(cwd, "tsconfig.json");
  try {
    if (fs.existsSync(tsconfigPath)) {
      const tsconfig = JSON.parse(fs.readFileSync(tsconfigPath, "utf8"));
      const paths = tsconfig.compilerOptions?.paths || {};
      const baseUrl = tsconfig.compilerOptions?.baseUrl || ".";

      for (const [alias, targets] of Object.entries(paths)) {
        const aliasKey = alias.replace("/*", "");
        const targetPath = targets[0]?.replace("/*", "") || "";
        TS_CONFIG_ALIAS[aliasKey] = path.resolve(cwd, baseUrl, targetPath).replace(/\\/g, "/");
      }
    }
  } catch {
    // ignore
  }

  return TS_CONFIG_ALIAS;
}

function normalizeImportPath(importPath, sourceFile, cwd) {
  const aliases = resolveTsConfigPaths(cwd);

  // Check tsconfig aliases (e.g., @/components/Button)
  for (const [alias, targetDir] of Object.entries(aliases)) {
    if (importPath.startsWith(alias + "/") || importPath === alias) {
      const relative = importPath.slice(alias.length);
      return path.join(targetDir, relative).replace(/\\/g, "/");
    }
  }

  // Relative import: resolve relative to source file
  if (importPath.startsWith(".")) {
    const sourceDir = path.dirname(sourceFile);
    const resolved = path.resolve(cwd, sourceDir, importPath).replace(/\\/g, "/");
    // Try common extensions
    for (const ext of [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", "/index.ts", "/index.js"]) {
      const candidate = resolved + ext;
      if (fs.existsSync(candidate)) return candidate;
    }
    return resolved;
  }

  // Bare specifier — probably an npm package, not in-project
  return null;
}

function extractImports(filePath) {
  try {
    const content = fs.readFileSync(filePath, "utf8");
    const imports = new Set();

    for (const pattern of IMPORT_PATTERNS) {
      pattern.lastIndex = 0;
      let match;
      while ((match = pattern.exec(content)) !== null) {
        imports.add(match[1]);
      }
    }

    return [...imports];
  } catch {
    return [];
  }
}

function buildDependencyMap(files, cwd) {
  const depMap = {}; // source -> [resolved paths]
  const codeFiles = files.filter((f) => !isTestFile(f) && /\.(ts|tsx|js|jsx|mjs|cjs)$/.test(f));

  for (const f of codeFiles) {
    const fullPath = path.resolve(cwd, f);
    if (!fs.existsSync(fullPath)) continue;

    const imports = extractImports(fullPath);
    const resolved = [];

    for (const imp of imports) {
      const normalized = normalizeImportPath(imp, f, cwd);
      if (normalized) {
        // Store relative to cwd
        const rel = path.relative(cwd, normalized).replace(/\\/g, "/");
        resolved.push(rel);
      }
    }

    depMap[f.replace(/\\/g, "/")] = resolved;
  }

  return depMap;
}

function reverseDependencyMap(depMap) {
  const reverse = {};
  for (const [source, targets] of Object.entries(depMap)) {
    if (!reverse[source]) reverse[source] = [];
    for (const target of targets) {
      if (!reverse[target]) reverse[target] = [];
      reverse[target].push(source);
    }
  }
  return reverse;
}

function findTransitiveDependents(reverseMap, target, maxNodes = 50) {
  const visited = new Set();
  const queue = [target];
  const results = [];

  while (queue.length > 0) {
    const current = queue.shift();
    const dependents = reverseMap[current] || [];

    for (const dep of dependents) {
      if (visited.has(dep)) continue;
      visited.add(dep);
      results.push(dep);
      queue.push(dep);

      if (results.length >= maxNodes) {
        return results;
      }
    }
  }

  return results;
}

function findRelatedTests(filePath, files) {
  const stem = path.basename(filePath).replace(path.extname(filePath), "");
  const dir = path.dirname(filePath);

  return files.filter((f) => {
    if (!isTestFile(f)) return false;
    const fStem = path.basename(f).replace(path.extname(f), "");
    const fDir = path.dirname(f);
    // Same stem in same or adjacent __tests__ dir
    return fStem.includes(stem) || fStem === stem || fDir.includes(dir);
  }).map((f) => f.replace(/\\/g, "/"));
}

function findAffectedArtifacts(filePath, files) {
  const dir = path.dirname(filePath);
  const stem = path.basename(filePath).replace(path.extname(filePath), "");

  return files.filter((f) => {
    // Check if any artifact pattern matches
    for (const ap of ARTIFACT_PATTERNS) {
      if (ap.pattern.test(f)) {
        const fDir = path.dirname(f);
        const fStem = path.basename(f).replace(path.extname(f), "");
        return fDir.startsWith(dir) || fStem === stem;
      }
    }
    return false;
  }).map((f) => f.replace(/\\/g, "/"));
}

async function analyzeImpact(cwd, target) {
  // Validate target
  const fullTarget = path.resolve(cwd, target);
  if (!fs.existsSync(fullTarget)) {
    return {
      error: true,
      code: "TARGET_NOT_FOUND",
      message: `Target file not found: ${target}`,
    };
  }

  const tools = diagnostics.detectAllTools();

  // Discover files if rg is available for speed
  let files;
  try {
    const discovery = require("./discovery.js");
    files = await discovery.discoverFiles(cwd);
  } catch {
    return {
      error: true,
      code: "TIMEOUT",
      message: "File discovery timed out",
    };
  }

  const normalizedTarget = target.replace(/\\/g, "/");
  const depMap = buildDependencyMap(files, cwd);
  const reverseMap = reverseDependencyMap(depMap);

  const directDependents = reverseMap[normalizedTarget] || [];
  const transitive = findTransitiveDependents(reverseMap, normalizedTarget);
  // Remove direct from transitive
  const probableTransitive = transitive.filter((d) => !directDependents.includes(d) && d !== normalizedTarget);

  const relatedTests = findRelatedTests(normalizedTarget, files);
  const affectedArtifacts = findAffectedArtifacts(normalizedTarget, files);

  let confidence = "low";
  if (directDependents.length > 0) {
    confidence = tools.rg ? "high" : "medium";
  } else if (tools.rg) {
    confidence = "medium";
  }

  return {
    target: normalizedTarget,
    directDependents: directDependents.slice(0, 20),
    probableTransitiveDependents: probableTransitive.slice(0, 20),
    relatedTests: relatedTests.slice(0, 10),
    affectedArtifacts: affectedArtifacts.slice(0, 10),
    confidence,
    basis: [
      "Import statement analysis (ES6 imports, require, dynamic imports)",
      "Tsconfig path alias resolution (@/ -> src/, etc.)",
      "Filename-based test matching",
      "Artifact directory pattern matching",
    ],
  };
}

module.exports = { analyzeImpact, buildDependencyMap, reverseDependencyMap, findTransitiveDependents };
