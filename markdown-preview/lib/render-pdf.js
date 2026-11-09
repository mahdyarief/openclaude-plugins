const { writeFile, mkdtemp, readFile } = require("node:fs/promises");
const { execFile, spawn } = require("node:child_process");
const { tmpdir } = require("node:os");
const { join, basename } = require("node:path");

const { existsSync, readdirSync, statSync } = require("node:fs");
const { createRequire } = require("node:module");
const path = require("node:path");

const PLUGIN_ROOT = path.resolve(__dirname, "..");
const THEMES_DIR = path.join(PLUGIN_ROOT, "themes");

// md2pdf / playwright-core reads MD2PDF_BROWSER as the executablePath of the
// Chromium it launches. We point it at Playwright's bundled
// chrome-headless-shell.exe so the PDF is rendered with no browser window
// visible (no blinking/headed window). Set HEADLESS_MODE=1 or HEADLESS_ON=1
// to force headless rendering.
const HEADLESS_SHELL = path.join(PLUGIN_ROOT, "node_modules", ".bin", "chrome-headless-shell.exe");

// Resolve the md2pdf CLI entry. Prefer the npm bin wrapper (md2pdf / .cmd on
// Windows), then the bundled ESM entry via node, then PATH lookup. The npm bin
// wrapper can be spawned directly without a shell on Windows, avoiding both
// command-injection surface and the DeprecationWarning.
function resolveMd2pdfCmd() {
  if (process.env.MD2PDF_PATH) return { cmd: process.env.MD2PDF_PATH, extraArgs: [] };
  const win = process.platform === "win32";
  const localBinCmd = path.join(PLUGIN_ROOT, "node_modules", ".bin", "md2pdf" + (win ? ".cmd" : ""));
  if (existsSync(localBinCmd)) return { cmd: localBinCmd, extraArgs: [] };
  try {
    const require = createRequire(__filename);
    const pkgDir = path.dirname(require.resolve("@amitdevx/md2pdf/package.json"));
    const cliEntry = path.join(pkgDir, "dist", "cli", "index.js");
    if (existsSync(cliEntry)) return { cmd: process.execPath, extraArgs: [cliEntry] };
  } catch {
    // fall through to PATH lookup
  }
  return { cmd: "md2pdf", extraArgs: [] };
}

const { cmd: MD2PDF_CMD, extraArgs: MD2PDF_EXTRA_ARGS } = resolveMd2pdfCmd();

// Scan the Playwright cache for an installed chrome-headless-shell.exe and
// return the newest one. Returns null when none is found.
function findHeadlessShell() {
  if (process.env.HEADLESS_BROWSER_PATH) return process.env.HEADLESS_BROWSER_PATH;

  const cache = process.env.LOCALAPPDATA
    ? path.join(process.env.LOCALAPPDATA, "ms-playwright")
    : null;
  if (cache && existsSync(cache)) {
    try {
      const dirs = readdirSync(cache)
        .filter((d) => /^chromium_headless_shell-\d+$/.test(d))
        .map((d) => path.join(cache, d, "chrome-headless-shell-win64", "chrome-headless-shell.exe"));
      const found = dirs.filter(existsSync).sort((a, b) => {
        const [va, vb] = [a, b].map((p) => {
          try { return statSync(p).mtimeMs; } catch { return 0; }
        });
        return vb - va;
      });
      if (found.length) return found[0];
    } catch { /* ignore */ }
  }
  return null;
}

// Resolve headless Chromium executable. md2pdf launches Chrome via
// playwright-core without --headless by default. We provide an explicit
// headless shell path via MD2PDF_BROWSER so rendering happens invisibly
// (no blinking window).
function resolveHeadlessBrowser() {
  if (
    process.env.HEADLESS_MODE !== "1" &&
    process.env.HEADLESS_ON !== "1"
  ) {
    return null;
  }
  if (process.env.MD2PDF_BROWSER) return process.env.MD2PDF_BROWSER;

  return findHeadlessShell();
}

const HEADLESS_BROWSER = resolveHeadlessBrowser();

