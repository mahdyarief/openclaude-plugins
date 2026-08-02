const { fs, path, SCHEMA_VERSION, getCachePath } = require("./shared.js");
const { execSync } = require("child_process");

function getGitHeadHash(cwd) {
  try {
    const hash = execSync("git rev-parse HEAD", { cwd, timeout: 5000, encoding: "utf8" }).trim();
    return hash;
  } catch {
    return null;
  }
}

function computeFileCountFingerprint(fileCounts) {
  // Simple hash from file counts for projects without git
  const str = JSON.stringify(fileCounts) + SCHEMA_VERSION;
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0; // Convert to 32bit integer
  }
  return hash.toString(36);
}

function loadCache(cwd) {
  const cachePath = getCachePath(cwd);
  try {
    if (!fs.existsSync(cachePath)) return null;
    const raw = fs.readFileSync(cachePath, "utf8");
    const envelope = JSON.parse(raw);
    if (envelope.version !== SCHEMA_VERSION) return null;
    return envelope;
  } catch {
    return null;
  }
}

function saveCache(cwd, envelope) {
  const cachePath = getCachePath(cwd);
  try {
    const dir = path.dirname(cachePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(cachePath, JSON.stringify(envelope, null, 2));
    return true;
  } catch {
    return false;
  }
}

function isCacheFresh(envelope, fileCounts, cwd) {
  if (!envelope) return false;

  // Check schema version
  if (envelope.version !== SCHEMA_VERSION) return false;

  // Check git hash first
  const gitHash = getGitHeadHash(cwd);
  if (gitHash) {
    return envelope.fingerprint === gitHash;
  }

  // Fallback: check file count fingerprint
  const currentFingerprint = computeFileCountFingerprint(fileCounts);
  return envelope.fingerprint === currentFingerprint;
}

function invalidateCache(cwd) {
  const cachePath = getCachePath(cwd);
  try {
    if (fs.existsSync(cachePath)) {
      fs.unlinkSync(cachePath);
    }
    return true;
  } catch {
    return false;
  }
}

module.exports = {
  getGitHeadHash,
  computeFileCountFingerprint,
  loadCache,
  saveCache,
  isCacheFresh,
  invalidateCache,
};
