const { writeFile, mkdtemp } = require("node:fs/promises");
const { execFile } = require("node:child_process");
const { tmpdir } = require("node:os");
const { join } = require("node:path");

const PANDOC = process.env.PANDOC_PATH || "pandoc";

// Detect Python binary: "python" on Windows (and many systems), "python3" on
// Linux/macOS where plain "python" is often absent.
function detectPython() {
  if (process.env.PYTHON_PATH) return process.env.PYTHON_PATH;
  const candidates = process.platform === "win32" ? ["python", "py"] : ["python3", "python"];
  const { spawnSync } = require("node:child_process");
  for (const bin of candidates) {
    try {
      const r = spawnSync(bin, ["--version"], { timeout: 10000 });
      if (r.status === 0) return bin;
    } catch { /* try next */ }
  }
  return candidates[0];
}
const PYTHON = detectPython();

const PNG_CSS = String.raw`
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    width: 1200px;
    margin: 0;
    padding: 2rem;
    line-height: 1.6;
    color: #1a1a1a;
    background: #fff;
  }
  pre {
    background: #f5f5f5;
    padding: 1rem;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 0.875rem;
  }
  code {
    font-family: "Fira Code", "Cascadia Code", Consolas, monospace;
    font-size: 0.875em;
    background: #f0f0f0;
    padding: 0.125em 0.25em;
    border-radius: 3px;
  }
  pre code { background: none; padding: 0; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ddd; padding: 0.5rem; text-align: left; }
  th { background: #f5f5f5; }
  img { max-width: 100%; }
  blockquote {
    border-left: 4px solid #ddd;
    margin-left: 0;
    padding-left: 1rem;
    color: #666;
  }
</style>
`;

// DrissionPage screenshot script — connects to the user's existing Chrome/Edge
// over CDP (no browser download, unlike puppeteer's bundled Chromium).
const PNG_SCRIPT = String.raw`
import sys
from DrissionPage import ChromiumPage, ChromiumOptions

html_path = sys.argv[1]
output_path = sys.argv[2]

co = ChromiumOptions()
co.headless(True)
co.set_argument("--force-device-scale-factor", "2")
co.set_argument("--window-size", "1200,1600")
co.set_argument("--no-first-run")
co.set_argument("--no-default-browser-check")

page = ChromiumPage(co)
page.get("file://" + html_path)
page.wait.doc_loaded()

# Full-page capture in one shot
page.get_screenshot(path=output_path, full_page=True)
page.quit()

import json
print(json.dumps({"paths": [output_path]}))
`;

// Ensure Python is available; auto-install DrissionPage if missing.
function checkPython() {
  return new Promise((resolve, reject) => {
    execFile(PYTHON, ["--version"], { timeout: 15000 }, (err) => {
      if (err) {
        reject(
          new Error(
            `Python is not available.\n` +
            `Command tried: ${PYTHON} --version\n` +
            `\nInstall Python 3.6+ first:\n` +
            `  - Windows: download from https://www.python.org/downloads/ (check "Add to PATH")\n` +
            `  - Or:  winget install Python.Python.3.13\n` +
            `  - macOS: brew install python\n` +
            `  - Linux: sudo apt install python3 python3-pip\n` +
            `\nThen retry this tool. You can override the interpreter with the PYTHON_PATH env var.`
          )
        );
        return;
      }
      resolve();
    });
  });
}

// Check DrissionPage; if missing, try to auto-install via pip.
function ensureDrissionPage() {
  return new Promise((resolve, reject) => {
    execFile(
      PYTHON,
      ["-c", "import DrissionPage; print(DrissionPage.__version__)"],
      { timeout: 15000 },
      (err, stdout, stderr) => {
        if (!err) {
          resolve({ installed: true, version: stdout.trim() });
          return;
        }
        // Not installed → attempt install
        reject(
          new Error(
            `DrissionPage is not installed.\n` +
            `(import error: ${(stderr || err.message || "").trim().split("\n")[0]})\n` +
            `\nInstall it and retry:\n` +
            `  pip install DrissionPage\n` +
            `  (or: ${PYTHON} -m pip install DrissionPage)\n` +
            `\nThis tool drives your existing Chrome/Edge browser; no browser download is needed.`
          )
        );
      }
    );
  });
}

function checkRequirements() {
  return checkPython().then(ensureDrissionPage);
}

async function renderPng(markdown, outputPath) {
  await checkRequirements();

  const tmpDir = await mkdtemp(join(tmpdir(), "md-preview-png-"));
  const mdPath = join(tmpDir, "input.md");
  const htmlPath = join(tmpDir, "output.html");
  const scriptPath = join(tmpDir, "screenshot.py");
  const cssPath = join(tmpDir, "header.css");

  await writeFile(mdPath, markdown, "utf-8");
  await writeFile(cssPath, PNG_CSS, "utf-8");

  // First render to HTML
  const pandocArgs = [
    mdPath,
    "-o", htmlPath,
    "--from", "markdown+autolink_bare_uris+tex_math_dollars",
    "--to", "html5",
    "--standalone",
    "--mathml",
    "--highlight-style", "tango",
    "--include-in-header", cssPath,
  ];

  await new Promise((resolve, reject) => {
    execFile(PANDOC, pandocArgs, { timeout: 60000 }, (err, stdout, stderr) => {
      if (err) { reject(new Error(`pandoc HTML failed: ${stderr || err.message}`)); return; }
      resolve();
    });
  });

  // Then screenshot with DrissionPage (Python)
  const pngPrefix = outputPath || join(tmpDir, "output.png");
  await writeFile(scriptPath, PNG_SCRIPT, "utf-8");

  const result = await new Promise((resolve, reject) => {
    execFile(PYTHON, [scriptPath, htmlPath, pngPrefix], { timeout: 90000 }, (err, stdout, stderr) => {
      if (err) {
        reject(new Error(`DrissionPage PNG failed: ${stderr || err.message}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout.trim()));
      } catch {
        reject(new Error(`Failed to parse DrissionPage output: ${stdout}`));
      }
    });
  });

  return result;
}

module.exports = { renderPng };