// Default theme: clean, print-optimized with Inter + JetBrains Mono.
const DEFAULT_THEME = "default";

// Mermaid theme per md2pdf theme (matches amitdevx/md2pdf theme mapping).
const MERMAID_THEMES = {
  default: "default",
  github: "base",
  "obsidian-light": "default",
  "obsidian-dark": "dark",
  dracula: "dark",
  nord: "neutral",
  academic: "neutral",
  "catatan-buku": "neutral",
  jurnal: "neutral",
  "tugas-kuliah": "neutral",
  artikel: "base",
  tufte: "neutral",
  proposal: "base",
  naskah: "neutral",
  "surat-dinas": "neutral",
  memo: "base",
  teknis: "default",
  notulen: "neutral",
  zine: "neutral",
};

// A table of contents breaks the layout of these document types.
const NO_TOC_THEMES = new Set(["jurnal", "artikel", "tufte", "naskah", "surat-dinas", "memo", "notulen", "zine"]);

// Themes that number headings themselves through CSS counters + ::before.
// When the document already carries its own numbers, both appear ("I. 1. ...").
const AUTO_NUMBERED_THEMES = {
  jurnal: ['h2:not(.toc-title)::before', "h3::before"],
  "tugas-kuliah": ["h1::before", "h2:not(.toc-title)::before", "h3::before"],
  teknis: ["h2:not(.toc-title)::before", "h3::before"],
  proposal: ["h2:not(.toc-title)::before", "h3::before"],
};

// A heading whose text already starts with its own number: "1.", "1.2",
// "1.2.1", "I.", "BAB I", "1)". Requires punctuation or a dotted level so a
// heading such as "2026 Outlook" or "3D Printing" is not mistaken for one.
const MANUAL_HEADING_RE =
  /^#{1,6}\s+(BAB\s+[IVXLC]+\b|[IVXLC]+[.)]\s|\d+(?:\.\d+)+[.)]?\s|\d+[.)]\s)(.*)$/i;

// A quantity reads like a number but continues with a lowercase word
// ("4.5 juta pengguna"); a real heading continues with a title word.
const QUANTITY_TAIL_RE = /^[a-z]/;

function hasManualHeadingNumbers(markdown) {
  const matches = [];
  for (const line of markdown.split(/\r?\n/)) {
    const m = MANUAL_HEADING_RE.exec(line);
    if (m) matches.push(m[2] || "");
  }
  // Two or more numbered headings is conclusive on its own.
  if (matches.length >= 2) return true;
  if (matches.length === 1) {
    return !QUANTITY_TAIL_RE.test(matches[0].trim());
  }
  return false;
}

// Neutralise the theme's own counter-based numbering so a document that
// numbers its headings by hand does not end up double-numbered.
async function suppressAutoNumbering(themePath, selectors, tmpDir) {
  const css = await readFile(themePath, "utf-8");
  const rules = selectors
    .map((sel) => `${sel} { content: none !important; }`)
    .join("\n");
  const overridePath = join(tmpDir, "theme-no-auto-numbering.css");
  await writeFile(overridePath, `${css}\n\n/* headings already numbered by the author */\n${rules}\n`, "utf-8");
  return overridePath;
}

const TOC_TITLES = {
  "tugas-kuliah": "Daftar Isi",
  "catatan-buku": "Daftar Isi",
  academic: "Contents",
  proposal: "Daftar Isi",
  teknis: "Contents",
};

// Resolve a theme string to an md2pdf CLI --theme value.
// Supports: built-in md2pdf themes, plugin-shipped custom themes (themes/<name>.css),
// relative .css paths resolved against the plugin root, and absolute .css paths.
function resolveTheme(theme) {
  if (!theme || typeof theme !== "string") return DEFAULT_THEME;
  const trimmed = theme.trim();

  // Absolute path to a CSS file -> pass straight through to md2pdf.
  if (path.isAbsolute(trimmed) && trimmed.toLowerCase().endsWith(".css")) {
    return trimmed;
  }

  // Plugin-shipped custom theme: themes/<name>.css
  const bare = trimmed.replace(/\.css$/i, "");
  const pluginTheme = path.join(THEMES_DIR, `${bare}.css`);
  if (existsSync(pluginTheme)) return pluginTheme;

  // Relative .css path resolved against the plugin root.
  if (trimmed.toLowerCase().endsWith(".css")) {
    const rootTheme = path.join(PLUGIN_ROOT, trimmed);
    if (existsSync(rootTheme)) return rootTheme;
  }

  // Fall back to a built-in md2pdf theme name or pass-through.
  return trimmed;
}

