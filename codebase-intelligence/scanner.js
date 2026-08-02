const { fs, path, getCachePath, errorResponse } = require("./shared.js");
const diagnostics = require("./diagnostics.js");
const discovery = require("./discovery.js");
const cache = require("./cache.js");
const summary = require("./summary.js");
const indexModule = require("./index.js");

async function scanProject(cwd, force = false) {
  // Validate path
  if (!fs.existsSync(cwd)) {
    return errorResponse("ENOENT", `Path not found: ${cwd}`);
  }
  if (!fs.statSync(cwd).isDirectory()) {
    return errorResponse("ENOENT", `Not a directory: ${cwd}`);
  }

  const tools = diagnostics.detectAllTools();
  const mode = diagnostics.getMode(tools);

  // Discover files
  let files;
  try {
    files = await discovery.discoverFiles(cwd);
  } catch (err) {
    if (err.message === "TOO_LARGE") {
      return errorResponse("TOO_LARGE", "Project exceeds 10,000 file limit. Narrow cwd scope.");
    }
    return errorResponse("TIMEOUT", `File discovery failed: ${err.message}`);
  }

  const fileCounts = discovery.countByKind(files);

  // Check cache freshness
  if (!force) {
    const cached = cache.loadCache(cwd);
    if (cache.isCacheFresh(cached, fileCounts, cwd)) {
      // Return cached data with updated timestamp
      return {
        status: "cached",
        rootName: path.basename(cwd),
        mode,
        fileCounts,
        modules: cached.modules,
        entrypoints: cached.entrypoints,
        hotspots: cached.hotspots,
        sourceOfTruthCandidates: cached.sourceOfTruthCandidates,
        artifactKinds: cached.artifactKinds,
        cachePath: getCachePath(cwd),
        lastScanAt: cached.scannedAt,
        nextSteps: ["Project is up to date. Use codebase_search to find code quickly."],
      };
    }
  }

  // Build summary
  const analysis = summary.buildSummary(files, cwd);

  // Determine fingerprint
  const gitHash = cache.getGitHeadHash(cwd);
  const fingerprint = gitHash || cache.computeFileCountFingerprint(fileCounts);

  // Save cache
  const envelope = {
    version: 1,
    fingerprint,
    scannedAt: new Date().toISOString(),
    fileCounts,
    modules: analysis.modules,
    entrypoints: analysis.entrypoints,
    hotspots: analysis.hotspots,
    sourceOfTruthCandidates: analysis.sourceOfTruthCandidates,
    artifactKinds: analysis.artifactKinds,
  };

  cache.saveCache(cwd, envelope);

  // Build + persist the search index (best-effort — scan must not fail on index errors)
  try {
    const idx = indexModule.buildIndex(files, cwd, fingerprint);
    indexModule.saveIndex(cwd, idx);
  } catch {
    // index is optional; scan result still valid
  }

  // Generate nextSteps based on findings
  const nextSteps = [];
  const installHints = diagnostics.getInstallHints(tools);
  for (const hint of installHints) {
    nextSteps.push(`Install ${hint.tool}: ${hint.install}`);
  }
  if (analysis.entrypoints.length === 0) {
    nextSteps.push("No entrypoints detected. Specify main files manually.");
  }
  if (nextSteps.length === 0) {
    nextSteps.push("Project is ready. Use codebase_search to find code quickly.");
  }

  return {
    status: "scanned",
    rootName: path.basename(cwd),
    mode,
    fileCounts,
    modules: analysis.modules,
    entrypoints: analysis.entrypoints,
    hotspots: analysis.hotspots,
    sourceOfTruthCandidates: analysis.sourceOfTruthCandidates,
    artifactKinds: analysis.artifactKinds,
    cachePath: getCachePath(cwd),
    scannedAt: envelope.scannedAt,
    nextSteps,
  };
}

module.exports = { scanProject };
