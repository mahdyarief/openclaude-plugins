const { execSync } = require("child_process");

let cachedTools = null;

function detectTool(command) {
  try {
    if (process.platform === "win32") {
      execSync(`where ${command}`, { stdio: "ignore", timeout: 3000 });
    } else {
      execSync(`which ${command}`, { stdio: "ignore", timeout: 3000 });
    }
    return true;
  } catch {
    return false;
  }
}

function detectAllTools() {
  if (cachedTools) return cachedTools;

  const hasRg = detectTool("rg");
  const hasSg = detectTool("sg");
  const hasMgrep = detectTool("mgrep");

  cachedTools = {
    rg: hasRg,
    astGrep: hasSg,
    mgrep: hasMgrep,
  };

  return cachedTools;
}

function getInstallHints(tools) {
  const hints = [];
  if (!tools.rg) {
    hints.push({
      tool: "ripgrep",
      description: "Fast recursive grep for code search",
      install: "scoop install ripgrep",
      url: "https://github.com/BurntSushi/ripgrep",
    });
  }
  if (!tools.astGrep) {
    hints.push({
      tool: "ast-grep",
      description: "Structural code search (AST-based pattern matching)",
      install: "scoop install ast-grep",
      url: "https://ast-grep.github.io/",
    });
  }
  return hints;
}

function getMode(tools) {
  return tools.rg ? "full" : "degraded";
}

function invalidateToolCache() {
  cachedTools = null;
}

module.exports = {
  detectTool,
  detectAllTools,
  getInstallHints,
  getMode,
  invalidateToolCache,
};
