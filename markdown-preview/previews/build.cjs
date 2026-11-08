// Regenerate theme previews: node previews/build.cjs
// Renders sample.md with every theme to previews/<theme>.pdf, plus a page-1
// thumbnail (<theme>.png) when poppler's pdftoppm is on PATH.
const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

process.env.HEADLESS_MODE = "1";
const { renderPdf } = require("../lib/render-pdf.js");

const DIR = __dirname;
const pluginThemes = fs
  .readdirSync(path.join(DIR, "..", "themes"))
  .filter((f) => f.endsWith(".css"))
  .map((f) => f.slice(0, -4));
const builtinThemes = ["github", "obsidian-light", "obsidian-dark", "dracula", "nord"];
const themes = [...pluginThemes, ...builtinThemes];

function hasPdftoppm() {
  try {
    execFileSync("pdftoppm", ["-v"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

(async () => {
  const md = fs.readFileSync(path.join(DIR, "sample.md"), "utf8");
  const thumbs = hasPdftoppm();
  let failed = 0;
  for (const theme of themes) {
    const pdf = path.join(DIR, `${theme}.pdf`);
    try {
      await renderPdf(md, pdf, { theme });
      if (thumbs) {
        execFileSync("pdftoppm", ["-png", "-r", "50", "-f", "1", "-l", "1", "-singlefile", pdf, path.join(DIR, theme)]);
      }
      console.log(`ok    ${theme}`);
    } catch (e) {
      failed++;
      console.error(`fail  ${theme}: ${e.message}`);
    }
  }
  if (!thumbs) console.warn("pdftoppm not found: thumbnails skipped");
  process.exit(failed ? 1 : 0);
})();
