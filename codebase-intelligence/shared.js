const path = require("path");
const fs = require("fs");

const SCHEMA_VERSION = 1;
const MAX_FILES = 10000;
const CACHE_DIR_NAME = ".openclaude";
const CACHE_FILE_NAME = "codebase-cache/scan-cache.json";

const CODE_EXTENSIONS = new Set([
  ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts",
  ".py", ".rs", ".go", ".java", ".rb", ".php", ".swift", ".kt",
  ".scala", ".ex", ".exs", ".hs", ".clj", ".cljs", ".elm",
  ".vue", ".svelte", ".astro",
]);

const TEST_PATTERNS = [
  /\.test\./, /\.spec\./, /\.e2e\./, /_test\./, /__tests__[/\\]/,
  /test_/, /tests[/\\]/, /spec[/\\]/,
];

const DOC_PATTERNS = [
  /[/\\]docs[/\\]/,
  /[/\\]specs?[/\\]/,
  /\.md$/,
  /\.mdx$/,
  /README/i,
  /CHANGELOG/i,
  /CONTRIBUTING/i,
];

const CONFIG_PATTERNS = [
  /\.json$/,
  /\.ya?ml$/,
  /\.toml$/,
  /\.env/,
  /\.ini$/,
  /\.cfg$/,
];

const ARTIFACT_PATTERNS = [
  { kind: "doc", pattern: /(?:^|[/\\])docs[/\\]/ },
  { kind: "spec", pattern: /(?:^|[/\\])specs?[/\\]/ },
  { kind: "schema", pattern: /\.schema\./ },
  { kind: "schema", pattern: /(?:^|[/\\])schemas?[/\\]/ },
  { kind: "config", pattern: /\.ya?ml$/ },
  { kind: "config", pattern: /\.json$/ },
  { kind: "config", pattern: /\.env/ },
  { kind: "sql", pattern: /\.sql$/ },
  { kind: "docker", pattern: /Dockerfile/ },
  { kind: "adr", pattern: /(?:^|[/\\])adr[-_]/ },
  { kind: "adr", pattern: /adr-\d+/ },
];

const DEFAULT_IGNORE = new Set([
  "node_modules", ".git", ".svn", ".hg", "dist", "build", ".next",
  ".openclaude", "target", "vendor", ".tox", "__pycache__",
  ".cache", "coverage", ".nyc_output",
]);

function isCodeFile(filePath) {
  const ext = path.extname(filePath);
  return CODE_EXTENSIONS.has(ext);
}

function isTestFile(filePath) {
  return TEST_PATTERNS.some((p) => p.test(filePath));
}

function isDocFile(filePath) {
  return DOC_PATTERNS.some((p) => p.test(filePath));
}

function isConfigFile(filePath) {
  return CONFIG_PATTERNS.some((p) => p.test(filePath));
}

function classifyFile(filePath) {
  if (isTestFile(filePath)) return "test";
  if (isCodeFile(filePath)) return "code";
  if (isDocFile(filePath)) return "doc";
  if (isConfigFile(filePath)) return "config";
  return "other";
}

function classifyArtifact(filePath) {
  for (const ap of ARTIFACT_PATTERNS) {
    if (ap.pattern.test(filePath)) return ap.kind;
  }
  return null;
}

function getCachePath(projectRoot) {
  return path.join(projectRoot, CACHE_DIR_NAME, CACHE_FILE_NAME);
}

function errorResponse(code, message) {
  return { error: true, code, message };
}

module.exports = {
  SCHEMA_VERSION,
  MAX_FILES,
  CACHE_DIR_NAME,
  CACHE_FILE_NAME,
  CODE_EXTENSIONS,
  TEST_PATTERNS,
  DOC_PATTERNS,
  CONFIG_PATTERNS,
  ARTIFACT_PATTERNS,
  DEFAULT_IGNORE,
  isCodeFile,
  isTestFile,
  isDocFile,
  isConfigFile,
  classifyFile,
  classifyArtifact,
  getCachePath,
  errorResponse,
  path,
  fs,
};