async function renderPdf(markdown, outputPath, options = {}) {
  const tmpDir = await mkdtemp(join(tmpdir(), "md-preview-pdf-"));
  const mdPath = join(tmpDir, "input.md");
  const pdfPath = outputPath || join(tmpDir, "output.pdf");

  await writeFile(mdPath, markdown, "utf-8");

  const themeName = (typeof options.theme === "string" && options.theme.trim()) || DEFAULT_THEME;
  let theme = resolveTheme(themeName);

  // Look up by bare theme name so "jurnal", "jurnal.css" and a path to
  // themes/jurnal.css all map to the same entry.
  const themeKey = basename(themeName).replace(/\.css$/i, "");

  // Avoid double numbering: themes that add their own counters are neutralised
  // when the markdown headings already carry numbers.
  const autoSelectors = AUTO_NUMBERED_THEMES[themeKey];
  if (autoSelectors && existsSync(theme) && hasManualHeadingNumbers(markdown)) {
    theme = await suppressAutoNumbering(theme, autoSelectors, tmpDir);
  }
  const mermaidTheme =
    options.mermaidTheme || MERMAID_THEMES[themeName] || MERMAID_THEMES.default;
  const toc = options.toc ?? !NO_TOC_THEMES.has(themeName);

  const args = [
    mdPath,
    "-o", pdfPath,
    "--theme", theme,
    "--mermaid-theme", mermaidTheme,
    ...(toc ? ["--toc"] : []),
    ...(toc && TOC_TITLES[themeName] ? ["--toc-title", TOC_TITLES[themeName]] : []),
    "--page-numbers",
    // md2pdf's cache keys on markdown content only, so edited theme CSS would be ignored.
    "--no-cache",
    // Without --force md2pdf silently skips an existing outputPath and still exits 0.
    "--force",
  ];

  const argsFull = [...MD2PDF_EXTRA_ARGS, ...args];
  const childEnv = { ...process.env };
  if (HEADLESS_BROWSER) {
    childEnv.MD2PDF_BROWSER = HEADLESS_BROWSER;
  }
  if (process.platform === "win32") {
    await new Promise((resolve, reject) => {
      const proc = spawn("cmd.exe", ["/c", MD2PDF_CMD, ...argsFull], {
        timeout: 180000,
        env: childEnv,
      });
      let stdout = "",
        stderr = "";
      proc.stdout.on("data", (d) => (stdout += d));
      proc.stderr.on("data", (d) => (stderr += d));
      proc.on("error", (err) => reject(err));
      proc.on("close", (code) => {
        // Reap any Chromium children md2pdf may have left behind so they
        // don't linger as zombies holding resources.
        try { proc.kill("SIGKILL"); } catch { /* already gone */ }
        if (code !== 0) {
          reject(
            new Error(
              `md2pdf PDF failed (exit ${code}): ${stderr || stdout}`
            )
          );
          return;
        }
        resolve(stdout);
      });
    });
  } else {
    await new Promise((resolve, reject) => {
      execFile(
        MD2PDF_CMD,
        argsFull,
        { timeout: 180000, env: childEnv },
        (err, stdout, stderr) => {
          if (err) {
            const msg = stderr || err.message || stdout;
            reject(new Error(`md2pdf PDF failed: ${msg}`));
            return;
          }
          resolve(stdout);
        }
      );
    });
  }

  return pdfPath;
}

module.exports = { renderPdf, DEFAULT_THEME, MERMAID_THEMES, hasManualHeadingNumbers };
